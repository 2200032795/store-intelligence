import cv2
import json
import uuid
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

try:
    from ultralytics import YOLO
except ImportError:
    print("[ERROR] pip install ultralytics")
    exit(1)

STORE_ID   = "STORE_BLR_002"
CAMERA_MAP = {
    "entry":   "CAM_ENTRY_01",
    "floor":   "CAM_FLOOR_01",
    "billing": "CAM_BILLING_01",
}


def load_layout(layout_path: str) -> dict:
    try:
        with open(layout_path) as f:
            data = json.load(f)
        return data.get("zones", {})
    except Exception:
        return {}


def make_event(store_id, camera_id, visitor_id, event_type,
               timestamp, zone_id=None, dwell_ms=0,
               is_staff=False, confidence=1.0,
               queue_depth=None, sku_zone=None, session_seq=0):
    return {
        "event_id":   str(uuid.uuid4()),
        "store_id":   store_id,
        "camera_id":  camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp":  timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "zone_id":    zone_id,
        "dwell_ms":   dwell_ms,
        "is_staff":   bool(is_staff),
        "confidence": round(float(confidence), 3),
        "metadata": {
            "queue_depth": queue_depth,
            "sku_zone":    sku_zone,
            "session_seq": session_seq,
        },
    }


def classify_zone(cx_norm, cy_norm, zones):
    for zone_name, bounds in zones.items():
        yr = bounds.get("y_range", [0, 1])
        xr = bounds.get("x_range", [0, 1])
        if xr[0] <= cx_norm <= xr[1] and yr[0] <= cy_norm <= yr[1]:
            return zone_name
    return None


def detect_staff(frame, bbox):
    x1, y1, x2, y2 = map(int, bbox)
    roi = frame[y1:y2, x1:x2]
    if roi.size == 0:
        return False
    hsv   = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    lower = np.array([100, 50, 20])
    upper = np.array([130, 255, 100])
    mask  = cv2.inRange(hsv, lower, upper)
    ratio = mask.sum() / (mask.size + 1e-6) * 255
    return ratio > 0.25


class VisitorTracker:
    def __init__(self):
        self.tracks      = {}
        self.visitor_map = {}
        self.exited      = {}
        self.events      = []
        self.session_seq = defaultdict(int)
        # billing queue tracking
        self.billing_visitors: set[str] = set()

    def _vid(self, track_id):
        if track_id not in self.visitor_map:
            self.visitor_map[track_id] = f"VIS_{uuid.uuid4().hex[:6]}"
        return self.visitor_map[track_id]

    def _seq(self, vid):
        self.session_seq[vid] += 1
        return self.session_seq[vid]

    def update(self, track_id, bbox, confidence, frame,
               frame_ts, camera_id, zones):
        h, w     = frame.shape[:2]
        x1, y1, x2, y2 = bbox
        cx_norm  = ((x1 + x2) / 2) / w
        cy_norm  = ((y1 + y2) / 2) / h
        zone     = classify_zone(cx_norm, cy_norm, zones)
        is_staff = detect_staff(frame, bbox)
        vid      = self._vid(track_id)
        prev     = self.tracks.get(track_id)

        if prev is None:
            event_type = "ENTRY"
            if vid in self.exited:
                gap = (frame_ts - self.exited[vid]["ts"]).total_seconds()
                if gap < 300:
                    event_type = "REENTRY"
            self.events.append(make_event(
                STORE_ID, camera_id, vid, event_type,
                frame_ts, zone_id=zone, confidence=confidence,
                is_staff=is_staff, session_seq=self._seq(vid)
            ))
            self.tracks[track_id] = {
                "zone":          zone,
                "zone_enter_ts": frame_ts,
                "last_ts":       frame_ts,
                "is_staff":      is_staff,
                "last_dwell_emit": frame_ts,
            }
            return

        prev_zone = prev["zone"]

        # Zone change detected
        if zone != prev_zone:
            if prev_zone:
                dwell_ms = int(
                    (frame_ts - prev["zone_enter_ts"]).total_seconds() * 1000
                )
                self.events.append(make_event(
                    STORE_ID, camera_id, vid, "ZONE_EXIT",
                    frame_ts, zone_id=prev_zone, dwell_ms=dwell_ms,
                    confidence=confidence, is_staff=is_staff,
                    session_seq=self._seq(vid)
                ))

                # BILLING_QUEUE_ABANDON — left billing without purchase
                if prev_zone == "BILLING" and vid in self.billing_visitors:
                    self.billing_visitors.discard(vid)
                    self.events.append(make_event(
                        STORE_ID, camera_id, vid, "BILLING_QUEUE_ABANDON",
                        frame_ts, zone_id="BILLING",
                        confidence=confidence, is_staff=is_staff,
                        session_seq=self._seq(vid)
                    ))

            if zone:
                self.events.append(make_event(
                    STORE_ID, camera_id, vid, "ZONE_ENTER",
                    frame_ts, zone_id=zone, confidence=confidence,
                    is_staff=is_staff, session_seq=self._seq(vid)
                ))

                # BILLING_QUEUE_JOIN — entered billing zone
                if zone == "BILLING" and not is_staff:
                    queue_depth = len(self.billing_visitors)
                    if queue_depth > 0:
                        self.events.append(make_event(
                            STORE_ID, camera_id, vid, "BILLING_QUEUE_JOIN",
                            frame_ts, zone_id="BILLING",
                            confidence=confidence, is_staff=is_staff,
                            queue_depth=queue_depth,
                            session_seq=self._seq(vid)
                        ))
                    self.billing_visitors.add(vid)

            prev["zone"]          = zone
            prev["zone_enter_ts"] = frame_ts
            prev["last_dwell_emit"] = frame_ts

        # ZONE_DWELL — every 30 seconds in same zone
        if zone:
            dwell_sec  = (frame_ts - prev["zone_enter_ts"]).total_seconds()
            last_dwell = prev.get("last_dwell_emit", prev["zone_enter_ts"])
            if dwell_sec >= 30 and (frame_ts - last_dwell).total_seconds() >= 30:
                self.events.append(make_event(
                    STORE_ID, camera_id, vid, "ZONE_DWELL",
                    frame_ts, zone_id=zone,
                    dwell_ms=int(dwell_sec * 1000),
                    confidence=confidence, is_staff=is_staff,
                    session_seq=self._seq(vid)
                ))
                prev["last_dwell_emit"] = frame_ts

        prev["last_ts"] = frame_ts

    def mark_lost(self, track_id, frame_ts, camera_id, zones):
        if track_id not in self.tracks:
            return
        state = self.tracks.pop(track_id)
        vid   = self.visitor_map.get(
            track_id, f"VIS_{uuid.uuid4().hex[:6]}"
        )
        # BILLING_QUEUE_ABANDON if lost while in billing
        if state["zone"] == "BILLING" and vid in self.billing_visitors:
            self.billing_visitors.discard(vid)
            self.events.append(make_event(
                STORE_ID, camera_id, vid, "BILLING_QUEUE_ABANDON",
                frame_ts, zone_id="BILLING",
                is_staff=state["is_staff"],
                session_seq=self._seq(vid)
            ))
        self.events.append(make_event(
            STORE_ID, camera_id, vid, "EXIT",
            frame_ts, zone_id=state["zone"],
            is_staff=state["is_staff"],
            session_seq=self._seq(vid)
        ))
        self.exited[vid] = {"ts": frame_ts}


def process_clip(video_path, camera_key, model, layout,
                 clip_start, output_events, conf_threshold=0.4):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open {video_path}")
        return

    fps       = cap.get(cv2.CAP_PROP_FPS) or 15.0
    camera_id = CAMERA_MAP.get(camera_key, "CAM_UNKNOWN")
    tracker   = VisitorTracker()
    active    = set()
    frame_idx = 0

    print(f"[INFO] Processing {Path(video_path).name} → {camera_id}")

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % 5 != 0:
            frame_idx += 1
            continue

        frame_ts = clip_start + timedelta(seconds=frame_idx / fps)
        results  = model.track(
            frame, persist=True, classes=[0],
            conf=conf_threshold, verbose=False
        )
        current  = set()

        if results and results[0].boxes is not None:
            for box in results[0].boxes:
                if box.id is None:
                    continue
                tid  = int(box.id[0])
                bbox = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0])
                current.add(tid)
                tracker.update(
                    tid, bbox, conf, frame,
                    frame_ts, camera_id, layout
                )

        for tid in active - current:
            tracker.mark_lost(tid, frame_ts, camera_id, layout)

        active    = current
        frame_idx += 1

    for tid in list(active):
        final_ts = clip_start + timedelta(seconds=frame_idx / fps)
        tracker.mark_lost(tid, final_ts, camera_id, layout)

    cap.release()
    output_events.extend(tracker.events)
    print(f"[INFO] {camera_id}: {len(tracker.events)} events emitted")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--videos_dir",  required=True)
    parser.add_argument("--layout",      default="app/store_layout.json")
    parser.add_argument("--output",      default="data/events.jsonl")
    parser.add_argument("--clip_start",  default="2026-04-10T10:00:00Z")
    parser.add_argument("--conf",        type=float, default=0.4)
    args = parser.parse_args()

    model      = YOLO("yolov8n.pt")
    layout     = load_layout(args.layout)
    clip_start = datetime.fromisoformat(
        args.clip_start.replace("Z", "+00:00")
    ).replace(tzinfo=timezone.utc)

    videos_dir = Path(args.videos_dir)
    all_events = []

    camera_keywords = {
        "entry":   ["entry", "entrance", "door", "cam1", "cam 1"],
        "floor":   ["floor", "main", "aisle", "cam2", "cam 2", "zone"],
        "billing": ["billing", "counter", "checkout", "cam3", "cam 3"],
    }

    for video_file in sorted(videos_dir.glob("*.mp4")):
        name_lower = video_file.stem.lower()
        camera_key = "floor"
        for key, keywords in camera_keywords.items():
            if any(kw in name_lower for kw in keywords):
                camera_key = key
                break
        process_clip(
            str(video_file), camera_key, model,
            layout, clip_start, all_events, args.conf
        )

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        for event in all_events:
            f.write(json.dumps(event) + "\n")

    print(f"\n✅ Done! {len(all_events)} events → {args.output}")


if __name__ == "__main__":
    main()