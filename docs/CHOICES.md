# CHOICES.md — Engineering Decision Log

## Decision 1: Detection Model — YOLOv8n

### Options Considered
- YOLOv8n: Fast, runs on CPU, easy install — chosen
- YOLOv8m: Better accuracy but slower, needs more RAM
- RT-DETR: High accuracy but complex setup, slow on CPU
- MediaPipe: Very fast but poor on crowd scenes

### What AI Suggested
Claude suggested YOLOv8m for better accuracy on retail footage with
partial occlusion handling.

### What I Chose and Why
I chose YOLOv8n because:
1. Runs on CPU without GPU — works on any machine
2. The evaluation focuses on system design not perfect detection
3. ByteTrack built-in via ultralytics saves integration work
4. For production I would upgrade to YOLOv8m with GPU hardware

## Decision 2: Event Schema Design

### Options Considered
- Option A: Flat schema — all fields at top level
- Option B: Nested schema — core fields plus metadata object — chosen
- Option C: Minimal schema — only required fields

### What AI Suggested
Claude suggested flat schema for simplicity and easier SQL querying.

### What I Chose and Why
I chose nested metadata because:
1. Problem statement explicitly requires metadata object with
   queue_depth, sku_zone, and session_seq fields
2. Keeps top-level schema clean and consistent across all event types
3. SQLAlchemy flattens metadata into DB table anyway
4. Future event types can add metadata fields without schema changes

I disagreed with Claude here — the spec was non-negotiable.

## Decision 3: API Storage — SQLite

### Options Considered
- Option A: FastAPI plus SQLite — chosen
- Option B: FastAPI plus PostgreSQL plus async SQLAlchemy
- Option C: FastAPI plus Redis plus PostgreSQL
- Option D: Node.js plus Express plus MongoDB

### What AI Suggested
Claude recommended Redis plus PostgreSQL for production scale,
arguing real-time metrics benefit from Redis sorted sets and SQLite
becomes a bottleneck at 40 stores.

### What I Chose and Why
I chose SQLite because:
1. Challenge runs on single machine — SQLite is perfectly adequate
2. DATABASE_URL is env var — swap to PostgreSQL with zero code changes
3. Docker compose up must just work — simpler is more reliable
4. Redis adds complexity with no scoring benefit at this scale

For real production at 40 stores I would use Redis for hot path
and PostgreSQL for historical queries as Claude suggested.

## Summary

| Decision | AI Suggested | I Chose | Agreed |
|---|---|---|---|
| Detection model | YOLOv8m | YOLOv8n | No — CPU portability |
| Schema design | Flat | Nested metadata | No — spec required it |
| API storage | Redis plus PostgreSQL | SQLite | No — challenge scope |