import math
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

# Edge weights: bottom is rarer (hands usually upper / mid; “from below” is harder to read).
_EDGE_WEIGHTS = ("top", "bottom", "left", "right")
_EDGE_PROBS = (0.34, 0.14, 0.26, 0.26)


def _cap_cross_vs_in(v_in, v_cross, max_ratio=0.88):
    """Limit cross-axis speed so trajectories stay aimable (cone into playfield)."""
    if abs(v_in) < 1e-6:
        return 0.0
    if abs(v_cross) > abs(v_in) * max_ratio:
        return math.copysign(abs(v_in) * max_ratio, v_cross)
    return v_cross


def _speed_mult(difficulty):
    """Soft cap — tuned for webcam + hand tracking reaction time."""
    d = max(0.5, float(difficulty))
    return min(2.35, d)


# Global scale on top of difficulty (pixels/frame feel ~30% slower than before).
_BALL_SPEED_SCALE = 0.68


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
        spd = _speed_mult(difficulty)
        cross_scale = 0.72 + 0.28 * min(difficulty / 3.0, 1.0)

        self.spawn_time = float(spawn_time)
        self.min_visible_seconds = float(min_visible_seconds)
        self.min_travel_fraction = float(min_travel_fraction)
        self.start_x = 0.0
        self.start_y = 0.0

        r = int(self.radius)
        mg_x = max(r + 24, min(80, width // 4))
        mg_y = max(r + 24, min(80, height // 4))
        mg_x = min(mg_x, width // 2 - 8)
        mg_y = min(mg_y, height // 2 - 8)

        # Bias spawn toward middle of edge (more time in frame before exit).
        def _edge_pos(aw, margin, bias=0.62):
            lo, hi = margin, aw - margin
            if lo >= hi:
                return aw // 2
            span = hi - lo
            if random.random() < bias:
                mid = (lo + hi) / 2
                quarter = span * 0.22
                return int(random.uniform(mid - quarter, mid + quarter))
            return random.randint(lo, hi)

        side = random.choices(_EDGE_WEIGHTS, weights=_EDGE_PROBS, k=1)[0]

        if side == "top":
            self.x = _edge_pos(width, mg_x)
            self.y = -self.radius
            vy = random.uniform(5.4, 8.2) * spd
            vx = random.uniform(-4.2, 4.2) * cross_scale
            vx = _cap_cross_vs_in(vy, vx, 0.88)
            self.vx, self.vy = vx * _BALL_SPEED_SCALE, vy * _BALL_SPEED_SCALE
        elif side == "bottom":
            self.x = _edge_pos(width, mg_x)
            self.y = height + self.radius
            vy = -random.uniform(5.4, 8.2) * spd
            vx = random.uniform(-4.2, 4.2) * cross_scale
            vx = _cap_cross_vs_in(vy, vx, 0.88)
            self.vx, self.vy = vx * _BALL_SPEED_SCALE, vy * _BALL_SPEED_SCALE
        elif side == "left":
            self.x = -self.radius
            self.y = _edge_pos(height, mg_y)
            vx = random.uniform(4.5, 7.2) * spd
            vy = random.uniform(-3.8, 3.8) * cross_scale
            vy = _cap_cross_vs_in(vx, vy, 0.88)
            self.vx, self.vy = vx * _BALL_SPEED_SCALE, vy * _BALL_SPEED_SCALE
        else:  # right
            self.x = width + self.radius
            self.y = _edge_pos(height, mg_y)
            vx = -random.uniform(4.5, 7.2) * spd
            vy = random.uniform(-3.8, 3.8) * cross_scale
            vy = _cap_cross_vs_in(vx, vy, 0.88)
            self.vx, self.vy = vx * _BALL_SPEED_SCALE, vy * _BALL_SPEED_SCALE

        self.start_x = float(self.x)
        self.start_y = float(self.y)

    def age_seconds(self, now):
        return float(now) - self.spawn_time

    def update(self):
        self.x += self.vx
        self.y += self.vy