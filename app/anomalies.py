from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from collections import defaultdict

from app.database import get_db, EventRecord

router = APIRouter(tags=["anomalies"])

QUEUE_SPIKE_THRESHOLD    = 5
QUEUE_CRITICAL_THRESHOLD = 8
DEAD_ZONE_MINUTES        = 30
CONVERSION_DROP_PCT      = 0.30


@router.get("/stores/{store_id}/anomalies")
def get_anomalies(store_id: str, db: Session = Depends(get_db)):
    events = (
        db.query(EventRecord)
        .filter(EventRecord.store_id == store_id, EventRecord.is_staff == False)
        .all()
    )

    anomalies = []
    now = datetime.now(timezone.utc)

    # 1. BILLING QUEUE SPIKE
    queue_events = [
        e for e in events
        if e.event_type == "BILLING_QUEUE_JOIN" and e.queue_depth is not None
    ]
    if queue_events:
        latest_q = max(queue_events, key=lambda e: e.timestamp)
        depth = latest_q.queue_depth
        if depth > QUEUE_CRITICAL_THRESHOLD:
            anomalies.append({
                "type":             "BILLING_QUEUE_SPIKE",
                "severity":         "CRITICAL",
                "detail":           f"Queue depth is {depth}",
                "suggested_action": "Open additional billing counter immediately",
                "detected_at":      latest_q.timestamp,
            })
        elif depth > QUEUE_SPIKE_THRESHOLD:
            anomalies.append({
                "type":             "BILLING_QUEUE_SPIKE",
                "severity":         "WARN",
                "detail":           f"Queue depth is {depth}",
                "suggested_action": "Alert floor staff to direct customers to billing",
                "detected_at":      latest_q.timestamp,
            })

    # 2. DEAD ZONE
    zone_last_visit: dict[str, str] = {}
    for e in events:
        if e.event_type == "ZONE_ENTER" and e.zone_id:
            if e.zone_id not in zone_last_visit or e.timestamp > zone_last_visit[e.zone_id]:
                zone_last_visit[e.zone_id] = e.timestamp

    all_zones = {"SKINCARE", "HAIRCARE", "MAKEUP", "FRAGRANCE", "PERSONAL_CARE", "BATH_BODY"}
    for zone in all_zones:
        last_ts_str = zone_last_visit.get(zone)
        if last_ts_str is None:
            anomalies.append({
                "type":             "DEAD_ZONE",
                "severity":         "INFO",
                "detail":           f"Zone {zone} has never been visited",
                "suggested_action": f"Check {zone} display and restocking",
                "detected_at":      now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
        else:
            last_ts = datetime.fromisoformat(last_ts_str.replace("Z", "+00:00"))
            if (now - last_ts).total_seconds() > DEAD_ZONE_MINUTES * 60:
                anomalies.append({
                    "type":             "DEAD_ZONE",
                    "severity":         "WARN",
                    "detail":           f"Zone {zone} — no visits in {DEAD_ZONE_MINUTES} min",
                    "suggested_action": f"Staff to check zone {zone}",
                    "detected_at":      now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                })

    # 3. CONVERSION DROP
    entered = {e.visitor_id for e in events if e.event_type in ("ENTRY", "REENTRY")}
    converted = {
        e.visitor_id for e in events
        if e.event_type == "ZONE_ENTER" and e.zone_id == "BILLING"
    }
    if len(entered) > 10:
        conv_rate = len(converted) / len(entered)
        baseline = 0.35
        if conv_rate < baseline * (1 - CONVERSION_DROP_PCT):
            anomalies.append({
                "type":             "CONVERSION_DROP",
                "severity":         "WARN",
                "detail":           f"Conversion {conv_rate:.1%} vs baseline {baseline:.1%}",
                "suggested_action": "Review funnel — check billing zone staffing",
                "detected_at":      now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            })

    # 4. HIGH REENTRY
    reentries = sum(1 for e in events if e.event_type == "REENTRY")
    if reentries > 5:
        anomalies.append({
            "type":             "HIGH_REENTRY",
            "severity":         "INFO",
            "detail":           f"{reentries} re-entry events detected",
            "suggested_action": "Verify entry camera coverage",
            "detected_at":      now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })

    if not anomalies:
        anomalies.append({
            "type":             "ALL_CLEAR",
            "severity":         "INFO",
            "detail":           "No active anomalies detected",
            "suggested_action": "Continue monitoring",
            "detected_at":      now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })

    return {"store_id": store_id, "anomalies": anomalies}