#!/bin/bash
# run.sh — One command to process all clips → events → ingest into API
# Usage: bash pipeline/run.sh

set -e

VIDEOS_DIR=${1:-"data/videos"}
LAYOUT=${2:-"app/store_layout.json"}
OUTPUT=${3:-"data/events.jsonl"}
API=${4:-"http://localhost:8000"}
CLIP_START=${5:-"2026-04-10T10:00:00Z"}

echo "============================================"
echo " Store Intelligence Pipeline"
echo "============================================"
echo " Videos dir : $VIDEOS_DIR"
echo " Layout     : $LAYOUT"
echo " Output     : $OUTPUT"
echo " API        : $API"
echo "============================================"

# Step 1: Run detection pipeline
echo ""
echo "[STEP 1] Running detection pipeline..."
python pipeline/detect.py \
  --videos_dir "$VIDEOS_DIR" \
  --layout     "$LAYOUT" \
  --output     "$OUTPUT" \
  --clip_start "$CLIP_START"

echo ""
echo "[STEP 1] Done — events saved to $OUTPUT"

# Step 2: Load POS transactions
echo ""
echo "[STEP 2] Loading POS transactions..."
POS_FILE="data/pos_transactions.csv"
if [ -f "$POS_FILE" ]; then
  python pipeline/load_pos.py --csv "$POS_FILE"
  echo "[STEP 2] Done — POS data loaded"
else
  echo "[STEP 2] Skipped — $POS_FILE not found"
fi

# Step 3: Ingest events into API
echo ""
echo "[STEP 3] Ingesting events into API..."
python pipeline/ingest_events.py "$API" "$OUTPUT"
echo "[STEP 3] Done — events ingested"

echo ""
echo "============================================"
echo " Pipeline complete!"
echo " API docs: $API/docs"
echo " Dashboard: python dashboard/live.py"
echo "============================================"