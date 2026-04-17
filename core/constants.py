# core/constants.py
# ─────────────────────────────────────────────────────────────────────────────
# all constants live here — colors, screen size, difficulty presets, csv cols
# nothing is computed, nothing is imported
# ─────────────────────────────────────────────────────────────────────────────

# screen
SCREEN_W, SCREEN_H = 1280, 720
FPS                = 60

# file output
CSV_PATH    = "patient_performance.csv"
CSV_COLUMNS = [
    "Timestamp", "TargetID", "ReactionTime", "ErrorDistance",
    "Velocity", "CurrentDifficulty", "HitScore", "MotionVariance",
    "TargetType", "AttentionLapse",
]

# ── pygame color palette ──────────────────────────────────────────────────────
BG_DARK   = ( 14,  16,  26)
PANEL     = ( 20,  25,  42)
PANEL2    = ( 26,  32,  55)
DARK_GREY = ( 20,  25,  42)
BORDER    = ( 45,  58,  95)
CYAN      = (  0, 210, 255)
PINK      = (255,  50, 130)
GREEN     = ( 50, 230, 120)
YELLOW    = (255, 210,  30)
ORANGE    = (255, 140,  30)
RED       = (255,  70,  70)
GOLD      = (255, 195,  40)
WHITE     = (255, 255, 255)
GREY      = (130, 145, 170)
LGREY     = (190, 205, 225)

# ── matplotlib hex equivalents ────────────────────────────────────────────────
HEX_NEON    = "#00d2ff"
HEX_PINK    = "#ff3282"
HEX_GREEN   = "#32e678"
HEX_YELLOW  = "#ffd21e"
HEX_ORANGE  = "#ff8c1e"
HEX_RED     = "#ff4646"
HEX_BG      = "#0e101a"
HEX_PANEL   = "#0d1117"
HEX_GRID    = "#1a2033"
HEX_DIM     = "#505a6e"
HEX_MID     = "#8892a6"
HEX_WHITE   = "#e8eaf0"

# ── difficulty presets ────────────────────────────────────────────────────────
# for adhd training: smaller targets + faster fade = higher attentional demand
DIFFICULTY_LEVELS = {
    1: {"circle_r": 55, "lifetime": 3.0, "label": "Level 1 - Introductory"},
    2: {"circle_r": 44, "lifetime": 2.5, "label": "Level 2 - Standard"},
    3: {"circle_r": 34, "lifetime": 2.0, "label": "Level 3 - Advanced"},
    4: {"circle_r": 26, "lifetime": 1.5, "label": "Level 4 - Expert"},
    5: {"circle_r": 18, "lifetime": 1.1, "label": "Level 5 - Elite"},
}

DIFF_COLORS = {
    1: GREEN, 2: CYAN, 3: YELLOW, 4: PINK, 5: RED
}

# ── scoring ───────────────────────────────────────────────────────────────────
HIT_POINTS = {"Perfect": 300, "Great": 200, "Good": 100}
HP_GAIN    = {"Perfect": 4.0, "Great": 2.0, "Good": 1.0}
HP_LOSS_MISS   = 12.0
HP_LOSS_MISCLICK = 0.0   # reserved for future use

# ── attention / dda thresholds ────────────────────────────────────────────────
STABILITY_VARIANCE_CAP = 500.0   # denominator in stability ratio
STABILITY_GOOD         = 0.7     # green zone
STABILITY_WARN         = 0.4     # yellow zone
IMPULSIVITY_VAR_THRESH = 120     # cursor variance above this = impulsive movement
DDA_WINDOW             = 3       # trials before difficulty re-evaluation
SPAWN_INTERVAL         = 2.2     # seconds between target spawns