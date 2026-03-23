"""
Webcam Arcade — glass HUD, balls, telegraph, overlays (design spec).
"""

from __future__ import annotations

import math

import cv2
import numpy as np

import arcade_text
import design_tokens as T


def _heart_outline_points(cx, cy, scale):
    pts = []
    for i in range(28):
        t = (i / 27.0) * 2 * math.pi
        x = 16 * (math.sin(t) ** 3)
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append([int(cx + x * scale), int(cy + y * scale)])
    return np.array(pts, dtype=np.int32)


def _rounded_rect_mask(h: int, w: int, r: int) -> np.ndarray:
    m = np.zeros((h, w), dtype=np.uint8)
    r = max(1, min(r, min(h, w) // 2 - 1))
    cv2.rectangle(m, (r, 0), (w - r, h), 255, -1)
    cv2.rectangle(m, (0, r), (w, h - r), 255, -1)
    cv2.ellipse(m, (r, r), (r, r), 180, 0, 90, 255, -1)
    cv2.ellipse(m, (w - r - 1, r), (r, r), 270, 0, 90, 255, -1)
    cv2.ellipse(m, (r, h - r - 1), (r, r), 90, 0, 90, 255, -1)
    cv2.ellipse(m, (w - r - 1, h - r - 1), (r, r), 0, 0, 90, 255, -1)
    return m


def draw_glass_panel(
    frame: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    corner_r: int | None = None,
) -> None:
    """Frosted rounded panel: blur + white 5.5% fill + white 10% border."""
    H, W = frame.shape[:2]
    x = max(0, min(W - 1, x))
    y = max(0, min(H - 1, y))
    w = max(4, min(W - x, w))
    h = max(4, min(H - y, h))
    cr = int(corner_r if corner_r is not None else T.PANEL_RADIUS)
    k = T.BLUR_KSIZE | 1
    if k < 7:
        k = 7

    roi = frame[y : y + h, x : x + w].copy()
    blur = cv2.GaussianBlur(roi, (k, k), 0)
    mask = _rounded_rect_mask(h, w, cr)
    m = (mask.astype(np.float32) / 255.0)[:, :, np.newaxis]

    frost = roi.astype(np.float32) * (1.0 - m[:, :, 0:1] * 0.82) + blur.astype(np.float32) * (
        m[:, :, 0:1] * 0.82
    )
    white = np.array(T.C_WHITE, dtype=np.float32)
    tinted = frost * (1.0 - m[:, :, 0:1] * T.PANEL_FILL_ALPHA) + white * (
        m[:, :, 0:1] * T.PANEL_FILL_ALPHA
    )
    out = np.clip(tinted, 0, 255).astype(np.uint8)
    frame[y : y + h, x : x + w] = np.where(m > 0.01, out, frame[y : y + h, x : x + w])

    border_col = np.array(T.bgr_with_white_opacity(T.BORDER_PANEL), dtype=np.float32)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    bz = frame[y : y + h, x : x + w].astype(np.float32)
    if contours:
        bo = np.zeros_like(bz)
        cv2.drawContours(bo, contours, -1, (1.0, 1.0, 1.0), 1)
        eb = bo[:, :, 0:1]
        blended = bz * (1.0 - eb * T.PANEL_BORDER_ALPHA) + border_col * (
            eb * T.PANEL_BORDER_ALPHA
        )
        frame[y : y + h, x : x + w] = np.where(
            eb > 0.01, np.clip(blended, 0, 255), frame[y : y + h, x : x + w]
        )


def _ball_exit_margin(ball, w: int, h: int) -> float:
    """1 = near exit in direction of travel; activates urgency halo < 20% margin."""
    r = float(ball.radius)
    vx, vy = float(ball.vx), float(ball.vy)
    if abs(vx) >= abs(vy):
        if vx > 1e-6:
            d = (w + r) - ball.x
            span = float(w)
        elif vx < -1e-6:
            d = ball.x + r
            span = float(w)
        else:
            return 0.0
    else:
        if vy > 1e-6:
            d = (h + r) - ball.y
            span = float(h)
        elif vy < -1e-6:
            d = ball.y + r
            span = float(h)
        else:
            return 0.0
    m = d / max(span, 1.0)
    if m > 0.20:
        return 0.0
    return max(0.0, min(1.0, 1.0 - m / 0.20))


def draw_ball_arcade(frame: np.ndarray, ball, frame_count: int = 0) -> None:
    h, w = frame.shape[:2]
    cx, cy = int(ball.x), int(ball.y)
    r = int(ball.radius)
    if r < 2:
        return
    is_h = getattr(ball, "is_health_ball", False)
    urgency = _ball_exit_margin(ball, w, h)

    if urgency > 0.2:
        glow_a = T.lerp(0.0, T.BALL_URGENCY_HALO_MAX, (urgency - 0.2) / 0.8)
        gr = int(r + 16 * urgency)
        rose = np.array(T.C_ROSE, dtype=np.float32)
        overlay = frame.copy()
        cv2.circle(overlay, (cx, cy), gr, tuple(int(c) for c in rose), -1, cv2.LINE_AA)
        cv2.addWeighted(overlay, glow_a, frame, 1.0 - glow_a, 0, frame)

    mid = np.array(T.BALL_HEALTH_MID if is_h else T.BALL_BODY_VIOLET_MID, dtype=np.float32)
    edge_c = np.array(T.BALL_HEALTH_EDGE if is_h else T.BALL_BODY_VIOLET_EDGE, dtype=np.float32)
    glow_c = np.array(T.BALL_HEALTH_GLOW if is_h else T.BALL_GLOW_VIOLET, dtype=np.float32)

    overlay = frame.copy()
    cv2.circle(overlay, (cx, cy), r, tuple(int(c) for c in mid), -1, cv2.LINE_AA)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    hx = cx - int(r * T.BALL_HIGHLIGHT_OFFSET[0])
    hy = cy - int(r * T.BALL_HIGHLIGHT_OFFSET[1])
    hr = max(2, int(r * 0.52))
    hi = frame.copy()
    wh = np.array(T.C_WHITE, dtype=np.float32)
    cv2.circle(hi, (hx, hy), hr, (255, 255, 255), -1, cv2.LINE_AA)
    cv2.addWeighted(hi, T.BALL_HIGHLIGHT_ALPHA * 0.55, frame, 1.0 - T.BALL_HIGHLIGHT_ALPHA * 0.55, 0, frame)

    rim_a = T.BORDER_BALL_URGENT if urgency > 0.2 else T.BORDER_BALL
    rim = tuple(int(c * rim_a) for c in T.C_WHITE)
    cv2.circle(frame, (cx, cy), r, rim, 1, cv2.LINE_AA)

    og = frame.copy()
    cv2.circle(og, (cx, cy), int(r + 24), tuple(int(c) for c in glow_c), -1, cv2.LINE_AA)
    ga = 0.15 if is_h else 0.18
    cv2.addWeighted(og, ga, frame, 1.0 - ga, 0, frame)

    if is_h:
        pulse = 1.0 + 0.05 * math.sin(frame_count * 0.12)
        dr = max(3, int(r + 4 * pulse))
        mint = tuple(int(c * T.MINT_GLOW_HEALTH) for c in T.C_MINT)
        cv2.circle(frame, (cx, cy), dr, mint, 2, cv2.LINE_AA)


def draw_ball_trails_arcade(frame: np.ndarray, balls) -> None:
    """Three ghost positions: 8%, 14%, 22% white (oldest → newest)."""
    for ball in balls:
        tr = getattr(ball, "trail", None)
        if tr is None or len(tr) < 2:
            continue
        pts = list(tr)
        if len(pts) < 2:
            continue
        ghosts = pts[-4:-1] if len(pts) >= 4 else pts[:-1]
        if len(ghosts) > 3:
            ghosts = ghosts[-3:]
        alphas = T.TRAIL_ALPHAS[-len(ghosts) :]
        while len(alphas) < len(ghosts):
            alphas = (T.TRAIL_ALPHAS[0],) + alphas
        for i, (px, py) in enumerate(ghosts):
            a = alphas[i] if i < len(alphas) else T.TRAIL_ALPHAS[-1]
            col = T.bgr_with_white_opacity(a)
            pr = max(2, int(ball.radius * (0.35 + 0.1 * i)))
            overlay = frame.copy()
            cv2.circle(overlay, (int(px), int(py)), pr, col, -1, cv2.LINE_AA)
            cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)


def draw_spawn_telegraphs_rect(frame: np.ndarray, spawn_pending, tick: int, _game=None) -> None:
    if not spawn_pending:
        return
    h, w = frame.shape[:2]
    phase = 0.5 + 0.5 * math.sin(tick * (2 * math.pi * T.TELEGRAPH_PULSE_HZ / 60.0))
    a = T.TELEGRAPH_PULSE_LOW + (T.TELEGRAPH_PULSE_HIGH - T.TELEGRAPH_PULSE_LOW) * phase

    for item in spawn_pending:
        ball = item["ball"]
        side = getattr(ball, "spawn_side", "top")
        diam = int(ball.radius * 2 * 1.4)
        bar_w = T.TELEGRAPH_BAR_W
        # Mockup: rose vertical strip for normal spawn; mint for health pickup
        col = T.C_MINT if getattr(ball, "is_health_ball", False) else T.C_HEART_FILL
        col_f = np.array(col, dtype=np.float32) * a

        if side == "top":
            x0, y0 = max(0, int(ball.x - diam // 2)), 0
            x1, y1 = min(w, x0 + diam), min(h, bar_w)
        elif side == "bottom":
            x0, y0 = max(0, int(ball.x - diam // 2)), max(0, h - bar_w)
            x1, y1 = min(w, x0 + diam), h
        elif side == "left":
            x0, y0 = 0, max(0, int(ball.y - diam // 2))
            x1, y1 = min(w, bar_w), min(h, y0 + diam)
        else:
            x0, y0 = max(0, w - bar_w), max(0, int(ball.y - diam // 2))
            x1, y1 = w, min(h, y0 + diam)
        if x1 <= x0 or y1 <= y0:
            continue
        roi = frame[y0:y1, x0:x1].astype(np.float32)
        blend = 0.55
        roi[:] = np.clip(roi * (1.0 - blend) + col_f * blend, 0, 255)
        frame[y0:y1, x0:x1] = roi.astype(np.uint8)


def draw_hands_arcade(frame: np.ndarray, hands) -> None:
    """Thin hollow white hit rings (mockup); strength follows tracking confidence."""
    for hand in hands:
        x = int(hand["x"])
        y = int(hand["y"])
        r = max(4, int(hand["radius"]))
        conf = float(hand.get("confidence", 0.75))
        ring_a = 0.45 + 0.40 * max(0.0, min(1.0, conf))
        col = T.bgr_with_white_opacity(ring_a)
        th = max(2, min(4, int(1 + r // 26)))
        cv2.circle(frame, (x, y), r, col, th, cv2.LINE_AA)


def draw_combo_flash(frame: np.ndarray, frames_left: int) -> None:
    if frames_left <= 0:
        return
    t = min(1.0, frames_left / float(T.DUR_COMBO_FLASH))
    a = T.AMBER_COMBO_FLASH * t
    overlay = np.full_like(frame, T.C_AMBER, dtype=np.uint8)
    cv2.addWeighted(overlay, a, frame, 1.0 - a, 0, frame)


def draw_life_loss_rose(frame: np.ndarray, frames_left: int) -> None:
    if frames_left <= 0:
        return
    a = T.ROSE_LIFE_FLASH * (frames_left / float(max(1, T.DUR_LIFE_LOSS_FLASH)))
    overlay = np.full_like(frame, T.C_ROSE, dtype=np.uint8)
    cv2.addWeighted(overlay, a, frame, 1.0 - a, 0, frame)


def _mission_label_title(m) -> str:
    mid = m.get("id", "")
    return {"pop": "Pops", "score": "Score", "combo": "Combo", "heal": "Heal"}.get(
        mid, "Goal"
    )


def _draw_goal_checkmark(frame, cx: int, cy: int, size: int, col) -> None:
    """Short vector check (mockup completed row)."""
    s = max(4, size)
    p0 = (cx - s, cy)
    p1 = (cx - s // 3, cy + s // 2)
    p2 = (cx + s, cy - s // 2)
    cv2.line(frame, p0, p1, col, max(2, s // 5), cv2.LINE_AA)
    cv2.line(frame, p1, p2, col, max(2, s // 5), cv2.LINE_AA)


def _rounded_rect_filled(frame, x0, y0, x1, y1, r, fill_bgr, border_bgr=None):
    """Small rounded rect for hint key pills (r ~ 3)."""
    r = max(1, min(r, min(x1 - x0, y1 - y0) // 2 - 1))
    m = np.zeros((y1 - y0, x1 - x0), dtype=np.uint8)
    cv2.rectangle(m, (r, 0), (x1 - x0 - r, y1 - y0), 255, -1)
    cv2.rectangle(m, (0, r), (x1 - x0, y1 - y0 - r), 255, -1)
    cv2.circle(m, (r, r), r, 255, -1)
    cv2.circle(m, (x1 - x0 - r - 1, r), r, 255, -1)
    cv2.circle(m, (r, y1 - y0 - r - 1), r, 255, -1)
    cv2.circle(m, (x1 - x0 - r - 1, y1 - y0 - r - 1), r, 255, -1)
    roi = frame[y0:y1, x0:x1]
    col = np.array(fill_bgr, dtype=np.float32)
    mm = (m > 0).astype(np.float32)[:, :, np.newaxis]
    rf = roi.astype(np.float32)
    roi[:] = np.clip(rf * (1.0 - mm) + col * mm, 0, 255).astype(np.uint8)
    if border_bgr is not None:
        bc = tuple(int(c) for c in border_bgr)
        contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            ox, oy = x0, y0
            for cnt in contours:
                cnt = cnt + np.array([[[ox, oy]]], dtype=cnt.dtype)
                cv2.drawContours(frame, [cnt], -1, bc, 1, cv2.LINE_AA)


def draw_arcade_hud(
    frame: np.ndarray,
    game,
    *,
    ui_tick: int,
    countdown_on: bool,
    milestone_on: bool,
    quiet_on: bool = False,
) -> None:
    h, w, _ = frame.shape
    missions = game.missions or []
    margin = T.HUD_MARGIN

    # --- Score panel (left) — mockup: tall glass card ---
    score_txt = f"{int(game.score):,}" if game.score >= 1000 else str(int(game.score))
    best_txt = f"Best {int(game.best_score)}"
    pw = 158
    ph = 94
    draw_glass_panel(frame, margin, margin, pw, ph)
    ly = margin + T.PANEL_PAD_Y + 14
    arcade_text.put_text(
        frame,
        "SCORE",
        margin + T.PANEL_PAD_X,
        ly,
        px_height=T.PX_PANEL_LABEL,
        color_bgr=T.bgr_with_white_opacity(T.TEXT_TERTIARY),
    )
    ly += 22
    arcade_text.put_text(
        frame,
        score_txt,
        margin + T.PANEL_PAD_X,
        ly,
        px_height=T.PX_SCORE_NUMBER,
        color_bgr=T.bgr_with_white_opacity(T.TEXT_PRIMARY),
    )
    ly += 30
    arcade_text.put_text(
        frame,
        best_txt,
        margin + T.PANEL_PAD_X,
        ly,
        px_height=T.PX_PANEL_LABEL,
        color_bgr=T.bgr_with_white_opacity(T.TEXT_GHOST),
    )

    # --- Hearts (center top) ---
    cx = w // 2
    hy = margin + 14
    n = int(game.lives_max)
    lost_anim = getattr(game, "life_loss_anim_frames", 0)
    total_w = n * T.HEART_W + (n - 1) * T.HEART_GAP
    x0 = cx - total_w // 2
    for i in range(n):
        hx = x0 + i * (T.HEART_W + T.HEART_GAP) + T.HEART_W // 2
        on = i < int(game.lives_left)
        scale = 0.38
        if not on and lost_anim > 0 and i == int(game.lives_left):
            scale *= max(0.0, lost_anim / float(T.DUR_HEART_LOSS_ANIM))
        pts = _heart_outline_points(hx, hy, scale * 0.42)
        if on:
            cv2.fillPoly(frame, [pts], T.C_HEART_FILL, cv2.LINE_AA)
            cv2.polylines(
                frame, [pts], True, T.bgr_with_white_opacity(0.22), 1, cv2.LINE_AA
            )
        else:
            cv2.polylines(
                frame,
                [pts],
                True,
                T.bgr_with_white_opacity(T.HEART_OUTLINE_ALPHA),
                max(1, int(T.HEART_STROKE_PX)),
                cv2.LINE_AA,
            )

    # --- Combo badge (center, below hearts) — combo >= 2, hide 2s after last pop ---
    combo = int(game.combo)
    mult = int(game.multiplier)
    last_pop = int(getattr(game, "combo_last_pop_frame", 0))
    fc = int(game.frame_count)
    pulse_f = int(getattr(game, "combo_pulse_frames", 0))
    visible = (
        combo >= T.COMBO_MIN_VISIBLE
        and not countdown_on
        and not quiet_on
        and (
            pulse_f > 0
            or (fc - last_pop) < T.COMBO_BADGE_FADE_FRAMES
        )
    )
    pulse_scale = 1.0
    if pulse_f > 0:
        u = pulse_f / float(max(1, T.COMBO_PULSE_FRAMES))
        pulse_scale = 1.0 + 0.18 * math.sin(u * math.pi)

    if visible:
        label = f"x {mult} combo"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.22, 1)
        bw = int((tw + 32) * pulse_scale)
        bh = int(28 * pulse_scale)
        bx = cx - bw // 2
        by = margin + 36
        draw_glass_panel(frame, bx, by, bw, bh, corner_r=T.COMBO_BADGE_RADIUS)
        roi = frame[by : by + bh, bx : bx + bw]
        amb = np.full_like(roi, T.C_AMBER, dtype=np.uint8)
        blended = cv2.addWeighted(roi, 1.0 - T.AMBER_COMBO_BADGE_BG, amb, T.AMBER_COMBO_BADGE_BG, 0)
        roi[:] = blended
        cr = min(T.COMBO_BADGE_RADIUS, min(bw, bh) // 2 - 1)
        m = _rounded_rect_mask(bh, bw, cr)
        contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        bor = np.zeros((bh, bw), dtype=np.uint8)
        cv2.drawContours(bor, contours, -1, 255, 1)
        bc = np.array(T.bgr_mult_alpha(T.C_AMBER, T.AMBER_COMBO_BADGE_BORDER), dtype=np.float32)
        r = roi.astype(np.float32)
        for c in range(3):
            r[:, :, c] = np.where(bor > 0, r[:, :, c] * 0.55 + bc[c] * 0.45, r[:, :, c])
        roi[:] = np.clip(r, 0, 255).astype(np.uint8)
        arcade_text.put_text(
            frame,
            label,
            bx + 14,
            by + 19,
            px_height=T.PX_COMBO_BADGE,
            color_bgr=T.bgr_mult_alpha(T.C_AMBER, T.AMBER_COMBO_TEXT),
        )

    # --- Goals panel (right) — mockup: "RUN N - GOALS", rows with bar + "25/47" ---
    gw = 228
    row_h = 30
    gh = 36 + len(missions[:3]) * row_h + 28
    gx = w - margin - gw
    gy = margin
    panel_h = min(h - margin - T.HINT_H - 12, gh)
    draw_glass_panel(frame, gx, gy, gw, max(52, panel_h))
    gy_t = gy + T.PANEL_PAD_Y + 10
    run_hdr = f"RUN {int(game.play_level)} - GOALS"
    arcade_text.put_text(
        frame,
        run_hdr.upper(),
        gx + T.PANEL_PAD_X,
        gy_t,
        px_height=T.PX_PANEL_LABEL,
        color_bgr=T.bgr_with_white_opacity(T.TEXT_TERTIARY),
    )
    gy_t += 22
    flash = int(getattr(game, "goal_flash_frames", 0))
    label_w = 56
    bar_left = gx + T.PANEL_PAD_X + label_w
    bar_right = gx + gw - T.PANEL_PAD_X - 44
    bar_w_tot = max(24, bar_right - bar_left)
    bar_h = 5
    _font = cv2.FONT_HERSHEY_SIMPLEX

    for m in missions[:3]:
        mid = m.get("id", "")
        lbl = _mission_label_title(m)
        tgt = max(1, int(m.get("target", 1)))
        prog = int(m.get("progress", 0))
        done_m = bool(m.get("done"))
        fill_t = 1.0 if done_m else max(0.0, min(1.0, prog / float(tgt)))

        arcade_text.put_text(
            frame,
            lbl,
            gx + T.PANEL_PAD_X,
            gy_t + 10,
            px_height=T.PX_GOAL_NAME,
            color_bgr=T.bgr_with_white_opacity(T.TEXT_SECONDARY),
        )

        if done_m:
            fill_col = T.bgr_mult_alpha(T.C_MINT, T.MINT_FILL_COMPLETE)
        elif mid == "pop":
            fill_col = T.bgr_mult_alpha(T.C_AMBER, T.AMBER_GOAL_NEAR)
        else:
            fill_col = T.bgr_mult_alpha(T.C_MINT, T.MINT_FILL_PROGRESS)
        if flash > 0 and done_m:
            fill_col = T.bgr_with_white_opacity(0.88)

        track = T.bgr_with_white_opacity(T.BORDER_DIM)
        bar_y = gy_t + 14
        cv2.rectangle(
            frame,
            (bar_left, bar_y),
            (bar_left + bar_w_tot, bar_y + bar_h),
            track,
            -1,
        )
        fw = int(bar_w_tot * fill_t)
        if fw > 0:
            cv2.rectangle(
                frame,
                (bar_left, bar_y),
                (bar_left + fw, bar_y + bar_h),
                fill_col,
                -1,
            )

        row_cy = bar_y + bar_h // 2 + 1
        if done_m:
            _draw_goal_checkmark(
                frame,
                bar_left + bar_w_tot + 20,
                row_cy,
                7,
                T.bgr_mult_alpha(T.C_MINT, T.MINT_FILL_COMPLETE),
            )
        else:
            cnt = f"{prog}/{tgt}"
            (cw, ch), _ = cv2.getTextSize(cnt, _font, 0.34, 1)
            arcade_text.put_text(
                frame,
                cnt,
                gx + gw - T.PANEL_PAD_X - cw,
                gy_t + 10,
                px_height=10,
                color_bgr=T.bgr_with_white_opacity(T.TEXT_PRIMARY),
            )

        gy_t += row_h

    foot = f"Lv {int(game.level)} · {int(game.coins):,} coins"
    arcade_text.put_text(
        frame,
        foot,
        gx + T.PANEL_PAD_X,
        gy + panel_h - 10,
        px_height=T.PX_GOAL_NAME,
        color_bgr=T.bgr_with_white_opacity(0.15),
    )


def draw_near_miss_sparks(frame: np.ndarray, sparks) -> None:
    for p in sparks:
        t = p["life"] / float(max(1, p.get("max_life", 1)))
        col = T.bgr_with_white_opacity(0.5 * max(0.15, t))
        r = int(p.get("r", 2))
        cv2.circle(frame, (int(p["x"]), int(p["y"])), r, col, -1, cv2.LINE_AA)


def draw_hint_bar(frame: np.ndarray, game, *, opacity: float = 1.0) -> None:
    if opacity <= 0.01:
        return
    h, w = frame.shape[:2]
    y0 = h - T.HINT_H
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, y0), (w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, T.HINT_BAR_ALPHA * opacity, frame, 1.0 - T.HINT_BAR_ALPHA * opacity, 0, frame)

    parts = [
        ("[M]", "reroll goals"),
        ("[N]", "next run"),
        ("[R]", "restart"),
        ("Esc", "quit"),
    ]
    if getattr(game, "game_over", False):
        parts = [("[R]", "restart"), ("Esc", "quit")]

    _font = cv2.FONT_HERSHEY_SIMPLEX
    ks, ds = 0.34, 0.30
    gap = 16
    pill_r = 3
    o = max(0.15, min(1.0, opacity))
    pill_fill = T.bgr_with_white_opacity(0.08 * o)
    pill_edge = T.bgr_with_white_opacity(0.12 * o)
    key_col = T.bgr_with_white_opacity(0.42 * o)
    desc_col = T.bgr_with_white_opacity(0.22 * o)

    seg_w = []
    for key, desc in parts:
        (kw, kh), _ = cv2.getTextSize(key, _font, ks, 1)
        (dw, _), _ = cv2.getTextSize(desc, _font, ds, 1)
        pw = kw + 12
        ph = max(kh + 8, 20)
        seg_w.append((key, desc, kw, kh, dw, pw, ph))

    tw_sum = 0
    for _a, _b, _kw, _kh, dw, pw, _ph in seg_w:
        tw_sum += pw + 8 + dw + gap
    if seg_w:
        tw_sum -= gap

    x = (w - tw_sum) // 2
    y_base = h - 8

    for key, desc, kw, kh, dw, pw, ph in seg_w:
        px1, px2 = x, x + pw
        py2 = y_base + 4
        py1 = max(y0 + 2, py2 - ph)
        _rounded_rect_filled(
            frame, px1, py1, px2, py2, pill_r, pill_fill, pill_edge
        )
        cv2.putText(
            frame,
            key,
            (x + (pw - kw) // 2, py2 - 5),
            _font,
            ks,
            key_col,
            1,
            cv2.LINE_AA,
        )
        x = px2 + 8
        (_, dh), _ = cv2.getTextSize(desc, _font, ds, 1)
        cv2.putText(
            frame,
            desc,
            (x, y_base),
            _font,
            ds,
            desc_col,
            1,
            cv2.LINE_AA,
        )
        x += dw + gap
