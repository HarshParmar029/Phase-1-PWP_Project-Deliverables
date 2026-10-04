"""Automated tests. Run:  python -m unittest discover -s tests -v"""
import os, sys, tempfile, unittest
_tmp = tempfile.mkdtemp()
os.environ["TSAFETY_DB"] = os.path.join(_tmp, "t.db")
os.environ["TSAFETY_MODEL"] = os.path.join(_tmp, "m.joblib")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import config as C, database as db, digital_id as did, geofence as gf, anomaly, simulator
from datetime import datetime, timezone, timedelta
from utils import iso, to_xy, from_xy, now_utc
import engine as eng_mod
db.init_db()


def register(name="Test User"):
    return did.create_digital_id(name, "Indian", "P1234567", "+91 90000 00000")


class TestGeofence(unittest.TestCase):
    def test_haversine_known_value(self):
        self.assertAlmostEqual(gf.haversine(0, 0, 0, 1), 111194.93, delta=1.0)

    def test_haversine_vs_geopy_if_available(self):
        try:
            from geopy.distance import great_circle
        except ImportError:
            self.skipTest("geopy not installed")
        a, b = (20.888, 70.401), (20.9, 70.4)
        self.assertAlmostEqual(gf.haversine(*a, *b), great_circle(a, b).meters, delta=1.0)

    def test_circle_and_polygon_against_reference(self):
        rng = np.random.default_rng(0)
        for z in gf.RESTRICTED + gf.CAUTION:
            cx, cy = to_xy(z["lat"], z["lon"])
            wrong = 0
            for _ in range(3000):
                lat, lon = from_xy(cx + rng.uniform(-400, 400), cy + rng.uniform(-400, 400))
                sd = gf.signed_distance(z, lat, lon)
                if abs(sd) < 0.5:
                    continue
                wrong += (sd <= 0) != gf.reference_inside(z, lat, lon)
            self.assertEqual(wrong, 0, z["name"])

    def test_events_edge_triggered(self):
        g = gf.GeofenceEngine()
        z = gf.RESTRICTED[0]
        ev1 = g.check("a", z["lat"], z["lon"])
        ev2 = g.check("a", z["lat"], z["lon"])
        self.assertIn("GEOFENCE_VIOLATION", [e["type"] for e in ev1])
        self.assertEqual([e for e in ev2 if e["type"] == "GEOFENCE_VIOLATION"], [])

    def test_exit_from_restricted_zone_event(self):
        g = gf.GeofenceEngine()
        z = gf.RESTRICTED[0]
        g.check("e", z["lat"], z["lon"])
        far_lat, far_lon = from_xy(to_xy(z["lat"], z["lon"])[0] + z["radius_m"] + 200, to_xy(z["lat"], z["lon"])[1])
        ev = g.check("e", far_lat, far_lon)
        self.assertIn("LEFT_RESTRICTED_ZONE", [e["type"] for e in ev])

    def test_hysteresis_no_flapping(self):
        g = gf.GeofenceEngine()
        z = gf.RESTRICTED[0]
        g.check("h", z["lat"], z["lon"])
        la, lo = from_xy(to_xy(z["lat"], z["lon"])[0] + z["radius_m"] + 5, to_xy(z["lat"], z["lon"])[1])
        g.check("h", la, lo)           # 5 m outside: still considered inside (hysteresis)
        ev = g.check("h", z["lat"], z["lon"])
        self.assertEqual([e for e in ev if e["type"] == "GEOFENCE_VIOLATION"], [])


class TestDigitalID(unittest.TestCase):
    def test_register_and_verify(self):
        d = register()
        r = did.verify_digital_id(d["tourist_id"])
        self.assertTrue(r["valid"], r)
        self.assertTrue(d["block_hash"].startswith("0" * C.POW_DIFFICULTY))

    def test_passport_not_stored_raw(self):
        d = register()
        t = db.get_tourist(d["tourist_id"])
        self.assertNotIn("P1234567", str(t))
        self.assertTrue(did.verify_passport(d["tourist_id"], "p1234567"))
        self.assertFalse(did.verify_passport(d["tourist_id"], "X999"))

    def test_record_tamper_detected(self):
        d = register()
        db.update_tourist_field(d["tourist_id"], "name", "Mallory")
        r = did.verify_digital_id(d["tourist_id"])
        self.assertFalse(r["valid"])
        db.update_tourist_field(d["tourist_id"], "name", "Test User")

    def test_expired_and_revoked_rejected(self):
        d = register()
        db.update_tourist_field(d["tourist_id"], "valid_until", iso(now_utc() - timedelta(days=1)))
        self.assertFalse(did.verify_digital_id(d["tourist_id"])["valid"])
        d2 = register()
        db.update_tourist_field(d2["tourist_id"], "revoked", 1)
        self.assertFalse(did.verify_digital_id(d2["tourist_id"])["valid"])

    def test_forged_qr_rejected(self):
        d = register()
        good = did.qr_text(d["tourist_id"], d["payload_hash"])
        self.assertTrue(did.verify_qr(good)["valid"])
        parts = good.split("|"); parts[2] = "SIG:" + "0" * 16
        self.assertFalse(did.verify_qr("|".join(parts))["valid"])
        self.assertFalse(did.verify_qr("garbage")["valid"])

    def test_network_consensus_and_tamper(self):
        d = register()
        net = did.get_network(reload=True)
        self.assertTrue(net.status()["consensus_ok"])
        net.tamper(1)
        st = net.status()
        self.assertEqual(st["nodes"][1]["state"], "TAMPERED")
        self.assertTrue(st["consensus_ok"])                       # 2 of 3 still healthy
        self.assertTrue(did.verify_digital_id(d["tourist_id"])["valid"])
        net.tamper(0)
        self.assertFalse(net.status()["consensus_ok"])            # majority compromised
        self.assertFalse(did.verify_digital_id(d["tourist_id"])["valid"])
        did.get_network(reload=True)

    def test_heal(self):
        register()
        net = did.get_network(reload=True)
        net.tamper(2)
        self.assertTrue(net.heal())
        self.assertEqual(net.status()["nodes"][2]["state"], "OK")


class TestAnomaly(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import train_model
        cls.model = train_model.train_and_save(n_traj=40, seed=7)

    def _recs(self, sc, seed):
        t = simulator.generate(sc, seed=seed)
        return t, [anomaly.make_fix(f["lat"], f["lon"], f["timestamp"]) for f in t.fixes]

    def test_route_deviation_detected(self):
        t, r = self._recs("route_deviation", 11)
        hits = [i for i in range(len(r)) if any(a["type"] == "ROUTE_DEVIATION" for a in anomaly.rule_layer(r[max(0, i - 9):i + 1]))]
        self.assertTrue(hits and hits[0] >= t.onset)

    def test_inactivity_detected_but_not_at_rest_point(self):
        t, r = self._recs("prolonged_inactivity", 5)
        self.assertTrue(any(any(a["type"] == "PROLONGED_INACTIVITY" for a in anomaly.rule_layer(r[max(0, i - 9):i + 1])) for i in range(len(r))))
        rp = C.REST_POINTS[0]
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        still = [anomaly.make_fix(rp["lat"], rp["lon"], iso(base + timedelta(seconds=30 * i))) for i in range(10)]
        self.assertEqual([a for a in anomaly.rule_layer(still) if a["type"] == "PROLONGED_INACTIVITY"], [])

    def test_signal_loss_rule_and_watchdog(self):
        t, r = self._recs("signal_loss", 3)
        self.assertTrue(any(any(a["type"] == "SIGNAL_LOSS" for a in anomaly.rule_layer(r[max(0, i - 9):i + 1])) for i in range(len(r))))
        self.assertIsNotNone(anomaly.check_gap(t.fixes[0]["timestamp"], t.fixes[0]["timestamp"].replace("10:00:00", "10:05:00")))

    def test_normal_walk_no_rule_alerts(self):
        bad = 0
        for s in range(30):
            _, r = self._recs("normal", 1000 + s)
            bad += any(anomaly.rule_layer(r[max(0, i - 9):i + 1]) for i in range(len(r)))
        self.assertEqual(bad, 0)


class TestEngineAndApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import train_model
        cls.model = train_model.train_and_save(n_traj=40, seed=7)
        import app as appmod
        appmod.app.config["TESTING"] = True
        cls.client = appmod.app.test_client()
        eng_mod.reset_engine(cls.model)

    def _run(self, tid, scenario, seed=1):
        eng_mod.get_engine().reset_tourist(tid)
        tr = simulator.generate(scenario, seed=seed, start_time=now_utc())
        out = []
        for f in tr.fixes:
            r = self.client.post("/api/location", json={"tourist_id": tid, **f}).get_json()
            out += [e["incident_type"] for e in r["events"]]
        return out

    def test_geofence_violation_end_to_end(self):
        tid = register()["tourist_id"]
        types = self._run(tid, "geofence_violation", 2)
        self.assertIn("GEOFENCE_VIOLATION", types)
        self.assertEqual(types.count("GEOFENCE_VIOLATION"), 1)
        self.assertTrue(any(n["channel"] == "SMS" for n in db.get_notifications(20)))

    def test_normal_walk_is_quiet(self):
        tid = register()["tourist_id"]
        types = self._run(tid, "normal", 4)
        self.assertEqual([t for t in types if t not in ("CAUTION_ZONE_ENTRY", "RESTRICTED_ZONE_APPROACH", "LEFT_SAFE_ZONE", "LEFT_RESTRICTED_ZONE")], [])

    def test_sos_and_lifecycle(self):
        tid = register()["tourist_id"]
        self.client.post("/api/location", json={"tourist_id": tid, "lat": 20.888, "lon": 70.401})
        r = self.client.post("/api/sos", json={"tourist_id": tid}).get_json()
        inc = r["events"][0]
        self.assertEqual(inc["severity"], "CRITICAL")
        self.assertAlmostEqual(inc["lat"], 20.888)
        self.assertTrue(self.client.post(f"/api/incident/{inc['id']}/ack").get_json()["ok"])
        self.assertEqual(db.get_incident(inc["id"])["status"], "ACKNOWLEDGED")

    def test_sos_without_any_gps_fix_does_not_crash(self):
        """Regression: SOS pressed before the first GPS fix used to return HTTP 500 (shown as 'offline')."""
        tid = register()["tourist_id"]
        eng_mod.get_engine().reset_tourist(tid)
        r = self.client.post("/api/sos", json={"tourist_id": tid, "note": "no gps yet"})
        self.assertEqual(r.status_code, 200)
        inc = r.get_json()["events"][0]
        self.assertEqual(inc["severity"], "CRITICAL")
        self.assertIsNone(inc["lat"])
        self.assertTrue(any("not available" in n["body"] for n in db.get_notifications(10)))

    def test_sos_uses_last_stored_location_and_is_idempotent(self):
        tid = register()["tourist_id"]
        self.client.post("/api/location", json={"tourist_id": tid, "lat": 20.889, "lon": 70.402})
        eng_mod.get_engine().last.pop(tid, None)            # simulate server restart: only DB remembers
        a = self.client.post("/api/sos", json={"tourist_id": tid, "request_id": "r1"}).get_json()
        self.assertAlmostEqual(a["events"][0]["lat"], 20.889)
        b = self.client.post("/api/sos", json={"tourist_id": tid, "request_id": "r1"}).get_json()
        self.assertTrue(b.get("duplicate"))
        self.assertEqual(b["events"], [])

    def test_sos_bad_coordinates_json_error(self):
        tid = register()["tourist_id"]
        r = self.client.post("/api/sos", json={"tourist_id": tid, "lat": "abc"})
        self.assertEqual(r.status_code, 400)
        self.assertTrue(r.is_json)

    def test_unknown_and_bad_input(self):
        self.assertEqual(self.client.post("/api/location", json={"tourist_id": "NOPE", "lat": 1, "lon": 1}).status_code, 400)
        self.assertEqual(self.client.post("/api/location", json={"lat": "x"}).status_code, 400)

    def test_demo_tourist_api(self):
        r = self.client.post("/api/demo_tourist").get_json()
        self.assertTrue(r["ok"])
        self.assertTrue(did.verify_digital_id(r["tourist_id"])["valid"])

    def test_scan_page_verifies_qr(self):
        d = register()
        good = did.qr_text(d["tourist_id"], d["payload_hash"])
        self.assertIn("PASSED", self.client.post("/scan", data={"qr": good}).get_data(as_text=True))
        self.assertIn("FAILED", self.client.post("/scan", data={"qr": "TID:x|HASH:y|SIG:z"}).get_data(as_text=True))

    def test_state_and_pages(self):
        register()
        s = self.client.get("/api/state").get_json()
        self.assertIn("stats", s)
        for p in ("/", "/register", "/dashboard", "/scan", "/intro"):
            self.assertEqual(self.client.get(p).status_code, 200)

    def test_watchdog_signal_loss(self):
        tid = register()["tourist_id"]
        eng = eng_mod.get_engine(); eng.reset_tourist(tid)
        self.client.post("/api/location", json={"tourist_id": tid, "lat": 20.888, "lon": 70.401})
        raised = eng.check_stale(now=iso(now_utc() + timedelta(seconds=200)))
        mine = [r for r in raised if r["tourist_id"] == tid]
        self.assertEqual([r["incident_type"] for r in mine], ["SIGNAL_LOSS"])
        self.assertEqual(eng.check_stale(now=iso(now_utc() + timedelta(seconds=210))), [])  # no duplicate


if __name__ == "__main__":
    unittest.main()
