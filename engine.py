"""
engine.py - The pipeline that ties every module together.

location update -> ID validity -> store fix -> geo-fence -> sliding window -> hybrid anomaly detector
-> duplicate suppression -> incident log (latency measured) -> notifications
Also: manual SOS and a watchdog for silent devices (SIGNAL_LOSS).
"""
import threading
import time

import anomaly
import config as C
import database as db
import notifier
from geofence import GeofenceEngine
from utils import iso, now_utc, parse_ts, epoch

ANOMALY_TYPES = ("ROUTE_DEVIATION", "PROLONGED_INACTIVITY", "BEHAVIOR_OUTLIER", "SIGNAL_LOSS")


class SafetyEngine:
    def __init__(self, model=None):
        self.geo = GeofenceEngine()
        self.win, self.active, self.last, self.run, self.lost = {}, {}, {}, {}, {}
        self._model = model
        self._sos_seen = set()
        self.lock = threading.RLock()

    # ------------------------------------------------------------ helpers
    @property
    def model(self):
        if self._model is None:
            self._model = anomaly.load_model()
        return self._model

    def current_run(self, tid):
        if tid not in self.run:
            self.run[tid] = db.get_current_run(tid)
        return self.run[tid]

    def reset_tourist(self, tid):
        """Start a new monitoring run (clears windows and geo-fence state, keeps history)."""
        with self.lock:
            self.run[tid] = self.current_run(tid) + 1
            for d in (self.win, self.active, self.last, self.lost):
                d.pop(tid, None)
            self.geo.reset(tid)
            return self.run[tid]

    def _raise(self, tid, tourist, run, ev, lat, lon, t0):
        inc_id = db.insert_incident(tid, run, ev["type"], ev["severity"], lat, lon, ev["message"])
        latency = (time.perf_counter() - t0) * 1000          # update received -> incident written
        db.set_incident_latency(inc_id, latency)
        inc = {"id": inc_id, "tourist_id": tid, "incident_type": ev["type"], "severity": ev["severity"],
               "lat": lat, "lon": lon, "message": ev["message"], "latency_ms": round(latency, 2)}
        notes = notifier.dispatch(inc, tourist, latency)
        inc["notifications"] = notes
        return inc

    # ------------------------------------------------------------ main entry points
    def process_fix(self, tid, lat, lon, ts=None):
        t0 = time.perf_counter()
        with self.lock:
            tourist = db.get_tourist(tid)
            if not tourist:
                return {"ok": False, "error": "Unknown tourist_id"}
            if tourist.get("revoked"):
                return {"ok": False, "error": "ID revoked"}
            if now_utc() > parse_ts(tourist["valid_until"]):
                return {"ok": False, "error": "ID expired"}
            ts = ts or iso()
            run = self.current_run(tid)
            db.insert_location(tid, run, lat, lon, ts)

            rec = anomaly.make_fix(lat, lon, ts)
            win = self.win.setdefault(tid, [])
            win.append(rec)
            del win[:-C.WINDOW_SIZE]
            self.last[tid] = rec
            was_lost = self.lost.pop(tid, False)

            events = list(self.geo.check(tid, lat, lon))
            alerts = anomaly.hybrid_alerts(win, self.model)
            if was_lost:
                alerts = [a for a in alerts if a["type"] != "SIGNAL_LOSS"]
            present = {a["type"] for a in alerts}
            act = self.active.setdefault(tid, set())
            events += [a for a in alerts if a["type"] not in act]
            act.intersection_update(present)
            act.update(present)

            incidents = [self._raise(tid, tourist, run, ev, lat, lon, t0) for ev in events]
            return {"ok": True, "events": incidents,
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 2)}

    def trigger_sos(self, tid, lat=None, lon=None, note="", request_id=None):
        """Manual SOS. Location priority: coordinates sent with the SOS -> last fix in memory ->
        last fix stored in the database -> none (SOS is STILL raised; never fails for lack of GPS).
        `request_id` makes client retries idempotent (no duplicate incidents)."""
        t0 = time.perf_counter()
        with self.lock:
            tourist = db.get_tourist(tid)
            if not tourist:
                return {"ok": False, "error": "Unknown tourist_id"}
            if request_id and request_id in self._sos_seen:
                return {"ok": True, "duplicate": True, "events": [], "latency_ms": 0.0}
            if lat is None or lon is None:
                if tid in self.last:
                    lat, lon = self.last[tid]["lat"], self.last[tid]["lon"]
                else:
                    last = db.get_last_location(tid)
                    lat, lon = (last["lat"], last["lon"]) if last else (None, None)
            if request_id:
                self._sos_seen.add(request_id)
            msg = "Manual SOS triggered by tourist" + (f" - {note}" if note else "")
            inc = self._raise(tid, tourist, self.current_run(tid),
                              {"type": "SOS", "severity": "CRITICAL", "message": msg}, lat, lon, t0)
            return {"ok": True, "events": [inc], "latency_ms": inc["latency_ms"]}

    def check_stale(self, now=None):
        """Watchdog: raise SIGNAL_LOSS for devices that went silent (called by the dashboard poll)."""
        now = epoch(now) if now else time.time()
        raised = []
        with self.lock:
            for tid, rec in list(self.last.items()):
                age = now - rec["t"]
                if C.GAP_LOSS_S < age <= 900 and not self.lost.get(tid):
                    t0 = time.perf_counter()
                    tourist = db.get_tourist(tid)
                    ev = {"type": "SIGNAL_LOSS", "severity": "HIGH",
                          "message": f"No location update for {age:.0f} s (last known position shown)"}
                    raised.append(self._raise(tid, tourist, self.current_run(tid), ev,
                                              rec["lat"], rec["lon"], t0))
                    self.lost[tid] = True
        return raised


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = SafetyEngine()
    return _engine


def reset_engine(model=None):
    global _engine
    _engine = SafetyEngine(model)
    return _engine
