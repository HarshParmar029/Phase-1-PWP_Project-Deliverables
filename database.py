"""database.py - SQLite schema and helpers (WAL mode, one short connection per call)."""
import os
import sqlite3
import config as C
from utils import iso


def get_conn():
    os.makedirs(os.path.dirname(C.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(C.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _q(sql, args=()):
    conn = get_conn()
    try:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def _x(sql, args=()):
    conn = get_conn()
    try:
        cur = conn.execute(sql, args)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def init_db():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS tourists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tourist_id TEXT UNIQUE NOT NULL, name TEXT NOT NULL, nationality TEXT,
        passport_hash TEXT, salt TEXT, emergency_contact TEXT,
        valid_from TEXT, valid_until TEXT, created_at TEXT, revoked INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        index_no INTEGER NOT NULL UNIQUE, tourist_id TEXT NOT NULL,
        payload_hash TEXT NOT NULL, previous_hash TEXT NOT NULL, block_hash TEXT NOT NULL,
        timestamp TEXT NOT NULL, nonce INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tourist_id TEXT NOT NULL, run_id INTEGER DEFAULT 0,
        lat REAL NOT NULL, lon REAL NOT NULL, timestamp TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_loc ON locations(tourist_id, run_id, id);
    CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tourist_id TEXT NOT NULL, run_id INTEGER DEFAULT 0,
        incident_type TEXT NOT NULL, severity TEXT NOT NULL,
        lat REAL, lon REAL, latency_ms REAL, message TEXT,
        status TEXT DEFAULT 'OPEN', created_at TEXT, ack_at TEXT, resolved_at TEXT);
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id INTEGER, tourist_id TEXT, channel TEXT, recipient TEXT, body TEXT,
        status TEXT, sim_delay_ms REAL, total_ms REAL, created_at TEXT);
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------- tourists / ledger
def insert_tourist(tourist_id, name, nationality, passport_hash, salt, contact, valid_from, valid_until):
    _x("INSERT INTO tourists (tourist_id,name,nationality,passport_hash,salt,emergency_contact,"
       "valid_from,valid_until,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
       (tourist_id, name, nationality, passport_hash, salt, contact, valid_from, valid_until, iso()))


def insert_block(b):
    _x("INSERT INTO ledger (index_no,tourist_id,payload_hash,previous_hash,block_hash,timestamp,nonce)"
       " VALUES (?,?,?,?,?,?,?)",
       (b["index_no"], b["tourist_id"], b["payload_hash"], b["previous_hash"],
        b["block_hash"], b["timestamp"], b["nonce"]))


def get_all_blocks():
    return _q("SELECT index_no,tourist_id,payload_hash,previous_hash,block_hash,timestamp,nonce "
              "FROM ledger ORDER BY index_no")


def get_block_for(tourist_id):
    r = _q("SELECT index_no,tourist_id,payload_hash,previous_hash,block_hash,timestamp,nonce "
           "FROM ledger WHERE tourist_id=? ORDER BY index_no LIMIT 1", (tourist_id,))
    return r[0] if r else None


def get_tourist(tourist_id):
    r = _q("SELECT * FROM tourists WHERE tourist_id=?", (tourist_id,))
    return r[0] if r else None


def get_all_tourists():
    return _q("SELECT * FROM tourists ORDER BY id DESC")


def update_tourist_field(tourist_id, field, value):
    assert field in {"name", "nationality", "passport_hash", "emergency_contact",
                     "valid_from", "valid_until", "revoked"}
    _x(f"UPDATE tourists SET {field}=? WHERE tourist_id=?", (value, tourist_id))


# ---------------------------------------------------------------- locations
def insert_location(tourist_id, run_id, lat, lon, ts):
    _x("INSERT INTO locations (tourist_id,run_id,lat,lon,timestamp) VALUES (?,?,?,?,?)",
       (tourist_id, run_id, lat, lon, ts))


def get_current_run(tourist_id):
    r = _q("SELECT MAX(run_id) AS m FROM locations WHERE tourist_id=?", (tourist_id,))
    return int(r[0]["m"]) if r and r[0]["m"] is not None else 0


def get_last_location(tourist_id):
    r = _q("SELECT lat,lon,timestamp FROM locations WHERE tourist_id=? ORDER BY id DESC LIMIT 1", (tourist_id,))
    return r[0] if r else None


def get_track(tourist_id, run_id, limit=200):
    rows = _q("SELECT lat,lon,timestamp FROM locations WHERE tourist_id=? AND run_id=? "
              "ORDER BY id DESC LIMIT ?", (tourist_id, run_id, limit))
    return list(reversed(rows))


# ---------------------------------------------------------------- incidents
def insert_incident(tourist_id, run_id, itype, severity, lat, lon, message):
    return _x("INSERT INTO incidents (tourist_id,run_id,incident_type,severity,lat,lon,message,status,created_at)"
              " VALUES (?,?,?,?,?,?,?,'OPEN',?)",
              (tourist_id, run_id, itype, severity, lat, lon, message, iso()))


def set_incident_latency(incident_id, latency_ms):
    _x("UPDATE incidents SET latency_ms=? WHERE id=?", (latency_ms, incident_id))


def get_incidents(limit=30):
    return _q("SELECT * FROM incidents ORDER BY id DESC LIMIT ?", (limit,))


def get_incident(incident_id):
    r = _q("SELECT * FROM incidents WHERE id=?", (incident_id,))
    return r[0] if r else None


def get_open_incidents(tourist_id, run_id):
    return _q("SELECT * FROM incidents WHERE tourist_id=? AND run_id=? AND status!='RESOLVED'",
              (tourist_id, run_id))


def set_incident_status(incident_id, status):
    col = {"ACKNOWLEDGED": "ack_at", "RESOLVED": "resolved_at"}[status]
    _x(f"UPDATE incidents SET status=?, {col}=? WHERE id=?", (status, iso(), incident_id))


def get_incident_points(limit=1000):
    return _q("SELECT lat,lon,severity FROM incidents WHERE lat IS NOT NULL ORDER BY id DESC LIMIT ?", (limit,))


# ---------------------------------------------------------------- notifications
def insert_notification(incident_id, tourist_id, channel, recipient, body, status, sim_delay_ms, total_ms):
    return _x("INSERT INTO notifications (incident_id,tourist_id,channel,recipient,body,status,"
              "sim_delay_ms,total_ms,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
              (incident_id, tourist_id, channel, recipient, body, status, sim_delay_ms, total_ms, iso()))


def get_notifications(limit=15):
    return _q("SELECT * FROM notifications ORDER BY id DESC LIMIT ?", (limit,))


# ---------------------------------------------------------------- stats
def get_stats():
    conn = get_conn()
    try:
        n_t = conn.execute("SELECT COUNT(*) FROM tourists").fetchone()[0]
        n_i = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
        n_open = conn.execute("SELECT COUNT(*) FROM incidents WHERE status='OPEN'").fetchone()[0]
        n_hi = conn.execute("SELECT COUNT(*) FROM incidents WHERE severity IN ('HIGH','CRITICAL')").fetchone()[0]
        n_sos = conn.execute("SELECT COUNT(*) FROM incidents WHERE incident_type='SOS'").fetchone()[0]
        lats = sorted(r[0] for r in conn.execute(
            "SELECT latency_ms FROM incidents WHERE latency_ms IS NOT NULL").fetchall())
    finally:
        conn.close()
    avg = sum(lats) / len(lats) if lats else 0.0
    p95 = lats[min(len(lats) - 1, int(0.95 * len(lats)))] if lats else 0.0
    return {"tourists": n_t, "incidents": n_i, "open_incidents": n_open, "high_critical": n_hi,
            "sos": n_sos, "avg_latency_ms": round(avg, 2), "p95_latency_ms": round(p95, 2)}
