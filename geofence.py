"""
geofence.py - Geo-fencing engine (Haversine circles + point-in-polygon).

Zone types : safe (circle), caution (circle/polygon), restricted (circle/polygon)
Events     : GEOFENCE_VIOLATION (HIGH)        entered a restricted zone
             RESTRICTED_ZONE_APPROACH (LOW)   within APPROACH_WARN_M of a restricted zone (proactive)
             CAUTION_ZONE_ENTRY (LOW)         entered a caution zone
             LEFT_RESTRICTED_ZONE (LOW)       left a restricted zone
             LEFT_SAFE_ZONE (LOW)             left the safe zone
Events are edge-triggered with hysteresis so GPS noise at a boundary does not flood the log.
"""
import math
import config as C
from utils import to_xy


def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres: a = sin^2(dphi/2) + cos p1 cos p2 sin^2(dl/2); d = 2R asin(sqrt a)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * C.EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def _prep(zone, ztype):
    z = dict(zone)
    z["type"] = ztype
    if z["shape"] == "polygon":
        z["_xy"] = [to_xy(la, lo) for la, lo in z["points"]]
        z["lat"] = sum(p[0] for p in z["points"]) / len(z["points"])
        z["lon"] = sum(p[1] for p in z["points"]) / len(z["points"])
    return z


SAFE = _prep(C.SAFE_ZONE, "safe")
CAUTION = [_prep(z, "caution") for z in C.CAUTION_ZONES]
RESTRICTED = [_prep(z, "restricted") for z in C.RESTRICTED_ZONES]


def _point_in_polygon(x, y, poly):
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def signed_distance(zone, lat, lon):
    """Metres to the zone boundary: negative inside, positive outside."""
    if zone["shape"] == "circle":
        return haversine(lat, lon, zone["lat"], zone["lon"]) - zone["radius_m"]
    x, y = to_xy(lat, lon)
    poly = zone["_xy"]
    d = min(_seg_dist(x, y, *poly[i], *poly[(i + 1) % len(poly)]) for i in range(len(poly)))
    return -d if _point_in_polygon(x, y, poly) else d


def reference_inside(zone, lat, lon):
    """INDEPENDENT planar implementation used only to cross-check the engine in tests/evaluation."""
    x, y = to_xy(lat, lon)
    if zone["shape"] == "circle":
        cx, cy = to_xy(zone["lat"], zone["lon"])
        return math.hypot(x - cx, y - cy) <= zone["radius_m"]
    poly, wn = zone["_xy"], 0            # winding-number algorithm
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        cross = (x2 - x1) * (y - y1) - (x - x1) * (y2 - y1)
        if y1 <= y < y2 and cross > 0:
            wn += 1
        elif y2 <= y < y1 and cross < 0:
            wn -= 1
    return wn != 0


class GeofenceEngine:
    def __init__(self):
        self.state = {}

    def reset(self, tourist_id):
        self.state.pop(tourist_id, None)

    @staticmethod
    def _inside(prev_inside, sd):
        """Hysteresis: enter at sd<=0, leave only when sd > HYSTERESIS."""
        if sd <= 0:
            return True
        if prev_inside and sd <= C.GEOFENCE_HYSTERESIS_M:
            return True
        return False

    def check(self, tourist_id, lat, lon):
        st = self.state.setdefault(tourist_id, {"in_safe": True, "restricted": set(),
                                                "approach": set(), "caution": set()})
        ev = []

        def add(t, sev, msg):
            ev.append({"type": t, "severity": sev, "message": msg, "lat": lat, "lon": lon})

        sd_safe = signed_distance(SAFE, lat, lon)
        now_safe = self._inside(st["in_safe"], sd_safe)
        if st["in_safe"] and not now_safe:
            add("LEFT_SAFE_ZONE", "LOW", f"Left {SAFE['name']} ({sd_safe:.0f} m beyond boundary)")
        st["in_safe"] = now_safe

        for z in RESTRICTED:
            sd = signed_distance(z, lat, lon)
            inside = self._inside(z["name"] in st["restricted"], sd)
            if inside and z["name"] not in st["restricted"]:
                add("GEOFENCE_VIOLATION", "HIGH", f"Entered restricted zone: {z['name']}")
            if (not inside) and z["name"] in st["restricted"]:
                add("LEFT_RESTRICTED_ZONE", "LOW", f"Left restricted zone: {z['name']}")
            (st["restricted"].add if inside else st["restricted"].discard)(z["name"])
            near = (not inside) and sd <= C.APPROACH_WARN_M
            was_near = z["name"] in st["approach"]
            if near and not was_near:
                add("RESTRICTED_ZONE_APPROACH", "LOW", f"Approaching {z['name']} ({sd:.0f} m away)")
            if near:
                st["approach"].add(z["name"])
            elif sd > C.APPROACH_WARN_M + C.GEOFENCE_HYSTERESIS_M or inside:
                st["approach"].discard(z["name"])

        for z in CAUTION:
            sd = signed_distance(z, lat, lon)
            inside = self._inside(z["name"] in st["caution"], sd)
            if inside and z["name"] not in st["caution"]:
                add("CAUTION_ZONE_ENTRY", "LOW", f"Entered caution zone: {z['name']}")
            (st["caution"].add if inside else st["caution"].discard)(z["name"])
        return ev


def zones_for_map():
    def clean(z):
        return {k: v for k, v in z.items() if not k.startswith("_")}
    return {"safe": clean(SAFE), "caution": [clean(z) for z in CAUTION],
            "restricted": [clean(z) for z in RESTRICTED]}
