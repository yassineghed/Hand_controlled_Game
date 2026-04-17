import math
import random
from collections import deque

import cv2
import numpy as np


# BGR colors for OpenCV
C_VOID          = (14, 10, 10)
C_WHITE         = (255, 255, 255)
C_MINT          = (170, 207, 125)   # #7dcfaa — progress bars, health ball
C_AMBER         = (122, 200, 255)   # #ffc87a — combo badge, score popups
C_ROSE          = (144, 112, 255)   # #ff7090 — hearts, danger

# Panel opacities
PANEL_FILL_ALPHA   = 0.055
PANEL_BORDER_ALPHA = 0.10
TEXT_PRIMARY       = 1.00
TEXT_SECONDARY     = 0.50
TEXT_TERTIARY      = 0.28
TEXT_GHOST         = 0.18

# Geometry
PANEL_CORNER  = 12
PANEL_PAD_X   = 15
PANEL_PAD_Y   = 9
HUD_MARGIN    = 12
HINT_BAR_H    = 28
BLUR_KSIZE    = (21, 21)

# Ball
TRAIL_COUNT   = 3
TRAIL_ALPHAS  = [0.08, 0.14, 0.22]

# Animation durations in frames at 30fps
DUR_POP_BURST   = 18
DUR_SCORE_POPUP = 30
DUR_COMBO_FLASH = 24
DUR_SHAKE       = 6

# Extra drawing-only tuning (matches engine/design_tokens look)
TELEGRAPH_TOTAL_FRAMES = 21  # ~0.35s @ 60fps
TELEGRAPH_BAR_W = 6
TELEGRAPH_PULSE_LOW = 0.20
TELEGRAPH_PULSE_HIGH = 0.55
TELEGRAPH_PULSE_HZ = 4.0

COMBO_BADGE_FADE_FRAMES = 120  # ~2s @ 60fps after last pop
COMBO_PULSE_FRAMES = 10

DUR_LIFE_LOSS_FLASH = 6
ROSE_LIFE_FLASH = 0.18


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))

# Adaptive dimming
DIM_ALPHA_MIN     = 0.45
DIM_ALPHA_MAX     = 0.72
DIM_SMOOTH_FACTOR = 0.04


def blend(frame, color, alpha, x1, y1, x2, y2, filled=True):
    overlay = frame.copy()
    t = -1 if filled else 1
    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, t, cv2.LINE_AA)
    cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)


def blend_circle(frame, center, radius, color, alpha, filled=True, thickness=1):
    overlay = frame.copy()
    t = -1 if filled else thickness
    cv2.circle(overlay, center, radius, color, t, cv2.LINE_AA)
    cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)


def draw_rounded_rect(frame, x, y, w, h, r, color, alpha, filled=True):
    overlay = frame.copy()
    if filled:
        cv2.circle(overlay, (x+r,   y+r),   r, color, -1, cv2.LINE_AA)
        cv2.circle(overlay, (x+w-r, y+r),   r, color, -1, cv2.LINE_AA)
        cv2.circle(overlay, (x+r,   y+h-r), r, color, -1, cv2.LINE_AA)
        cv2.circle(overlay, (x+w-r, y+h-r), r, color, -1, cv2.LINE_AA)
        cv2.rectangle(overlay, (x+r, y),   (x+w-r, y+h), color, -1)
        cv2.rectangle(overlay, (x, y+r),   (x+w, y+h-r), color, -1)
    else:
        # Quarter-arc per corner (not full circles)
        cv2.ellipse(overlay, (x+r,   y+r),   (r, r), 0, 180, 270, color, 1, cv2.LINE_AA)
        cv2.ellipse(overlay, (x+w-r, y+r),   (r, r), 0, 270, 360, color, 1, cv2.LINE_AA)
        cv2.ellipse(overlay, (x+r,   y+h-r), (r, r), 0,  90, 180, color, 1, cv2.LINE_AA)
        cv2.ellipse(overlay, (x+w-r, y+h-r), (r, r), 0,   0,  90, color, 1, cv2.LINE_AA)
        cv2.line(overlay, (x+r,   y),     (x+w-r, y),     color, 1, cv2.LINE_AA)
        cv2.line(overlay, (x+r,   y+h),   (x+w-r, y+h),   color, 1, cv2.LINE_AA)
        cv2.line(overlay, (x,     y+r),   (x,     y+h-r), color, 1, cv2.LINE_AA)
        cv2.line(overlay, (x+w,   y+r),   (x+w,   y+h-r), color, 1, cv2.LINE_AA)
    cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)


def draw_glass_panel(frame, x, y, w, h):
    # Blur behind panel to simulate frosted glass
    frame[y:y+h, x:x+w] = cv2.GaussianBlur(frame[y:y+h, x:x+w], BLUR_KSIZE, 0)
    # Fill
    draw_rounded_rect(frame, x, y, w, h, PANEL_CORNER, C_WHITE, PANEL_FILL_ALPHA, filled=True)
    # Border
    draw_rounded_rect(frame, x, y, w, h, PANEL_CORNER, C_WHITE, PANEL_BORDER_ALPHA, filled=False)


def draw_text(frame, text, x, y, alpha=1.0, scale=0.4,
              font=cv2.FONT_HERSHEY_DUPLEX, thickness=1, color=C_WHITE):
    c = tuple(int(ch * alpha) for ch in color)
    cv2.putText(frame, text, (x, y), font, scale, c, thickness, cv2.LINE_AA)
    return cv2.getTextSize(text, font, scale, thickness)[0]


class AdaptiveDimmer:
    def __init__(self):
        self.smooth_alpha = 0.60

    def apply(self, frame):
        brightness = float(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean())
        raw = DIM_ALPHA_MIN + (brightness / 255.0) * (DIM_ALPHA_MAX - DIM_ALPHA_MIN)
        self.smooth_alpha = (1 - DIM_SMOOTH_FACTOR) * self.smooth_alpha + DIM_SMOOTH_FACTOR * raw
        tint = np.full_like(frame, C_VOID)
        cv2.addWeighted(frame, 1.0 - self.smooth_alpha, tint, self.smooth_alpha, 0, frame)
        return frame


def draw_ball(frame, cx, cy, r, is_health=False, ball_type="normal"):
    if ball_type == "bomb":
        body = (25, 25, 180)   # deep red
        blend_circle(frame, (cx, cy), r, body, alpha=0.90, filled=True)
        # Dark highlight
        blend_circle(frame, (cx - int(r * 0.25), cy - int(r * 0.22)), int(r * 0.4), (60, 60, 200), alpha=0.45, filled=True)
        # Danger ring
        blend_circle(frame, (cx, cy), r + 3, (40, 40, 220), alpha=0.55, filled=False, thickness=2)
        blend_circle(frame, (cx, cy), r, C_WHITE, alpha=0.06, filled=False)
    elif ball_type == "gold":
        body = (25, 185, 255)  # gold BGR
        blend_circle(frame, (cx, cy), r, body, alpha=0.85, filled=True)
        blend_circle(frame, (cx - int(r * 0.28), cy - int(r * 0.24)), int(r * 0.52), C_WHITE, alpha=0.65, filled=True)
        blend_circle(frame, (cx, cy), r + 2, (30, 200, 255), alpha=0.40, filled=False, thickness=2)
        blend_circle(frame, (cx, cy), r, C_WHITE, alpha=0.10, filled=False)
    elif is_health or ball_type == "health":
        body = (140, 195, 100)
        blend_circle(frame, (cx, cy), r, body, alpha=0.75, filled=True)
        blend_circle(frame, (cx - int(r * 0.28), cy - int(r * 0.24)), int(r * 0.52), C_WHITE, alpha=0.55, filled=True)
        blend_circle(frame, (cx, cy), r, C_WHITE, alpha=0.08, filled=False)
        blend_circle(frame, (cx, cy), r + 4, C_MINT, alpha=0.30, filled=False)
    else:
        body = (180, 150, 170)
        blend_circle(frame, (cx, cy), r, body, alpha=0.75, filled=True)
        blend_circle(frame, (cx - int(r * 0.28), cy - int(r * 0.24)), int(r * 0.52), C_WHITE, alpha=0.55, filled=True)
        blend_circle(frame, (cx, cy), r, C_WHITE, alpha=0.08, filled=False)


def draw_ball_with_trail(frame, ball):
    trail = getattr(ball, "trail", None)
    if trail:
        for i, (tx, ty) in enumerate(reversed(list(trail))):
            if i >= TRAIL_COUNT:
                break
            blend_circle(
                frame,
                (int(tx), int(ty)),
                ball.radius,
                C_WHITE,
                alpha=TRAIL_ALPHAS[min(i, len(TRAIL_ALPHAS) - 1)],
                filled=True,
            )


def draw_lane_rails(frame, lane_info: dict):
    """Draw perspective converging lines for the 3 lanes."""
    if not lane_info:
        return
    vp_x = int(lane_info["vp_x"])
    vp_y = int(lane_info["vp_y"])
    player_y = int(lane_info["player_y"])
    lane_x_near = lane_info["lane_x_near"]
    w = int(lane_info["width"])

    overlay = frame.copy()
    # Outer edges at screen sides
    edge_xs = [0, w]
    all_xs = [int(lx) for lx in lane_x_near] + edge_xs
    for bx in all_xs:
        cv2.line(overlay, (vp_x, vp_y), (bx, player_y), C_WHITE, 1, cv2.LINE_AA)
    cv2.addWeighted(overlay, 0.12, frame, 0.88, 0, frame)

    # Subtle horizontal horizon line
    blend(frame, C_WHITE, 0.06, 0, vp_y - 1, w, vp_y + 1)


def draw_score_panel(frame, score, best_score):
    x, y, w, h = HUD_MARGIN, HUD_MARGIN, 100, 60
    draw_glass_panel(frame, x, y, w, h)
    draw_text(frame, "SCORE", x + PANEL_PAD_X, y + 16, alpha=TEXT_TERTIARY, scale=0.28)
    draw_text(
        frame,
        f"{score:,}",
        x + PANEL_PAD_X,
        y + 40,
        alpha=TEXT_PRIMARY,
        scale=0.75,
        font=cv2.FONT_HERSHEY_SIMPLEX,
        thickness=1,
    )
    draw_text(frame, f"Best {best_score:,}", x + PANEL_PAD_X, y + 55, alpha=TEXT_GHOST * 0.8, scale=0.26)


def draw_lives(frame, lives, max_lives, fw):
    size = 16
    gap = 6
    total_w = max_lives * (size + gap) - gap
    sx = (fw - total_w) // 2
    y = HUD_MARGIN + size // 2 + 2
    for i in range(max_lives):
        cx = sx + i * (size + gap) + size // 2
        r = size // 2
        filled = i < lives
        a = 0.85 if filled else 0.0
        color = C_ROSE
        # Two circles for bumps
        blend_circle(frame, (cx - r // 2, y - r // 3), r // 2 + 1, color, alpha=a, filled=True)
        blend_circle(frame, (cx + r // 2, y - r // 3), r // 2 + 1, color, alpha=a, filled=True)
        # Triangle for bottom point
        pts = np.array([[cx - r, y - r // 3], [cx + r, y - r // 3], [cx, y + r]], np.int32)
        ov = frame.copy()
        if filled:
            cv2.fillPoly(ov, [pts], color, cv2.LINE_AA)
        else:
            cv2.polylines(ov, [pts], True, C_WHITE, 1, cv2.LINE_AA)
        cv2.addWeighted(ov, a if filled else 0.20, frame, 1 - (a if filled else 0.20), 0, frame)


def draw_combo_badge(frame, combo, fw):
    raise NotImplementedError("Use draw_combo_badge_animated")


def draw_combo_badge_animated(
    frame,
    combo,
    fw,
    *,
    pulse_f: int,
    last_pop_frame: int,
    frame_count: int,
):
    if combo < 2:
        return

    age = int(frame_count) - int(last_pop_frame)
    visible = pulse_f > 0 or age < COMBO_BADGE_FADE_FRAMES
    if not visible:
        return

    fade_t = 1.0 if pulse_f > 0 else 1.0 - (_clamp01(age / COMBO_BADGE_FADE_FRAMES))
    pulse_f = max(0, int(pulse_f))

    text = f"x{combo}  combo"
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, 0.32, 1)

    if pulse_f > 0:
        u = pulse_f / float(max(1, COMBO_PULSE_FRAMES))
        pulse_scale = 1.0 + 0.18 * math.sin(u * math.pi)
    else:
        pulse_scale = 1.0

    scale_w = max(0.8, pulse_scale)
    w = int((tw + 20) * scale_w)
    h = int((th + 8) * scale_w)
    x = (fw - w) // 2
    y = HUD_MARGIN + 38

    a_bg = 0.10 * fade_t
    a_border = 0.20 * fade_t
    draw_rounded_rect(frame, x, y, w, h, h // 2, C_AMBER, a_bg, filled=True)
    draw_rounded_rect(frame, x, y, w, h, h // 2, C_AMBER, a_border, filled=False)

    a_text = 0.85 * fade_t
    draw_text(frame, text, x + 10, y + th + 3, alpha=a_text, scale=0.32 * scale_w, color=C_AMBER)


def draw_spawn_telegraphs(frame, spawn_pending, tick: int):
    if not spawn_pending:
        return

    h, w = frame.shape[:2]
    ui_tick = int(tick)
    phase = 0.5 + 0.5 * math.sin(ui_tick * (2 * math.pi * TELEGRAPH_PULSE_HZ / 60.0))

    for item in spawn_pending:
        if not isinstance(item, dict):
            continue
        ball = item.get("ball")
        if ball is None:
            continue

        side = getattr(ball, "spawn_side", "top")
        r = int(getattr(ball, "radius", 28))
        diam = int(r * 2 * 1.4)
        left = int(getattr(ball, "x", 0))
        top = int(getattr(ball, "y", 0))

        frames_left = int(item.get("frames", TELEGRAPH_TOTAL_FRAMES))
        fade = _clamp01(frames_left / float(max(1, TELEGRAPH_TOTAL_FRAMES)))
        a = (TELEGRAPH_PULSE_LOW + (TELEGRAPH_PULSE_HIGH - TELEGRAPH_PULSE_LOW) * phase) * (
            0.25 + 0.75 * fade
        )
        a = max(0.0, min(1.0, a))

        is_health = bool(getattr(ball, "is_health_ball", False))
        col = C_MINT if is_health else C_ROSE

        bar_w = TELEGRAPH_BAR_W
        if side == "top":
            x0, y0 = max(0, left - diam // 2), 0
            x1, y1 = min(w, x0 + diam), min(h, bar_w)
        elif side == "bottom":
            x0, y0 = max(0, left - diam // 2), max(0, h - bar_w)
            x1, y1 = min(w, x0 + diam), h
        elif side == "left":
            x0, y0 = 0, max(0, top - diam // 2)
            x1, y1 = min(w, bar_w), min(h, y0 + diam)
        else:  # right
            x0, y0 = max(0, w - bar_w), max(0, top - diam // 2)
            x1, y1 = w, min(h, y0 + diam)

        if x1 <= x0 + 2 or y1 <= y0 + 2:
            continue

        # Frosted strip base, then tint overlay for readability.
        draw_glass_panel(frame, x0, y0, x1 - x0, y1 - y0)
        blend(frame, col, 0.85 * a, x0, y0, x1, y1)


def draw_life_loss_overlay(frame, frames_left: int):
    if frames_left <= 0:
        return
    a = ROSE_LIFE_FLASH * (_clamp01(frames_left / float(max(1, DUR_LIFE_LOSS_FLASH))))
    if a <= 0.001:
        return
    overlay = np.full_like(frame, C_ROSE, dtype=np.uint8)
    cv2.addWeighted(overlay, a, frame, 1.0 - a, 0, frame)


def draw_goals_panel(frame, goals, run_number, level, coins, fw):
    pw = 145
    ph = 22 + len(goals) * 18 + 20
    x = fw - HUD_MARGIN - pw
    y = HUD_MARGIN
    draw_glass_panel(frame, x, y, pw, ph)
    draw_text(frame, f"RUN {run_number}  GOALS", x + PANEL_PAD_X, y + 14, alpha=TEXT_TERTIARY, scale=0.26)
    bar_x = x + PANEL_PAD_X + 46
    bar_w = pw - PANEL_PAD_X * 2 - 46 - 28
    for i, g in enumerate(goals):
        ry = y + 22 + i * 18
        pct = min(g["current"] / max(g["target"], 1), 1.0)
        done = pct >= 1.0
        draw_text(frame, g["name"], x + PANEL_PAD_X, ry + 11, alpha=TEXT_SECONDARY, scale=0.27)
        blend(frame, C_WHITE, 0.07, bar_x, ry + 5, bar_x + bar_w, ry + 7)
        if pct > 0:
            fc = C_MINT if (done or pct <= 0.80) else C_AMBER
            fa = 0.90 if done else (0.55 if pct > 0.80 else 0.65)
            blend(frame, fc, fa, bar_x, ry + 5, bar_x + int(bar_w * pct), ry + 7)
        val = "v" if done else f"{g['current']}/{g['target']}"
        col = C_MINT if done else C_WHITE
        draw_text(frame, val, bar_x + bar_w + 4, ry + 11, alpha=0.80 if done else TEXT_GHOST, scale=0.26, color=col)
    fy = y + ph - 7
    blend(frame, C_WHITE, 0.07, x + PANEL_PAD_X, fy - 10, x + pw - PANEL_PAD_X, fy - 9)
    draw_text(frame, f"Lv {level}  {coins:,}", x + PANEL_PAD_X, fy, alpha=TEXT_GHOST * 0.8, scale=0.25)


def draw_hand_rings(frame, hand_positions):
    # hand_positions = list of (cx, cy, confidence, pop_radius)
    for (cx, cy, conf, pop_r) in hand_positions:
        a = 0.15 + conf * 0.20
        blend_circle(frame, (int(cx), int(cy)), int(pop_r), C_WHITE, alpha=a, filled=False, thickness=2)
        blend_circle(frame, (int(cx), int(cy)), 3, C_WHITE, alpha=a * 0.6, filled=True)


def draw_hint_bar(frame, fw, fh, hints, alpha=1.0):
    if alpha <= 0.01:
        return
    y = fh - HINT_BAR_H
    blend(frame, (0, 0, 0), 0.35 * alpha, 0, y, fw, fh)
    sp = fw // (len(hints) + 1)
    for i, (key, desc) in enumerate(hints):
        cx = sp * (i + 1)
        ky = y + HINT_BAR_H // 2 + 4
        (tw, _th), _ = cv2.getTextSize(key, cv2.FONT_HERSHEY_DUPLEX, 0.28, 1)
        blend(frame, C_WHITE, 0.08 * alpha, cx - tw // 2 - 4, ky - 10, cx + tw // 2 + 4, ky + 2)
        draw_text(frame, key, cx - tw // 2, ky - 1, alpha=0.35 * alpha, scale=0.28)
        draw_text(frame, desc, cx + tw // 2 + 10, ky - 1, alpha=0.20 * alpha, scale=0.28)


class Particle:
    def __init__(self, cx, cy, combo=1):
        a = random.uniform(0, 2 * math.pi)
        s = random.uniform(4, 9) * (1 + combo * 0.1)
        self.x, self.y = float(cx), float(cy)
        self.vx, self.vy = math.cos(a) * s, math.sin(a) * s
        self.r = random.randint(2, 5)
        self.life = self.max_life = DUR_POP_BURST

    def update(self):
        self.vx *= 0.88
        self.vy *= 0.88
        self.x += self.vx
        self.y += self.vy
        self.life -= 1

    @property
    def alpha(self):
        return (self.life / self.max_life) * 0.85

    @property
    def alive(self):
        return self.life > 0


def draw_particles(frame, particles):
    for p in particles:
        if isinstance(p, dict):
            life = float(p.get("life", 0))
            max_life = float(p.get("max_life", 1))
            if life <= 0 or max_life <= 0:
                continue
            t = life / max_life
            alpha = max(0.0, min(1.0, t * 0.85))
            x = int(p.get("x", 0))
            y = int(p.get("y", 0))
            if "r0" in p:
                base_r = float(p.get("r0", 3.0))
                r = max(1, int(base_r * (0.35 + 0.65 * t)))
            elif "size" in p:
                r = max(1, int(p.get("size", 3)))
            else:
                r = max(1, int(p.get("r", 2)))
            col = p.get("color", C_WHITE)
            blend_circle(frame, (x, y), r, col, alpha=alpha, filled=True)
            continue

        if getattr(p, "alive", True):
            if getattr(p, "alive", False) is False:
                continue
            blend_circle(frame, (int(p.x), int(p.y)), int(p.r), C_WHITE, p.alpha, filled=True)


class ScorePopup:
    def __init__(self, cx, cy, points, combo=1):
        self.x, self.y = float(cx), float(cy)
        self.text = f"+{points}"
        self.color = C_AMBER if combo >= 3 else C_WHITE
        self.life = self.max_life = DUR_SCORE_POPUP

    def update(self):
        self.y -= 40.0 / self.max_life
        self.life -= 1

    @property
    def alpha(self):
        t = self.life / self.max_life
        if t > 0.87:
            return (1.0 - t) / 0.13
        if t > 0.47:
            return 1.0
        return t / 0.47

    @property
    def alive(self):
        return self.life > 0


def draw_score_popups(frame, popups):
    for p in popups:
        if isinstance(p, dict):
            life = float(p.get("life", 0))
            max_life = float(p.get("max_life", 1))
            if life <= 0 or max_life <= 0:
                continue
            t = life / max_life
            if t > 0.87:
                a = (1.0 - t) / 0.13
            elif t > 0.47:
                a = 1.0
            else:
                a = t / 0.47
            txt = str(p.get("text", ""))
            col = p.get("color", C_WHITE)
            sc = float(p.get("scale", 0.55))
            kind = p.get("kind", "")
            if kind and kind not in ("score_popup", "event"):
                continue
            draw_text(
                frame,
                txt,
                int(p.get("x", 0)),
                int(p.get("y", 0)),
                alpha=max(0.0, min(1.0, a)),
                scale=sc,
                font=cv2.FONT_HERSHEY_SIMPLEX,
                thickness=1,
                color=col,
            )
            continue

        if getattr(p, "alive", False):
            draw_text(
                frame,
                p.text,
                int(p.x),
                int(p.y),
                alpha=p.alpha,
                scale=0.55,
                font=cv2.FONT_HERSHEY_SIMPLEX,
                color=p.color,
            )


SHAKE_KF = [(0, 0), (-8, 4), (7, -5), (-5, 3), (4, -2), (-2, 1), (0, 0)]


def get_shake(shake_frames):
    if shake_frames <= 0:
        return 0, 0
    return SHAKE_KF[min(DUR_SHAKE - shake_frames, len(SHAKE_KF) - 1)]


def draw_flashes(frame, shake_frames, combo_flash_frames):
    if shake_frames > 0:
        blend(frame, C_ROSE, 0.18 * (shake_frames / DUR_SHAKE), 0, 0, frame.shape[1], frame.shape[0])
    if combo_flash_frames > 0:
        blend(
            frame,
            C_AMBER,
            0.12 * (combo_flash_frames / DUR_COMBO_FLASH),
            0,
            0,
            frame.shape[1],
            frame.shape[0],
        )


class Renderer:
    def __init__(self):
        self.dimmer = AdaptiveDimmer()
        self.hint_alpha = 1.0
        self._hand_trails = deque(maxlen=12)  # past hand positions, one list per frame

    def draw_frame(self, frame, state):
        frame = self.dimmer.apply(frame)
        h, w = frame.shape[:2]
        shake_frames = int(state.get("shake_frames", 0))
        dx, dy = get_shake(shake_frames)
        # Draw without per-element offsets; global shake is applied by warping at the end.
        ox, oy = 0, 0

        mode = state.get("mode", "play")
        if mode == "loading":
            # Minimal frosted loading plate; keep rest of pipeline simple.
            fw, fh = w, h
            pw, ph = min(360, fw - 24), min(120, fh - 24)
            x = (fw - pw) // 2
            y = (fh - ph) // 2
            draw_glass_panel(frame, x, y, pw, ph)
            draw_text(frame, "WEBCAM ARCADE", x + PANEL_PAD_X, y + 44, alpha=TEXT_PRIMARY, scale=0.60)
            tick = int(state.get("tick", 0))
            dots = "." * ((tick // 18) % 4)
            draw_text(frame, f"Loading hand tracker{dots}", x + PANEL_PAD_X, y + 76, alpha=TEXT_TERTIARY, scale=0.32)
            return frame

        if mode == "pregame":
            # Frosted guidance while players hold still.
            fw, fh = w, h
            pw, ph = min(420, fw - 24), min(140, fh - 24)
            x = (fw - pw) // 2
            y = (fh - ph) // 2
            draw_glass_panel(frame, x, y, pw, ph)
            steady = float(state.get("pregame_steady", 0))
            need = float(max(1.0, state.get("pregame_steady_need", 1)))
            pct = max(0.0, min(1.0, steady / need))
            draw_text(frame, "Hold steady", x + PANEL_PAD_X, y + 46, alpha=TEXT_PRIMARY, scale=0.54)
            draw_text(frame, f"Starting in {int((1.0 - pct) * need)}f", x + PANEL_PAD_X, y + 78, alpha=TEXT_TERTIARY, scale=0.30)
            bar_x = x + PANEL_PAD_X
            bar_y = y + 102
            bar_w = pw - PANEL_PAD_X * 2
            blend(frame, C_WHITE, 0.07, bar_x, bar_y, bar_x + bar_w, bar_y + 6)
            if pct > 0:
                blend(frame, C_MINT, 0.75, bar_x, bar_y, bar_x + int(bar_w * pct), bar_y + 6)

        # L2 — lane rails (perspective converging lines)
        draw_lane_rails(frame, state.get("lane_info", {}))

        # L2.1 — life loss rose overlay
        draw_life_loss_overlay(frame, int(state.get("life_loss_overlay_frames", 0)))

        # L3 — balls (depth cue from size growth; approach glow near player)
        for b in state.get("balls", []):
            cx = int(getattr(b, "cx", getattr(b, "x", 0)))
            cy = int(getattr(b, "cy", getattr(b, "y", 0)))
            btype = str(getattr(b, "ball_type", "normal"))
            is_health = btype == "health"
            z = float(getattr(b, "z", 1.0))
            # Approach glow kicks in at z > 0.60
            if z > 0.60:
                t = (z - 0.60) / 0.40
                glow_r = int(b.radius * (1.0 + 0.55 * t))
                glow_a = 0.08 + 0.28 * t
                if btype == "bomb":
                    glow_col = (30, 30, 220)
                elif btype == "gold":
                    glow_col = (30, 200, 255)
                elif is_health:
                    glow_col = C_MINT
                else:
                    glow_col = C_ROSE
                blend_circle(frame, (cx, cy), glow_r, glow_col, alpha=glow_a, filled=True)
            draw_ball(frame, cx, cy, int(b.radius), is_health, btype)

        # L5 — hand sparkle trail + rings
        cur_hands = [(int(cx), int(cy)) for (cx, cy, *_) in state.get("hand_positions", [])]
        self._hand_trails.append(cur_hands)
        trail_list = list(self._hand_trails)
        n = len(trail_list)
        for i, positions in enumerate(trail_list[:-1]):  # skip current frame (drawn as ring)
            t = i / max(n - 1, 1)           # 0 = oldest, ~1 = one frame before current
            alpha = t * 0.38
            r = max(1, int(2 + 7 * t))
            for (px, py) in positions:
                blend_circle(frame, (px, py), r, C_AMBER, alpha=alpha, filled=True)
        draw_hand_rings(frame, state.get("hand_positions", []))

        # L5.5 — lane indicator: highlight which lane each hand is in
        lane_info = state.get("lane_info", {})
        if lane_info:
            vp_x = int(lane_info["vp_x"])
            vp_y = int(lane_info["vp_y"])
            player_y = int(lane_info["player_y"])
            lane_x_near = lane_info["lane_x_near"]
            lw3 = w / 3.0
            for (hx, hy, *_) in state.get("hand_positions", []):
                hl = 0 if hx < lw3 else (1 if hx < lw3 * 2 else 2)
                lnx = int(lane_x_near[hl])
                # Fill the triangle for the active lane
                pts = np.array([[vp_x, vp_y], [lnx - 30, player_y], [lnx + 30, player_y]], np.int32)
                ov = frame.copy()
                cv2.fillPoly(ov, [pts], C_WHITE)
                cv2.addWeighted(ov, 0.06, frame, 0.94, 0, frame)

        # L6 — particles + flashes
        draw_particles(frame, state.get("particles", []))
        draw_flashes(frame, state.get("shake_frames", 0), state.get("combo_flash_frames", 0))

        # L6.5 — rage mode overlay (pulsing red-orange tint)
        if state.get("rage_mode", False):
            ui_tick = int(state.get("ui_tick", 0))
            pulse = 0.5 + 0.5 * math.sin(ui_tick * 0.25)
            rage_a = 0.06 + 0.08 * pulse
            blend(frame, (30, 30, 220), rage_a, 0, 0, w, h)
        rage_flash = int(state.get("rage_flash_frames", 0))
        if rage_flash > 0:
            blend(frame, (30, 80, 255), 0.25 * (rage_flash / 30.0), 0, 0, w, h)

        # L7 — score popups
        draw_score_popups(frame, state.get("popups", []))

        # L8 — HUD panels
        draw_score_panel(frame, state.get("score", 0), state.get("best_score", 0))
        draw_lives(frame, state.get("lives", 0), state.get("max_lives", 0), w)
        draw_combo_badge_animated(
            frame,
            int(state.get("combo", 0)),
            w,
            pulse_f=int(state.get("combo_pulse_frames", 0)),
            last_pop_frame=int(state.get("combo_last_pop_frame", -999999)),
            frame_count=int(state.get("frame_count", 0)),
        )
        draw_goals_panel(frame, state.get("goals", []), state.get("run_number", 1), state.get("level", 1), state.get("coins", 0), w)

        # L9 — hint bar (fades after run 2)
        run_number = int(state.get("run_number", 1))
        hint_alpha = state.get("hint_alpha", None)
        if hint_alpha is not None:
            self.hint_alpha = float(hint_alpha)
        else:
            if run_number > 2:
                self.hint_alpha = max(0.0, self.hint_alpha - 1 / 60)
        draw_hint_bar(
            frame,
            w,
            h,
            [("[M]", "reroll"), ("[N]", "next"), ("[R]", "restart"), ("[Esc]", "quit")],
            alpha=self.hint_alpha,
        )
        # Apply global shake to the entire rendered scene (HUD included).
        if shake_frames > 0 and (dx != 0 or dy != 0):
            m = np.float32([[1, 0, dx], [0, 1, dy]])
            frame = cv2.warpAffine(
                frame,
                m,
                (w, h),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REFLECT,
            )
        return frame


_renderer = Renderer()


def draw_frame(frame: np.ndarray, game_state: dict) -> np.ndarray:
    return _renderer.draw_frame(frame, game_state)

