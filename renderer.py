import math

import cv2
import numpy as np


_FONT = cv2.FONT_HERSHEY_SIMPLEX
T_UI_FAST = 12
T_UI_MEDIUM = 26
T_UI_LONG = 52

# --- Unified UI (BGR): same “night arcade” family everywhere ---
UI = {
    "grad_top": (42, 32, 58),
    "grad_bot": (24, 20, 38),
    "card": (44, 40, 56),
    "track": (40, 38, 52),
    "track_rim": (82, 90, 118),
    "title": (200, 248, 255),
    "title_sh": (14, 12, 22),
    "subtitle": (195, 205, 225),
    "subtitle_muted": (155, 168, 188),
    "hint": (165, 174, 196),
    "accent": (255, 215, 120),  # warm highlight (progress sweep, borders)
    "accent_soft": (200, 190, 255),  # combo / highlights without harsh gold
    "ok": (88, 200, 125),
    "border": (90, 86, 110),
    "hand_ok": (72, 210, 255),  # matches title family
    "hand_idle": (58, 54, 64),
    "hand_ring_ok": (210, 235, 255),
    "hand_ring_idle": (92, 96, 108),
    "hud_veil": (32, 34, 48),
    "hud_line": (130, 195, 245),
    "run_bar_fill": (120, 235, 255),
    "hud_chip": (42, 44, 58),
    "outline_soft": (36, 38, 52),
    "life_full": (170, 115, 245),
    "life_mid": (155, 185, 255),
    "life_low": (105, 95, 255),
    "life_off": (62, 60, 74),
    "xp_fill": (255, 195, 110),
    "mission_done": (115, 220, 175),
    "hud_dock": (38, 40, 54),
    "hud_divider": (70, 68, 88),
    "ball_rim": (55, 52, 62),
}

# Hands — warm gold / soft magenta (readable, less harsh than pure primaries)
_HAND_OUTER = (255, 200, 95)
_HAND_INNER = (220, 95, 255)


def _grad_layer(h, w):
    t = np.linspace(0, 1, h, dtype=np.float32).reshape(h, 1, 1)
    top = np.array(UI["grad_top"], dtype=np.float32)
    bot = np.array(UI["grad_bot"], dtype=np.float32)
    g = top * (1.0 - t) + bot * t
    return np.broadcast_to(g, (h, w, 3))


def _hershey_safe(text: str) -> str:
    """
    OpenCV's bundled Hershey fonts only draw ASCII; other codepoints show as '?'.
    Normalize common punctuation, then drop anything else non-ASCII.
    """
    s = str(text)
    for a, b in (
        ("\u2212", "-"),
        ("\u2013", "-"),
        ("\u2014", "-"),
        ("\u00b7", "|"),
        ("\u2022", "*"),
        ("\u2026", "..."),
        ("\u00d7", "x"),
        ("\u2018", "'"),
        ("\u2019", "'"),
        ("\u2020", "+"),
    ):
        s = s.replace(a, b)
    return "".join(c for c in s if ord(c) < 128)


def _shadow_text(frame, text, x, y, scale, thick, color, shadow=None):
    if shadow is None:
        shadow = UI["title_sh"]
    text = _hershey_safe(text)
    cv2.putText(frame, text, (x + 2, y + 2), _FONT, scale, shadow, thick, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), _FONT, scale, color, thick, cv2.LINE_AA)


def _outlined_text(frame, text, x, y, scale, thick, fill, outline=None):
    """Readable on any background — no tinted banner needed."""
    if outline is None:
        outline = UI["outline_soft"]
    text = _hershey_safe(text)
    ot = max(thick + 2, 3)
    cv2.putText(frame, text, (x, y), _FONT, scale, outline, ot, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), _FONT, scale, fill, thick, cv2.LINE_AA)


def _progress_bar(frame, bx, by, bw, bh, tick, fill_t=None):
    """Shared track; determinate fill_t in [0,1] or None = indeterminate sweep."""
    cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), UI["track"], -1)
    cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), UI["track_rim"], 1, cv2.LINE_AA)
    inner_h = max(1, bh - 4)
    if fill_t is not None:
        fw = int((bw - 4) * max(0.0, min(1.0, fill_t)))
        if fw > 2:
            cv2.rectangle(
                frame,
                (bx + 2, by + 2),
                (bx + 2 + fw, by + 2 + inner_h),
                UI["ok"],
                -1,
            )
    else:
        phase = (tick * 5) % (bw + 100)
        seg = min(100, bw // 2)
        x0 = bx + 2 + phase - 40
        x0c = max(bx + 2, x0)
        x1c = min(bx + bw - 2, x0 + seg)
        if x1c > x0c:
            o = frame.copy()
            cv2.rectangle(o, (x0c, by + 2), (x1c, by + 2 + inner_h), UI["accent"], -1)
            cv2.addWeighted(o, 0.5, frame, 0.5, 0, frame)


def _modal_blend_card(frame, x1, y1, x2, y2, cam_weight=0.38):
    roi = frame[y1:y2, x1:x2].copy()
    bh, bw = roi.shape[:2]
    card = np.full((bh, bw, 3), UI["card"], dtype=np.uint8)
    blended = cv2.addWeighted(roi, cam_weight, card, 1.0 - cam_weight, 0)
    frame[y1:y2, x1:x2] = blended


def _modal_border(frame, x1, y1, x2, y2, tick):
    pulse = 0.5 + 0.5 * math.sin(tick * 0.11)
    edge = _lerp_bgr(UI["border"], UI["accent"], 0.28 + 0.22 * pulse)
    cv2.rectangle(frame, (x1, y1), (x2 - 1, y2 - 1), edge, 2, cv2.LINE_AA)


def _draw_top_banner(frame, title, tick=0):
    """Optional tiny title — skip when empty to keep the playfield clear."""
    if not title:
        return
    _outlined_text(frame, title, 12, 24, 0.48, 1, (240, 245, 255))


def _clamp_bgr(b, g, r):
    return (int(max(0, min(255, b))), int(max(0, min(255, g))), int(max(0, min(255, r))))


def _mul_bgr(color, factor):
    return _clamp_bgr(color[0] * factor, color[1] * factor, color[2] * factor)


def _lerp_bgr(a, b, t):
    t = max(0.0, min(1.0, t))
    return _clamp_bgr(
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    )


def _ease_out_cubic(t):
    t = max(0.0, min(1.0, t))
    return 1.0 - pow(1.0 - t, 3)


def _top_veil_gradient(frame, strip_h, vmax=0.24, vmin=0.05):
    """
    Feathered top tint: strongest under the HUD, fades out so the playfield
    stays open and the camera feed feels less “boxed in”.
    """
    h, w = frame.shape[:2]
    strip_h = max(0, min(int(strip_h), h))
    if strip_h <= 0:
        return
    roi = frame[:strip_h, :].astype(np.float32)
    t = np.linspace(1.0, 0.0, strip_h, dtype=np.float32) ** 0.82
    alphas = (vmin + (vmax - vmin) * t).reshape(strip_h, 1, 1)
    veil = np.array(UI["hud_veil"], dtype=np.float32)
    blended = roi * (1.0 - alphas) + veil * alphas
    frame[:strip_h, :] = np.clip(blended, 0, 255).astype(np.uint8)


def _hud_frost_plate(frame, x1, y1, x2, y2, fill_alpha=0.38, chip_color=None):
    """Small frosted panel behind text groups — easier scanning than raw outlines."""
    H, W = frame.shape[:2]
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(W, int(x2)), min(H, int(y2))
    if x2 <= x1 + 2 or y2 <= y1 + 2:
        return
    roi = frame[y1:y2, x1:x2].astype(np.float32)
    base_bgr = chip_color if chip_color is not None else UI["hud_chip"]
    chip_arr = np.array(base_bgr, dtype=np.float32)
    blended = roi * (1.0 - fill_alpha) + chip_arr * fill_alpha
    frame[y1:y2, x1:x2] = blended.astype(np.uint8)
    rim = _lerp_bgr(base_bgr, UI["border"], 0.45)
    cv2.rectangle(frame, (x1, y1), (x2 - 1, y2 - 1), rim, 1, cv2.LINE_AA)


def _hud_dock_gradient(
    frame,
    x1,
    y1,
    x2,
    y2,
    *,
    chip_bgr=None,
    max_alpha=0.58,
    gamma=1.22,
    top_rim=True,
):
    """
    HUD header tint: strong at top, alpha -> 0 at bottom (camera shows through).
    """
    H, W = frame.shape[:2]
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(W, int(x2)), min(H, int(y2))
    if x2 <= x1 + 2 or y2 <= y1 + 2:
        return
    roi = frame[y1:y2, x1:x2].astype(np.float32)
    base_bgr = chip_bgr if chip_bgr is not None else UI["hud_dock"]
    chip_arr = np.array(base_bgr, dtype=np.float32)
    h = y2 - y1
    t = np.linspace(1.0, 0.0, h, dtype=np.float32)
    t = np.power(t, gamma)
    alphas = (max_alpha * t).reshape(h, 1, 1)
    blended = roi * (1.0 - alphas) + chip_arr * alphas
    frame[y1:y2, x1:x2] = np.clip(blended, 0, 255).astype(np.uint8)
    if top_rim:
        rim = _lerp_bgr(base_bgr, UI["border"], 0.55)
        cv2.line(frame, (x1, y1), (x2 - 1, y1), rim, 1, cv2.LINE_AA)


def _fade_vertical_line(frame, x, y0, y1, base_bgr):
    """Column divider: strong at top, blends into the scene toward the bottom."""
    W = frame.shape[1]
    x = int(max(0, min(W - 1, x)))
    y0, y1 = int(y0), int(y1)
    if y1 <= y0 + 2:
        return
    h = y1 - y0
    steps = max(8, min(28, h // 3))
    dv = np.array(base_bgr, dtype=np.float32)
    for i in range(steps):
        ya = int(y0 + (i / steps) * h)
        yb = int(y0 + ((i + 1) / steps) * h)
        if yb <= ya:
            continue
        ym = min(max((ya + yb) // 2, 0), frame.shape[0] - 1)
        pix = frame[ym, x].astype(np.float32)
        fade = (ym - y0) / float(h)
        strength = math.pow(max(0.0, 1.0 - fade), 1.12) * 0.38
        col = pix * (1.0 - strength) + dv * strength
        col_bgr = tuple(int(np.clip(c, 0, 255)) for c in col)
        cv2.line(frame, (x, ya), (x, yb), col_bgr, 1, cv2.LINE_AA)

def _strong_text(frame, text, x, y, scale, fill, outline=None):
    """Heavier glyphs for hero numbers (Hershey has no real bold)."""
    if outline is None:
        outline = UI["outline_soft"]
    text = _hershey_safe(text)
    ot = max(int(scale * 4), 4)
    cv2.putText(frame, text, (x, y), _FONT, scale, outline, ot, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), _FONT, scale, fill, 2, cv2.LINE_AA)
    cv2.putText(frame, text, (x + 1, y), _FONT, scale, fill, 1, cv2.LINE_AA)


def _mission_compact(m):
    """Short HUD lines: id + counts only (full label is clutter during motion)."""
    mid = m.get("id", "")
    prog = int(m.get("progress", 0))
    tgt = int(m.get("target", 0))
    done = bool(m.get("done", False))
    mark = "+" if done else "-"
    if mid == "score":
        body = f"Score {prog}/{tgt}"
    elif mid == "pop":
        body = f"Pops {prog}/{tgt}"
    elif mid == "combo":
        body = f"Combo {prog}/{tgt}"
    elif mid == "heal":
        body = f"Heal {prog}/{tgt}"
    else:
        body = _truncate(m.get("label", ""), 16)
    return f"{mark} {body}"


def _bottom_veil_gradient(frame, strip_h, vmax=0.18, vmin=0.02):
    """Light footer tint so hints read without a hard bar."""
    h, w = frame.shape[:2]
    strip_h = max(0, min(int(strip_h), h))
    if strip_h <= 0:
        return
    y0 = h - strip_h
    roi = frame[y0:h, :].astype(np.float32)
    # strong near bottom edge, fade upward
    t = np.linspace(0.0, 1.0, strip_h, dtype=np.float32) ** 0.9
    alphas = (vmin + (vmax - vmin) * t).reshape(strip_h, 1, 1)
    veil = np.array(UI["hud_veil"], dtype=np.float32)
    blended = roi * (1.0 - alphas) + veil * alphas
    frame[y0:h, :] = np.clip(blended, 0, 255).astype(np.uint8)


def _text_right(frame, text, right_x, y, scale, thick, fill, outline=None):
    (tw, _), _ = cv2.getTextSize(text, _FONT, scale, thick)
    _outlined_text(frame, text, int(right_x - tw), y, scale, thick, fill, outline)


def _truncate(s, max_chars):
    s = str(s)
    if len(s) <= max_chars:
        return s
    return s[: max(0, max_chars - 1)] + "..."


def draw_loading_screen(camera_bgr, tick):
    """
    Same gradient language as in-game banner + modals; full-screen over camera.
    """
    h, w = camera_bgr.shape[:2]
    cam = camera_bgr.astype(np.float32)
    grad = _grad_layer(h, w)
    out = (cam * 0.20 + grad * 0.80).astype(np.uint8)

    title = "HAND POP!"
    sub = "Preparing hand tracking"
    dots = "." * (1 + (tick // 12) % 3)

    (tw, th), _ = cv2.getTextSize(title, _FONT, 2.15, 5)
    tx = (w - tw) // 2
    ty = int(h * 0.36)
    _shadow_text(out, title, tx, ty, 2.15, 5, UI["title"])

    sub_line = sub + dots + " "
    (sw, sh), _ = cv2.getTextSize(sub_line, _FONT, 0.82, 2)
    sx = (w - sw) // 2
    sy = ty + th + 26
    cv2.putText(out, sub_line, (sx, sy), _FONT, 0.82, UI["subtitle"], 2, cv2.LINE_AA)

    bw, bh = int(min(w * 0.44, 540)), 12
    bx = (w - bw) // 2
    by = int(h * 0.56)
    _progress_bar(out, bx, by, bw, bh, tick, fill_t=None)

    for i in range(5):
        a = tick * 0.09 + i * 1.1
        px = int(w * 0.15 + i * (w * 0.17))
        py = int(h * 0.70 + 14 * math.sin(a))
        pr = 4 + int(3 * (0.5 + 0.5 * math.sin(a * 1.3)))
        cv2.circle(out, (px, py), pr, UI["hand_ok"], -1, cv2.LINE_AA)

    hint = "Camera preview - wave when ready"
    (hw, _), _ = cv2.getTextSize(hint, _FONT, 0.52, 1)
    cv2.putText(
        out,
        hint,
        ((w - hw) // 2, h - 26),
        _FONT,
        0.52,
        UI["hint"],
        1,
        cv2.LINE_AA,
    )
    return out


def draw_hands(frame, hands):
    for hand in hands:
        x = int(hand["x"])
        y = int(hand["y"])
        r = int(hand["radius"])
        cv2.circle(frame, (x, y), r, _HAND_OUTER, 2, cv2.LINE_AA)
        cv2.circle(frame, (x, y), max(1, r - 2), _HAND_INNER, 1, cv2.LINE_AA)


def _draw_shaded_sphere(frame, cx, cy, r, color):
    """2.5D ball: ambient shadow, fill, dual specular, soft rim (not harsh black)."""
    if r < 3:
        cv2.circle(frame, (cx, cy), r, color, -1, cv2.LINE_AA)
        return
    sh = _mul_bgr(color, 0.32)
    cv2.circle(
        frame,
        (cx + max(1, r // 7), cy + max(1, r // 4)),
        max(1, r - 2),
        sh,
        -1,
        cv2.LINE_AA,
    )
    cv2.circle(frame, (cx, cy), r, color, -1, cv2.LINE_AA)
    hi = _lerp_bgr(color, (255, 255, 255), 0.5)
    hr = max(3, r // 3)
    cv2.circle(frame, (cx - r // 3, cy - r // 3), hr, hi, -1, cv2.LINE_AA)
    hi2 = _lerp_bgr(color, (255, 255, 255), 0.25)
    cv2.circle(frame, (cx + r // 5, cy + r // 6), max(2, r // 5), hi2, -1, cv2.LINE_AA)
    rim = _lerp_bgr(color, UI["ball_rim"], 0.55)
    cv2.circle(frame, (cx, cy), r, rim, 2, cv2.LINE_AA)


def _draw_health_pickup(frame, cx, cy, r, color, frame_count):
    """Larger green circle with pulsing glow and white + sign in the center."""
    pulse = 1.0 + 0.06 * math.sin(frame_count * 0.12)
    r_draw = int(r * pulse)
    sh = _mul_bgr(color, 0.28)
    cv2.circle(frame, (cx + max(1, r_draw // 8), cy + max(1, r_draw // 5)), max(1, r_draw - 2), sh, -1)
    cv2.circle(frame, (cx, cy), r_draw, color, -1)
    cv2.circle(frame, (cx, cy), r_draw, (255, 255, 255), 2)
    half = max(6, r_draw // 2)
    thick = max(3, r_draw // 6)
    cv2.line(frame, (cx - half, cy), (cx + half, cy), (255, 255, 255), thick, cv2.LINE_AA)
    cv2.line(frame, (cx, cy - half), (cx, cy + half), (255, 255, 255), thick, cv2.LINE_AA)


def draw_balls(frame, balls, frame_count=0):
    """
    Score balls: shaded sphere + dark rim. Health: larger green circle with + sign.
    `ball.color` is still used for confetti on pop.
    """
    for ball in balls:
        color = getattr(ball, "color", (0, 0, 255))
        cx, cy = int(ball.x), int(ball.y)
        r = int(ball.radius)
        if getattr(ball, "is_health_ball", False):
            _draw_health_pickup(frame, cx, cy, r, color, frame_count)
        else:
            _draw_shaded_sphere(frame, cx, cy, r, color)


def draw_confetti(frame, particles):
    for p in particles:
        x = int(p["x"])
        y = int(p["y"])
        size = int(p.get("size", 3))
        if size <= 0:
            size = 1

        max_life = p.get("max_life", p.get("life", 1)) or 1
        life = p.get("life", 0)
        t = max(0.0, min(1.0, float(life) / float(max_life)))
        intensity = 0.25 + 0.75 * t

        color = p.get("color", (255, 255, 255))
        faded_color = (
            int(color[0] * intensity),
            int(color[1] * intensity),
            int(color[2] * intensity),
        )

        cv2.circle(frame, (x, y), size, faded_color, -1)


def _draw_lives_row(frame, lives_left, lives_max, center_y, center_x=None, spacing=24, r=9):
    h, w, _ = frame.shape
    if center_x is None:
        center_x = w // 2
    total_w = (lives_max - 1) * spacing
    x0 = int(center_x - total_w // 2)

    if lives_left >= 4:
        on_color = UI["life_full"]
    elif lives_left >= 2:
        on_color = UI["life_mid"]
    else:
        on_color = UI["life_low"]
    off_color = UI["life_off"]
    rim = (72, 70, 88)

    for i in range(lives_max):
        cx = x0 + i * spacing
        color = on_color if i < lives_left else off_color
        cv2.circle(frame, (cx, center_y), r, color, -1, cv2.LINE_AA)
        cv2.circle(frame, (cx, center_y), r, rim, 1, cv2.LINE_AA)


def _draw_thin_bar(frame, bx, by, bw, bh, fill_t, fill_col, track_col=None, rim_col=None):
    track_col = track_col or UI["track"]
    rim_col = rim_col or UI["track_rim"]
    cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), track_col, -1)
    cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), rim_col, 1, cv2.LINE_AA)
    inner_h = max(1, bh - 4)
    fw = int((bw - 4) * max(0.0, min(1.0, fill_t)))
    if fw > 2:
        cv2.rectangle(
            frame,
            (bx + 2, by + 2),
            (bx + 2 + fw, by + 2 + inner_h),
            fill_col,
            -1,
        )


def draw_unified_hud(frame, game, *, ui_tick, quiet_on, countdown_on, milestone_on):
    """
    Single top dock (one surface, three columns): matches how polished games group HUD.
    Left = performance, center = risk + run flow (lives sized for peripheral vision),
    right = profile + compact tasks. Dividers align scanning; no orphan center strip.
    """
    if getattr(game, "game_over", False):
        return

    h, w, _ = frame.shape
    missions = game.missions or []
    has_missions = len(missions) > 0
    done = sum(1 for m in missions if bool(m.get("done", False)))
    total = max(1, len(missions))
    t_m = done / float(total)

    margin_x = 0
    dock_top = 0
    dock_h = 136 if has_missions else 102
    dock_x1 = margin_x
    dock_x2 = w - margin_x
    dock_bot = dock_top + dock_h

    _hud_dock_gradient(
        frame,
        dock_x1,
        dock_top,
        dock_x2,
        dock_bot,
        chip_bgr=UI["hud_dock"],
        max_alpha=0.60,
        gamma=1.22,
        top_rim=True,
    )
    # Feather a little extra darkness only in the top few px (optional continuity)
    _top_veil_gradient(frame, min(h, dock_top + 6), vmax=0.06, vmin=0.0)

    col_w = max(80, (dock_x2 - dock_x1) // 3)
    split1 = dock_x1 + col_w
    split2 = dock_x1 + 2 * col_w
    if split2 > dock_x2 - 20:
        split2 = dock_x2 - 20
        split1 = dock_x1 + (split2 - dock_x1) // 2
    mid_cx = (split1 + split2) // 2

    div_y0 = dock_top + 8
    div_y1 = dock_bot - 4
    _fade_vertical_line(frame, split1, div_y0, div_y1, UI["hud_divider"])
    _fade_vertical_line(frame, split2, div_y0, div_y1, UI["hud_divider"])

    show_chase = (
        not quiet_on
        and not countdown_on
        and not milestone_on
        and int(game.best_score) > 0
        and 1 <= (int(game.best_score) - int(game.score)) <= 8
    )

    # --- Left column: hero score + record ---
    lx = dock_x1 + 12
    ly = dock_top + 26
    score_txt = _hershey_safe(
        f"{int(game.score):,}" if game.score >= 1000 else str(int(game.score))
    )
    _strong_text(frame, score_txt, lx, ly, 0.76, UI["title"])
    (_, sh_sc), _ = cv2.getTextSize(score_txt, _FONT, 0.76, 2)
    rec_y = ly + sh_sc + 6
    rec = f"Record {int(game.best_score)}"
    _outlined_text(frame, rec, lx, rec_y, 0.38, 1, UI["subtitle"])
    if show_chase:
        gap = int(game.best_score) - int(game.score)
        chase = "1 pt to beat record" if gap == 1 else f"{gap} pts to beat record"
        (_, rh), _ = cv2.getTextSize(rec, _FONT, 0.38, 1)
        _outlined_text(frame, chase, lx, rec_y + rh + 4, 0.32, 1, UI["accent"])

    # --- Center column: lives + run + task bar + combo ---
    cy = dock_top + 44
    _draw_lives_row(frame, game.lives_left, game.lives_max, cy, center_x=mid_cx)
    if missions:
        run_label = f"RUN {int(game.play_level)}  |  {done}/{total} tasks"
    else:
        run_label = f"RUN {int(game.play_level)}"
    sl = 0.34
    (rw, _), _ = cv2.getTextSize(_hershey_safe(run_label), _FONT, sl, 1)
    _outlined_text(frame, run_label, mid_cx - rw // 2, cy + 20, sl, 1, UI["subtitle_muted"])

    bar_w = min(200, col_w - 20)
    bar_h = 7
    bx = int(mid_cx - bar_w // 2)
    by = cy + 30
    _draw_thin_bar(
        frame,
        bx,
        by,
        bar_w,
        bar_h,
        t_m,
        UI["run_bar_fill"],
        track_col=(50, 48, 64),
        rim_col=(98, 102, 128),
    )

    if not countdown_on and int(game.multiplier) > 1 and not milestone_on:
        ctext = f"x{int(game.multiplier)}"
        cs = 0.5
        (cw, _), _ = cv2.getTextSize(ctext, _FONT, cs, 2)
        combo_y = by + bar_h + 16
        _strong_text(frame, ctext, mid_cx - cw // 2, combo_y, cs, UI["accent_soft"])
        if int(game.combo) >= 10 and not quiet_on:
            breathe = 0.92 + 0.08 * math.sin(ui_tick * 0.12)
            hs = "On a roll"
            hs_scale = 0.30
            (hw, _), _ = cv2.getTextSize(hs, _FONT, hs_scale, 1)
            base = UI["accent"]
            col = (
                int(base[0] * breathe),
                int(base[1] * breathe),
                int(base[2] * breathe),
            )
            _outlined_text(frame, hs, mid_cx - hw // 2, combo_y + 18, hs_scale, 1, col)

    # --- Right column: profile, XP, coins, compact missions ---
    rx = dock_x2 - 12
    ry = dock_top + 22
    stage_short = _truncate(game.stage_name, 10)
    prof_line = f"Lv{int(game.level)}  {stage_short}"
    _text_right(frame, prof_line, rx, ry, 0.38, 1, UI["title"])

    xp_next = max(1, int(getattr(game, "xp_next", 1)))
    t_xp = max(0.0, min(1.0, float(game.xp) / float(xp_next)))
    (_, ph_p), _ = cv2.getTextSize(_hershey_safe(prof_line), _FONT, 0.38, 1)
    bar_w2 = min(138, col_w - 22)
    by2 = ry + ph_p + 7
    bx2 = rx - bar_w2
    _draw_thin_bar(
        frame,
        bx2,
        by2,
        bar_w2,
        6,
        t_xp,
        UI["xp_fill"],
        track_col=(50, 48, 64),
        rim_col=(98, 102, 128),
    )

    coin_line = f"{int(game.coins)} coins"
    _text_right(frame, coin_line, rx, by2 + 16, 0.34, 1, UI["accent"])

    if has_missions:
        my = by2 + 30
        for m in missions[:3]:
            line = _mission_compact(m)
            col = UI["mission_done"] if m.get("done") else UI["subtitle"]
            _text_right(frame, line, rx, my, 0.33, 1, col)
            (_, mh), _ = cv2.getTextSize(_hershey_safe(line), _FONT, 0.33, 1)
            my += mh + 4
        _text_right(frame, "[M] reroll", rx, my + 2, 0.28, 1, UI["hint"])


def draw_level_transition_overlay(frame, transition_pending, _transition_frames):
    """Big message only — run progress lives in draw_unified_hud."""
    if not transition_pending:
        return
    h, w, _ = frame.shape
    y0 = int(h * 0.20)
    t1 = "Run complete"
    (tw1, _), _ = cv2.getTextSize(t1, _FONT, 0.58, 2)
    _outlined_text(frame, t1, (w - tw1) // 2, y0, 0.58, 2, UI["accent_soft"])
    t2 = "Preparing the next run..."
    (tw2, _), _ = cv2.getTextSize(t2, _FONT, 0.38, 1)
    _outlined_text(frame, t2, (w - tw2) // 2, y0 + 28, 0.38, 1, UI["subtitle"])
    t3 = "[N] continue"
    (tw3, _), _ = cv2.getTextSize(t3, _FONT, 0.34, 1)
    _outlined_text(frame, t3, (w - tw3) // 2, y0 + 50, 0.34, 1, UI["hint"])


def draw_floating_texts(frame, texts, max_items=6):
    if max_items > 0:
        texts = texts[-max_items:]
    for t in texts:
        cx, y = t["x"], int(t["y"])
        msg = _hershey_safe(t.get("text", ""))
        if not msg:
            continue
        life = t.get("life", 0)
        max_life = t.get("max_life", 1)
        t_norm = life / max(max_life, 1)
        alpha = 0.22 + 0.78 * _ease_out_cubic(t_norm)
        scale = t.get("scale", 0.9)
        thick = max(1, int(scale * 2))
        col = tuple(int(c * alpha) for c in t.get("color", (255, 255, 255)))
        (tw, th), _ = cv2.getTextSize(msg, _FONT, scale, thick)
        x = int(cx) - tw // 2
        _outlined_text(frame, msg, x, y, scale, thick, col)


def draw_countdown(frame, countdown_frames, tick=0):
    total = T_UI_LONG + T_UI_MEDIUM - 6
    if countdown_frames <= 0 or total <= 0:
        return
    phase = (total - countdown_frames) // T_UI_MEDIUM
    if phase == 0:
        label = "3"
    elif phase == 1:
        label = "2"
    elif phase == 2:
        label = "1"
    else:
        label = "GO!"
    h, w, _ = frame.shape
    scale = 2.2 if label != "GO!" else 2.0
    thick = 4
    (tw, th), _ = cv2.getTextSize(label, _FONT, scale, thick)
    x = (w - tw) // 2
    y = (h - th) // 2 + int(th * 0.4)
    pulse = 0.94 + 0.06 * math.sin(tick * 0.14)
    col = (int(245 * pulse), int(250 * pulse), int(255 * pulse))
    _outlined_text(frame, label, x, y, scale, thick, col, outline=UI["outline_soft"])


def draw_combo_milestone(frame, combo_milestone):
    if combo_milestone is None or combo_milestone.get("frames", 0) <= 0:
        return
    m = combo_milestone.get("multiplier", 1)
    f = combo_milestone.get("frames", 0)
    alpha = _ease_out_cubic(min(1.0, f / float(T_UI_MEDIUM)))
    h, w, _ = frame.shape
    text = f"COMBO x{m}!"
    scale = 0.95
    thick = 2
    (tw, th), _ = cv2.getTextSize(text, _FONT, scale, thick)
    x = (w - tw) // 2
    y = int(h * 0.33)
    col = (int(230 * alpha), int(210 * alpha), int(255 * alpha))
    _outlined_text(frame, text, x, y, scale, thick, col, outline=UI["outline_soft"])


def draw_juice_rim(frame, frames_left, tick):
    """Gold pulse on the frame edge for milestones / new best / life pickup."""
    if frames_left <= 0:
        return
    h, w, _ = frame.shape
    pulse = 0.55 + 0.45 * math.sin(tick * 0.22)
    strength = _ease_out_cubic(min(1.0, frames_left / float(T_UI_MEDIUM)))
    thick = max(2, int(2 + 4 * strength * pulse))
    glow = _lerp_bgr((60, 140, 220), (120, 230, 255), pulse)
    cv2.rectangle(frame, (0, 0), (w - 1, h - 1), glow, thick, cv2.LINE_AA)


def draw_game_over(frame, score, best_score, summary=None, tick=0):
    h, w, _ = frame.shape
    box_w = int(min(w * 0.58, 520))
    box_h = 218 if summary else 168
    x1 = (w - box_w) // 2
    y1 = (h - box_h) // 2
    x2, y2 = x1 + box_w, y1 + box_h

    _modal_blend_card(frame, x1, y1, x2, y2, cam_weight=0.42)
    _modal_border(frame, x1, y1, x2, y2, tick)

    title = "GAME OVER"
    (tw, th), _ = cv2.getTextSize(title, _FONT, 1.72, 4)
    tx = (w - tw) // 2
    ty = y1 + int(box_h * 0.22)
    _shadow_text(frame, title, tx, ty, 1.72, 4, UI["title"])

    y_line = ty + th + 16
    sc = f"{int(score):,}" if score >= 1000 else str(int(score))
    (swsc, _), _ = cv2.getTextSize(sc, _FONT, 0.78, 2)
    _outlined_text(frame, sc, (w - swsc) // 2, y_line, 0.78, 2, UI["title"])
    (bw, _), _ = cv2.getTextSize(f"BEST {int(best_score)}", _FONT, 0.42, 1)
    _outlined_text(
        frame,
        f"BEST {int(best_score)}",
        (w - bw) // 2,
        y_line + 22,
        0.42,
        1,
        UI["subtitle"],
    )

    y_stats = y_line + 52
    if summary:
        info = (
            f"Pops {summary.get('pops', 0)}   Miss {summary.get('misses', 0)}   "
            f"{summary.get('accuracy', 0.0):.0f}% acc   Combo {summary.get('best_combo', 0)}"
        )
        (iw, _), _ = cv2.getTextSize(info, _FONT, 0.46, 1)
        _outlined_text(
            frame,
            info,
            (w - iw) // 2,
            y_stats,
            0.46,
            1,
            UI["subtitle"],
        )
        rew = (
            f"Missions +{summary.get('coins_earned', 0)} coins | "
            f"{summary.get('missions_completed', 0)} cleared"
        )
        (rw, _), _ = cv2.getTextSize(rew, _FONT, 0.42, 1)
        _outlined_text(
            frame,
            rew,
            (w - rw) // 2,
            y_stats + 20,
            0.42,
            1,
            (130, 220, 185),
        )
        stage = f"LV {summary.get('level', 1)} | {summary.get('stage', 'Rookie')}"
        (vw, _), _ = cv2.getTextSize(stage, _FONT, 0.42, 1)
        _outlined_text(
            frame,
            stage,
            (w - vw) // 2,
            y_stats + 40,
            0.42,
            1,
            UI["hint"],
        )
        y_bottom = y_stats + 64
    else:
        y_bottom = y_line + 44

    sub = "[R] restart"
    (sw2, _), _ = cv2.getTextSize(sub, _FONT, 0.48, 1)
    _outlined_text(frame, sub, (w - sw2) // 2, min(y2 - 22, y_bottom), 0.48, 1, UI["accent"])


def draw_pregame_overlay(frame, num_hands, steady_count, steady_need, tick):
    """
    Same modal card + progress bar language as loading / game over.
    """
    h, w = frame.shape[:2]
    bw = int(min(w * 0.68, 720))
    bh = int(min(h * 0.34, 280))
    x1 = (w - bw) // 2
    y1 = (h - bh) // 2
    x2, y2 = x1 + bw, y1 + bh

    _modal_blend_card(frame, x1, y1, x2, y2, cam_weight=0.38)
    _modal_border(frame, x1, y1, x2, y2, tick)

    title = "Show both hands to start"
    sub = "Hold them steady - gold rings show when each hand is tracked."

    (tw, th), _ = cv2.getTextSize(title, _FONT, 0.95, 2)
    tx = (w - tw) // 2
    ty = y1 + int(bh * 0.20)
    _shadow_text(frame, title, tx, ty, 0.95, 2, UI["title"])

    sub_scale = 0.52
    lines = []
    acc = ""
    for word in sub.split():
        test = (acc + " " + word).strip()
        (sw, _), _ = cv2.getTextSize(test, _FONT, sub_scale, 1)
        if sw > bw - 36 and acc:
            lines.append(acc)
            acc = word
        else:
            acc = test
    if acc:
        lines.append(acc)

    ly = ty + th + 18
    for line in lines[:3]:
        (lw, lh), _ = cv2.getTextSize(line, _FONT, sub_scale, 1)
        cv2.putText(
            frame,
            line,
            ((w - lw) // 2, ly),
            _FONT,
            sub_scale,
            UI["subtitle"],
            1,
            cv2.LINE_AA,
        )
        ly += lh + 6

    cx = w // 2
    base_y = y1 + int(bh * 0.62)
    gap = 88
    for i in range(2):
        hx = cx - gap // 2 - 22 + i * gap
        hy = base_y
        ok = num_hands > i
        fill = UI["hand_ok"] if ok else UI["hand_idle"]
        ring = UI["hand_ring_ok"] if ok else UI["hand_ring_idle"]
        cv2.circle(frame, (hx, hy), 22, fill, -1, cv2.LINE_AA)
        cv2.circle(frame, (hx, hy), 22, ring, 2, cv2.LINE_AA)
        label = f"{i + 1}"
        (lw, lh), _ = cv2.getTextSize(label, _FONT, 0.55, 1)
        cv2.putText(
            frame,
            label,
            (hx - lw // 2, hy + lh // 2),
            _FONT,
            0.55,
            UI["title_sh"] if ok else UI["hint"],
            1,
            cv2.LINE_AA,
        )

    status = f"{min(num_hands, 2)} / 2 hands visible"
    (uw, uh), _ = cv2.getTextSize(status, _FONT, 0.62, 2)
    st_col = _lerp_bgr(UI["subtitle"], UI["ok"], 0.55) if num_hands >= 2 else UI["subtitle"]
    cv2.putText(
        frame,
        status,
        ((w - uw) // 2, base_y + 42),
        _FONT,
        0.62,
        st_col,
        2,
        cv2.LINE_AA,
    )

    if num_hands >= 2 and steady_need > 0:
        bar_w = bw - 48
        bar_h = 10
        bx = (w - bar_w) // 2
        by = y2 - 30
        fill_t = steady_count / float(steady_need)
        _progress_bar(frame, bx, by, bar_w, bar_h, tick, fill_t=fill_t)
        cv2.putText(
            frame,
            "Hold steady...",
            (bx, by - 8),
            _FONT,
            0.5,
            UI["hint"],
            1,
            cv2.LINE_AA,
        )


def draw_instructions(frame, game, tick=0):
    h, w, _ = frame.shape
    _bottom_veil_gradient(frame, 40, vmax=0.16, vmin=0.02)
    if game.lives_left >= game.lives_max:
        extra = " | Green + after first miss"
    else:
        extra = " | Green + = +1 life"
    line = f"Pop balls{extra}  |  [M] reroll  |  [N] skip wait"
    s, thick = 0.34, 1
    for _ in range(14):
        (tw, _), _ = cv2.getTextSize(line, _FONT, s, thick)
        if tw <= w - 24:
            break
        s = max(0.28, s - 0.02)
    _outlined_text(frame, line, (w - tw) // 2, h - 14, s, thick, UI["subtitle_muted"])


def render(
    frame,
    game,
    hands,
    *,
    game_active=True,
    pregame_steady=0,
    pregame_steady_need=18,
    ui_tick=0,
):
    _draw_top_banner(frame, "", ui_tick)
    draw_hands(frame, hands)

    if not game_active:
        draw_pregame_overlay(
            frame,
            len(hands),
            pregame_steady,
            pregame_steady_need,
            ui_tick,
        )
        return

    countdown_on = game.countdown_frames > 0
    milestone_on = game.combo_milestone is not None and game.combo_milestone.get("frames", 0) > 0
    quiet_on = getattr(game, "quiet_frames", 0) > 0

    draw_balls(frame, game.balls, game.frame_count)
    draw_confetti(frame, game.confetti_particles)

    if not game.game_over:
        draw_unified_hud(
            frame,
            game,
            ui_tick=ui_tick,
            quiet_on=quiet_on,
            countdown_on=countdown_on,
            milestone_on=milestone_on,
        )
    if not game.game_over:
        draw_level_transition_overlay(
            frame,
            game.level_transition_pending,
            game.level_complete_frames,
        )
    draw_floating_texts(frame, game.floating_texts, max_items=2 if quiet_on else 6)

    if countdown_on:
        draw_countdown(frame, game.countdown_frames, ui_tick)
    elif milestone_on:
        draw_combo_milestone(frame, game.combo_milestone)

    if game.juice_rim_frames > 0 and not countdown_on and not quiet_on:
        draw_juice_rim(frame, game.juice_rim_frames, ui_tick)

    if game.game_over:
        draw_game_over(frame, game.score, game.best_score, game.session_summary, ui_tick)
    elif not countdown_on and not quiet_on:
        draw_instructions(frame, game, ui_tick)
