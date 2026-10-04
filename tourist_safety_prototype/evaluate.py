"""
evaluate.py - Reproducible quantitative evaluation of the whole system.

    python evaluate.py            # full run (about 2-4 minutes)
    python evaluate.py --quick    # small smoke run

Everything below is MEASURED by running the real code on labelled synthetic trajectories
(results/metrics.json, results/*.csv, results/*.png, results/REPORT.md).  Nothing is hard-coded.
The evaluation database is a temporary file, so your demo data is never touched.
"""
import argparse
import csv
import json
import os
import re
import sys
import tempfile
import time

_TMP = tempfile.mkdtemp(prefix="tsafety_eval_")
os.environ["TSAFETY_DB"] = os.path.join(_TMP, "eval.db")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon as MPoly
import numpy as np

import anomaly, config as C, database as db, digital_id as did, geofence as gf, simulator, train_model
from utils import to_xy, from_xy, iso, now_utc

OUT = os.path.join(C.BASE_DIR, "results")
os.makedirs(OUT, exist_ok=True)
W = C.WINDOW_SIZE
SCI = {"normal": 1, "route_deviation": 2, "prolonged_inactivity": 3, "geofence_violation": 4, "signal_loss": 5, "lost_wandering": 6}
ANOM_SCEN = ("normal", "route_deviation", "prolonged_inactivity", "lost_wandering")
SK_DIFF = []
MODES = [("rules", "Rules only"), ("if", "Isolation Forest only"), ("hybrid", "Hybrid (proposed)")]


# =====================================================================================
# 1. anomaly detection
# =====================================================================================
def precompute(tr):
    recs = [anomaly.make_fix(f["lat"], f["lon"], f["timestamp"]) for f in tr.fixes]
    n = len(recs)
    rule = np.zeros(n, bool)
    for i in range(n):
        rule[i] = any(a["type"] in anomaly.ANOMALY_TYPES for a in anomaly.rule_layer(recs[max(0, i - W + 1):i + 1]))
    idx, F = anomaly.window_feature_matrix(recs)
    return {"scen": tr.scenario, "rule": rule, "idx": np.array(idx), "F": np.array(F),
            "labels": np.array(tr.labels), "onset": tr.onset, "t": np.array([r["t"] for r in recs])}


def attach_if(pres, model):
    pred = model.predict(np.vstack([p["F"] for p in pres])) == -1
    k = 0
    for p in pres:
        m = len(p["idx"])
        n = len(p["rule"])
        p["ifp"] = np.zeros(n, bool)
        p["ifp"][p["idx"]] = pred[k:k + m]
        p["maxdev"] = np.zeros(n)
        p["maxdev"][p["idx"]] = p["F"][:, 1]
        k += m


def flags(p, mode, thr):
    if mode == "rules":
        return p["rule"]
    if mode == "if":
        return p["ifp"]
    return p["rule"] | (p["ifp"] & (p["maxdev"] > thr))


def metrics(pres, mode, thr=None, keep=False):
    thr = thr or C.HYBRID_DEV_M
    YT, YP = [], []
    TP = FP = TN = FN = 0
    detected, n_anom, delays = 0, 0, []
    by = {}
    normal_alert, n_normal, edges, hours = 0, 0, 0, 0.0
    for p in pres:
        f, lab = flags(p, mode, thr), p["labels"]
        for i in p["idx"]:
            truth = lab[i - W + 1:i + 1].sum() >= W / 2
            pred = f[i]
            if keep:
                YT.append(int(truth)); YP.append(int(pred))
            TP += truth and pred; FP += (not truth) and pred; FN += truth and not pred; TN += (not truth) and not pred
        if p["scen"] == "normal":
            n_normal += 1
            normal_alert += bool(f.any())
            edges += int((f[1:] & ~f[:-1]).sum() + f[0])
            hours += (p["t"][-1] - p["t"][0] + C.FIX_INTERVAL_S) / 3600
        else:
            n_anom += 1
            hit = np.where(f[p["onset"]:])[0]
            b = by.setdefault(p["scen"], [0, 0, []])
            b[0] += 1
            if len(hit):
                detected += 1; b[1] += 1
                d = p["t"][p["onset"] + hit[0]] - p["t"][p["onset"]]
                delays.append(d); b[2].append(d)
    prec = TP / (TP + FP) if TP + FP else 0.0
    rec = TP / (TP + FN) if TP + FN else 0.0
    sk = None
    if keep:
        from sklearn.metrics import precision_recall_fscore_support, accuracy_score
        pr, rc, f1, _ = precision_recall_fscore_support(YT, YP, average="binary", zero_division=0)
        sk = max(abs(pr - prec), abs(rc - rec), abs(f1 - (2 * prec * rec / (prec + rec) if prec + rec else 0.0)),
                 abs(accuracy_score(YT, YP) - (TP + TN) / max(1, TP + TN + FP + FN)))
    return {"sklearn_diff": sk, "TP": int(TP), "FP": int(FP), "TN": int(TN), "FN": int(FN),
            "accuracy": (TP + TN) / max(1, TP + TN + FP + FN), "precision": prec, "recall": rec,
            "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
            "episode_detection": detected / max(1, n_anom),
            "delay_s": float(np.mean(delays)) if delays else float("nan"), "delays": [float(d) for d in delays],
            "false_alert_traj": normal_alert / max(1, n_normal), "false_alerts_per_hour": edges / max(1e-9, hours),
            "by_scen": {k: {"det": v[1] / v[0], "delay": float(np.mean(v[2])) if v[2] else float("nan")} for k, v in by.items()}}


def make_set(seed, n_train, n_test, contamination=None):
    X = train_model.build_training_features(n_train, seed)
    model = anomaly.train_isolation_forest([X], contamination=contamination, seed=seed, save=False)
    trajs = []
    for sc in ANOM_SCEN:
        for i in range(n_test):
            trajs.append(simulator.generate(sc, seed=10_000_000 + seed * 100_000 + SCI[sc] * 100 + i))
    pres = [precompute(t) for t in trajs]
    return X, model, pres


def eval_anomaly(seeds, n_train, n_test):
    per_seed = {m: [] for m, _ in MODES}
    agg_conf = {m: np.zeros((2, 2), int) for m, _ in MODES}
    all_delays = {m: [] for m, _ in MODES}
    n_windows = 0
    for s in seeds:
        t0 = time.time()
        X, model, pres = make_set(s, n_train, n_test)
        attach_if(pres, model)
        n_windows = sum(len(p["idx"]) for p in pres)
        for m, _ in MODES:
            r = metrics(pres, m, keep=(s == 0))
            if r["sklearn_diff"] is not None:
                SK_DIFF.append(r["sklearn_diff"])
            per_seed[m].append(r)
            agg_conf[m] += np.array([[r["TN"], r["FP"]], [r["FN"], r["TP"]]])
            all_delays[m] += r["delays"]
        print(f"  seed {s}: train windows {len(X)}, test windows {n_windows} ({time.time() - t0:.0f}s)")
    keys = ["accuracy", "precision", "recall", "f1", "episode_detection", "delay_s", "false_alert_traj", "false_alerts_per_hour"]
    table = {}
    for m, name in MODES:
        table[m] = {"name": name, "by_scen": {}}
        for sc in per_seed[m][0]["by_scen"]:
            table[m]["by_scen"][sc] = {"det": float(np.mean([r["by_scen"][sc]["det"] for r in per_seed[m]])),
                                       "delay": float(np.nanmean([r["by_scen"][sc]["delay"] for r in per_seed[m]]))}
        for k in keys:
            v = np.array([r[k] for r in per_seed[m]], float)
            table[m][k] = float(np.nanmean(v))
            table[m][k + "_std"] = float(np.nanstd(v))
    return table, agg_conf, all_delays, n_windows


def eval_sweep(n_train, n_test):
    """Operating-point study on a separate VALIDATION seed (not the test seeds)."""
    rows = []
    for cont in (0.005, 0.01, 0.02, 0.05):
        X = train_model.build_training_features(n_train, 900)
        model = anomaly.train_isolation_forest([X], contamination=cont, seed=900, save=False)
        if cont == 0.005:
            trajs = []
            for sc in ANOM_SCEN:
                trajs += [simulator.generate(sc, seed=77_000_000 + SCI[sc] * 100 + i) for i in range(n_test)]
            pres = [precompute(t) for t in trajs]
        attach_if(pres, model)
        for thr in (60, 80, 100, 120, 150, 200, 250):
            r = metrics(pres, "hybrid", thr)
            rows.append({"contamination": cont, "dev_threshold_m": thr, **{k: r[k] for k in (
                "precision", "recall", "f1", "episode_detection", "delay_s", "false_alert_traj", "false_alerts_per_hour")}})
    return rows


# =====================================================================================
# 2. geo-fencing
# =====================================================================================
def eval_geofence(n_each):
    rng = np.random.default_rng(5)
    zones = [gf.SAFE] + gf.CAUTION + gf.RESTRICTED
    pts_total = pts_wrong = 0
    for z in zones:
        cx, cy = to_xy(z["lat"], z["lon"])
        span = (z.get("radius_m") or 300) + 250
        for _ in range(4000):
            lat, lon = from_xy(cx + rng.uniform(-span, span), cy + rng.uniform(-span, span))
            sd = gf.signed_distance(z, lat, lon)
            if abs(sd) < 0.5:
                continue
            pts_total += 1
            pts_wrong += (sd <= 0) != gf.reference_inside(z, lat, lon)
    geopy_max_err = None
    try:
        from geopy.distance import great_circle
        errs = []
        for _ in range(2000):
            a = from_xy(*rng.uniform(-1500, 1500, 2)); b = from_xy(*rng.uniform(-1500, 1500, 2))
            errs.append(abs(gf.haversine(*a, *b) - great_circle(a, b, ).meters))
        geopy_max_err = float(max(errs))
    except ImportError:
        pass
    TP = FP = FN = TN = exact = lead_n = 0
    leads = []
    for sc in ("geofence_violation", "normal", "route_deviation"):
        for i in range(n_each if sc == "geofence_violation" else n_each // 2):
            tr = simulator.generate(sc, seed=31_000_000 + SCI[sc] * 100 + i)
            g = gf.GeofenceEngine()
            truth_first, pred_first, appr_first = None, None, None
            for k, f in enumerate(tr.fixes):
                if truth_first is None and any(gf.reference_inside(z, f["lat"], f["lon"]) for z in gf.RESTRICTED):
                    truth_first = k
                for e in g.check("x", f["lat"], f["lon"]):
                    if e["type"] == "GEOFENCE_VIOLATION" and pred_first is None:
                        pred_first = k
                    if e["type"] == "RESTRICTED_ZONE_APPROACH" and appr_first is None:
                        appr_first = k
            truth, pred = truth_first is not None, pred_first is not None
            TP += truth and pred; FP += (not truth) and pred; FN += truth and not pred; TN += (not truth) and not pred
            if truth and pred:
                exact += (truth_first == pred_first)
                if appr_first is not None and appr_first < pred_first:
                    leads.append((pred_first - appr_first) * C.FIX_INTERVAL_S)
    n = TP + FP + FN + TN
    return {"geopy_max_err_m": geopy_max_err, "point_tests": pts_total, "point_errors": int(pts_wrong),
            "trajectories": n, "TP": int(TP), "FP": int(FP), "FN": int(FN), "TN": int(TN),
            "accuracy": (TP + TN) / n, "precision": TP / max(1, TP + FP), "recall": TP / max(1, TP + FN),
            "exact_fix_detection": exact / max(1, TP), "approach_warning_rate": len(leads) / max(1, TP),
            "approach_lead_s_mean": float(np.mean(leads)) if leads else None}


# =====================================================================================
# 3. digital ID
# =====================================================================================
def _sql(sql, args=()):
    c = db.get_conn(); c.execute(sql, args); c.commit(); c.close()


def eval_identity(n_ids, n_tamper):
    db.init_db(); did.reset_network()
    ids, reg_ms = [], []
    for i in range(n_ids):
        t0 = time.perf_counter()
        ids.append(did.create_digital_id(f"Tourist {i}", "Indian", f"P{1000000 + i}", "+91 90000 00000"))
        reg_ms.append((time.perf_counter() - t0) * 1000)
    ok, vt = 0, []
    for d in ids:
        t0 = time.perf_counter()
        ok += did.verify_digital_id(d["tourist_id"])["valid"]
        vt.append((time.perf_counter() - t0) * 1000)
    ok_qr = sum(did.verify_qr(did.qr_text(d["tourist_id"], d["payload_hash"]))["valid"] for d in ids[:50])

    kinds = ["name", "nationality", "emergency_contact", "valid_until", "payload_hash", "block_hash", "previous_hash", "delete_block"]
    detected, by_kind, restored_ok = 0, {k: [0, 0] for k in kinds}, 0
    rng = np.random.default_rng(1)
    for n in range(n_tamper):
        d = ids[int(rng.integers(0, len(ids)))]
        kind = kinds[n % len(kinds)]
        tid = d["tourist_id"]
        t = db.get_tourist(tid); blk = db.get_block_for(tid)
        if kind in ("name", "nationality", "emergency_contact"):
            db.update_tourist_field(tid, kind, "TAMPERED"); undo = lambda: db.update_tourist_field(tid, kind, t[kind])
        elif kind == "valid_until":
            db.update_tourist_field(tid, kind, "2099-01-01T00:00:00+00:00"); undo = lambda: db.update_tourist_field(tid, kind, t[kind])
        elif kind == "delete_block":
            _sql("DELETE FROM ledger WHERE index_no=?", (blk["index_no"],))
            undo = lambda: db.insert_block(blk)
        else:
            _sql(f"UPDATE ledger SET {kind}=? WHERE index_no=?", ("f" * 64, blk["index_no"]))
            undo = lambda: _sql(f"UPDATE ledger SET {kind}=? WHERE index_no=?", (blk[kind], blk["index_no"]))
        bad = not did.verify_digital_id(tid)["valid"]
        detected += bad; by_kind[kind][0] += 1; by_kind[kind][1] += bad
        undo()
        restored_ok += did.verify_digital_id(tid)["valid"]

    forged = 0
    for d in ids[:20]:
        parts = did.qr_text(d["tourist_id"], d["payload_hash"]).split("|")
        parts[2] = "SIG:" + "0" * 16
        forged += not did.verify_qr("|".join(parts))["valid"]

    d = ids[0]
    db.update_tourist_field(d["tourist_id"], "valid_until", iso(now_utc().replace(year=2020)))
    expired_rejected = not did.verify_digital_id(d["tourist_id"])["valid"]
    db.update_tourist_field(d["tourist_id"], "valid_until", d["valid_until"])

    net = did.get_network(reload=True)
    net.tamper(1); one = net.status(); v1 = did.verify_digital_id(ids[-1]["tourist_id"])["valid"]
    net.tamper(0); two = net.status(); v2 = did.verify_digital_id(ids[-1]["tourist_id"])["valid"]
    did.get_network(reload=True)
    return {"ids": n_ids, "register_ms_mean": float(np.mean(reg_ms)), "verify_ms_mean": float(np.mean(vt)),
            "verify_ms_p95": float(np.percentile(vt, 95)), "valid_accepted": ok / n_ids, "qr_valid": ok_qr / 50,
            "tamper_cases": n_tamper, "tamper_detected": detected / n_tamper,
            "tamper_by_kind": {k: f"{v[1]}/{v[0]}" for k, v in by_kind.items()},
            "restored_valid_after_undo": restored_ok / n_tamper, "forged_qr_rejected": forged / 20,
            "expired_rejected": bool(expired_rejected),
            "net_one_node_tampered": {"flagged": one["nodes"][1]["state"], "consensus": one["consensus_ok"], "id_valid": v1},
            "net_two_nodes_tampered": {"consensus": two["consensus_ok"], "id_valid": v2},
            "pow_difficulty": C.POW_DIFFICULTY}


# =====================================================================================
# 4. end-to-end through the real Flask app + latency
# =====================================================================================
def eval_e2e(n_runs):
    model = train_model.train_and_save(150, 42)          # final shipped model
    import engine as eng_mod
    eng_mod.reset_engine(model)
    import app as appmod
    appmod.app.config["TESTING"] = True
    client = appmod.app.test_client()
    plan = ["geofence_violation", "route_deviation", "prolonged_inactivity", "signal_loss", "normal", "sos"]
    expect = {"geofence_violation": {"GEOFENCE_VIOLATION"}, "route_deviation": {"ROUTE_DEVIATION", "BEHAVIOR_OUTLIER"},
              "prolonged_inactivity": {"PROLONGED_INACTIVITY"}, "signal_loss": {"SIGNAL_LOSS"}, "sos": {"SOS"}}
    benign = {"CAUTION_ZONE_ENTRY", "RESTRICTED_ZONE_APPROACH", "LEFT_SAFE_ZONE", "LEFT_RESTRICTED_ZONE"}
    per, success = {p: [0, 0] for p in plan}, 0
    for r in range(n_runs):
        sc = plan[r % len(plan)]
        page = client.post("/register", data={"name": f"E2E {r}", "nationality": "Indian", "passport": f"E{r:06d}",
                                              "emergency_contact": "+91 90000 00000"}).get_data(as_text=True)
        tid = re.search(r"TID-[0-9A-F]{8}", page).group(0)
        okv = "PASSED" in client.get(f"/verify/{tid}").get_data(as_text=True)
        client.post(f"/api/reset/{tid}")
        types, hi_sev = [], False
        if sc == "sos":
            client.post("/api/location", json={"tourist_id": tid, "lat": 20.888, "lon": 70.401})
            res = client.post("/api/sos", json={"tourist_id": tid}).get_json()
            types += [e["incident_type"] for e in res["events"]]
        else:
            tr = simulator.generate(sc, seed=55_000_000 + r, start_time=now_utc())
            for f in tr.fixes:
                res = client.post("/api/location", json={"tourist_id": tid, **f}).get_json()
                types += [e["incident_type"] for e in res["events"]]
        rows = [i for i in db.get_incidents(500) if i["tourist_id"] == tid]
        in_db = len(rows) == len(types)
        with_coords = all(i["lat"] is not None for i in rows)
        sms_ok = all(any(n["incident_id"] == i["id"] and n["channel"] == "SMS" for n in db.get_notifications(2000))
                     for i in rows if C.SEVERITY_RANK[i["severity"]] >= C.SEVERITY_RANK[C.NOTIFY_MIN_SEVERITY])
        if sc == "normal":
            correct = not (set(types) - benign)
        else:
            correct = bool(expect[sc] & set(types))
        ok = okv and correct and in_db and with_coords and sms_ok
        per[sc][0] += 1; per[sc][1] += ok; success += ok
    incs = db.get_incidents(100000)
    lat = np.array([i["latency_ms"] for i in incs if i["latency_ms"] is not None])
    notes = [n for n in db.get_notifications(100000) if n["channel"] == "SMS"]
    tot = np.array([n["total_ms"] for n in notes]) if notes else np.array([0.0])
    return {"runs": n_runs, "success_rate": success / n_runs, "per_scenario": {k: f"{v[1]}/{v[0]}" for k, v in per.items()},
            "incidents": len(lat), "latency_ms_mean": float(lat.mean()), "latency_ms_p50": float(np.percentile(lat, 50)),
            "latency_ms_p95": float(np.percentile(lat, 95)), "latency_ms_p99": float(np.percentile(lat, 99)),
            "latency_ms_max": float(lat.max()), "latencies": lat.tolist(),
            "sms_total_ms_p95": float(np.percentile(tot, 95)), "sms_total_ms_max": float(tot.max()), "sms_count": len(notes)}


# =====================================================================================
# 5. figures
# =====================================================================================
def figures(table, conf, delays, sweep, e2e):
    names = [n for _, n in MODES]
    cols = ["#1f3864", "#0f7c8a", "#8c1c1c", "#c9a227"]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    for j, (k, lab) in enumerate([("accuracy", "Accuracy"), ("precision", "Precision"), ("recall", "Recall"), ("f1", "F1-score")]):
        vals = [table[m][k] for m, _ in MODES]; err = [table[m][k + "_std"] for m, _ in MODES]
        b = ax.bar(np.arange(3) + (j - 1.5) * 0.2, vals, 0.2, yerr=err, capsize=3, label=lab, color=cols[j])
        for r, v in zip(b, vals):
            ax.text(r.get_x() + r.get_width() / 2, v + 0.03, f"{v:.2f}", ha="center", fontsize=7)
    ax.set_xticks(range(3)); ax.set_xticklabels(names); ax.set_ylim(0, 1.15); ax.set_ylabel("Score")
    ax.set_title("Anomaly detection performance (mean ± std over seeds, window level)"); ax.legend(ncol=4, loc="lower center", fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_anomaly_bars.png"), dpi=150); plt.close(fig)

    c = conf["hybrid"]
    fig, ax = plt.subplots(figsize=(4.6, 4))
    ax.imshow(c, cmap="Blues")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, int(c[i, j]), ha="center", va="center", color="white" if c[i, j] > c.max() / 2 else "black", fontsize=13)
    ax.set_xticks([0, 1]); ax.set_xticklabels(["Normal", "Anomaly"]); ax.set_yticks([0, 1]); ax.set_yticklabels(["Normal", "Anomaly"])
    ax.set_xlabel("Predicted"); ax.set_ylabel("Actual"); ax.set_title("Confusion matrix - hybrid (all seeds, windows)")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_confusion.png"), dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.boxplot([delays[m] for m, _ in MODES], tick_labels=["Rules", "Isolation\nForest", "Hybrid"], showmeans=True)
    ax.set_ylabel("Detection delay after anomaly onset (s)"); ax.set_title("Detection delay of detected episodes")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_delay.png"), dpi=150); plt.close(fig)

    lat = np.array(e2e["latencies"])
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.hist(lat, bins=40, color="#1f3864"); ax.axvline(e2e["latency_ms_p95"], color="#8c1c1c", ls="--", label=f"95th percentile = {e2e['latency_ms_p95']:.1f} ms")
    ax.set_xlabel("Alert latency (ms) - location update received to incident written"); ax.set_ylabel("Number of alerts")
    ax.set_title("Alert latency distribution (server-side processing)"); ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_latency_hist.png"), dpi=150); plt.close(fig)

    fig, axs = plt.subplots(1, 2, figsize=(11, 4.2))
    for cont in (0.005, 0.01, 0.02, 0.05):
        rs = [r for r in sweep if r["contamination"] == cont]
        axs[0].plot([r["dev_threshold_m"] for r in rs], [r["f1"] for r in rs], marker="o", label=f"contamination {cont}")
        axs[1].plot([r["dev_threshold_m"] for r in rs], [r["false_alert_traj"] * 100 for r in rs], marker="o", label=f"contamination {cont}")
    axs[0].set_xlabel("Corroboration threshold (m)"); axs[0].set_ylabel("Window-level F1 (hybrid)"); axs[0].set_title("Operating-point study (validation seed)"); axs[0].legend(fontsize=7)
    axs[1].set_xlabel("Corroboration threshold (m)"); axs[1].set_ylabel("Normal walks with a false alert (%)"); axs[1].set_title("False-alert rate")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_sweep.png"), dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.2, 6.2))
    for z in [gf.SAFE] + gf.CAUTION + gf.RESTRICTED:
        col = {"safe": "#2e7d32", "caution": "#f9a825", "restricted": "#c62828"}[z["type"]]
        if z["shape"] == "circle":
            ax.add_patch(Circle(to_xy(z["lat"], z["lon"]), z["radius_m"], fc=col, alpha=0.12 if z["type"] == "safe" else 0.35, ec=col))
        else:
            ax.add_patch(MPoly(z["_xy"], fc=col, alpha=0.35, ec=col))
    ax.plot(*simulator.ROUTE.T, "b-", lw=2.5, label="Planned route")
    for sc, col in (("normal", "green"), ("route_deviation", "orange"), ("prolonged_inactivity", "purple"), ("lost_wandering", "brown"), ("geofence_violation", "red")):
        tr = simulator.generate(sc, seed=8)
        xy = np.array([to_xy(f["lat"], f["lon"]) for f in tr.fixes])
        ax.plot(xy[:, 0], xy[:, 1], ".-", ms=3, lw=0.8, color=col, label=sc)
    ax.set_aspect("equal"); ax.set_xlim(-1700, 1700); ax.set_ylim(-1700, 1700); ax.set_xlabel("East (m)"); ax.set_ylabel("North (m)")
    ax.set_title("Synthetic trajectories, route and zones"); ax.legend(fontsize=7, loc="lower left")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_trajectories.png"), dpi=150); plt.close(fig)


# =====================================================================================
def objective_check(M):
    t, g, a, i, e = M["anomaly"]["hybrid"], M["geofence"], M["anomaly"], M["identity"], M["e2e"]
    sms_p95_s = e["sms_total_ms_p95"] / 1000
    return [
        ("O1 geo-fence entry/exit", g["accuracy"] == 1.0 and e["latency_ms_p95"] < 5000,
         f"accuracy {g['accuracy']:.1%} on {g['trajectories']} trajectories, {g['point_tests']} random point tests ({g['point_errors']} errors); p95 processing {e['latency_ms_p95']:.1f} ms (<5 s)"),
        ("O2 anomaly detection", t["episode_detection"] >= 0.90 and t["false_alert_traj"] <= 0.10,
         f"episode detection {t['episode_detection']:.1%}, false alerts on normal walks {t['false_alert_traj']:.1%}; window-level recall {t['recall']:.2f} (target 0.90 {'met' if t['recall'] >= 0.9 else 'NOT met'})"),
        ("O3 tamper-evident ID", i["tamper_detected"] == 1.0 and i["verify_ms_p95"] < 3000,
         f"tamper detection {i['tamper_detected']:.1%} of {i['tamper_cases']} cases; forged QR rejected {i['forged_qr_rejected']:.0%}; verify p95 {i['verify_ms_p95']:.2f} ms (<3 s)"),
        ("O4 alert with coordinates <= 10 s", sms_p95_s <= 10,
         f"p95 processing {e['latency_ms_p95']:.1f} ms; p95 incl. SIMULATED SMS delay {sms_p95_s:.2f} s (real SMS delay not measured)"),
        ("O5 integrated end-to-end", e["success_rate"] == 1.0,
         f"{e['success_rate']:.1%} of {e['runs']} full runs (register -> verify -> track -> alert -> log -> notify)"),
    ]


def write_report(M, sweep, checks, args):
    A = M["anomaly"]
    L = ["# Evaluation report (auto-generated by evaluate.py)", "",
         f"Seeds: {args.seeds} | training trajectories per seed: {args.ntrain} | test trajectories per scenario: {args.ntest} | test windows per seed: {M['n_windows']}", "",
         "## 1. Anomaly detection (mean ± std over seeds; window level)", "",
         "| Detector | Accuracy | Precision | Recall | F1 | Episode detection | Mean delay (s) | Normal walks with false alert | False alerts / hour |", "|---|---|---|---|---|---|---|---|---|"]
    for m, n in MODES:
        r = A[m]
        L.append(f"| {n} | {r['accuracy']:.2f}±{r['accuracy_std']:.2f} | {r['precision']:.2f}±{r['precision_std']:.2f} | {r['recall']:.2f}±{r['recall_std']:.2f} | {r['f1']:.2f}±{r['f1_std']:.2f} | "
                 f"{r['episode_detection']:.1%} | {r['delay_s']:.0f}±{r['delay_s_std']:.0f} | {r['false_alert_traj']:.1%} | {r['false_alerts_per_hour']:.2f} |")
    L += ["", "### Episode detection and delay by anomaly type", "", "| Anomaly type | Rules | Isolation Forest | Hybrid |", "|---|---|---|---|"]
    for sc in A["hybrid"]["by_scen"]:
        cells = [f"{A[m]['by_scen'][sc]['det']:.0%} / {A[m]['by_scen'][sc]['delay']:.0f} s" for m, _ in MODES]
        L.append(f"| {sc} | " + " | ".join(cells) + " |")
    L += ["", f"Metric implementation cross-checked against scikit-learn.metrics: max difference {M['sklearn_max_diff']:.2e}."]
    g = M["geofence"]
    L += ["", "## 2. Geo-fencing", "",
          (f"* Haversine vs geopy great-circle on 2000 random pairs: max difference {g['geopy_max_err_m']:.4f} m." if g.get("geopy_max_err_m") is not None else "* geopy not installed - cross-check skipped (pip install geopy)."),
          f"* Random-point test: {g['point_tests']} points, {g['point_errors']} disagreements with the independent planar reference.",
          f"* Trajectories: {g['trajectories']} -> TP {g['TP']}, FP {g['FP']}, FN {g['FN']}, TN {g['TN']} (accuracy {g['accuracy']:.1%}, precision {g['precision']:.1%}, recall {g['recall']:.1%}).",
          f"* Violation raised at the exact first inside fix in {g['exact_fix_detection']:.1%} of violations; proactive *approach* warning issued first in {g['approach_warning_rate']:.1%} (mean lead {g['approach_lead_s_mean'] or 0:.0f} s)."]
    i = M["identity"]
    L += ["", "## 3. Digital Tourist ID", "",
          f"* {i['ids']} IDs registered (mean {i['register_ms_mean']:.1f} ms incl. proof-of-work difficulty {i['pow_difficulty']}); valid IDs accepted {i['valid_accepted']:.1%}; verification mean {i['verify_ms_mean']:.2f} ms, p95 {i['verify_ms_p95']:.2f} ms.",
          f"* Tamper detection: {i['tamper_detected']:.1%} of {i['tamper_cases']} cases; per kind: {i['tamper_by_kind']}. Restored records verify again: {i['restored_valid_after_undo']:.1%}.",
          f"* Forged QR rejected {i['forged_qr_rejected']:.0%}; expired ID rejected: {i['expired_rejected']}.",
          f"* Validator network: 1 of 3 nodes tampered -> node flagged {i['net_one_node_tampered']['flagged']}, consensus {i['net_one_node_tampered']['consensus']}, ID still valid {i['net_one_node_tampered']['id_valid']}; "
          f"2 of 3 tampered -> consensus {i['net_two_nodes_tampered']['consensus']}, ID valid {i['net_two_nodes_tampered']['id_valid']} (majority compromised is correctly NOT trusted)."]
    e = M["e2e"]
    L += ["", "## 4. End-to-end and alert latency", "",
          f"* {e['runs']} full runs through the Flask API: success {e['success_rate']:.1%}; per scenario {e['per_scenario']}.",
          f"* Alert latency (update received -> incident written), {e['incidents']} incidents: mean {e['latency_ms_mean']:.1f} ms, p50 {e['latency_ms_p50']:.1f}, p95 {e['latency_ms_p95']:.1f}, p99 {e['latency_ms_p99']:.1f}, max {e['latency_ms_max']:.1f} ms.",
          f"* {e['sms_count']} SMS notifications; p95 incl. SIMULATED delivery delay {e['sms_total_ms_p95'] / 1000:.2f} s."]
    L += ["", "## 5. Objective check", "", "| Objective | Status | Evidence |", "|---|---|---|"]
    for n, ok, ev in checks:
        L.append(f"| {n} | {'MET' if ok else 'NOT MET'} | {ev} |")
    A_, R_, I_, H_ = M["anomaly"], M["anomaly"]["rules"], M["anomaly"]["if"], M["anomaly"]["hybrid"]
    L += ["", "## Answers to the research questions (from the measured numbers)", "",
          f"* **RQ1** One pipeline (`engine.py`) runs geo-fencing and anomaly detection on every fix; {M['e2e']['runs']} full runs succeeded at {M['e2e']['success_rate']:.0%}, with alerts raised without any tourist action.",
          f"* **RQ2** Hybrid episode detection {H_['episode_detection']:.1%} (rules {R_['episode_detection']:.1%}, Isolation Forest {I_['episode_detection']:.1%}); false-alert walks {H_['false_alert_traj']:.1%}; window-level precision {H_['precision']:.2f}, recall {H_['recall']:.2f}.",
          f"* **RQ3** Salted-hash ID + proof-of-work hash chain + HMAC QR: {M['identity']['tamper_detected']:.0%} tamper detection, verification p95 {M['identity']['verify_ms_p95']:.2f} ms, no raw passport stored.",
          f"* **RQ4** Server-side alert latency p95 {M['e2e']['latency_ms_p95']:.1f} ms. A measured manual-reporting baseline was NOT collected in Phase 1 (would need a user study), so no numeric comparison is claimed.",
          f"* **RQ5** False-alert walks: Isolation Forest alone {I_['false_alert_traj']:.1%} vs hybrid {H_['false_alert_traj']:.1%} ({'reduced' if H_['false_alert_traj'] < I_['false_alert_traj'] else 'NOT reduced'}). "
          f"Mean delay: rules {R_['delay_s']:.0f} s vs hybrid {H_['delay_s']:.0f} s - the hybrid is {'earlier' if H_['delay_s'] < R_['delay_s'] else 'NOT earlier'} on average; its benefit is higher COVERAGE ({R_['episode_detection']:.1%} -> {H_['episode_detection']:.1%}), especially for lost/wandering behaviour that no rule describes."]
    best = max((r for r in sweep if r["false_alert_traj"] <= 0.05), key=lambda r: r["f1"], default=None)
    if best:
        L += ["", f"Validation sweep: best F1 with <=5% false-alert walks = {best['f1']:.2f} at contamination {best['contamination']}, corroboration {best['dev_threshold_m']} m (see sweep.csv / fig_sweep.png)."]
    L += ["", "## Honest limitations", "",
          "* All numbers come from SYNTHETIC trajectories with simulated GPS noise; real-world performance may differ (real-dataset validation is future work).",
          "* Alert latency is server-side processing only; SMS delivery delay is a simulated model unless Twilio credentials are configured.",
          "* The ledger is a single-process simulation of a permissioned network (majority validation, proof-of-work), not a public blockchain with Byzantine fault tolerance.",
          "* Ground truth for geo-fencing uses an independent planar implementation on the same coordinates; boundary points closer than 0.5 m are excluded."]
    open(os.path.join(OUT, "REPORT.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--ntrain", type=int, default=150)
    ap.add_argument("--ntest", type=int, default=60)
    args = ap.parse_args()
    if args.quick:
        args.seeds, args.ntrain, args.ntest = 2, 60, 20
    t0 = time.time()
    print("[1/5] anomaly detection"); table, conf, delays, nwin = eval_anomaly(range(args.seeds), args.ntrain, args.ntest)
    print("[2/5] operating-point sweep"); sweep = eval_sweep(args.ntrain, args.ntest)
    print("[3/5] geo-fencing"); geo = eval_geofence(120 if not args.quick else 20)
    print("[4/5] digital ID"); ident = eval_identity(200 if not args.quick else 40, 50 if not args.quick else 16)
    print("[5/5] end-to-end + latency"); e2e = eval_e2e(60 if not args.quick else 12)
    M = {"anomaly": table, "geofence": geo, "identity": ident, "e2e": e2e, "n_windows": nwin, "sklearn_max_diff": max(SK_DIFF) if SK_DIFF else None,
         "config": {"hybrid_dev_m": C.HYBRID_DEV_M, "contamination": C.IF_CONTAMINATION, "window": W}}
    checks = objective_check(M)
    figures(table, conf, delays, sweep, e2e)
    import pandas as pd
    pd.DataFrame(sweep).round(4).to_csv(os.path.join(OUT, "sweep.csv"), index=False)
    rows = [{"detector": table[m]["name"], **{k: round(table[m][k], 4) for k in ("accuracy", "precision", "recall", "f1", "episode_detection", "delay_s", "false_alert_traj", "false_alerts_per_hour")}} for m, _ in MODES]
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "anomaly_table.csv"), index=False)
    save = json.loads(json.dumps(M, default=float)); save["e2e"].pop("latencies")
    json.dump(save, open(os.path.join(OUT, "metrics.json"), "w"), indent=2)
    write_report(M, sweep, checks, args)
    print(open(os.path.join(OUT, "REPORT.md"), encoding="utf-8").read())
    print(f"Done in {time.time() - t0:.0f} s. Files in {OUT}")


if __name__ == "__main__":
    main()
