# DESIGN.md — Store Intelligence System

## System Overview

This system converts raw CCTV footage into real-time store analytics for
Brigade Bangalore store (ST1008). Built as a four-stage pipeline:

CCTV Videos → Detection Pipeline → Events (JSONL) → FastAPI → SQLite → Dashboard

## Architecture

DETECTION LAYER
  YOLOv8n + ByteTrack + Zone Classifier
  emits structured JSONL events
        |
FASTAPI API
  POST /events/ingest
  GET  /stores/{id}/metrics
  GET  /stores/{id}/funnel
  GET  /stores/{id}/heatmap
  GET  /stores/{id}/anomalies
  GET  /health
        |
SQLite DATABASE
  events + pos_transactions tables

## Component Decisions

### Detection Layer
- Model: YOLOv8n — fast on CPU, no GPU needed
- Tracker: ByteTrack via ultralytics model.track()
- Frame sampling: Every 5th frame (15fps to 3fps) — 5x faster
- Staff detection: HSV colour mask for dark-blue uniforms
- Zone classification: Normalised bounding-box centroid mapped to zone rectangles from store_layout.json

### Event Schema
- UUID v4 event_ids — globally unique, idempotent ingest
- ISO-8601 UTC timestamps from clip start + frame offset
- is_staff flag on every event for API-layer filtering
- confidence always emitted — low-confidence never silently dropped

### API Layer
- FastAPI — async, auto OpenAPI docs at /docs
- SQLite — sufficient for challenge; swap via DATABASE_URL env var
- SQLAlchemy ORM — clean DB/business logic separation
- Pydantic v2 — strict schema validation on ingest

### POS Correlation
Visitor in BILLING zone within 5 minutes before a POS transaction counts as converted visitor. No customer_id needed.

## Trade-offs

| Decision | Chosen | Alternative | Reason |
|---|---|---|---|
| Storage | SQLite | PostgreSQL | Simpler; swappable via env var |
| Dashboard | Terminal | React UI | Ships faster |
| Staff detection | Colour heuristic | Trained classifier | No labelled data |
| Tracking | ByteTrack | DeepSORT | Faster on crowded scenes |
| Re-entry window | 5 minutes | 2 minutes | Avoid double-counting brief exits |
| Zone classification | Rule-based coordinates | ML classifier | Deterministic and debuggable |