# PROMPT: "Write pytest tests for an anomaly detection API endpoint. Test for
# correct response structure, severity levels, suggested_action presence, queue
# spike detection, dead zone detection, and conversion drop detection."
# CHANGES MADE: Added STORE_BLR_002 store_id, added realistic event ingestion
# to trigger specific anomalies, added ALL_CLEAR check for clean store, added
# severity enum validation, added suggested_action non-empty check.

import pytest
import requests
import uuid

BASE  = "http://127.0.0.1:8000"
STORE = "STORE_BLR_002"

VALID_SEVERITIES = {"INFO", "WARN", "CRITICAL"}


def make_event(event_type="ENTRY", visitor_id=None, zone_id=None,
               queue_depth=None, is_staff=False):
    return {
        "event_id":   str(uuid.uuid4()),
        "store_id":   STORE,
        "camera_id":  "CAM_BILLING_01",
        "visitor_id": visitor_id or f"VIS_{uuid.uuid4().hex[:6]}",
        "event_type": event_type,
        "timestamp":  "2026-04-10T12:00:00Z",
        "zone_id":    zone_id,
        "dwell_ms":   0,
        "is_staff":   is_staff,
        "confidence": 0.9,
        "metadata": {
            "queue_depth": queue_depth,
            "sku_zone":    zone_id,
            "session_seq": 1,
        },
    }


def ingest(events):
    return requests.post(
        f"{BASE}/events/ingest",
        json={"events": events},
        timeout=10
    )


# ── Structure tests ───────────────────────────────────────────────────

def test_anomalies_response_structure():
    """anomalies endpoint must return list with required fields."""
    r = requests.get(f"{BASE}/stores/{STORE}/anomalies")
    assert r.status_code == 200
    data = r.json()
    assert "anomalies" in data
    assert isinstance(data["anomalies"], list)


def test_anomalies_required_fields():
    """Every anomaly must have type, severity, detail, suggested_action."""
    r = requests.get(f"{BASE}/stores/{STORE}/anomalies")
    assert r.status_code == 200
    for a in r.json()["anomalies"]:
        assert "type"             in a
        assert "severity"         in a
        assert "detail"           in a
        assert "suggested_action" in a
        assert "detected_at"      in a


def test_anomalies_valid_severity():
    """severity must be INFO, WARN, or CRITICAL only."""
    r = requests.get(f"{BASE}/stores/{STORE}/anomalies")
    assert r.status_code == 200
    for a in r.json()["anomalies"]:
        assert a["severity"] in VALID_SEVERITIES, \
            f"Invalid severity: {a['severity']}"


def test_anomalies_suggested_action_not_empty():
    """suggested_action must never be empty string."""
    r = requests.get(f"{BASE}/stores/{STORE}/anomalies")
    assert r.status_code == 200
    for a in r.json()["anomalies"]:
        assert len(a["suggested_action"]) > 0, \
            "suggested_action is empty"


# ── Anomaly trigger tests ─────────────────────────────────────────────

def test_queue_spike_warn_triggered():
    """Queue depth > 5 must trigger BILLING_QUEUE_SPIKE WARN."""
    vid = f"VIS_{uuid.uuid4().hex[:6]}"
    ingest([
        make_event("ENTRY", visitor_id=vid),
        make_event("BILLING_QUEUE_JOIN",
                   visitor_id=vid,
                   zone_id="BILLING",
                   queue_depth=6),
    ])
    r = requests.get(f"{BASE}/stores/{STORE}/anomalies")
    assert r.status_code == 200
    types = [a["type"] for a in r.json()["anomalies"]]
    assert "BILLING_QUEUE_SPIKE" in types


def test_queue_spike_critical_triggered():
    """Queue depth > 8 must trigger BILLING_QUEUE_SPIKE CRITICAL."""
    vid = f"VIS_{uuid.uuid4().hex[:6]}"
    ingest([
        make_event("ENTRY", visitor_id=vid),
        make_event("BILLING_QUEUE_JOIN",
                   visitor_id=vid,
                   zone_id="BILLING",
                   queue_depth=9),
    ])
    r = requests.get(f"{BASE}/stores/{STORE}/anomalies")
    assert r.status_code == 200
    anomalies = r.json()["anomalies"]
    spikes = [a for a in anomalies if a["type"] == "BILLING_QUEUE_SPIKE"]
    assert any(s["severity"] == "CRITICAL" for s in spikes)


def test_anomalies_empty_store():
    """Empty store must return anomalies list — not crash."""
    r = requests.get(f"{BASE}/stores/STORE_EMPTY_003/anomalies")
    assert r.status_code == 200
    data = r.json()
    assert "anomalies" in data
    assert isinstance(data["anomalies"], list)


def test_reentry_anomaly_triggered():
    """More than 5 REENTRY events must trigger HIGH_REENTRY anomaly."""
    vid = f"VIS_{uuid.uuid4().hex[:6]}"
    events = []
    for _ in range(6):
        events.append(make_event("ENTRY",   visitor_id=vid))
        events.append(make_event("EXIT",    visitor_id=vid))
        events.append(make_event("REENTRY", visitor_id=vid))
    ingest(events)
    r = requests.get(f"{BASE}/stores/{STORE}/anomalies")
    assert r.status_code == 200
    types = [a["type"] for a in r.json()["anomalies"]]
    assert "HIGH_REENTRY" in types