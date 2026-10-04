"""
app.py - Flask web application: registration, Digital ID, verification, tourist app view,
location/SOS API and the authority dashboard.
Run:  python app.py      ->  http://127.0.0.1:5000
"""
import math
import secrets
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

import anomaly
import config as C
import database as db
import digital_id
import geofence
import simulator
from engine import get_engine
from utils import to_xy, now_utc, iso

app = Flask(__name__)
app.secret_key = C.SECRET_KEY
db.init_db()


def _json():
    return request.get_json(silent=True, force=True) or {}


# ------------------------------------------------------------------ pages
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/intro")
def intro():
    """Full-screen title card with the presenter's name (for the demo video)."""
    return render_template("intro.html")


@app.route("/api/demo_tourist", methods=["POST"])
def api_demo_tourist():
    """Creates a fresh demo tourist (used by the automatic demo on the dashboard)."""
    d = digital_id.create_digital_id("Harsh Parmar", "Indian", "D" + str(secrets.randbelow(10**7)).zfill(7),
                                     "+91 90000 00000")
    return jsonify({"ok": True, "tourist_id": d["tourist_id"], "qr_url": d["qr_url"]})


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = {k: request.form.get(k, "").strip() for k in ("name", "nationality", "passport", "emergency_contact")}
        if not all(f.values()):
            flash("All fields are required.", "error")
            return redirect(url_for("register"))
        return render_template("digital_id.html", data=digital_id.create_digital_id(
            f["name"], f["nationality"], f["passport"], f["emergency_contact"]))
    return render_template("register.html")


@app.route("/verify/<tourist_id>")
def verify(tourist_id):
    return render_template("verify.html", result=digital_id.verify_digital_id(tourist_id), tourist_id=tourist_id)


@app.route("/scan", methods=["GET", "POST"])
def scan():
    """Authority verification by QR: a QR scanner app returns the text, paste it here."""
    if request.method == "POST":
        res = digital_id.verify_qr(request.form.get("qr", "").strip())
        return render_template("verify.html", result=res, tourist_id=res.get("tourist_id", "(from QR)"))
    return render_template("scan.html")


@app.route("/tourist/<tourist_id>")
def tourist_app(tourist_id):
    t = db.get_tourist(tourist_id)
    if not t:
        flash("Unknown tourist id.", "error")
        return redirect(url_for("register"))
    return render_template("tourist.html", t=t)


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


# ------------------------------------------------------------------ APIs
@app.route("/api/location", methods=["POST"])
def api_location():
    d = _json()
    try:
        res = get_engine().process_fix(d.get("tourist_id"), float(d["lat"]), float(d["lon"]), d.get("timestamp"))
    except (KeyError, TypeError, ValueError):
        return jsonify({"ok": False, "error": "lat, lon and tourist_id are required"}), 400
    return jsonify(res), (200 if res.get("ok") else 400)


@app.route("/api/sos", methods=["POST"])
def api_sos():
    d = _json()
    try:
        lat = float(d["lat"]) if d.get("lat") is not None else None
        lon = float(d["lon"]) if d.get("lon") is not None else None
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "lat/lon must be numbers"}), 400
    res = get_engine().trigger_sos(d.get("tourist_id"), lat, lon, str(d.get("note", ""))[:200],
                                   d.get("request_id"))
    return jsonify(res), (200 if res.get("ok") else 400)


@app.errorhandler(500)
def server_error(_e):
    """API clients always get JSON (the tourist app must never mistake a server bug for 'offline')."""
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Internal server error"}), 500
    return "Internal server error", 500


@app.route("/api/reset/<tourist_id>", methods=["POST"])
def api_reset(tourist_id):
    if not db.get_tourist(tourist_id):
        return jsonify({"ok": False, "error": "Unknown tourist_id"}), 400
    return jsonify({"ok": True, "run": get_engine().reset_tourist(tourist_id)})


@app.route("/api/demo/<scenario>")
def api_demo(scenario):
    if scenario not in simulator.SCENARIOS:
        return jsonify({"ok": False, "error": "unknown scenario"}), 404
    tr = simulator.generate(scenario, seed=None, start_time=now_utc())
    return jsonify({"ok": True, "scenario": scenario, "fixes": tr.fixes, "onset": tr.onset, "meta": tr.meta})


@app.route("/api/verify_qr", methods=["POST"])
def api_verify_qr():
    return jsonify(digital_id.verify_qr(_json().get("qr", "")))


@app.route("/api/incident/<int:iid>/<action>", methods=["POST"])
def api_incident(iid, action):
    status = {"ack": "ACKNOWLEDGED", "resolve": "RESOLVED"}.get(action)
    if not status or not db.get_incident(iid):
        return jsonify({"ok": False}), 400
    db.set_incident_status(iid, status)
    return jsonify({"ok": True})


@app.route("/api/network/<action>", methods=["POST"])
def api_network(action):
    net = digital_id.get_network()
    if action == "tamper":
        node = int(_json().get("node", 1))
        ok = net.tamper(node)
    elif action == "heal":
        ok = net.heal()
    elif action == "audit":
        return jsonify({"ok": True, "issues": digital_id.audit_ledger(), "status": net.status()})
    else:
        return jsonify({"ok": False}), 404
    return jsonify({"ok": ok, "status": net.status()})


@app.route("/map")
def folium_map():
    """Street-tile map built with folium (needs internet for tiles). The dashboard's own SVG map works offline."""
    try:
        import folium
    except ImportError:
        return "folium is not installed: pip install folium", 501
    z = geofence.zones_for_map()
    m = folium.Map(location=list(C.ORIGIN), zoom_start=14, tiles="OpenStreetMap")
    folium.Circle([z["safe"]["lat"], z["safe"]["lon"]], radius=z["safe"]["radius_m"], color="green",
                  fill=True, fill_opacity=0.08, tooltip=z["safe"]["name"]).add_to(m)
    for q, col in [(c, "orange") for c in z["caution"]] + [(r, "red") for r in z["restricted"]]:
        if q["shape"] == "circle":
            folium.Circle([q["lat"], q["lon"]], radius=q["radius_m"], color=col, fill=True, tooltip=q["name"]).add_to(m)
        else:
            folium.Polygon(q["points"], color=col, fill=True, tooltip=q["name"]).add_to(m)
    folium.PolyLine(C.PLANNED_ROUTE, color="blue", weight=4, tooltip="Planned route").add_to(m)
    eng = get_engine()
    for t in db.get_all_tourists():
        track = db.get_track(t["tourist_id"], eng.current_run(t["tourist_id"]), 200)
        if track:
            folium.PolyLine([(p["lat"], p["lon"]) for p in track], color="teal", weight=3).add_to(m)
            folium.Marker([track[-1]["lat"], track[-1]["lon"]], tooltip=t["name"],
                          icon=folium.Icon(color="green", icon="user", prefix="fa")).add_to(m)
    for i in db.get_incidents(60):
        if i["lat"] is not None:
            folium.CircleMarker([i["lat"], i["lon"]], radius=7, color="red", fill=True,
                                tooltip=f"{i['incident_type']} ({i['severity']}): {i['message']}").add_to(m)
    return m.get_root().render()


WEIGHT = {"LOW": 1, "MEDIUM": 3, "HIGH": 6, "CRITICAL": 10}


@app.route("/api/state")
def api_state():
    eng = get_engine()
    eng.check_stale()
    tourists = []
    for t in db.get_all_tourists():
        tid = t["tourist_id"]
        run = eng.current_run(tid)
        track = db.get_track(tid, run, 120)
        open_inc = db.get_open_incidents(tid, run)
        risk = min(100, sum(WEIGHT[i["severity"]] for i in open_inc if i["status"] == "OPEN"))
        status = "SOS" if any(i["incident_type"] == "SOS" and i["status"] == "OPEN" for i in open_inc) else \
                 "ALERT" if any(C.SEVERITY_RANK[i["severity"]] >= 2 and i["status"] == "OPEN" for i in open_inc) else "OK"
        tourists.append({"tourist_id": tid, "name": t["name"], "status": status, "risk": risk,
                         "track": track, "last": track[-1] if track else None})
    heat = {}
    for p in db.get_incident_points():
        x, y = to_xy(p["lat"], p["lon"])
        key = (math.floor(x / 100), math.floor(y / 100))
        heat[key] = heat.get(key, 0) + C.SEVERITY_RANK.get(p["severity"], 1)
    return jsonify({
        "server_time": iso(), "stats": db.get_stats(), "tourists": tourists,
        "incidents": db.get_incidents(30), "notifications": db.get_notifications(12),
        "zones": geofence.zones_for_map(), "route": [{"lat": a, "lon": b} for a, b in C.PLANNED_ROUTE],
        "rest_points": C.REST_POINTS, "origin": C.ORIGIN,
        "heat": [{"i": k[0], "j": k[1], "w": v} for k, v in heat.items()],
        "network": digital_id.get_network().status(),
    })


if __name__ == "__main__":
    print("=" * 62)
    print("  Tourist Safety Monitoring & Incident Response System")
    print("  Programming with Python | Group 2 | Marwadi University")
    print("  Open: http://127.0.0.1:5000")
    print("=" * 62)
    app.run(debug=False, port=5000, threaded=True)
