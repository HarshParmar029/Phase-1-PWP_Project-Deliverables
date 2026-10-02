"""
digital_id.py - Blockchain-based Digital Tourist ID.

* passport number is never stored raw: salted (per-record random salt + server pepper) SHA-256
* payload (canonical JSON) -> SHA-256 -> mined into a hash-chained block (proof-of-work nonce)
* block is committed only after majority approval by the simulated validator network
* QR code carries the tourist id, a payload-hash prefix and an HMAC signature (forged QR rejected)
* verification = record, payload hash, block hash + PoW, WHOLE chain, network consensus, expiry, revocation
"""
import hashlib
import hmac
import json
import os
import secrets
import threading
from datetime import timedelta

import config as C
import database as db
import ledger_network as ln
from utils import now_utc, iso, parse_ts

_lock = threading.RLock()
_network = None


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_network(reload=False):
    """Lazy singleton: validator nodes are seeded from the persisted ledger at start-up."""
    global _network
    with _lock:
        if _network is None or reload:
            ensure_genesis()
            _network = ln.LedgerNetwork()
            _network.load(db.get_all_blocks())
        return _network


def reset_network():
    global _network
    _network = None


def ensure_genesis():
    if not db.get_all_blocks():
        db.insert_block(ln.genesis_block())


def salt_passport(passport, salt):
    return sha256(C.PASSPORT_PEPPER + salt + passport.strip().upper())


def build_payload(t):
    payload = {k: t[k] for k in ("tourist_id", "name", "nationality", "passport_hash",
                                 "emergency_contact", "valid_from", "valid_until")}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return payload, sha256(canonical)


def qr_signature(tourist_id, payload_hash):
    msg = f"{tourist_id}|{payload_hash[:16]}".encode()
    return hmac.new(C.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()[:16]


def qr_text(tourist_id, payload_hash):
    return f"TID:{tourist_id}|HASH:{payload_hash[:16]}|SIG:{qr_signature(tourist_id, payload_hash)}|VERIFY:/verify/{tourist_id}"


def make_qr(data, tourist_id):
    os.makedirs(C.QR_DIR, exist_ok=True)
    path = os.path.join(C.QR_DIR, f"{tourist_id}.png")
    try:
        import qrcode
        qr = qrcode.QRCode(version=None, box_size=6, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        qr.make_image(fill_color="black", back_color="white").save(path)
    except ImportError:   # keeps the rest of the system usable if qrcode is not installed
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (260, 260), "white")
        ImageDraw.Draw(img).text((20, 120), "pip install qrcode[pil]", fill="black")
        img.save(path)
    return f"/static/qrcodes/{tourist_id}.png"


def create_digital_id(name, nationality, passport, emergency_contact, validity_days=None):
    with _lock:
        net = get_network()
        now = now_utc()
        tourist_id = "TID-" + secrets.token_hex(4).upper()
        salt = secrets.token_hex(8)
        t = {"tourist_id": tourist_id, "name": name, "nationality": nationality,
             "passport_hash": salt_passport(passport, salt), "emergency_contact": emergency_contact,
             "valid_from": iso(now),
             "valid_until": iso(now + timedelta(days=validity_days or C.ID_VALIDITY_DAYS))}
        _, payload_hash = build_payload(t)

        blocks = db.get_all_blocks()
        prev = blocks[-1]
        block = ln.mine(prev["index_no"] + 1, tourist_id, payload_hash, prev["block_hash"], iso(now))
        votes = net.propose(block)           # raises if the validators reject it
        db.insert_tourist(tourist_id, name, nationality, t["passport_hash"], salt,
                          emergency_contact, t["valid_from"], t["valid_until"])
        db.insert_block(block)
        return {**t, "payload_hash": payload_hash, "block_hash": block["block_hash"],
                "previous_hash": block["previous_hash"], "index_no": block["index_no"],
                "nonce": block["nonce"], "validator_votes": f"{votes}/{len(net.nodes)}",
                "passport_hash_short": t["passport_hash"][:12] + "...",
                "qr_url": make_qr(qr_text(tourist_id, payload_hash), tourist_id)}


def verify_chain(blocks=None):
    """Walk the whole persisted chain. Returns (ok, first_bad_index, reason)."""
    blocks = blocks if blocks is not None else db.get_all_blocks()
    if not blocks:
        return False, None, "empty ledger"
    prev = None
    for i, b in enumerate(blocks):
        if b["index_no"] != i:
            return False, i, "missing or reordered block"
        ok, why = ln.validate_block(b, prev)
        if not ok:
            return False, i, why
        prev = b
    return True, None, "ok"


def verify_digital_id(tourist_id):
    checks = []

    def add(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        return ok

    t = db.get_tourist(tourist_id)
    if not add("Record exists", t is not None, "" if t else "unknown tourist id"):
        return {"valid": False, "reason": "Record not found", "checks": checks}

    blk = db.get_block_for(tourist_id)
    if not add("Ledger entry exists", blk is not None):
        return {"valid": False, "reason": "No ledger entry", "checks": checks}

    _, expected = build_payload(t)
    add("Payload hash matches ledger", expected == blk["payload_hash"],
        "record was modified after issue" if expected != blk["payload_hash"] else "")
    chain_ok, bad, why = verify_chain()
    add("Hash chain intact (whole ledger)", chain_ok, "" if chain_ok else f"broken at block {bad}: {why}")
    cons = get_network().consensus(blk["index_no"], blk["block_hash"])
    add("Validator-network consensus", cons["ok"], f"{cons['agree']}/{cons['total']} nodes agree")
    expired = now_utc() > parse_ts(t["valid_until"])
    add("Not expired", not expired, f"valid until {t['valid_until'][:19]}")
    add("Not revoked", not t.get("revoked"))

    valid = all(c["ok"] for c in checks)
    failed = [c["name"] for c in checks if not c["ok"]]
    return {"valid": valid, "reason": "" if valid else "Failed: " + ", ".join(failed),
            "checks": checks, "tourist_id": tourist_id, "name": t["name"],
            "nationality": t["nationality"], "valid_until": t["valid_until"],
            "payload_hash": blk["payload_hash"], "block_hash": blk["block_hash"],
            "block_index": blk["index_no"]}


def verify_qr(text):
    """Verify a scanned QR string: HMAC signature first, then full ledger verification."""
    try:
        parts = dict(p.split(":", 1) for p in text.split("|"))
        tid, hprefix, sig = parts["TID"], parts["HASH"], parts["SIG"]
    except Exception:
        return {"valid": False, "reason": "Malformed QR payload", "checks": []}
    blk = db.get_block_for(tid)
    if blk is None:
        return {"valid": False, "reason": "Unknown tourist id in QR", "checks": []}
    good_sig = hmac.compare_digest(sig, qr_signature(tid, blk["payload_hash"]))
    if not good_sig or blk["payload_hash"][:16] != hprefix:
        return {"valid": False, "reason": "QR signature invalid (forged or altered QR)", "checks": []}
    return verify_digital_id(tid)


def verify_passport(tourist_id, passport):
    """Authority-side check: does this physical passport match the stored salted hash?"""
    t = db.get_tourist(tourist_id)
    return bool(t) and hmac.compare_digest(t["passport_hash"], salt_passport(passport, t["salt"]))


def audit_ledger():
    """Full audit: chain + every tourist record against its block. Returns list of issues."""
    issues = []
    ok, bad, why = verify_chain()
    if not ok:
        issues.append(f"chain broken at block {bad}: {why}")
    for t in db.get_all_tourists():
        blk = db.get_block_for(t["tourist_id"])
        if blk is None or build_payload(t)[1] != blk["payload_hash"]:
            issues.append(f"{t['tourist_id']}: record does not match ledger")
    return issues
