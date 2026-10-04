"""utils.py - time helpers and a local metric projection (equirectangular)."""
import math
from datetime import datetime, timezone
import config as C


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt=None):
    return (dt or now_utc()).isoformat()


def parse_ts(s):
    dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def epoch(s):
    return parse_ts(s).timestamp()


_LAT0, _LON0 = C.ORIGIN
_KY = math.radians(1.0) * C.EARTH_RADIUS_M
_KX = _KY * math.cos(math.radians(_LAT0))


def to_xy(lat, lon):
    """(lat, lon) -> local metres (east, north) relative to C.ORIGIN."""
    return ((lon - _LON0) * _KX, (lat - _LAT0) * _KY)


def from_xy(x, y):
    return (_LAT0 + y / _KY, _LON0 + x / _KX)
