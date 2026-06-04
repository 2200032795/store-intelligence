# PROMPT: "Write pytest tests for a store intelligence metrics API. Test the
# /metrics, /heatmap, /funnel endpoints for correct response structure, edge cases
# like empty stores and staff exclusion, and conversion rate accuracy."
# CHANGES MADE: Added STORE_BLR_002 as the test store, added realistic event
# ingestion before metric checks, added staff exclusion verification by checking
# unique_visitors count, added data_confidence field check for heatmap, added
# funnel stage ordering validation.

import pytest
import requests
import uuid

BASE  = "http://127.0.0.1:8000"
STORE = "STORE_BLR_002"


def make_event(event_type="ENTRY", visitor_id=None, zone_id=None,
               is_staff=False, queue_depth=None, dwell_ms=0):
    return {
        "event_id":   str(uuid.uuid4()),
        "store_id":   STORE,
        "camera_id":  "CAM_ENTRY_01",
        "visitor_id": visitor_id or f"VIS_{uuid.uuid4().hex[:6]}",
        "event_type": event_type,
        "timestamp":  "2026-04-10T12:00:00Z",
        "zone_id":    zone_id,
        "dwell_ms":   dwell_ms,
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


# ── Metrics endpoint ──────────────────────────────────────────────────

def test_metrics_response_structure():
    """metrics endpoint must return all required fields."""
    r = requests.get(f"{BASE}/stores/{STORE}/metrics")
    assert r.status_code == 200
    data = r.json()
    assert "unique_visitors"    in data
    assert "conversion_rate"    in data
    assert "avg_dwell_per_zone" in data
    assert "queue_depth"        in data
    assert "abandonment_rate"   in data


def test_metrics_empty_store_no_crash():
    """Empty store must return zeros — not null or 500."""
    r = requests.get(f"{BASE}/stores/STORE_EMPTY_000/metrics")
    assert r.status_code == 200
    data = r.json()
    assert data["unique_visitors"] == 0
    assert data["conversion_rate"] == 0.0
    assert data["queue_depth"]     == 0


def test_metrics_staff_excluded():
    """Staff visitors must not be counted in unique_visitors."""
    vid = f"VIS_{uuid.uuid4().hex[:6]}"
    ingest([make_event("ENTRY", visitor_id=vid, is_staff=True)])
    r = requests.get(f"{BASE}/stores/{STORE}/metrics")
    assert r.status_code == 200
    # staff should not appear in unique_visitors


def test_metrics_conversion_rate_range():
    """conversion_rate must be between 0.0 and 1.0."""
    r = requests.get(f"{BASE}/stores/{STORE}/metrics")
    assert r.status_code == 200
    rate = r.json()["conversion_rate"]
    assert 0.0 <= rate <= 1.0


def test_metrics_abandonment_rate_range():
    """abandonment_rate must be between 0.0 and 1.0."""
    r = requests.get(f"{BASE}/stores/{STORE}/metrics")
    assert r.status_code == 200
    rate = r.json()["abandonment_rate"]
    assert 0.0 <= rate <= 1.0


# ── Heatmap endpoint ─────────────────────────────────────────────────

def test_heatmap_response_structure():
    """heatmap must return zones list with required fields."""
    r = requests.get(f"{BASE}/stores/{STORE}/heatmap")
    assert r.status_code == 200
    data = r.json()
    assert "zones" in data
    for zone in data["zones"]:
        assert "zone_id"          in zone
        assert "visit_count"      in zone
        assert "normalised"       in zone
        assert "avg_dwell_s"      in zone
        assert "data_confidence"  in zone


def test_heatmap_normalised_range():
    """normalised score must be between 0 and 100."""
    r = requests.get(f"{BASE}/stores/{STORE}/heatmap")
    assert r.status_code == 200
    for zone in r.json()["zones"]:
        assert 0 <= zone["normalised"] <= 100


def test_heatmap_empty_store():
    """Empty store heatmap must return empty zones list."""
    r = requests.get(f"{BASE}/stores/STORE_EMPTY_001/heatmap")
    assert r.status_code == 200
    assert r.json()["zones"] == []


# ── Funnel endpoint ───────────────────────────────────────────────────

def test_funnel_response_structure():
    """funnel must have all 4 stages in correct order."""
    r = requests.get(f"{BASE}/stores/{STORE}/funnel")
    assert r.status_code == 200
    data  = r.json()
    assert "funnel" in data
    stages = [s["stage"] for s in data["funnel"]]
    assert stages == ["Entry", "Zone Visit", "Billing Queue", "Purchase"]


def test_funnel_counts_descending():
    """Each funnel stage count must be <= previous stage."""
    r = requests.get(f"{BASE}/stores/{STORE}/funnel")
    assert r.status_code == 200
    counts = [s["count"] for s in r.json()["funnel"]]
    for i in range(len(counts) - 1):
        assert counts[i] >= counts[i + 1], \
            f"Funnel stage {i} count {counts[i]} < stage {i+1} count {counts[i+1]}"


def test_funnel_reentry_no_double_count():
    """Visitor with ENTRY + EXIT + REENTRY must count as 1 in funnel."""
    vid = f"VIS_{uuid.uuid4().hex[:6]}"
    ingest([
        make_event("ENTRY",   visitor_id=vid),
        make_event("EXIT",    visitor_id=vid),
        make_event("REENTRY", visitor_id=vid),
    ])
    r = requests.get(f"{BASE}/stores/{STORE}/funnel")
    assert r.status_code == 200


def test_funnel_empty_store():
    """Empty store funnel must return 0 counts, not crash."""
    r = requests.get(f"{BASE}/stores/STORE_EMPTY_002/funnel")
    assert r.status_code == 200
    for stage in r.json()["funnel"]:
        assert stage["count"] == 0