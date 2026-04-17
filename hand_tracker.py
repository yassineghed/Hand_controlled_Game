import math
import threading
import time

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


class HandTracker:

    def __init__(self, model_path):
        self._lock = threading.Lock()
        self._last_hands = []
        self._last_ts = 0
        self._frame_w = 1280
        self._frame_h = 720

        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=mp.tasks.vision.RunningMode.LIVE_STREAM,
            num_hands=2,
            min_hand_detection_confidence=0.3,
            min_hand_presence_confidence=0.3,
            min_tracking_confidence=0.2,
            result_callback=self._on_result,
        )
        self.landmarker = vision.HandLandmarker.create_from_options(options)

    def _on_result(self, result, output_image, timestamp_ms):
        hands = []
        if result and getattr(result, "hand_landmarks", None):
            w, h = self._frame_w, self._frame_h
            for hand in result.hand_landmarks:
                vis = [
                    float(lm.visibility)
                    for lm in hand
                    if getattr(lm, "visibility", None) is not None
                ]
                conf = sum(vis) / len(vis) if vis else 0.75
                conf = max(0.35, min(1.0, conf * 1.15))

                cx = (hand[0].x + hand[5].x + hand[9].x + hand[13].x + hand[17].x) / 5
                cy = (hand[0].y + hand[5].y + hand[9].y + hand[13].y + hand[17].y) / 5

                dx = (hand[5].x - hand[17].x) * w
                dy = (hand[5].y - hand[17].y) * h

                hands.append({
                    "x": cx * w,
                    "y": cy * h,
                    "radius": math.sqrt(dx * dx + dy * dy) * 0.8,
                    "confidence": conf,
                })
        with self._lock:
            self._last_hands = hands

    def _submit_frame(self, frame):
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (w // 2, h // 2))
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        ts = max(self._last_ts + 1, int(time.perf_counter() * 1000))
        self._last_ts = ts
        self.landmarker.detect_async(mp_image, ts)

    def detect(self, frame):
        h, w = frame.shape[:2]
        self._frame_w = w
        self._frame_h = h

        # Submit frame for detection in background — never blocks the game loop
        threading.Thread(target=self._submit_frame, args=(frame,), daemon=True).start()

        with self._lock:
            return list(self._last_hands)
