import cv2
import time


def draw_hands(frame, hands):

    for hand in hands:

        x = int(hand["x"])
        y = int(hand["y"])
        r = int(hand["radius"])

        cv2.circle(frame, (x, y), r, (0,255,0), 3)


def draw_balls(frame, balls, now=None):

    """
    Draw balls with a short spawn-in animation and a fading "safe" ring.
    """
    if now is None:
        now = time.perf_counter()

    spawn_anim_seconds = 0.01
    min_scale = 0.6  # scale ball radius up right after spawn

    for ball in balls:
        age = ball.age_seconds(now)

        # Spawn animation: scale up quickly so it doesn't feel like balls "pop in".
        if spawn_anim_seconds <= 0:
            t = 1.0
        else:
            t = max(0.0, min(1.0, age / spawn_anim_seconds))
        scale = min_scale + (1.0 - min_scale) * t
        radius = max(1, int(ball.radius * scale))

        cx, cy = int(ball.x), int(ball.y)

        # Safe/fresh ring: lasts for the same duration as the fairness window.
        safe_t = getattr(ball, "min_visible_seconds", 0.0) or 0.0
        if safe_t > 0 and age < safe_t:
            remaining = max(0.0, min(1.0, 1.0 - (age / safe_t)))
            c = int(220 * remaining)  # BGR brightness
            ring_color = (0, c, c)  # yellow-ish (BGR)
            ring_radius = radius + int(10 * remaining)
            ring_radius = max(ring_radius, radius + 2)
            cv2.circle(frame, (cx, cy), ring_radius, ring_color, 2)

        cv2.circle(
            frame,
            (cx, cy),
            radius,
            (0, 0, 255),
            -1
        )


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
    cv2.putText(
        frame,
        "Move hands to pop balls (new balls are safe briefly)",
        (20, h - 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (230, 230, 230),
        2,
    )


def render(frame, game, hands):
    _draw_top_banner(frame, "HAND POP!")
    draw_hands(frame, hands)
    draw_balls(frame, game.balls, now=time.perf_counter())
    draw_confetti(frame, game.confetti_particles)
    draw_score(frame, game.score)
    draw_combo(frame, game.combo, game.multiplier)
    draw_lives(frame, game.lives_left, game.lives_max)

    if game.game_over:
        draw_game_over(frame)
    else:
        draw_instructions(frame)