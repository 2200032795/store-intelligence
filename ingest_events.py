import argparse
import json
import requests
from pathlib import Path

BATCH_SIZE = 200


def ingest(events_path: str, api_base: str):
    path = Path(events_path)
    if not path.exists():
        print(f"[ERROR] File not found: {events_path}")
        return

    events = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    print(f"[INFO] Loaded {len(events)} events from {events_path}")

    total_accepted = total_dup = total_rejected = 0

    for i in range(0, len(events), BATCH_SIZE):
        batch = events[i:i + BATCH_SIZE]
        try:
            r = requests.post(
                f"{api_base}/events/ingest",
                json={"events": batch},
                timeout=30,
            )
            if r.status_code == 200:
                data = r.json()
                total_accepted += data.get("accepted", 0)
                total_dup      += data.get("duplicate", 0)
                total_rejected += data.get("rejected", 0)
                print(f"  Batch {i//BATCH_SIZE + 1}: accepted={data['accepted']} dup={data['duplicate']}")
            else:
                print(f"  [WARN] Batch failed: {r.status_code}")
        except Exception as e:
            print(f"  [ERROR] {e}")

    print(f"\n✅ Done — accepted={total_accepted} duplicates={total_dup} rejected={total_rejected}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", default="data/events.jsonl")
    parser.add_argument("--api",    default="http://localhost:8000")
    args = parser.parse_args()
    ingest(args.events, args.api)