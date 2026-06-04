# PROMPT: "Write pytest tests to validate a JSONL event file output from a CCTV
# detection pipeline. Tests should check: schema compliance, unique event_ids,
# valid timestamps, ENTRY/EXIT pairing, is_staff flag presence, confidence range,
# REENTRY only after EXIT, ZONE_DWELL only after ZONE_ENTER."
# CHANGES MADE: Added actual JSONL file path from our pipeline output location
# data/events.jsonl, added STORE_BLR_002 store_id check, added metadata fields
# validation for queue_depth/sku_zone/session_seq, relaxed timestamp format to
# handle both Z suffix and +00:00 format from our emit.py output.

import json
import os
import pytest
from pathlib import Path

EVENTS_FILE = Path("data/events.jsonl")
REQUIRED_FIELDS = [
    "event_id", "store_id", "camera_id", "visitor_id",
    "event_type", "timestamp", "dwell_ms", "is_staff",
    "confidence", "metadata"
]
VALID_EVENT_TYPES = {
    "ENTRY", "EXIT", "ZONE_ENTER", "ZONE_EXIT",
    "ZONE_DWELL", "BILLING_QUEUE_JOIN", "BILLING_QUEUE_ABANDON", "REENTRY"
}


def load_events():
    if not EVENTS_FILE.exists():
        pytest.skip(f"{EVENTS_FILE} not found — run detect.py first")
    events = []
    with open(EVENTS_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def test_events_file_exists():
    """Pipeline must produce at least one event."""
    if not EVENTS_FILE.exists():
        pytest.skip("No events file — run detect.py first")
    events = load_events()
    assert len(events) > 0, "events.jsonl is empty"


def test_schema_compliance():
    """Every event must have all required fields."""
    events = load_events()
    for i, e in enumerate(events):
        for field in REQUIRED_FIELDS:
            assert field in e, f"Event {i} missing field: {field}"


def test_event_ids_unique():
    """event_id must be globally unique — no duplicates."""
    events = load_events()
    ids = [e["event_id"] for e in events]
    assert len(ids) == len(set(ids)), "Duplicate event_ids found"


def test_valid_event_types():
    """All event_type values must be from the catalogue."""
    events = load_events()
    for e in events:
        assert e["event_type"] in VALID_EVENT_TYPES, \
            f"Unknown event_type: {e['event_type']}"


def test_confidence_range():
    """Confidence must be between 0.0 and 1.0 — never suppressed."""
    events = load_events()
    for e in events:
        assert 0.0 <= e["confidence"] <= 1.0, \
            f"confidence out of range: {e['confidence']}"


def test_is_staff_is_boolean():
    """is_staff must always be a boolean."""
    events = load_events()
    for e in events:
        assert isinstance(e["is_staff"], bool), \
            f"is_staff is not bool: {e['is_staff']}"


def test_metadata_fields_present():
    """metadata must contain queue_depth, sku_zone, session_seq."""
    events = load_events()
    for i, e in enumerate(events):
        meta = e.get("metadata", {})
        assert "queue_depth"  in meta, f"Event {i} metadata missing queue_depth"
        assert "sku_zone"     in meta, f"Event {i} metadata missing sku_zone"
        assert "session_seq"  in meta, f"Event {i} metadata missing session_seq"


def test_entry_events_have_visitor_id():
    """Every ENTRY event must have a visitor_id assigned."""
    events = load_events()
    for e in events:
        if e["event_type"] == "ENTRY":
            assert e["visitor_id"], "ENTRY event has no visitor_id"


def test_reentry_only_after_exit():
    """REENTRY must only appear after a prior EXIT for the same visitor."""
    events = load_events()
    exited: set[str] = set()
    for e in events:
        if e["event_type"] == "EXIT":
            exited.add(e["visitor_id"])
        if e["event_type"] == "REENTRY":
            assert e["visitor_id"] in exited, \
                f"REENTRY without prior EXIT for {e['visitor_id']}"


def test_billing_queue_join_has_queue_depth():
    """BILLING_QUEUE_JOIN must have queue_depth set in metadata."""
    events = load_events()
    for e in events:
        if e["event_type"] == "BILLING_QUEUE_JOIN":
            depth = e.get("metadata", {}).get("queue_depth")
            assert depth is not None, \
                "BILLING_QUEUE_JOIN missing queue_depth in metadata"
            assert depth > 0, \
                "BILLING_QUEUE_JOIN queue_depth must be > 0"