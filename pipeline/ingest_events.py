import json
import requests
import sys

FILE = sys.argv[2] if len(sys.argv) > 2 else "data/events.jsonl"
API = "http://127.0.0.1:8000/events/ingest"

with open(FILE, encoding="utf-8") as f:
    lines = [l.strip() for l in f if l.strip()]

BATCH = 50
ok = fail = 0

for i in range(0, len(lines), BATCH):
    batch = [json.loads(l) for l in lines[i:i+BATCH]]
    try:
        r = requests.post(API, json={"events": batch}, timeout=10)
        if r.status_code in (200, 201):
            ok += len(batch)
        else:
            print(f"Batch {i} failed: {r.status_code} {r.text[:100]}")
            fail += len(batch)
    except Exception as e:
        fail += len(batch)

print(f"Ingested: {ok}  Failed: {fail}")