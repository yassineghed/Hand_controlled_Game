"""
Adaptive dimming — one tint alpha from frame brightness, EMA-smoothed in the game loop.
Returns alpha in [0.45, 0.72] per spec.
"""

from __future__ import annotations

import cv2
import numpy as np

ALPHA_MIN = 0.45
ALPHA_MAX = 0.72
EMA_BLEND = 0.04  # smooth_alpha = (1-EMA)*smooth + EMA*raw


def compute_overlay_alpha(frame: np.ndarray) -> float:
    """
    Average frame brightness → tint overlay alpha.
    Bright room → stronger tint; dark room → lighter tint.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    brightness = float(gray.mean())
    alpha = ALPHA_MIN + (brightness / 255.0) * (ALPHA_MAX - ALPHA_MIN)
    return float(np.clip(alpha, ALPHA_MIN, ALPHA_MAX))


def apply_tint(frame: np.ndarray, alpha: float) -> None:
    """Blend void #0a0a0e over frame in place."""
    a = float(np.clip(alpha, 0.0, 1.0))
    tint_color = np.array((14, 10, 10), dtype=np.float32)  # #0a0a0e BGR
    roi = frame.astype(np.float32)
    blended = roi * (1.0 - a) + tint_color * a
    frame[:, :] = np.clip(blended, 0, 255).astype(np.uint8)


def apply_extra_darken(frame: np.ndarray, alpha: float) -> None:
    """Additional black overlay (e.g. game over 45%)."""
    a = float(np.clip(alpha, 0.0, 1.0))
    black = np.zeros_like(frame, dtype=np.float32)
    roi = frame.astype(np.float32)
    blended = roi * (1.0 - a) + black * a
    frame[:, :] = np.clip(blended, 0, 255).astype(np.uint8)


class AdaptiveTintSmoother:
    """Holds EMA state; call each frame after compute_overlay_alpha."""

    def __init__(self, initial: float | None = None):
        self.alpha = float(initial if initial is not None else (ALPHA_MIN + ALPHA_MAX) * 0.5)

    def step(self, frame: np.ndarray) -> float:
        raw = compute_overlay_alpha(frame)
        self.alpha = (1.0 - EMA_BLEND) * self.alpha + EMA_BLEND * raw
        self.alpha = float(np.clip(self.alpha, ALPHA_MIN, ALPHA_MAX))
        return self.alpha
