"""
config.py - Central configuration for the Tourist Safety Monitoring & Incident Response System.
All zones, the planned route and every detection threshold live here so that the
evaluation (evaluate.py) and the live app (app.py) always use identical settings.

Coordinates are approximate points around Somnath, Gujarat and are for SIMULATION only.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("TSAFETY_DB", os.path.join(BASE_DIR, "data", "safety.db"))
MODEL_PATH = os.environ.get("TSAFETY_MODEL", os.path.join(BASE_DIR, "models", "isolation_forest.joblib"))
QR_DIR = os.path.join(BASE_DIR, "static", "qrcodes")

# ---- secrets (override with environment variables in real deployments) -------------
SECRET_KEY = os.environ.get("TSAFETY_SECRET", "pwp-phase1-dev-secret-change-me")
PASSPORT_PEPPER = os.environ.get("TSAFETY_PEPPER", "MU_PWP_2026_PEPPER")

# ---- digital ID / ledger ------------------------------------------------------------
ID_VALIDITY_DAYS = 7
POW_DIFFICULTY = 3            # block hash must start with this many hex zeros
NUM_LEDGER_NODES = 3          # simulated permissioned validator nodes

# ---- geometry -----------------------------------------------------------------------
EARTH_RADIUS_M = 6371008.8
ORIGIN = (20.8905, 70.4075)   # map centre / local projection origin

SAFE_ZONE = {"name": "Somnath Safe Zone", "shape": "circle",
             "lat": 20.8905, "lon": 70.4075, "radius_m": 1600}

CAUTION_ZONES = [
    {"name": "Crowded Market Lane", "shape": "circle",
     "lat": 20.8935, "lon": 70.4030, "radius_m": 150},
]

RESTRICTED_ZONES = [
    {"name": "Restricted Coastal Cliff Area", "shape": "circle",
     "lat": 20.9000, "lon": 70.4000, "radius_m": 150},
    {"name": "Restricted Construction Site", "shape": "polygon",
     "points": [(20.8790, 70.4137), (20.8790, 70.4163), (20.8810, 70.4163), (20.8810, 70.4137)]},
]

# Five-waypoint itinerary (lat, lon)
PLANNED_ROUTE = [
    (20.8880, 70.4010),
    (20.8895, 70.4050),
    (20.8930, 70.4080),
    (20.8975, 70.4105),
    (20.8950, 70.4160),
]

# Designated rest points (a stationary tourist here is NOT an anomaly)
REST_POINTS = [
    {"name": "Tea Stall & Rest Shelter", "lat": 20.8912, "lon": 70.4065, "radius_m": 60},
    {"name": "Viewpoint Bench", "lat": 20.8975, "lon": 70.4105, "radius_m": 60},
]

# ---- geo-fencing --------------------------------------------------------------------
GEOFENCE_HYSTERESIS_M = 15    # avoids flapping caused by GPS noise at a boundary
APPROACH_WARN_M = 100         # advisory when within this distance of a restricted zone

# ---- anomaly detection --------------------------------------------------------------
FIX_INTERVAL_S = 30
WINDOW_SIZE = 10              # 10 fixes = 5 minutes
ROUTE_DEV_M = 250             # rule: last ROUTE_DEV_CONSEC fixes farther than this
ROUTE_DEV_CONSEC = 3
INACTIVITY_NET_M = 20         # rule: net displacement over a full window below this
GAP_LOSS_S = 120              # rule: no update for this long = SIGNAL_LOSS
IF_TREES = 100
IF_CONTAMINATION = 0.01
HYBRID_DEV_M = 120            # IF outlier must be corroborated by this route deviation
GPS_NOISE_SIGMA_M = 6.0
WALK_SPEED_MS = 1.2

# ---- incident response --------------------------------------------------------------
SEVERITY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
NOTIFY_MIN_SEVERITY = "HIGH"  # SMS to emergency contact from this severity upward
SIMULATED_SMS_DELAY_MEDIAN_S = 1.5   # parameter of the SIMULATED channel, not a measurement
