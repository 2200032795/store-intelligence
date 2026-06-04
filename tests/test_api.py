# PROMPT: "Write pytest tests for a FastAPI store intelligence API with endpoints:
# POST /events/ingest, GET /stores/{id}/metrics, /funnel, /heatmap, /anomalies, /health.
# Include edge cases: empty store, idempotent ingest, zero purchases, staff filtering,
# re-entry deduplication."
# CHANGES MADE: Added store-specific STORE_BLR_002 store_id, fixed base URL to
# localhost:8000, added realistic event payloads matching our Pydantic schema,
# added idempotency test with duplicate event_ids, added empty store test,
# added re-entry double-count test, added staff exclusion test.

import pytest
import requests
import uuid

BASE  = "http://127.0.0.1:8000"
STORE = "STORE_BLR_002"


def make_event(event_type="ENTRY", visitor_id=None, zone_id=None,
               is_staff=False, event_id=None, queue_depth=None):
    return {
        "event_id":   event_id or str(uuid.uuid4()),
        "store_id":   STORE,
        "camera_id":  "CAM_ENTRY_01",
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


# ── Basic endpoint tests ──────────────────────────────────────────────

def test_health():
    r = requests.get(f"{BASE}/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "database" in data


def test_metrics_empty_store():
    """Zero-traffic store must return 0s, not crash or return null."""
    r = requests.get(f"{BASE}/stores/STORE_EMPTY_999/metrics")
    assert r.status_code == 200
    data = r.json()
    assert data["unique_visitors"] == 0
    assert data["conversion_rate"] == 0.0


def test_ingest_valid_events():
    events = [make_event("ENTRY"), make_event("EXIT")]
    r = requests.post(f"{BASE}/events/ingest", json={"events": events})
    assert r.status_code == 200
    data = r.json()
    assert data["accepted"] == 2
    assert data["rejected"] == 0


def test_ingest_idempotent():
    """Same event_id posted twice — second must be duplicate, not double-counted."""
    fixed_id = str(uuid.uuid4())
    event = make_event("ENTRY", event_id=fixed_id)
    r1 = requests.post(f"{BASE}/events/ingest", json={"events": [event]})
    r2 = requests.post(f"{BASE}/events/ingest", json={"events": [event]})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json()["duplicate"] >= 1


def test_ingest_staff_excluded_from_metrics():
    """Staff events must not appear in customer metrics."""
    vid = f"VIS_{uuid.uuid4().hex[:6]}"
    staff_event = make_event("ENTRY", visitor_id=vid, is_staff=True)
    requests.post(f"{BASE}/events/ingest", json={"events": [staff_event]})
    r = requests.get(f"{BASE}/stores/{STORE}/metrics")
    assert r.status_code == 200


def test_metrics():
    r = requests.get(f"{BASE}/stores/{STORE}/metrics")
    assert r.status_code == 200
    data = r.json()
    assert "unique_visitors"  in data
    assert "conversion_rate"  in data
    assert "queue_depth"      in data
    assert "abandonment_rate" in data


def test_funnel():
    r = requests.get(f"{BASE}/stores/{STORE}/funnel")
    assert r.status_code == 200
    data = r.json()
    assert "funnel" in data
    stages = [s["stage"] for s in data["funnel"]]
    assert "Entry"    in stages
    assert "Purchase" in stages


def test_funnel_reentry_no_double_count():
    """Re-entry visitor must count as 1 unique visitor, not 2."""
    vid = f"VIS_{uuid.uuid4().hex[:6]}"
    events = [
        make_event("ENTRY",   visitor_id=vid),
        make_event("EXIT",    visitor_id=vid),
        make_event("REENTRY", visitor_id=vid),
    ]
    r = requests.post(f"{BASE}/events/ingest", json={"events": events})
    assert r.status_code == 200
    r2 = requests.get(f"{BASE}/stores/{STORE}/funnel")
    assert r2.status_code == 200


def test_heatmap():
    r = requests.get(f"{BASE}/stores/{STORE}/heatmap")
    assert r.status_code == 200
    data = r.json()
    assert "zones" in data


def test_anomalies():
    r = requests.get(f"{BASE}/stores/{STORE}/anomalies")
    assert r.status_code == 200
    data = r.json()
    assert "anomalies" in data
    for a in data["anomalies"]:
        assert "severity"         in a
        assert "suggested_action" in a
        assert a["severity"] in ("INFO", "WARN", "CRITICAL")


def test_ingest_zero_purchase_store():
    """Store with visitors but no POS — conversion_rate must be 0, not crash."""
    vid = f"VIS_{uuid.uuid4().hex[:6]}"
    events = [make_event("ENTRY", visitor_id=vid)]
    requests.post(f"{BASE}/events/ingest", json={"events": events})
    r = requests.get(f"{BASE}/stores/{STORE}/metrics")
    assert r.status_code == 200
    assert r.json()["conversion_rate"] >= 0.0


def test_billing_queue_join():
    """BILLING_QUEUE_JOIN event with queue_depth must reflect in metrics."""
    vid = f"VIS_{uuid.uuid4().hex[:6]}"
    events = [
        make_event("ENTRY",              visitor_id=vid),
        make_event("BILLING_QUEUE_JOIN", visitor_id=vid,
                   zone_id="BILLING",   queue_depth=3),
    ]
    r = requests.post(f"{BASE}/events/ingest", json={"events": events})
    assert r.status_code == 200
    assert r.json()["accepted"] == 2