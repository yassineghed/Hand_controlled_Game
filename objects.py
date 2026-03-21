import random

import cv2
import numpy as np


def _bgr_scale_saturation(bgr, sat_scale):
    """OpenCV HSV: S channel 0–255. sat_scale 1.2 = +20% saturation."""
    pixel = np.uint8([[bgr]])
    hsv = cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[0, 0, 1] = np.clip(hsv[0, 0, 1] * sat_scale, 0, 255)
    out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)[0, 0]
    return tuple(int(c) for c in out)


def _bgr_more_pastel(bgr, sat_scale=0.8, white_blend=0.12):
    """~20% softer: lower saturation by 20%, slight white blend (health pickup)."""
    pixel = np.uint8([[bgr]])
    hsv = cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[0, 0, 1] = np.clip(hsv[0, 0, 1] * sat_scale, 0, 255)
    mid = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)[0, 0]
    w = np.array([255.0, 255.0, 255.0], dtype=np.float32)
    out = mid * (1.0 - white_blend) + w * white_blend
    return tuple(int(np.clip(c, 0, 255)) for c in out)


# BGR bases (pastel); +20% saturation applied for clearer targets on camera.
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

# Softer mint green than vivid (0, 220, 0); still reads as “life”.
HEALTH_BALL_COLOR = _bgr_more_pastel((0, 220, 0), sat_scale=0.8, white_blend=0.12)


class Ball:
    def __init__(
        self,
        width,
        height,
        difficulty=1.0,
        spawn_time=0.0,
        min_visible_seconds=3 / 5,
        min_travel_fraction=0.15,
        is_health_ball=False,
    ):
        self.is_health_ball = bool(is_health_ball)
        self.radius = random.randint(34, 48) if self.is_health_ball else random.randint(20, 35)
        self.color = HEALTH_BALL_COLOR if self.is_health_ball else random.choice(BALL_COLORS)

        difficulty = max(0.5, float(difficulty))

        self.spawn_time = float(spawn_time)
        self.min_visible_seconds = float(min_visible_seconds)
        self.min_travel_fraction = float(min_travel_fraction)
        # Used to ensure a ball doesn't get removed "too quickly".
        self.start_x = 0.0
        self.start_y = 0.0

        # Spawn balls from different screen edges with higher speeds
        # (more variety than only top/left/right)
        side = random.choice(["top", "bottom", "left", "right"])

        if side == "top":
            self.x = random.randint(50, width - 50)
            self.y = -self.radius
            self.vx = random.uniform(-6, 6) * (0.8 + 0.2 * difficulty)
            self.vy = random.uniform(8, 12) * difficulty
        elif side == "bottom":
            self.x = random.randint(50, width - 50)
            self.y = height + self.radius
            self.vx = random.uniform(-6, 6) * (0.8 + 0.2 * difficulty)
            self.vy = random.uniform(-12, -8) * difficulty
        elif side == "left":
            self.x = -self.radius
            self.y = random.randint(50, height - 50)
            self.vx = random.uniform(6, 10) * difficulty
            self.vy = random.uniform(-4, 4) * (0.7 + 0.3 * difficulty)
        else:  # right
            self.x = width + self.radius
            self.y = random.randint(50, height - 50)
            self.vx = random.uniform(-10, -6) * difficulty
            self.vy = random.uniform(-4, 4) * (0.7 + 0.3 * difficulty)

        self.start_x = float(self.x)
        self.start_y = float(self.y)

    def age_seconds(self, now):
        return float(now) - self.spawn_time

    def update(self):
        self.x += self.vx
        self.y += self.vy