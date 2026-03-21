import math

import cv2
import numpy as np


# BGR — hands never use green (reserved for life / health pickups).
_HAND_OUTER = (255, 220, 0)   # bright cyan
_HAND_INNER = (255, 0, 180)   # magenta accent


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
    Full-screen loading panel over a dimmed camera feed (or solid black).
    `tick` increments each frame for animation.
    """
    h, w = camera_bgr.shape[:2]
    cam = camera_bgr.astype(np.float32)
    tcol = np.linspace(0, 1, h, dtype=np.float32).reshape(h, 1, 1)
    top = np.array([42, 32, 58], dtype=np.float32)
    bot = np.array([24, 20, 38], dtype=np.float32)
    grad = top * (1.0 - tcol) + bot * tcol
    grad = np.broadcast_to(grad, (h, w, 3))
    out = (cam * 0.18 + grad * 0.82).astype(np.uint8)

    font = cv2.FONT_HERSHEY_SIMPLEX
    title = "HAND POP!"
    sub = "Preparing hand tracking"
    dots = "." * (1 + (tick // 12) % 3)

    (tw, th), bl = cv2.getTextSize(title, font, 2.2, 5)
    tx = (w - tw) // 2
    ty = int(h * 0.38)
    cv2.putText(out, title, (tx + 3, ty + 3), font, 2.2, (12, 10, 20), 5, cv2.LINE_AA)
    cv2.putText(out, title, (tx, ty), font, 2.2, (200, 255, 255), 5, cv2.LINE_AA)

    (sw, sh), _ = cv2.getTextSize(sub + "...", font, 0.85, 2)
    sx = (w - sw) // 2
    sy = ty + th + 28
    cv2.putText(out, sub + dots + "  ", (sx, sy), font, 0.85, (210, 220, 235), 2, cv2.LINE_AA)

    bw, bh = int(min(w * 0.42, 520)), 12
    bx = (w - bw) // 2
    by = int(h * 0.58)
    cv2.rectangle(out, (bx, by), (bx + bw, by + bh), (38, 36, 48), -1)
    cv2.rectangle(out, (bx, by), (bx + bw, by + bh), (95, 110, 140), 1)

    phase = (tick * 5) % (bw + 120)
    seg_w = min(100, bw // 2)
    hx0 = bx + phase - 40
    hx1 = hx0 + seg_w
    hx0c = max(bx + 2, hx0)
    hx1c = min(bx + bw - 2, hx1)
    if hx1c > hx0c:
        overlay = out.copy()
        cv2.rectangle(overlay, (hx0c, by + 2), (hx1c, by + bh - 2), (255, 210, 120), -1)
        cv2.addWeighted(overlay, 0.55, out, 0.45, 0, out)

    for i in range(5):
        a = tick * 0.09 + i * 1.1
        px = int(w * 0.15 + i * (w * 0.17))
        py = int(h * 0.72 + 14 * math.sin(a))
        pr = 4 + int(3 * (0.5 + 0.5 * math.sin(a * 1.3)))
        cv2.circle(out, (px, py), pr, (120, 200, 255), -1, cv2.LINE_AA)

    hint = "Camera preview — wave when ready"
    (hw, hh), _ = cv2.getTextSize(hint, font, 0.55, 1)
    cv2.putText(
        out,
        hint,
        ((w - hw) // 2, h - 28),
        font,
        0.55,
        (160, 175, 195),
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


def draw_score(frame, score):
    h, w, _ = frame.shape
    text = f"Score {score}"
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.9
    thickness = 2
    (tw, _), _ = cv2.getTextSize(text, font, scale, thickness)
    cv2.putText(
        frame,
        text,
        (w - tw - 20, 45),
        font,
        scale,
        (255, 255, 255),
        thickness
    )


def draw_combo(frame, combo, multiplier):
    # Minimal UI: only show multiplier when it matters.
    if multiplier <= 1:
        return
    h, w, _ = frame.shape
    text = f"x{multiplier}"
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 1.0
    thickness = 3
    (tw, _), _ = cv2.getTextSize(text, font, scale, thickness)
    cv2.putText(
        frame,
        text,
        (int((w - tw) / 2), 75),
        font,
        scale,
        (255, 215, 0),
        thickness
    )


def _draw_top_banner(frame, title):
    _, w, _ = frame.shape
    panel_h = 80
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, panel_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)

    cv2.putText(
        frame,
        title,
        (18, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (200, 255, 255),
        3
    )


def draw_lives(frame, lives_left, lives_max):
    # Minimal hearts row.
    x0 = 20
    y = 45
    spacing = 22
    r = 8

    if lives_left >= 4:
        on_color = (0, 220, 0)
    elif lives_left >= 2:
        on_color = (0, 220, 220)
    else:
        on_color = (0, 0, 255)
    off_color = (80, 80, 80)

    for i in range(lives_max):
        cx = x0 + i * spacing
        color = on_color if i < lives_left else off_color
        cv2.circle(frame, (cx, y), r, color, -1)


def draw_game_over(frame):
    h, w, _ = frame.shape

    box_w = int(w * 0.62)
    box_h = 150
    x1 = int((w - box_w) / 2)
    y1 = int((h - box_h) / 2)
    x2 = x1 + box_w
    y2 = y1 + box_h

    overlay = frame.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    title = "GAME OVER"
    subtitle = "Press R to restart"
    font = cv2.FONT_HERSHEY_SIMPLEX

    cv2.putText(
        frame,
        title,
        (x1 + 20, y1 + 60),
        font,
        2.0,
        (255, 255, 255),
        5
    )
    cv2.putText(
        frame,
        subtitle,
        (x1 + 20, y1 + 115),
        font,
        0.95,
        (220, 220, 220),
        3
    )


def draw_pregame_overlay(frame, num_hands, steady_count, steady_need, tick):
    """
    Center card: explain both hands required, live hand count, steady progress when 2 hands visible.
    """
    h, w = frame.shape[:2]
    bw = int(min(w * 0.68, 720))
    bh = int(min(h * 0.34, 280))
    x1 = (w - bw) // 2
    y1 = (h - bh) // 2
    x2, y2 = x1 + bw, y1 + bh

    roi = frame[y1:y2, x1:x2].copy()
    card = np.full((bh, bw, 3), (44, 40, 56), dtype=np.uint8)
    blended = cv2.addWeighted(roi, 0.38, card, 0.62, 0)
    frame[y1:y2, x1:x2] = blended

    pulse = 0.5 + 0.5 * math.sin(tick * 0.12)
    edge = _lerp_bgr((90, 85, 110), (255, 210, 100), 0.35 + 0.25 * pulse)
    cv2.rectangle(frame, (x1, y1), (x2 - 1, y2 - 1), edge, 2, cv2.LINE_AA)

    font = cv2.FONT_HERSHEY_SIMPLEX
    title = "Show both hands to start"
    sub = "Hold them in front of the camera — cyan rings appear when we track each hand."

    (tw, th), _ = cv2.getTextSize(title, font, 0.95, 2)
    tx = (w - tw) // 2
    ty = y1 + int(bh * 0.20)
    cv2.putText(frame, title, (tx + 2, ty + 2), font, 0.95, (10, 8, 14), 2, cv2.LINE_AA)
    cv2.putText(frame, title, (tx, ty), font, 0.95, (220, 245, 255), 2, cv2.LINE_AA)

    sub_scale = 0.52
    lines = []
    acc = ""
    for word in sub.split():
        test = (acc + " " + word).strip()
        (sw, _), _ = cv2.getTextSize(test, font, sub_scale, 1)
        if sw > bw - 36 and acc:
            lines.append(acc)
            acc = word
        else:
            acc = test
    if acc:
        lines.append(acc)

    ly = ty + th + 18
    for line in lines[:3]:
        (lw, lh), _ = cv2.getTextSize(line, font, sub_scale, 1)
        cv2.putText(
            frame,
            line,
            ((w - lw) // 2, ly),
            font,
            sub_scale,
            (185, 195, 215),
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
        fill = (60, 200, 255) if ok else (55, 52, 62)
        ring = (200, 230, 255) if ok else (95, 100, 115)
        cv2.circle(frame, (hx, hy), 22, fill, -1, cv2.LINE_AA)
        cv2.circle(frame, (hx, hy), 22, ring, 2, cv2.LINE_AA)
        label = f"{i + 1}"
        (lw, lh), _ = cv2.getTextSize(label, font, 0.55, 1)
        cv2.putText(
            frame,
            label,
            (hx - lw // 2, hy + lh // 2),
            font,
            0.55,
            (20, 22, 28) if ok else (180, 185, 195),
            1,
            cv2.LINE_AA,
        )

    status = f"{min(num_hands, 2)} / 2 hands visible"
    (uw, uh), _ = cv2.getTextSize(status, font, 0.62, 2)
    cv2.putText(
        frame,
        status,
        ((w - uw) // 2, base_y + 42),
        font,
        0.62,
        (160, 230, 180) if num_hands >= 2 else (200, 200, 210),
        2,
        cv2.LINE_AA,
    )

    if num_hands >= 2 and steady_need > 0:
        bar_w = bw - 48
        bar_h = 8
        bx = (w - bar_w) // 2
        by = y2 - 28
        cv2.rectangle(frame, (bx, by), (bx + bar_w, by + bar_h), (40, 38, 50), -1)
        fill_w = int(bar_w * min(1.0, steady_count / float(steady_need)))
        if fill_w > 2:
            cv2.rectangle(frame, (bx + 2, by + 2), (bx + fill_w - 2, by + bar_h - 2), (80, 200, 120), -1)
        cv2.putText(
            frame,
            "Hold steady…",
            (bx, by - 8),
            font,
            0.5,
            (170, 180, 200),
            1,
            cv2.LINE_AA,
        )


def draw_instructions(frame, game):
    h, w, _ = frame.shape
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.58
    thick = 2
    col = (230, 230, 230)
    cv2.putText(frame, "Pop colored balls for score", (20, h - 42), font, scale, col, thick)
    if game.lives_left >= game.lives_max:
        line2 = "Green + life pickups unlock after you lose a heart"
    else:
        line2 = "Green + = +1 life (missing it is OK)"
    s2 = scale
    for _ in range(12):
        (tw2, _), _ = cv2.getTextSize(line2, font, s2, thick)
        if tw2 <= w - 36:
            break
        s2 = max(0.42, s2 - 0.04)
    cv2.putText(frame, line2, (20, h - 18), font, s2, col, thick)


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
    _draw_top_banner(frame, "HAND POP!")
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
    draw_score(frame, game.score)
    draw_combo(frame, game.combo, game.multiplier)
    draw_lives(frame, game.lives_left, game.lives_max)

    if game.game_over:
        draw_game_over(frame)
    else:
        draw_instructions(frame, game)