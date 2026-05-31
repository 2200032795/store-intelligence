# Store Intelligence System
### Purplle Tech Challenge 2026 — Round 2

An end-to-end pipeline that converts raw CCTV footage into live store analytics.

## Quick Start (5 Commands)

1. Clone and enter project
git clone <your-repo-url>
cd store-intelligence

2. Create virtual environment
python -m venv venv
venv\Scripts\activate

3. Install dependencies
pip install -r requirements.txt

4. Load POS transaction data
python pipeline/load_pos.py --csv data/Brigade_Bangalore_10_April_26.csv

5. Start the API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

API is now live at: http://localhost:8000
Interactive docs: http://localhost:8000/docs

## Run Detection Pipeline

python pipeline/detect.py --videos_dir data/videos --layout store_layout.json --output data/events.jsonl --clip_start 2026-04-10T10:00:00Z

## Ingest Events into API

python pipeline/ingest_events.py --events data/events.jsonl --api http://localhost:8000

## Live Dashboard

pip install rich
python dashboard/live.py --store STORE_BLR_002 --api http://localhost:8000

## Run Tests

pip install pytest
pytest tests/ -v

## API Endpoints

POST /events/ingest — Ingest batch of events
GET  /stores/{id}/metrics — Visitors, conversion rate, dwell time
GET  /stores/{id}/funnel — Conversion funnel with drop-off %
GET  /stores/{id}/heatmap — Zone visit frequency heatmap
GET  /stores/{id}/anomalies — Active anomalies with severity
GET  /health — Service health and feed lag status

Store ID: STORE_BLR_002

## Project Structure

store-intelligence/
├── pipeline/
│   ├── detect.py
│   ├── load_pos.py
│   └── ingest_events.py
├── app/
│   ├── main.py
│   ├── models.py
│   ├── database.py
│   ├── ingestion.py
│   ├── metrics.py
│   ├── funnel.py
│   ├── anomalies.py
│   └── health.py
├── tests/
├── dashboard/
│   └── live.py
├── docs/
│   ├── DESIGN.md
│   └── CHOICES.md
├── store_layout.json
└── README.md

## Tech Stack

Detection   — YOLOv8n plus ByteTrack
API         — FastAPI plus Uvicorn
Database    — SQLite via SQLAlchemy
Schema      — Pydantic v2
Logging     — structlog
Dashboard   — rich terminal
Tests       — pytest