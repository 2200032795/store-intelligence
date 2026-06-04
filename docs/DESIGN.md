# DESIGN.md — Store Intelligence System

## System Overview

This project converts raw CCTV footage into real-time retail analytics for the store `STORE_BLR_002`. The system processes video streams, generates structured behavioral events, ingests them into a FastAPI service, computes operational metrics, and exposes live analytics through REST APIs and a terminal dashboard.

The architecture follows a modular pipeline:

```text
CCTV Videos
      ↓
Detection Pipeline
      ↓
Structured Events (JSONL)
      ↓
FastAPI Intelligence API
      ↓
SQLite Database
      ↓
Analytics + Dashboard
```

The primary business objective is to measure offline store conversion rate:

```text
Conversion Rate =
Visitors Who Purchased ÷ Total Unique Visitors
```

---

## System Architecture

### 1. Detection Layer

The detection pipeline processes CCTV clips from multiple camera angles.

Main responsibilities:

* Detect customers entering and exiting the store
* Track movement across frames
* Assign visitor session IDs
* Identify store zones
* Emit structured events

### Technologies Used

| Component        | Technology          |
| ---------------- | ------------------- |
| Object Detection | YOLOv8n             |
| Tracking         | ByteTrack           |
| Event Emission   | JSONL               |
| Zone Mapping     | Rule-based geometry |
| Staff Detection  | HSV color heuristic |

### Detection Flow

```text
Video Frames
      ↓
YOLOv8n Person Detection
      ↓
ByteTrack Tracking
      ↓
Zone Classification
      ↓
Event Generation
      ↓
events.jsonl
```

### Design Decisions

* YOLOv8n was selected for CPU portability and fast inference
* Frame sampling reduces computation cost
* Bounding-box centroid mapping assigns visitors to zones
* Confidence values are always emitted, even for uncertain detections
* Event timestamps are generated using clip start time and frame offset

---

## Event Processing Pipeline

The detection pipeline emits structured behavioral events in JSONL format.

Supported event types:

* ENTRY
* EXIT
* ZONE_ENTER
* ZONE_EXIT
* ZONE_DWELL
* BILLING_QUEUE_JOIN
* BILLING_QUEUE_ABANDON
* REENTRY

Each event contains:

* Unique event_id
* visitor_id
* store_id
* camera_id
* timestamp
* confidence
* metadata fields

The schema is designed to support:

* Real-time analytics
* Session reconstruction
* Funnel computation
* Queue analysis
* Heatmap generation
* Anomaly detection

A nested metadata structure was used to support event-specific fields without changing the core schema.

---

## FastAPI Intelligence Layer

The API layer ingests events and exposes real-time analytics.

### API Endpoints

| Endpoint                   | Purpose               |
| -------------------------- | --------------------- |
| POST /events/ingest        | Ingest event batches  |
| GET /stores/{id}/metrics   | Store KPIs            |
| GET /stores/{id}/funnel    | Conversion funnel     |
| GET /stores/{id}/heatmap   | Zone analytics        |
| GET /stores/{id}/anomalies | Operational anomalies |
| GET /health                | Service health        |

### Responsibilities

* Validate incoming events
* Deduplicate by event_id
* Store data in SQLite
* Compute real-time analytics
* Detect operational anomalies
* Expose queryable intelligence APIs

### Validation and Reliability

* Pydantic v2 validates event schemas
* UUID event IDs provide idempotency
* Structured logging improves observability
* Health endpoint monitors stale event feeds
* Graceful error responses prevent raw stack traces

---

## Database Design

SQLite was selected for simplicity and reliability during evaluation.

### Tables

#### events

Stores all behavioral events emitted by the detection layer.

#### pos_transactions

Stores transaction records used for conversion analysis.

### POS Correlation Logic

A visitor is considered converted if:

* The visitor was detected in the billing zone
* A POS transaction occurred within 5 minutes

This approach matches the challenge specification while avoiding the need for customer identity tracking.

---

## Funnel Computation

The funnel endpoint computes:

```text
ENTRY
   ↓
ZONE VISIT
   ↓
BILLING QUEUE
   ↓
PURCHASE
```

Session-level deduplication prevents re-entry inflation and ensures accurate conversion metrics.

---

## Heatmap Logic

Heatmaps are generated using:

* Zone visit frequency
* Average dwell duration
* Normalized scores from 0–100

A data_confidence flag is returned when the number of sessions is low.

---

## Anomaly Detection

The anomaly engine identifies operational issues such as:

* Queue spikes
* Conversion drops
* Dead zones
* Stale event feeds

Each anomaly includes:

* Severity level
* Suggested action
* Timestamp
* Affected store

---

## Trade-offs and Constraints

| Decision            | Chosen          | Alternative        | Reason                        |
| ------------------- | --------------- | ------------------ | ----------------------------- |
| Detection Model     | YOLOv8n         | YOLOv8m            | Faster CPU inference          |
| Database            | SQLite          | PostgreSQL         | Simpler deployment            |
| Dashboard           | Terminal UI     | React frontend     | Faster implementation         |
| Zone Classification | Rule-based      | ML classifier      | Deterministic and explainable |
| Staff Detection     | Color heuristic | Trained classifier | No labeled dataset            |

---

## AI-Assisted Decisions

AI tools were used throughout the project to evaluate architectural options, compare technologies, and improve implementation speed. However, all final decisions were validated against the challenge requirements before adoption.

### Detection Model Selection

AI initially recommended YOLOv8m because it generally performs better in crowded scenes and partial occlusions. After evaluating the computational cost, I selected YOLOv8n because the challenge environment prioritizes portability and CPU execution.

### Event Schema Design

AI suggested using a flatter event schema for easier SQL querying. I chose a nested metadata structure because event-specific fields such as queue_depth and session_seq do not apply to every event type and are easier to extend inside metadata.

### Zone Classification Strategy

I evaluated both machine-learning-based zone classification and rule-based geometric mapping. AI suggested a lightweight classifier for flexibility, but I selected coordinate-based mapping because it is deterministic, easier to debug, and requires no additional training data.

### Reflection

AI accelerated research and implementation significantly, especially when comparing architectural alternatives and identifying edge cases. However, I intentionally prioritized reliability, simplicity, and reproducibility over adopting more complex AI-generated solutions.
