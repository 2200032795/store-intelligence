from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from app.database import get_db, EventRecord, POSTransaction

router = APIRouter(tags=["metrics"])

POS_STORE_MAP = {"STORE_BLR_002": "ST1008"}


def _customer_events(db: Session, store_id: str):
    return (
        db.query(EventRecord)
        .filter(
            EventRecord.store_id == store_id,
            EventRecord.is_staff == False,
        )
        .all()
    )


def _correlate_conversions(events, pos_txns) -> int:
    def parse_ts(s: str):
        return datetime.fromisoformat(s.replace("Z", "+00:00"))

    billing_windows = []
    for e in events:
        if e.zone_id == "BILLING" and e.event_type in ("ZONE_ENTER", "ZONE_DWELL"):
            billing_windows.append((e.visitor_id, parse_ts(e.timestamp)))

    converted_visitors: set[str] = set()
    for txn in pos_txns:
        try:
            # DD-MM-YYYY format parse చేస్తున్నాం
            date_part = datetime.strptime(txn.order_date, "%d-%m-%Y").date()
            time_part = datetime.strptime(txn.order_time, "%H:%M:%S").time()
            # IST (UTC+5:30) → UTC convert
            txn_ist = datetime.combine(date_part, time_part)
            txn_utc = txn_ist.replace(
                tzinfo=timezone(timedelta(hours=5, minutes=30))
            ).astimezone(timezone.utc)
        except Exception:
            continue
        for vid, bts in billing_windows:
            gap = (txn_utc - bts).total_seconds()
            if 0 <= gap <= 300:
                converted_visitors.add(vid)
    return len(converted_visitors)


@router.get("/stores/{store_id}/metrics")
def get_metrics(store_id: str, db: Session = Depends(get_db)):
    events = _customer_events(db, store_id)
    if not events:
        return {
            "store_id":        store_id,
            "unique_visitors":  0,
            "conversion_rate":  0.0,
            "avg_dwell_per_zone": {},
            "queue_depth":      0,
            "abandonment_rate": 0.0,
            "data_note":        "No events ingested yet",
        }

    entry_visitors = {
        e.visitor_id for e in events
        if e.event_type in ("ENTRY", "REENTRY")
    }
    unique_visitors = len(entry_visitors)

    zone_dwell: dict[str, list[int]] = defaultdict(list)
    for e in events:
        if e.event_type == "ZONE_DWELL" and e.zone_id:
            zone_dwell[e.zone_id].append(e.dwell_ms)
    avg_dwell = {
        z: round(sum(v) / len(v) / 1000, 1)
        for z, v in zone_dwell.items()
    }

    queue_events = [
        e for e in events
        if e.event_type == "BILLING_QUEUE_JOIN" and e.queue_depth is not None
    ]
    queue_depth = queue_events[-1].queue_depth if queue_events else 0

    joins    = sum(1 for e in events if e.event_type == "BILLING_QUEUE_JOIN")
    abandons = sum(1 for e in events if e.event_type == "BILLING_QUEUE_ABANDON")
    abandonment_rate = round(abandons / joins, 3) if joins else 0.0

    pos_store = POS_STORE_MAP.get(store_id, store_id)
    pos_txns  = db.query(POSTransaction).filter(
        POSTransaction.store_id == pos_store
    ).all()

    converted       = _correlate_conversions(events, pos_txns)
    conversion_rate = round(converted / unique_visitors, 3) if unique_visitors else 0.0

    return {
        "store_id":            store_id,
        "unique_visitors":     unique_visitors,
        "conversion_rate":     conversion_rate,
        "converted_visitors":  converted,
        "avg_dwell_per_zone":  avg_dwell,
        "queue_depth":         queue_depth,
        "abandonment_rate":    abandonment_rate,
        "total_pos_txns":      len({t.order_id for t in pos_txns}),
    }


@router.get("/stores/{store_id}/heatmap")
def get_heatmap(store_id: str, db: Session = Depends(get_db)):
    events = _customer_events(db, store_id)

    zone_visits: dict[str, int]    = defaultdict(int)
    zone_dwell:  dict[str, list]   = defaultdict(list)

    for e in events:
        if e.event_type == "ZONE_ENTER" and e.zone_id:
            zone_visits[e.zone_id] += 1
        if e.event_type == "ZONE_DWELL" and e.zone_id:
            zone_dwell[e.zone_id].append(e.dwell_ms)

    max_visits     = max(zone_visits.values(), default=1)
    total_sessions = len({e.visitor_id for e in events if e.event_type == "ENTRY"})

    heatmap = []
    for zone, visits in zone_visits.items():
        avg_dwell_s = (
            round(sum(zone_dwell[zone]) / len(zone_dwell[zone]) / 1000, 1)
            if zone_dwell[zone] else 0.0
        )
        heatmap.append({
            "zone_id":          zone,
            "visit_count":      visits,
            "normalised":       round(visits / max_visits * 100),
            "avg_dwell_s":      avg_dwell_s,
            "data_confidence":  "low" if total_sessions < 20 else "normal",
        })

    heatmap.sort(key=lambda x: x["normalised"], reverse=True)
    return {"store_id": store_id, "zones": heatmap}