import math

import cv2


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


def draw_instructions(frame):
    h, w, _ = frame.shape
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.58
    thick = 2
    col = (230, 230, 230)
    cv2.putText(frame, "Pop colored balls for score", (20, h - 42), font, scale, col, thick)
    cv2.putText(
        frame,
        "Green + = +1 life (missing it is OK)",
        (20, h - 18),
        font,
        scale,
        col,
        thick,
    )


def render(frame, game, hands):
    _draw_top_banner(frame, "HAND POP!")
    draw_hands(frame, hands)
    draw_balls(frame, game.balls, game.frame_count)
    draw_confetti(frame, game.confetti_particles)
    draw_score(frame, game.score)
    draw_combo(frame, game.combo, game.multiplier)
    draw_lives(frame, game.lives_left, game.lives_max)

    if game.game_over:
        draw_game_over(frame)
    else:
        draw_instructions(frame)