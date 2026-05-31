import os
from sqlalchemy import (
    create_engine, Column, String, Integer, Float,
    Boolean, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./store_intelligence.db")

connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    poolclass=StaticPool,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class EventRecord(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_event_id"),)

    id         = Column(Integer, primary_key=True, autoincrement=True)
    event_id   = Column(String, unique=True, nullable=False, index=True)
    store_id   = Column(String, nullable=False, index=True)
    camera_id  = Column(String, nullable=False)
    visitor_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False)
    timestamp  = Column(String, nullable=False)
    zone_id    = Column(String, nullable=True)
    dwell_ms   = Column(Integer, default=0)
    is_staff   = Column(Boolean, default=False)
    confidence = Column(Float, default=1.0)
    queue_depth= Column(Integer, nullable=True)
    sku_zone   = Column(String, nullable=True)
    session_seq= Column(Integer, default=0)


class POSTransaction(Base):
    __tablename__ = "pos_transactions"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    order_id       = Column(String, nullable=False)
    invoice_number = Column(String, nullable=False, unique=True)
    store_id       = Column(String, nullable=False, index=True)
    order_date     = Column(String, nullable=False)
    order_time     = Column(String, nullable=False)
    customer_number= Column(String, nullable=True)
    gmv            = Column(Float, default=0.0)
    dep_name       = Column(String, nullable=True)
    sub_category   = Column(String, nullable=True)
    salesperson_id = Column(String, nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()