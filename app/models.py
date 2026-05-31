from pydantic import BaseModel, Field, validator
from typing import Optional, List
from enum import Enum
import uuid


class EventType(str, Enum):
    ENTRY                 = "ENTRY"
    EXIT                  = "EXIT"
    ZONE_ENTER            = "ZONE_ENTER"
    ZONE_EXIT             = "ZONE_EXIT"
    ZONE_DWELL            = "ZONE_DWELL"
    BILLING_QUEUE_JOIN    = "BILLING_QUEUE_JOIN"
    BILLING_QUEUE_ABANDON = "BILLING_QUEUE_ABANDON"
    REENTRY               = "REENTRY"


class EventMetadata(BaseModel):
    queue_depth : Optional[int]   = None
    sku_zone    : Optional[str]   = None
    session_seq : int             = 0


class StoreEvent(BaseModel):
    event_id   : str              = Field(default_factory=lambda: str(uuid.uuid4()))
    store_id   : str
    camera_id  : str
    visitor_id : str
    event_type : EventType
    timestamp  : str
    zone_id    : Optional[str]    = None
    dwell_ms   : int              = 0
    is_staff   : bool             = False
    confidence : float            = Field(ge=0.0, le=1.0, default=1.0)
    metadata   : EventMetadata    = Field(default_factory=EventMetadata)

    @validator("timestamp")
    def validate_ts(cls, v):
        from datetime import datetime
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"Invalid timestamp: {v}")
        return v


class IngestRequest(BaseModel):
    events: List[StoreEvent] = Field(..., max_items=500)


class IngestResponse(BaseModel):
    accepted : int
    rejected : int
    duplicate: int
    errors   : List[dict] = []