from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import IngestRequest, IngestResponse, StoreEvent
from app.database import get_db, EventRecord

router = APIRouter(tags=["ingest"])


def _to_record(e: StoreEvent) -> EventRecord:
    return EventRecord(
        event_id   = e.event_id,
        store_id   = e.store_id,
        camera_id  = e.camera_id,
        visitor_id = e.visitor_id,
        event_type = e.event_type.value,
        timestamp  = e.timestamp,
        zone_id    = e.zone_id,
        dwell_ms   = e.dwell_ms,
        is_staff   = e.is_staff,
        confidence = e.confidence,
        queue_depth= e.metadata.queue_depth,
        sku_zone   = e.metadata.sku_zone,
        session_seq= e.metadata.session_seq,
    )


@router.post("/events/ingest", response_model=IngestResponse)
def ingest_events(payload: IngestRequest, db: Session = Depends(get_db)):
    accepted = rejected = duplicate = 0
    errors = []

    for event in payload.events:
        try:
            record = _to_record(event)
            db.add(record)
            db.flush()
            accepted += 1
        except IntegrityError:
            db.rollback()
            duplicate += 1
        except Exception as exc:
            db.rollback()
            rejected += 1
            errors.append({"event_id": event.event_id, "error": str(exc)})

    db.commit()
    return IngestResponse(
        accepted=accepted,
        rejected=rejected,
        duplicate=duplicate,
        errors=errors,
    )