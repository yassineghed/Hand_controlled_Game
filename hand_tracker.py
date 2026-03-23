import mediapipe as mp
import cv2
import math
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


class HandTracker:

    def __init__(self, model_path):

        base_options = python.BaseOptions(model_asset_path=model_path)

        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            num_hands=2,
            min_hand_detection_confidence=0.3,
            min_hand_presence_confidence=0.3,
            min_tracking_confidence=0.2
        )
        self.landmarker = vision.HandLandmarker.create_from_options(options)


    def detect(self, frame):

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb
        )

        result = self.landmarker.detect(mp_image)

        if not result or not getattr(result, "hand_landmarks", None):
            return []

        hands = []

        h, w, _ = frame.shape

        for i, hand in enumerate(result.hand_landmarks):
            vis = []
            for lm in hand:
                v = getattr(lm, "visibility", None)
                if v is not None:
                    vis.append(float(v))
            conf = sum(vis) / len(vis) if vis else 0.75
            conf = max(0.35, min(1.0, conf * 1.15))

            cx = (
                hand[0].x +
                hand[5].x +
                hand[9].x +
                hand[13].x +
                hand[17].x
            ) / 5

            cy = (
                hand[0].y +
                hand[5].y +
                hand[9].y +
                hand[13].y +
                hand[17].y
            ) / 5

            x = cx * w
            y = cy * h

            dx = (hand[5].x - hand[17].x) * w
            dy = (hand[5].y - hand[17].y) * h

            radius = math.sqrt(dx*dx + dy*dy) * 0.8

            hands.append({
                "x": x,
                "y": y,
                "radius": radius,
                "confidence": conf,
            })

        return hands