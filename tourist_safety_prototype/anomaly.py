"""
anomaly.py - Hybrid AI anomaly detection on a sliding window of GPS fixes.

Rule layer (interpretable)  : ROUTE_DEVIATION, PROLONGED_INACTIVITY, SIGNAL_LOSS
Machine-learning layer      : Isolation Forest trained ONLY on normal trajectories (no labels needed)
Hybrid decision             : alert if a rule fires, OR if the forest flags an outlier AND the maximum
                              route deviation in the window exceeds HYBRID_DEV_M (spatial corroboration)
Window features (6)         : mean/max distance from planned route, mean speed, net displacement,
                              path length, circular heading variance
"""
import os
import numpy as np
import joblib
from sklearn.ensemble import IsolationForest

import config as C
from utils import to_xy, epoch

ROUTE_XY = np.array([to_xy(la, lo) for la, lo in C.PLANNED_ROUTE])
REST_XY = [(to_xy(r["lat"], r["lon"]), r["radius_m"]) for r in C.REST_POINTS]
ANOMALY_TYPES = ("ROUTE_DEVIATION", "PROLONGED_INACTIVITY")


def dist_to_route(x, y):
    """Distance in metres from a point to the planned route POLYLINE (point-to-segment, not waypoints)."""
    p0, p1 = ROUTE_XY[:-1], ROUTE_XY[1:]
    d = p1 - p0
    L2 = (d ** 2).sum(axis=1)
    t = np.clip(((x - p0[:, 0]) * d[:, 0] + (y - p0[:, 1]) * d[:, 1]) / L2, 0.0, 1.0)
    return float(np.min(np.hypot(x - (p0[:, 0] + t * d[:, 0]), y - (p0[:, 1] + t * d[:, 1]))))


def near_rest_point(x, y):
    return any(np.hypot(x - c[0], y - c[1]) <= r for c, r in REST_XY)


def make_fix(lat, lon, ts):
    """Pre-compute everything a window needs once per fix."""
    x, y = to_xy(lat, lon)
    return {"lat": lat, "lon": lon, "ts": ts, "t": epoch(ts), "x": x, "y": y, "dev": dist_to_route(x, y)}


def extract_features(win):
    xs = np.array([f["x"] for f in win]); ys = np.array([f["y"] for f in win])
    ts = np.array([f["t"] for f in win]); dev = np.array([f["dev"] for f in win])
    if len(win) < 2:
        return np.zeros(6)
    dx, dy = np.diff(xs), np.diff(ys)
    seg = np.hypot(dx, dy)
    speeds = seg / np.maximum(np.diff(ts), 1.0)
    ang = np.arctan2(dy, dx)
    heading_var = 1.0 - float(np.hypot(np.cos(ang).mean(), np.sin(ang).mean()))   # circular variance
    net = float(np.hypot(xs[-1] - xs[0], ys[-1] - ys[0]))
    return np.array([dev.mean(), dev.max(), speeds.mean(), net, seg.sum(), heading_var])


def rule_layer(win):
    alerts = []
    if len(win) >= 2 and win[-1]["t"] - win[-2]["t"] > C.GAP_LOSS_S:
        gap = win[-1]["t"] - win[-2]["t"]
        alerts.append({"type": "SIGNAL_LOSS", "severity": "MEDIUM",
                       "message": f"Location updates resumed after a {gap:.0f} s gap"})
    if len(win) >= C.ROUTE_DEV_CONSEC and all(f["dev"] > C.ROUTE_DEV_M for f in win[-C.ROUTE_DEV_CONSEC:]):
        alerts.append({"type": "ROUTE_DEVIATION", "severity": "MEDIUM",
                       "message": f"Last {C.ROUTE_DEV_CONSEC} fixes > {C.ROUTE_DEV_M} m from planned route "
                                  f"(now {win[-1]['dev']:.0f} m)"})
    if len(win) >= C.WINDOW_SIZE:
        net = float(np.hypot(win[-1]["x"] - win[0]["x"], win[-1]["y"] - win[0]["y"]))
        if net < C.INACTIVITY_NET_M and not near_rest_point(win[-1]["x"], win[-1]["y"]):
            alerts.append({"type": "PROLONGED_INACTIVITY", "severity": "HIGH",
                           "message": f"No movement (net {net:.1f} m over {C.WINDOW_SIZE * C.FIX_INTERVAL_S // 60} min)"
                                      " and not at a rest point"})
    return alerts


def check_gap(last_ts, now_ts):
    """Watchdog used when NO fix arrives at all. Returns seconds of silence if over the limit."""
    gap = epoch(now_ts) - epoch(last_ts)
    return gap if gap > C.GAP_LOSS_S else None


# ---------------------------------------------------------------- Isolation Forest
def new_forest(contamination=None, seed=42):
    return IsolationForest(n_estimators=C.IF_TREES, contamination=contamination or C.IF_CONTAMINATION,
                           random_state=seed)


def train_isolation_forest(X, contamination=None, seed=42, save=True):
    model = new_forest(contamination, seed).fit(np.vstack(X))
    if save:
        os.makedirs(os.path.dirname(C.MODEL_PATH), exist_ok=True)
        joblib.dump(model, C.MODEL_PATH)
    return model


def load_model():
    """Load the saved model; if none exists, train one on simulated normal trajectories."""
    if os.path.exists(C.MODEL_PATH):
        return joblib.load(C.MODEL_PATH)
    import train_model
    return train_model.train_and_save()


def window_feature_matrix(recs):
    """Features of every FULL window of a fix list (index of window end, matrix)."""
    idx, F = [], []
    for i in range(C.WINDOW_SIZE - 1, len(recs)):
        idx.append(i)
        F.append(extract_features(recs[i - C.WINDOW_SIZE + 1:i + 1]))
    return idx, F


def hybrid_alerts(win, model, dev_thr=None):
    """Live decision for the latest window (used by the engine)."""
    alerts = rule_layer(win)
    if len(win) == C.WINDOW_SIZE and not any(a["type"] in ANOMALY_TYPES for a in alerts):
        feat = extract_features(win)
        if model.predict(feat.reshape(1, -1))[0] == -1 and feat[1] > (dev_thr or C.HYBRID_DEV_M):
            alerts.append({"type": "BEHAVIOR_OUTLIER", "severity": "MEDIUM",
                           "message": f"Isolation Forest outlier + max route deviation {feat[1]:.0f} m"})
    return alerts
