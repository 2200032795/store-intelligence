from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db, EventRecord, POSTransaction
from app.metrics import _correlate_conversions, POS_STORE_MAP

router = APIRouter(tags=["funnel"])


@router.get("/stores/{store_id}/funnel")
def get_funnel(store_id: str, db: Session = Depends(get_db)):
    events = (
        db.query(EventRecord)
        .filter(EventRecord.store_id == store_id, EventRecord.is_staff == False)
        .all()
    )

    entered:       set[str] = set()
    zone_visited:  set[str] = set()
    billing_queue: set[str] = set()

    for e in events:
        if e.event_type in ("ENTRY", "REENTRY"):
            entered.add(e.visitor_id)
        if e.event_type == "ZONE_ENTER" and e.zone_id not in (None, "ENTRY_EXIT", "BILLING"):
            zone_visited.add(e.visitor_id)
        if e.event_type == "BILLING_QUEUE_JOIN":
            billing_queue.add(e.visitor_id)

    zone_visited  &= entered
    billing_queue &= entered

    pos_store = POS_STORE_MAP.get(store_id, store_id)
    pos_txns = db.query(POSTransaction).filter(
        POSTransaction.store_id == pos_store
    ).all()
    purchased = _correlate_conversions(events, pos_txns)

    total = len(entered) or 1

    def pct(n): return round(n / total * 100, 1)
    def drop(a, b): return round((a - b) / a * 100, 1) if a else 0.0

    stages = [
        {"stage": "Entry",         "count": len(entered),       "pct_of_total": 100.0},
        {"stage": "Zone Visit",    "count": len(zone_visited),  "pct_of_total": pct(len(zone_visited)),
         "drop_off_pct": drop(len(entered), len(zone_visited))},
        {"stage": "Billing Queue", "count": len(billing_queue), "pct_of_total": pct(len(billing_queue)),
         "drop_off_pct": drop(len(zone_visited), len(billing_queue))},
        {"stage": "Purchase",      "count": purchased,          "pct_of_total": pct(purchased),
         "drop_off_pct": drop(len(billing_queue), purchased)},
    ]

    return {"store_id": store_id, "funnel": stages}