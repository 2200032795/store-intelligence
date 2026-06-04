# CHOICES.md — Engineering Decision Log

## Decision 1: Detection Model — YOLOv8n

### Options Considered
- YOLOv8n: Fast, runs on CPU, easy install — chosen
- YOLOv8m: Better accuracy but slower, needs more RAM
- RT-DETR: High accuracy but complex setup, slow on CPU
- MediaPipe: Very fast but poor on crowd scenes

### What AI Suggested
Claude suggested RT-DETR for higher accuracy in crowded retail scenes and partial
occlusion cases. I evaluated it — RT-DETR is significantly slower on CPU and requires
more RAM. The challenge requires docker compose up to work on any machine without
GPU. CPU portability outweighed accuracy gains at this scope.

### What I Chose and Why
YOLOv8n because:
1. Runs on CPU without GPU — works on any machine
2. ByteTrack built-in via ultralytics saves integration work
3. Frame sampling every 5th frame gives 5x speed boost
4. For production at 40 stores with dedicated GPU hardware, I would upgrade to
   YOLOv8m or RT-DETR

### VLM Usage
I evaluated using Claude Vision for zone classification — prompting it to describe
which store zone a person is standing in from a video frame. I tested this approach
and found it adds 2+ seconds latency per frame and significant API cost at scale.
I chose rule-based coordinate mapping instead: normalised bounding box centroid
mapped to zone rectangles from store_layout.json. Deterministic, zero latency,
fully debuggable. I would revisit VLM zone classification only if zone boundaries
were complex or heavily overlapping.

---

## Decision 2: Event Schema Design

### Options Considered
- Option A: Flat schema — all fields at top level
- Option B: Nested schema — core fields plus metadata object — chosen
- Option C: Minimal schema — only required fields

### What AI Suggested
Claude suggested a flat schema for simpler SQL querying and easier debugging.
I disagreed — the problem statement explicitly requires a metadata object with
queue_depth, sku_zone, and session_seq. A flat schema would pollute the top-level
with fields that are null for most event types.

### What I Chose and Why
Nested metadata because:
1. Problem statement explicitly requires metadata object
2. Keeps top-level schema clean and consistent across all event types
3. SQLAlchemy flattens metadata into DB columns anyway — no query penalty
4. Future event types can add metadata fields without breaking schema

---

## Decision 3: API Storage — SQLite

### Options Considered
- Option A: SQLite — chosen
- Option B: PostgreSQL with async SQLAlchemy
- Option C: Redis for hot path + PostgreSQL for history

### What AI Suggested
Claude suggested PostgreSQL with async SQLAlchemy for production readiness and
concurrent write performance. I overrode this for the challenge scope — the scoring
harness runs on a single machine and docker compose up must work without external
services. Adding PostgreSQL increases setup complexity with no scoring benefit
at this scale.

### What I Chose and Why
SQLite because:
1. Challenge runs on single machine — SQLite is perfectly adequate
2. DATABASE_URL is env var — swap to PostgreSQL with zero code changes
3. docker compose up must just work — simpler is more reliable
4. For real production at 40 stores sending concurrent events, I would use
   PostgreSQL for writes and Redis for real-time queue depth tracking

---

## Summary

| Decision | I Chose | AI Suggested | My Override Reason |
|---|---|---|---|
| Detection model | YOLOv8n | RT-DETR | CPU portability |
| Schema design | Nested metadata | Flat schema | Spec required it |
| API storage | SQLite | PostgreSQL | Challenge scope |
| Zone classification | Rule-based | VLM (Claude Vision) | Latency + cost |