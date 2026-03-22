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
    "hint": (165, 174, 196),
    "accent": (255, 215, 120),  # warm highlight (progress sweep, borders)
    "ok": (88, 200, 125),
    "border": (90, 86, 110),
    "hand_ok": (72, 210, 255),  # matches title family
    "hand_idle": (58, 54, 64),
    "hand_ring_ok": (210, 235, 255),
    "hand_ring_idle": (92, 96, 108),
    "hud_veil": (26, 28, 40),
    "hud_line": (120, 200, 255),
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


def _top_veil(frame, strip_h, alpha=0.34):
    """Darken top band so HUD text reads on busy camera feed."""
    h, w = frame.shape[:2]
    strip_h = max(0, min(int(strip_h), h))
    if strip_h <= 0:
        return
    roi = frame[0:strip_h, 0:w]
    veil = np.full_like(roi, UI["hud_veil"], dtype=np.uint8)
    blended = cv2.addWeighted(roi, 1.0 - alpha, veil, alpha, 0)
    frame[0:strip_h, 0:w] = blended


def _text_right(frame, text, right_x, y, scale, thick, fill, outline=None):
    (tw, _), _ = cv2.getTextSize(text, _FONT, scale, thick)
    _outlined_text(frame, text, int(right_x - tw), y, scale, thick, fill, outline)


def _truncate(s, max_chars):
    s = str(s)
    if len(s) <= max_chars:
        return s
    return s[: max(0, max_chars - 1)] + "…"


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


def _draw_lives_row(frame, lives_left, lives_max, center_y):
    h, w, _ = frame.shape
    spacing = 18
    r = 6
    total_w = (lives_max - 1) * spacing
    x0 = (w - total_w) // 2

    if lives_left >= 4:
        on_color = (72, 210, 130)
    elif lives_left >= 2:
        on_color = (255, 200, 90)
    else:
        on_color = (80, 80, 255)
    off_color = (52, 50, 58)

    for i in range(lives_max):
        cx = x0 + i * spacing
        color = on_color if i < lives_left else off_color
        cv2.circle(frame, (cx, center_y), r, color, -1, cv2.LINE_AA)
        cv2.circle(frame, (cx, center_y), r, (28, 26, 34), 1, cv2.LINE_AA)


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
    Single top layout: score (left), lives + run progress (center), profile + missions (right).
    Avoids stacking everything in one corner and overlapping combo/lives.
    """
    if getattr(game, "game_over", False):
        return

    h, w, _ = frame.shape
    missions = game.missions or []
    has_missions = len(missions) > 0
    strip_h = 102 if has_missions else 86
    _top_veil(frame, strip_h, 0.32)

    margin = 16
    right_x = w - margin

    # --- Left: score + best (+ chase hint) ---
    score_txt = f"{int(game.score):,}" if game.score >= 1000 else str(int(game.score))
    _outlined_text(frame, score_txt, margin, 30, 0.62, 1, UI["title"])
    _outlined_text(frame, f"BEST {int(game.best_score)}", margin, 52, 0.34, 1, UI["subtitle"])
    if not quiet_on and not countdown_on and not milestone_on:
        gap = int(game.best_score) - int(game.score)
        if int(game.best_score) > 0 and 1 <= gap <= 8:
            chase = "1 to beat best!" if gap == 1 else f"{gap} to beat best!"
            _outlined_text(frame, chase, margin, 72, 0.34, 1, UI["hud_line"])

    # --- Center: lives, run label, mission aggregate bar, combo row ---
    cy = 28
    _draw_lives_row(frame, game.lives_left, game.lives_max, cy)
    done = sum(1 for m in missions if bool(m.get("done", False)))
    total = max(1, len(missions))
    t_m = done / float(total)
    run_label = f"RUN {int(game.play_level)}"
    sl, st = 0.36, 1
    (rw, _), _ = cv2.getTextSize(run_label, _FONT, sl, st)
    _outlined_text(frame, run_label, (w - rw) // 2, cy + 18, sl, st, UI["subtitle"])

    bar_w = min(150, w // 4)
    bar_h = 6
    bx = (w - bar_w) // 2
    by = cy + 24
    _draw_thin_bar(frame, bx, by, bar_w, bar_h, t_m, UI["hud_line"])

    if not countdown_on and int(game.multiplier) > 1:
        ctext = f"×{int(game.multiplier)}"
        cs, ct = 0.56, 1
        (cw, _), _ = cv2.getTextSize(ctext, _FONT, cs, ct)
        _outlined_text(
            frame,
            ctext,
            (w - cw) // 2,
            by + 16,
            cs,
            ct,
            UI["accent"],
        )
        if int(game.combo) >= 10 and not quiet_on and not milestone_on:
            flicker = 0.88 + 0.12 * math.sin(ui_tick * 0.22)
            hs = "HOT STREAK"
            hs_scale = 0.34
            (hw, _), _ = cv2.getTextSize(hs, _FONT, hs_scale, 1)
            col = (
                int(140 * flicker),
                int(210 * flicker),
                int(255 * flicker),
            )
            _outlined_text(frame, hs, (w - hw) // 2, by + 36, hs_scale, 1, col)

    # --- Right: meta level, XP, coins, missions (right-aligned) ---
    stage_short = _truncate(game.stage_name, 12)
    _text_right(frame, f"LV {int(game.level)} · {stage_short}", right_x, 26, 0.38, 1, UI["title"])
    xp_next = max(1, int(getattr(game, "xp_next", 1)))
    t_xp = max(0.0, min(1.0, float(game.xp) / float(xp_next)))
    bar_w2 = min(118, w // 5)
    bx2 = right_x - bar_w2
    by2 = 40
    _draw_thin_bar(frame, bx2, by2, bar_w2, 5, t_xp, (140, 200, 255))
    _text_right(frame, f"{int(game.coins)} coins", right_x, by2 + 12, 0.34, 1, UI["accent"])

    if has_missions:
        my = by2 + 30
        for m in missions[:3]:
            done_m = bool(m.get("done", False))
            short = _truncate(m.get("label", ""), 22)
            line = f"{int(m.get('progress', 0))}/{int(m.get('target', 0))} {short}"
            col = (120, 230, 175) if done_m else UI["subtitle"]
            _text_right(frame, line, right_x, my, 0.32, 1, col)
            my += 17
        _text_right(frame, "[M] reroll tasks", right_x, my + 2, 0.28, 1, UI["hint"])


def draw_level_transition_overlay(frame, transition_pending, _transition_frames):
    """Big message only — run progress lives in draw_unified_hud."""
    if not transition_pending:
        return
    h, w, _ = frame.shape
    y0 = int(h * 0.20)
    _outlined_text(
        frame,
        "RUN COMPLETE",
        (w // 2) - 118,
        y0,
        0.62,
        2,
        UI["accent"],
    )
    _outlined_text(
        frame,
        "Next run loading…",
        (w // 2) - 108,
        y0 + 28,
        0.40,
        1,
        UI["subtitle"],
    )
    _outlined_text(
        frame,
        "[N] continue now",
        (w // 2) - 88,
        y0 + 50,
        0.36,
        1,
        UI["hint"],
    )


def draw_floating_texts(frame, texts, max_items=6):
    if max_items > 0:
        texts = texts[-max_items:]
    for t in texts:
        cx, y = t["x"], int(t["y"])
        life = t.get("life", 0)
        max_life = t.get("max_life", 1)
        t_norm = life / max(max_life, 1)
        alpha = 0.22 + 0.78 * _ease_out_cubic(t_norm)
        scale = t.get("scale", 0.9)
        thick = max(1, int(scale * 2))
        col = tuple(int(c * alpha) for c in t.get("color", (255, 255, 255)))
        (tw, th), _ = cv2.getTextSize(t["text"], _FONT, scale, thick)
        x = int(cx) - tw // 2
        _outlined_text(frame, t["text"], x, y, scale, thick, col)


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
    pulse = 0.9 + 0.15 * math.sin(tick * 0.2)
    col = (int(255 * pulse), int(248 * pulse), int(220 * pulse))
    _outlined_text(frame, label, x, y, scale, thick, col, outline=(25, 20, 35))


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
    col = (int(255 * alpha), int(235 * alpha), int(130 * alpha))
    _outlined_text(frame, text, x, y, scale, thick, col)


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
            f"Missions +{summary.get('coins_earned', 0)} coins · "
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
        stage = f"LV {summary.get('level', 1)} · {summary.get('stage', 'Rookie')}"
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
    if game.lives_left >= game.lives_max:
        extra = " · Green + unlocks after first miss"
    else:
        extra = " · Green + = +1 life"
    line = f"Pop balls for score{extra} · [M] reroll tasks · [N] skip run wait"
    s, thick = 0.36, 1
    for _ in range(14):
        (tw, _), _ = cv2.getTextSize(line, _FONT, s, thick)
        if tw <= w - 20:
            break
        s = max(0.28, s - 0.02)
    _outlined_text(frame, line, (w - tw) // 2, h - 12, s, thick, UI["hint"])


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