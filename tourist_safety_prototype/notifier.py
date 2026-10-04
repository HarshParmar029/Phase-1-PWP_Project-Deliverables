"""
notifier.py - Incident notifications to emergency contacts and the authority control room.

Channels
  SMS -> emergency contact    SIMULATED by default (status SIMULATED_SENT, delay drawn from a
                              log-normal model - a PARAMETER, not a measurement). If TWILIO_SID,
                              TWILIO_TOKEN and TWILIO_FROM are set and the `twilio` package is
                              installed, a real SMS is attempted (not exercised in the prototype tests).
  DASHBOARD -> authority      written in the same database transaction flow (near-zero delay).
Every message carries the tourist's coordinates and a map link.
"""
import os
import random
import config as C
import database as db

_rng = random.Random(2026)


def _body(inc, tourist):
    if inc.get("lat") is not None and inc.get("lon") is not None:
        loc = f"Location: {inc['lat']:.5f},{inc['lon']:.5f} https://maps.google.com/?q={inc['lat']:.6f},{inc['lon']:.6f}"
    else:
        loc = "Location: not available yet (no GPS fix received)"
    return f"[{inc['severity']}] {inc['incident_type']} for {tourist['name']} ({tourist['tourist_id']}). {inc['message']}. {loc}"


def _send_real_sms(to, body):
    try:
        from twilio.rest import Client
        c = Client(os.environ["TWILIO_SID"], os.environ["TWILIO_TOKEN"])
        c.messages.create(to=to, from_=os.environ["TWILIO_FROM"], body=body)
        return True
    except Exception:
        return False


def dispatch(inc, tourist, processing_ms):
    """Create notification rows. Returns list of notification dicts."""
    out = []
    body = _body(inc, tourist)
    db.insert_notification(inc["id"], tourist["tourist_id"], "DASHBOARD", "Authority control room",
                           body, "DELIVERED", 0.0, processing_ms)
    out.append({"channel": "DASHBOARD", "total_ms": processing_ms})
    if C.SEVERITY_RANK[inc["severity"]] >= C.SEVERITY_RANK[C.NOTIFY_MIN_SEVERITY]:
        if all(k in os.environ for k in ("TWILIO_SID", "TWILIO_TOKEN", "TWILIO_FROM")):
            status = "SENT" if _send_real_sms(tourist["emergency_contact"], body) else "FAILED"
            delay = 0.0
        else:
            delay = _rng.lognormvariate(0, 0.5) * C.SIMULATED_SMS_DELAY_MEDIAN_S * 1000
            status = "SIMULATED_SENT"
        db.insert_notification(inc["id"], tourist["tourist_id"], "SMS", tourist["emergency_contact"],
                               body, status, delay, processing_ms + delay)
        out.append({"channel": "SMS", "status": status, "sim_delay_ms": delay, "total_ms": processing_ms + delay})
    return out
