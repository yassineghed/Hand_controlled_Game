import random

import cv2
import numpy as np


def _bgr_scale_saturation(bgr, sat_scale):
    pixel = np.uint8([[bgr]])
    hsv = cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[0, 0, 1] = np.clip(hsv[0, 0, 1] * sat_scale, 0, 255)
    out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)[0, 0]
    return tuple(int(c) for c in out)


def _bgr_more_pastel(bgr, sat_scale=0.8, white_blend=0.12):
    pixel = np.uint8([[bgr]])
    hsv = cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[0, 0, 1] = np.clip(hsv[0, 0, 1] * sat_scale, 0, 255)
    mid = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)[0, 0]
    w = np.array([255.0, 255.0, 255.0], dtype=np.float32)
    out = mid * (1.0 - white_blend) + w * white_blend
    return tuple(int(np.clip(c, 0, 255)) for c in out)


_BALL_PASTEL_BASES = [
    (180, 230, 255),
    (220, 230, 200),
    (180, 210, 255),
    (230, 200, 240),
    (240, 220, 200),
    (200, 200, 255),
    (210, 220, 235),
    (200, 240, 230),
    (225, 210, 230),
]
BALL_COLORS = [_bgr_scale_saturation(c, 1.2) for c in _BALL_PASTEL_BASES]
HEALTH_BALL_COLOR = _bgr_more_pastel((0, 220, 0), sat_scale=0.8, white_blend=0.12)

# Bomb: dark red-orange; Gold: bright gold
BOMB_COLOR = (30, 30, 200)       # BGR deep red
GOLD_COLOR = (30, 200, 255)      # BGR gold/amber


class Ball:
    """
    Z-based lane runner ball.
    z=0.0 = vanishing point (far), z=1.0 = player plane.

    ball_type: "normal" | "bomb" | "gold" | "health"
      - bomb : hitting = -2 lives + combo break; passing = -1 life
      - gold : hitting = +3 pts; passing = -1 life
      - health: hitting = +1 life; passing = safe (no penalty)
    """

    def __init__(
        self,
        lane: int,
        z_speed: float,
        spawn_time: float = 0.0,
        ball_type: str = "normal",
    ):
        self.lane = int(lane)
        self.z = 0.0
        self.z_speed = float(z_speed)
        self.spawn_time = float(spawn_time)
        self.ball_type = str(ball_type)
        self.is_health_ball = (ball_type == "health")

        if ball_type == "bomb":
            self.color = BOMB_COLOR
        elif ball_type == "gold":
            self.color = GOLD_COLOR
        elif ball_type == "health":
            self.color = HEALTH_BALL_COLOR
        else:
            self.color = random.choice(BALL_COLORS)

        # Screen-space position + radius — updated each frame from LaneSystem
        self.x = 0.0
        self.y = 0.0
        self.radius = 3

        self._near_miss_cd = 0

    def age_seconds(self, now: float) -> float:
        return float(now) - self.spawn_time

    def update(self):
        self.z += self.z_speed
