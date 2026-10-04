"""
simulator.py - Synthetic GPS trajectory generator with exact ground-truth labels.

A tourist walks the planned route at ~1.2 m/s (one fix / 30 s) with Gaussian GPS noise (sigma 6 m),
random short photo pauses and (sometimes) a legitimate stop at a designated rest point.
Scenarios: normal (incl. harmless side-trips), route_deviation (~500 m perpendicular drift),
           prolonged_inactivity (~7 min), lost_wandering (erratic, 70-190 m off route),
           geofence_violation (walks into a restricted zone), signal_loss (device silent 3-5 min).
"""
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import numpy as np

import config as C
from utils import to_xy, from_xy, iso
import geofence

ROUTE = np.array([to_xy(la, lo) for la, lo in C.PLANNED_ROUTE])
_SEG = np.hypot(*(ROUTE[1:] - ROUTE[:-1]).T)
CUM = np.concatenate([[0.0], np.cumsum(_SEG)])
LENGTH = float(CUM[-1])
STEP_M = C.WALK_SPEED_MS * C.FIX_INTERVAL_S


def route_point(s):
    s = min(max(s, 0.0), LENGTH)
    i = min(int(np.searchsorted(CUM, s, side="right")) - 1, len(_SEG) - 1)
    t = (s - CUM[i]) / _SEG[i]
    p = ROUTE[i] + t * (ROUTE[i + 1] - ROUTE[i])
    u = (ROUTE[i + 1] - ROUTE[i]) / _SEG[i]
    return p[0], p[1], u[0], u[1]


def nearest_s(x, y):
    best, bs = 1e18, 0.0
    for i in range(len(_SEG)):
        a, b = ROUTE[i], ROUTE[i + 1]
        d = b - a
        t = float(np.clip(((x - a[0]) * d[0] + (y - a[1]) * d[1]) / (d @ d), 0, 1))
        dist = math.hypot(x - (a[0] + t * d[0]), y - (a[1] + t * d[1]))
        if dist < best:
            best, bs = dist, CUM[i] + t * _SEG[i]
    return bs


REST_S = [nearest_s(*to_xy(r["lat"], r["lon"])) for r in C.REST_POINTS]


@dataclass
class Trajectory:
    scenario: str
    fixes: list
    labels: list
    onset: int = None
    meta: dict = field(default_factory=dict)


def _speed(rng, mu=None):
    return float(np.clip(rng.normal(mu or C.WALK_SPEED_MS, 0.15), 0.6, 1.8)) * C.FIX_INTERVAL_S


def _tourist_speed(rng):
    """Each tourist has an individual pace (slow seniors ... brisk walkers)."""
    return float(np.clip(rng.normal(C.WALK_SPEED_MS, 0.12), 0.85, 1.4))


def _lateral(rng, n, sidetrips=False):
    """Natural sideways wander around the route (Ornstein-Uhlenbeck, ~18 m) plus, for normal
    tourists, occasional harmless side-trips (shop, photo spot) of 80-200 m that return to the route."""
    off, cur = np.zeros(n), 0.0
    for i in range(n):
        cur = 0.9 * cur + rng.normal(0, 8.0)
        off[i] = cur
    if sidetrips and rng.random() < 0.35:
        k, L = int(rng.integers(5, max(6, n - 20))), int(rng.integers(8, 17))
        peak, side = float(rng.uniform(80, 200)), float(rng.choice([-1, 1]))
        for i in range(k, min(n, k + L + 1)):
            off[i] += side * peak * math.sin(math.pi * (i - k) / L)
    return off


def _base_s(rng, n, s0, rest=True, pause_p=0.05, mu=None):
    """Arc-length positions of a walker incl. short pauses and an optional legitimate rest stop."""
    plan = None
    if rest and rng.random() < 0.3:
        cand = [r for r in REST_S if r > s0 + 60]
        if cand:
            plan = [float(rng.choice(cand)), int(rng.integers(8, 15)), False]
    s, held, out = s0, 0, []
    for _ in range(n):
        out.append(s)
        if held > 0:
            held -= 1
            continue
        nxt = min(s + _speed(rng, mu), LENGTH)
        if plan and not plan[2] and s < plan[0] <= nxt:
            s, held, plan[2] = plan[0], plan[1], True
            continue
        if rng.random() < pause_p:
            held = int(rng.integers(1, 4))
        s = nxt
    return out


def _finish(scenario, xy, rng, start_time, labels, onset, meta, keep=None):
    t0 = start_time or datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    fixes = []
    for i, (x, y) in enumerate(xy):
        if keep is not None and not keep[i]:
            continue
        nx, ny = rng.normal(0, C.GPS_NOISE_SIGMA_M, 2)
        lat, lon = from_xy(x + nx, y + ny)
        fixes.append({"lat": lat, "lon": lon, "timestamp": iso(t0 + timedelta(seconds=C.FIX_INTERVAL_S * i))})
    lab = [l for i, l in enumerate(labels) if keep is None or keep[i]]
    return Trajectory(scenario, fixes, lab, onset, meta)


def _xy_from_s(ss, lat=None):
    out = []
    for i, s in enumerate(ss):
        x, y, ux, uy = route_point(s)
        o = 0.0 if lat is None else float(lat[i])
        out.append((x - uy * o, y + ux * o))
    return out


def generate(scenario, seed=None, start_time=None, n=48):
    rng = np.random.default_rng(seed)
    s0 = float(rng.uniform(0, 150))
    mu = _tourist_speed(rng)

    if scenario == "normal":
        ss = _base_s(rng, n, s0, mu=mu)
        return _finish("normal", _xy_from_s(ss, _lateral(rng, n, sidetrips=True)), rng, start_time, [0] * n, None, {})

    if scenario == "route_deviation":
        k0 = int(rng.integers(12, 23))
        side = float(rng.choice([-1, 1]))
        ss = _base_s(rng, n, s0, rest=False, pause_p=0.02, mu=mu)
        wander = _lateral(rng, n)
        ramp = int(math.ceil(500 / STEP_M))
        xy, s_frozen, cur = [], ss[k0], None
        for i in range(n):
            if i < k0:
                x, y, ux, uy = route_point(ss[i])
                xy.append((x - uy * wander[i], y + ux * wander[i]))
            else:
                j = i - k0 + 1
                if j <= ramp:
                    s = s_frozen
                    off = min(500.0, STEP_M * j)
                else:
                    s = min(s_frozen + (j - ramp) * mu * C.FIX_INTERVAL_S, LENGTH)
                    off = 500.0
                x, y, ux, uy = route_point(s)
                xy.append((x - uy * off * side, y + ux * off * side))
        labels = [1 if i >= k0 else 0 for i in range(n)]
        return _finish("route_deviation", xy, rng, start_time, labels, k0, {"side": side})

    if scenario == "prolonged_inactivity":
        ss = _base_s(rng, n, s0, rest=False, pause_p=0.03, mu=mu)
        wander = _lateral(rng, n)
        for _ in range(50):
            k0 = int(rng.integers(10, 21))
            x, y = route_point(ss[k0])[:2]
            if not any(math.hypot(x - c[0], y - c[1]) < 120 for c, _r in
                       [(to_xy(r["lat"], r["lon"]), r["radius_m"]) for r in C.REST_POINTS]):
                break
        hold = 14                                  # 14 fixes = 7 minutes
        out, s = [], ss[k0]
        lat = wander.copy()
        for i in range(n):
            if k0 <= i < k0 + hold:
                out.append(s)
                lat[i] = lat[k0 - 1]              # standing still: no wander either
            elif i >= k0 + hold:
                s = min(s + _speed(rng, mu), LENGTH)
                out.append(s)
            else:
                out.append(ss[i])
        labels = [1 if k0 <= i < k0 + hold else 0 for i in range(n)]
        return _finish("prolonged_inactivity", _xy_from_s(out, lat), rng, start_time, labels, k0, {"hold_fixes": hold})

    if scenario == "lost_wandering":
        # disoriented tourist: leaves the route and wanders erratically 70-190 m away for ~8 minutes.
        # Neither route-deviation (>250 m) nor inactivity (net<20 m) rules fire - a behavioural outlier.
        ss = _base_s(rng, n, s0, rest=False, pause_p=0.02, mu=mu)
        wander = _lateral(rng, n)
        k0, hold = int(rng.integers(12, 23)), 16
        side = float(rng.choice([-1, 1]))
        xy = []
        for i in range(k0):
            x, y, ux, uy = route_point(ss[i])
            xy.append((x - uy * wander[i], y + ux * wander[i]))
        x, y, ux, uy = route_point(ss[k0])
        pos = np.array([x - uy * wander[k0], y + ux * wander[k0]])
        nx, ny = -uy * side, ux * side
        centre = pos + 130.0 * np.array([nx, ny])
        heading = math.atan2(ny, nx)
        for j in range(hold):
            to_c = centre - pos
            if j >= 4:
                heading += rng.normal(0, 1.0)
                if np.hypot(*to_c) > 70:
                    heading = math.atan2(to_c[1], to_c[0]) + rng.normal(0, 0.6)
            step = rng.uniform(0.5, 1.0) * C.FIX_INTERVAL_S
            pos = pos + step * np.array([math.cos(heading), math.sin(heading)])
            xy.append((float(pos[0]), float(pos[1])))
        labels = [1 if i >= k0 else 0 for i in range(len(xy))]
        return _finish("lost_wandering", xy, rng, start_time, labels, k0, {"hold_fixes": hold})

    if scenario == "signal_loss":
        ss = _base_s(rng, n, s0, rest=False, pause_p=0.02, mu=mu)
        k0, gap = int(rng.integers(12, 25)), int(rng.integers(6, 11))
        keep = [not (k0 <= i < k0 + gap) for i in range(n)]
        tr = _finish("signal_loss", _xy_from_s(ss), rng, start_time, [0] * n, k0,
                     {"gap_fixes": gap}, keep=keep)
        tr.meta["gap_seconds"] = (gap + 1) * C.FIX_INTERVAL_S
        return tr

    if scenario == "geofence_violation":
        target = geofence.RESTRICTED[int(rng.integers(0, len(geofence.RESTRICTED)))]
        tx, ty = to_xy(target["lat"], target["lon"])
        s_start = max(0.0, nearest_s(tx, ty) - 150.0)
        xy, s = [], s_start
        for _ in range(4):
            xy.append(route_point(s)[:2])
            s += _speed(rng)
        x, y = xy[-1]
        inside_count = 0
        while inside_count < 3 and len(xy) < 160:
            d = math.hypot(tx - x, ty - y)
            step = min(_speed(rng), d)
            x, y = x + (tx - x) / d * step, y + (ty - y) / d * step
            xy.append((x, y))
            la, lo = from_xy(x, y)
            inside_count = inside_count + 1 if geofence.reference_inside(target, la, lo) else 0
        return _finish("geofence_violation", xy, rng, start_time, [0] * len(xy), 4,
                       {"target": target["name"]})
    raise ValueError(f"unknown scenario {scenario}")


SCENARIOS = ["normal", "route_deviation", "prolonged_inactivity", "lost_wandering", "geofence_violation", "signal_loss"]
