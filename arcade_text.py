"""
Typography: DM Sans via cv2.freetype when a .ttf is present; else Hershey fallback.

Place DMSans-Light.ttf (300) or variable font next to main.py, or set ARCADE_FONT_PATH.
Google Fonts import (web): see design_tokens.GOOGLE_FONTS_DM_SANS_CSS
"""

from __future__ import annotations

from pathlib import Path

import cv2

import design_tokens as T

_FONT = cv2.FONT_HERSHEY_SIMPLEX
_FALLBACK_SCALE = {
    "score_num": 0.62,
    "score_pop": 0.48,
    "combo": 0.22,
    "label": 0.20,
    "goal": 0.20,
    "hint_key": 0.18,
    "hint_desc": 0.20,
}

_ft_instance = None
_ft_path: Path | None = None


def _try_load_freetype():
    global _ft_instance, _ft_path
    if _ft_instance is not None:
        return _ft_instance
    base = Path(__file__).resolve().parent
    candidates = [
        base / "DMSans-Light.ttf",
        base / "fonts" / "DMSans-Light.ttf",
        base / "DMSans-Regular.ttf",
        base / "fonts" / "DMSans-Regular.ttf",
    ]
    for p in candidates:
        if not p.is_file():
            continue
        try:
            ft = cv2.freetype.createFreeType2()
            ft.loadFontData(str(p), 0)
            _ft_instance = ft
            _ft_path = p
            return ft
        except (cv2.error, AttributeError):
            continue
    _ft_instance = False
    return None


def has_freetype_font() -> bool:
    ft = _try_load_freetype()
    return ft is not None and ft is not False


def put_text(
    frame,
    text: str,
    x: int,
    y: int,
    *,
    px_height: int,
    color_bgr,
    italic: bool = False,
    thickness: int = -1,
    line_type=cv2.LINE_AA,
):
    """
    Baseline y (OpenCV convention). px_height ≈ cap height target.
    """
    text = str(text)
    if not text:
        return
    ft = _try_load_freetype()
    if ft and ft is not False:
        try:
            th = max(1, px_height // 20) if thickness < 0 else max(1, thickness)
            # OpenCV freetype: no italic flag — use Light/Italic TTF if needed.
            ft.putText(
                frame,
                text,
                (int(x), int(y)),
                int(px_height),
                color_bgr,
                th,
                line_type,
                False,
            )
            return
        except (cv2.error, TypeError, AttributeError):
            pass
    # Hershey fallback — weight contrast via thickness; italic N/A
    key = "score_num"
    if px_height <= 12:
        key = "hint_key"
    elif px_height <= 15:
        key = "combo"
    elif px_height <= 20:
        key = "score_pop"
    scale = _FALLBACK_SCALE.get(key, 0.4)
    th = 1 if px_height < 14 else 2
    cv2.putText(frame, text, (int(x), int(y)), _FONT, scale, color_bgr, th, line_type)
