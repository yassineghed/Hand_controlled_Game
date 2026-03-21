import math

import cv2
import numpy as np


_FONT = cv2.FONT_HERSHEY_SIMPLEX

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
    "hint": (165, 174, 196),
    "accent": (255, 215, 120),  # warm highlight (progress sweep, borders)
    "ok": (88, 200, 125),
    "border": (90, 86, 110),
    "hand_ok": (72, 210, 255),  # matches title family
    "hand_idle": (58, 54, 64),
    "hand_ring_ok": (210, 235, 255),
    "hand_ring_idle": (92, 96, 108),
}

# Hands — cyan / magenta (distinct from life green)
_HAND_OUTER = (255, 220, 0)
_HAND_INNER = (255, 0, 180)


def _grad_layer(h, w):
    t = np.linspace(0, 1, h, dtype=np.float32).reshape(h, 1, 1)
    top = np.array(UI["grad_top"], dtype=np.float32)
    bot = np.array(UI["grad_bot"], dtype=np.float32)
    g = top * (1.0 - t) + bot * t
    return np.broadcast_to(g, (h, w, 3))


def _shadow_text(frame, text, x, y, scale, thick, color, shadow=None):
    if shadow is None:
        shadow = UI["title_sh"]
    cv2.putText(frame, text, (x + 2, y + 2), _FONT, scale, shadow, thick, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), _FONT, scale, color, thick, cv2.LINE_AA)


def _outlined_text(frame, text, x, y, scale, thick, fill, outline=None):
    """Readable on any background — no tinted banner needed."""
    if outline is None:
        outline = (22, 20, 32)
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
    """Gameplay: no bar — title floats on camera. (tick unused; kept for API.)"""
    _outlined_text(frame, title, 16, 40, 0.72, 2, (248, 252, 255))


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

    hint = "Camera preview — wave when ready"
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
        cv2.circle(frame, (x, y), r, _HAND_OUTER, 3)
        cv2.circle(frame, (x, y), max(1, r - 2), _HAND_INNER, 1)


def _draw_shaded_sphere(frame, cx, cy, r, color):
    """Simple 2.5D ball: soft shadow, base fill, specular blob."""
    if r < 3:
        cv2.circle(frame, (cx, cy), r, color, -1)
        return
    sh = _mul_bgr(color, 0.28)
    cv2.circle(frame, (cx + max(1, r // 8), cy + max(1, r // 5)), max(1, r - 2), sh, -1)
    cv2.circle(frame, (cx, cy), r, color, -1)
    hi = _lerp_bgr(color, (255, 255, 255), 0.55)
    hr = max(3, r // 3)
    cv2.circle(frame, (cx - r // 3, cy - r // 3), hr, hi, -1)
    cv2.circle(frame, (cx, cy), r, (40, 40, 40), 2)


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


def draw_score(frame, score, best_score):
    h, w, _ = frame.shape
    scale = 0.75
    thickness = 2
    s_text = f"Score {score}"
    b_text = f"Best {best_score}"
    (sw, _), _ = cv2.getTextSize(s_text, _FONT, scale, thickness)
    (bw, _), _ = cv2.getTextSize(b_text, _FONT, scale, thickness)
    _outlined_text(frame, s_text, 16, 40, scale, thickness, (252, 252, 255))
    _outlined_text(frame, b_text, w - bw - 16, 40, scale, thickness, (200, 220, 255))


def draw_combo(frame, combo, multiplier):
    if multiplier <= 1:
        return
    h, w, _ = frame.shape
    text = f"x{multiplier}"
    scale = 0.95
    thickness = 2
    (tw, _), _ = cv2.getTextSize(text, _FONT, scale, thickness)
    x = int((w - tw) / 2)
    y = 92
    _outlined_text(frame, text, x, y, scale, thickness, (200, 230, 255))


def draw_floating_texts(frame, texts):
    for t in texts:
        cx, y = t["x"], int(t["y"])
        life = t.get("life", 0)
        max_life = t.get("max_life", 1)
        alpha = max(0.35, life / max(max_life, 1))
        scale = t.get("scale", 0.9)
        thick = max(1, int(scale * 2))
        col = tuple(int(c * alpha) for c in t.get("color", (255, 255, 255)))
        (tw, th), _ = cv2.getTextSize(t["text"], _FONT, scale, thick)
        x = int(cx) - tw // 2
        _outlined_text(frame, t["text"], x, y, scale, thick, col)


def draw_countdown(frame, countdown_frames, tick=0):
    total = 72
    if countdown_frames <= 0 or total <= 0:
        return
    phase = (total - countdown_frames) // 18
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
    pulse = 0.9 + 0.15 * math.sin(tick * 0.2)
    col = (int(255 * pulse), int(248 * pulse), int(220 * pulse))
    _outlined_text(frame, label, x, y, scale, thick, col, outline=(25, 20, 35))


def draw_combo_milestone(frame, combo_milestone):
    if combo_milestone is None or combo_milestone.get("frames", 0) <= 0:
        return
    m = combo_milestone.get("multiplier", 1)
    f = combo_milestone.get("frames", 0)
    alpha = min(1.0, f / 12.0)
    h, w, _ = frame.shape
    text = f"COMBO x{m}!"
    scale = 1.1
    thick = 3
    (tw, th), _ = cv2.getTextSize(text, _FONT, scale, thick)
    x = (w - tw) // 2
    y = int(h * 0.35)
    col = (int(255 * alpha), int(230 * alpha), int(120 * alpha))
    _outlined_text(frame, text, x, y, scale, thick, col)


def draw_lives(frame, lives_left, lives_max):
    h, w, _ = frame.shape
    spacing = 20
    r = 7
    total_w = (lives_max - 1) * spacing
    x0 = (w - total_w) // 2
    y = 58

    if lives_left >= 4:
        on_color = (0, 220, 0)
    elif lives_left >= 2:
        on_color = (0, 220, 220)
    else:
        on_color = (0, 0, 255)
    off_color = (58, 56, 62)

    for i in range(lives_max):
        cx = x0 + i * spacing
        color = on_color if i < lives_left else off_color
        cv2.circle(frame, (cx, y), r, color, -1)


def draw_game_over(frame, score, best_score, tick=0):
    h, w, _ = frame.shape
    box_w = int(min(w * 0.62, 560))
    box_h = 188
    x1 = (w - box_w) // 2
    y1 = (h - box_h) // 2
    x2, y2 = x1 + box_w, y1 + box_h

    _modal_blend_card(frame, x1, y1, x2, y2, cam_weight=0.36)
    _modal_border(frame, x1, y1, x2, y2, tick)

    title = "GAME OVER"
    (tw, th), _ = cv2.getTextSize(title, _FONT, 1.85, 4)
    tx = (w - tw) // 2
    ty = y1 + int(box_h * 0.28)
    _shadow_text(frame, title, tx, ty, 1.85, 4, UI["title"])

    scores = f"Score {score}  |  Best {best_score}"
    (sw, sh), _ = cv2.getTextSize(scores, _FONT, 0.72, 2)
    cv2.putText(
        frame,
        scores,
        ((w - sw) // 2, ty + th + 18),
        _FONT,
        0.72,
        UI["subtitle"],
        2,
        cv2.LINE_AA,
    )

    subtitle = "Press R to restart"
    (sw2, sh2), _ = cv2.getTextSize(subtitle, _FONT, 0.88, 2)
    cv2.putText(
        frame,
        subtitle,
        ((w - sw2) // 2, ty + th + 18 + sh + 20),
        _FONT,
        0.88,
        UI["subtitle"],
        2,
        cv2.LINE_AA,
    )


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
    sub = "Hold them in front of the camera — cyan rings appear when we track each hand."

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
            "Hold steady…",
            (bx, by - 8),
            _FONT,
            0.5,
            UI["hint"],
            1,
            cv2.LINE_AA,
        )


def draw_instructions(frame, game, tick=0):
    h, w, _ = frame.shape
    y1 = h - 34
    y2 = h - 12
    _outlined_text(
        frame,
        "Pop colored balls for score",
        18,
        y1,
        0.52,
        1,
        (232, 236, 245),
    )
    if game.lives_left >= game.lives_max:
        line2 = "Green + life pickups unlock after you lose a heart"
    else:
        line2 = "Green + = +1 life (missing it is OK)"
    s2 = 0.52
    thick = 1
    for _ in range(12):
        (tw2, _), _ = cv2.getTextSize(line2, _FONT, s2, thick)
        if tw2 <= w - 32:
            break
        s2 = max(0.4, s2 - 0.035)
    _outlined_text(frame, line2, 18, y2, s2, thick, (210, 218, 232))


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

    draw_balls(frame, game.balls, game.frame_count)
    draw_confetti(frame, game.confetti_particles)
    draw_score(frame, game.score, game.best_score)
    draw_combo(frame, game.combo, game.multiplier)
    draw_lives(frame, game.lives_left, game.lives_max)
    draw_floating_texts(frame, game.floating_texts)
    draw_combo_milestone(frame, game.combo_milestone)
    draw_countdown(frame, game.countdown_frames, ui_tick)

    if game.game_over:
        draw_game_over(frame, game.score, game.best_score, ui_tick)
    else:
        draw_instructions(frame, game, ui_tick)