from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone

from app.database import get_db, EventRecord

router = APIRouter(tags=["health"])

STALE_THRESHOLD_MIN = 10


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    status = "ok"
    stores_status = {}

    try:
        rows = (
            db.query(EventRecord.store_id, func.max(EventRecord.timestamp))
            .group_by(EventRecord.store_id)
            .all()
        )
        for store_id, last_ts_str in rows:
            if last_ts_str is None:
                stores_status[store_id] = {"last_event": None, "feed_status": "NO_DATA"}
                continue
            last_ts = datetime.fromisoformat(last_ts_str.replace("Z", "+00:00"))
            lag_min = (now - last_ts).total_seconds() / 60
            feed_status = "STALE_FEED" if lag_min > STALE_THRESHOLD_MIN else "OK"
            if feed_status == "STALE_FEED":
                status = "degraded"
            stores_status[store_id] = {
                "last_event":  last_ts_str,
                "lag_minutes": round(lag_min, 1),
                "feed_status": feed_status,
            }
        db_status = "connected"
    except Exception as exc:
        db_status = f"error: {str(exc)}"
        status = "degraded"

    return {
        "status":    status,
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "database":  db_status,
        "stores":    stores_status,
    }