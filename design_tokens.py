"""
Webcam Arcade — design tokens (BGR for OpenCV).
Every color: hex reference + rgba() with exact opacity where applicable.
"""

import math

# ─── Base surfaces ─────────────────────────────────────────────────────────
# Void #0a0a0e — game backdrop / adaptive tint base
C_VOID = (14, 10, 10)  # #0a0a0e BGR
# Glass panel: white 5.5% (see PANEL_FILL_ALPHA) + blur — never solid fills
C_WHITE = (255, 255, 255)

# Soot — hint bar: black 35%
C_HINT_BAR_BG = (0, 0, 0)
HINT_BAR_ALPHA = 0.35

# ─── Accents (full-strength BGR; multiply by opacity at use) ───────────────
# Mint #7dcfaa — progress, health glow, completion
C_MINT = (170, 207, 125)  # #7dcfaa
MINT_FILL_PROGRESS = 0.65
MINT_FILL_COMPLETE = 0.90
MINT_GLOW_HEALTH = 0.55

# Amber #ffc87a — combo, score pop high mult, near-complete goals
C_AMBER = (122, 200, 255)  # #ffc87a
AMBER_COMBO_BADGE_BG = 0.10
AMBER_COMBO_BADGE_BORDER = 0.20
AMBER_COMBO_TEXT = 0.85
AMBER_GOAL_NEAR = 0.55  # goal > 80% fill
AMBER_COMBO_FLASH = 0.12

# Rose #ff7090 — life loss, danger
C_ROSE = (144, 112, 255)  # #ff7090
# Heart fill (mockup) #FF829D — slightly softer pink than core rose
C_HEART_FILL = (157, 130, 255)  # #FF829D BGR (mockup hearts)
ROSE_HEART_FILL = 0.85  # legacy multiplier when using C_ROSE
ROSE_URGENCY_HALO = 0.35
ROSE_LIFE_FLASH = 0.18
ROSE_TELEGRAPH_URGENCY = 0.40

# ─── White text opacity scale ───────────────────────────────────────────────
TEXT_PRIMARY = 1.00    # 100% — score number, active labels
TEXT_SECONDARY = 0.50  # 50% — goal names, sub-labels
TEXT_TERTIARY = 0.28   # 28% — "SCORE" label, best score line
TEXT_GHOST = 0.18      # 18% — hint bar secondary, coins/level ghost
BORDER_PANEL = 0.10    # 10% — panel borders
BORDER_DIM = 0.07      # 7% — goal track background
BORDER_BALL = 0.08     # 8% — ball rim normal
BORDER_BALL_URGENT = 0.25

# Glass geometry
PANEL_FILL_ALPHA = 0.055
PANEL_BORDER_ALPHA = 0.10
PANEL_RADIUS = 12
PANEL_PAD_X = 15
PANEL_PAD_Y = 9
HUD_MARGIN = 12
HINT_H = 28
BLUR_KSIZE = 21  # OpenCV Gaussian (odd); ~20px effective

# Hearts
HEART_W = 16
HEART_H = 14
HEART_GAP = 5
HEART_OUTLINE_ALPHA = 0.20
HEART_STROKE_PX = 1.2

# Combo badge
COMBO_BADGE_RADIUS = 20  # pill corner
COMBO_MIN_VISIBLE = 2
COMBO_BADGE_FADE_FRAMES = 120  # 2s @ 60fps after last pop
COMBO_PULSE_FRAMES = 10
COMBO_PULSE_SCALE_0 = 1.0
COMBO_PULSE_SCALE_PEAK = 1.18

# Ball visual (BGR mid/edge tints — blended at stated alphas in renderer)
BALL_HIGHLIGHT_OFFSET = (0.32, 0.28)  # (cx - r*0.32, cy - r*0.28)
BALL_HIGHLIGHT_ALPHA = 0.96
BALL_BODY_VIOLET_MID = (255, 190, 210)   # rgba(210,190,255,.5) ~ body
BALL_BODY_VIOLET_EDGE = (230, 120, 150)  # rgba(150,120,230,.15) edge line
BALL_GLOW_VIOLET = (255, 140, 170)       # rgba(170,140,255,.18) outer
BALL_HEALTH_MID = (180, 230, 140)
BALL_HEALTH_EDGE = (130, 195, 80)
BALL_HEALTH_GLOW = (155, 210, 100)
BALL_URGENCY_HALO_MAX = 0.40

# Trail (oldest → newest): 8%, 14%, 22% white
TRAIL_ALPHAS = (0.08, 0.14, 0.22)

# Telegraph (0.35s pre-spawn)
TELEGRAPH_SEC = 0.35
TELEGRAPH_BAR_W = 6
TELEGRAPH_PULSE_LOW = 0.20
TELEGRAPH_PULSE_HIGH = 0.55
TELEGRAPH_PULSE_HZ = 4.0

# Pop burst
POP_PARTICLE_MIN = 10
POP_PARTICLE_MAX = 14
POP_PARTICLE_WHITE = 0.80
DUR_POP_BURST = 18

# Score popup
DUR_SCORE_POP = 30
SCORE_POP_DRIFT_PX = 40

# Combo full-screen flash
DUR_COMBO_FLASH = 24

# Life loss
DUR_LIFE_LOSS_FLASH = 6
DUR_HEART_LOSS_ANIM = 12

# Near-miss sparks
NEAR_MISS_DIST_MULT = 1.5
NEAR_MISS_SPARK_COUNT = 4
DUR_NEAR_MISS_SPARK = 12

# Goal complete row flash
DUR_GOAL_FLASH = 14

# Calibration / overlays
CALIBRATION_TINT_ALPHA = 0.60
GAME_OVER_EXTRA_BLACK = 0.45

# Google Fonts (for HTML); OpenCV: use cv2.freetype + DMSans-*.ttf if present
GOOGLE_FONTS_DM_SANS_CSS = (
    "https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,300;0,400;1,300&display=swap"
)

# Typography targets (px at 720p reference — Hershey approximated in arcade_text)
PX_SCORE_NUMBER = 24
PX_SCORE_POP = 18
PX_COMBO_BADGE = 9
PX_PANEL_LABEL = 8
PX_GOAL_NAME = 8
PX_HINT_KEY = 7


def bgr_with_white_opacity(opacity: float) -> tuple:
    """White at opacity → BGR uint8 tuple."""
    o = max(0.0, min(1.0, float(opacity)))
    v = int(round(255 * o))
    return (v, v, v)


def bgr_mult_alpha(bgr, alpha: float) -> tuple:
    """Tint BGR channels by alpha (0–1)."""
    a = max(0.0, min(1.0, float(alpha)))
    return tuple(int(c * a) for c in bgr)


def lerp(a: float, b: float, t: float) -> float:
    t = max(0.0, min(1.0, t))
    return a + (b - a) * t


def ease_out_elastic(t: float) -> float:
    """Elastic ease for badge pop (approximation)."""
    t = max(0.0, min(1.0, t))
    if t == 0 or t == 1:
        return t
    p = 0.3
    return pow(2, -10 * t) * math.sin((t - p / 4) * (2 * math.pi) / p) + 1
