"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           NEURO-OSU: ADAPTIVE KINETIC PATH-FINDER                            ║
║           A Serious Game for Motor Recovery & Cognitive Training             ║
╚══════════════════════════════════════════════════════════════════════════════╝

PROJECT DESCRIPTION
───────────────────
Objective:
    Neuro-Osu is a clinically-motivated "serious game" that quantifies motor
    precision, reaction speed, and trajectory stability in patients undergoing
    neurological rehabilitation. By mapping classical Osu-style mechanics onto
    measurable biomechanical parameters, it generates a longitudinal performance
    record suitable for clinical review.

Interactivity:
    • Hit Circles  – Neon targets spawn and fade; patient must click before
                     time runs out. Reaction latency is recorded.
    • Neural Paths – Click-and-drag sliders that follow curved/straight paths;
                     deviation from the ideal trajectory is measured per frame.
    • Adaptive DDA – Stability Ratio triggers automatic difficulty escalation
                     (or de-escalation) every 3 consecutive qualifying trials.

Data Captured (patient_performance.csv):
    Timestamp | TargetID | ReactionTime | ErrorDistance | Velocity |
    CurrentDifficulty | HitScore | MotionVariance | TargetType

Output:
    • Real-time Pygame gameplay window (patient-facing)
    • Live Matplotlib clinical dashboard (doctor-facing, separate thread)
    • CSV export of every interaction for longitudinal analysis
"""

# ─────────────────────────────────────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────────────────────────────────────
import pygame
import sys
import math
import random
import time
import csv
import os
import threading
import multiprocessing
from collections import deque
from datetime import datetime

import matplotlib
# Use Qt5 backend which is more thread-friendly than TkAgg
try:
    matplotlib.use("Qt5Agg")
except:
    matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.gridspec import GridSpec

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS & PALETTE
# ─────────────────────────────────────────────────────────────────────────────
SCREEN_W, SCREEN_H = 1280, 720
FPS = 60

# New Custom Palette
BG_DARK       = ( 53,  50,  76)   # #35324c (Background)
DARK_GREY     = ( 43,  40,  62)   # Slightly darker for contrast
CYAN          = ( 92, 157, 159)   # #5c9d9f (Teal - Primary Targets & UI)
PINK          = (220, 152, 164)   # #dc98a4 (Light Pink - Accents & Sliders)
YELLOW        = (193,  61,  80)   # #c13d50 (Deep Red - Highlights)
WHITE         = (255, 255, 255)   # Base text
GREY          = (195, 202, 216)   # #c3cad8 (Light Grey)
GREEN         = ( 92, 157, 159)   # #5c9d9f (Teal - Reused for "Good/Perfect")
RED           = (193,  61,  80)   # #c13d50 (Deep Red - Reused for "Miss")

CSV_PATH = "patient_performance.csv"
CSV_COLUMNS = [
    "Timestamp", "TargetID", "ReactionTime", "ErrorDistance",
    "Velocity", "CurrentDifficulty", "HitScore", "MotionVariance", "TargetType"
]

# ─────────────────────────────────────────────────────────────────────────────
# DIFFICULTY PRESETS
# ─────────────────────────────────────────────────────────────────────────────
DIFFICULTY_LEVELS = {
    1: {"circle_r": 55, "lifetime": 3.0, "path_width": 28, "label": "Level 1 – Introductory"},
    2: {"circle_r": 44, "lifetime": 2.5, "path_width": 22, "label": "Level 2 – Standard"},
    3: {"circle_r": 34, "lifetime": 2.0, "path_width": 16, "label": "Level 3 – Advanced"},
    4: {"circle_r": 26, "lifetime": 1.5, "path_width": 11, "label": "Level 4 – Expert"},
    5: {"circle_r": 18, "lifetime": 1.1, "path_width":  7, "label": "Level 5 – Elite"},
}

# ─────────────────────────────────────────────────────────────────────────────
# SHARED DATA STORE  (thread-safe via lock)
# ─────────────────────────────────────────────────────────────────────────────
class SharedData:
    def __init__(self):
        self.lock = threading.Lock()
        self.trial_numbers   = deque(maxlen=200)
        self.reaction_times  = deque(maxlen=200)
        self.stabilities     = deque(maxlen=200)   # 1 – norm_variance
        self.difficulties    = deque(maxlen=200)
        self.scores          = deque(maxlen=200)
        self.total_trials    = 0
        self.total_hits      = 0
        self.current_diff    = 1
        self.session_start   = time.time()

shared = SharedData()

# ─────────────────────────────────────────────────────────────────────────────
# CSV LOGGER
# ─────────────────────────────────────────────────────────────────────────────
def init_csv():
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, "w", newline="") as f:
            csv.writer(f).writerow(CSV_COLUMNS)

def log_trial(target_id, reaction_time, error_dist, velocity,
              difficulty, hit_score, motion_var, target_type):
    row = [
        datetime.now().isoformat(timespec="milliseconds"),
        target_id,
        f"{reaction_time:.4f}",
        f"{error_dist:.2f}",
        f"{velocity:.2f}",
        difficulty,
        hit_score,
        f"{motion_var:.4f}",
        target_type,
    ]
    with open(CSV_PATH, "a", newline="") as f:
        csv.writer(f).writerow(row)

    with shared.lock:
        shared.total_trials += 1
        shared.trial_numbers.append(shared.total_trials)
        shared.reaction_times.append(reaction_time)
        stability = max(0.0, 1.0 - min(motion_var / 500.0, 1.0))
        shared.stabilities.append(stability)
        shared.difficulties.append(difficulty)
        shared.scores.append(1 if hit_score != "Miss" else 0)
        if hit_score != "Miss":
            shared.total_hits += 1
        shared.current_diff = difficulty

# ─────────────────────────────────────────────────────────────────────────────
# ADAPTIVE DIFFICULTY ENGINE
# ─────────────────────────────────────────────────────────────────────────────
class DifficultyManager:
    def __init__(self):
        self.level = 1
        self.recent_scores   = deque(maxlen=3)   # "Perfect"/"Great"/"Good"/"Miss"
        self.recent_variance = deque(maxlen=3)   # float

    @property
    def params(self):
        return DIFFICULTY_LEVELS[self.level]

    def record(self, hit_score, motion_var):
        self.recent_scores.append(hit_score)
        self.recent_variance.append(motion_var)
        if len(self.recent_scores) == 3:
            self._evaluate()

    def _evaluate(self):
        all_good  = all(s in ("Perfect", "Great", "Good") for s in self.recent_scores)
        low_shake = all(v < 120 for v in self.recent_variance)
        all_miss  = all(s == "Miss" for s in self.recent_scores)

        if all_good and low_shake and self.level < 5:
            self.level += 1
            self.recent_scores.clear()
            self.recent_variance.clear()
        elif all_miss and self.level > 1:
            self.level -= 1
            self.recent_scores.clear()
            self.recent_variance.clear()

# ─────────────────────────────────────────────────────────────────────────────
# PARTICLE SYSTEM
# ─────────────────────────────────────────────────────────────────────────────
class Particle:
    def __init__(self, x, y, color):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(1.5, 5.0)
        self.x, self.y = x, y
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.color = color
        self.life  = 1.0
        self.decay = random.uniform(0.03, 0.07)
        self.size  = random.randint(3, 8)

    def update(self):
        self.x    += self.vx
        self.y    += self.vy
        
        # Add friction so they slow down smoothly
        self.vx   *= 0.92
        self.vy   *= 0.92 
        self.vy   += 0.05 # Lighter gravity
        
        self.life -= self.decay
        self.size  = max(0.1, self.size - 0.1)

    def draw(self, surf):
        alpha = max(0, int(self.life * 255))
        col   = (*self.color[:3], alpha)
        s = pygame.Surface((self.size * 2, self.size * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, col, (self.size, self.size), int(self.size))
        surf.blit(s, (int(self.x - self.size), int(self.y - self.size)))

# ─────────────────────────────────────────────────────────────────────────────
# FLOATING FEEDBACK TEXT
# ─────────────────────────────────────────────────────────────────────────────
class FloatText:
    def __init__(self, text, x, y, color, font):
        self.text  = text
        self.x, self.y = x, y
        self.color = color
        self.font  = font
        self.life  = 1.0
        self.vy    = -1.5

    def update(self):
        self.y    += self.vy
        self.life -= 0.025

    def draw(self, surf):
        alpha = max(0, int(self.life * 255))
        col   = (*self.color[:3], alpha)
        s = self.font.render(self.text, True, col)
        surf.blit(s, (int(self.x - s.get_width() // 2), int(self.y)))

# ─────────────────────────────────────────────────────────────────────────────
# HIT CIRCLE
# ─────────────────────────────────────────────────────────────────────────────
class HitCircle:
    _id_counter = 0

    def __init__(self, x, y, params):
        HitCircle._id_counter += 1
        self.id       = HitCircle._id_counter
        self.x, self.y = x, y
        self.radius   = params["circle_r"]
        self.lifetime = params["lifetime"]
        self.spawn_t  = time.time()
        self.alive    = True
        self.clicked  = False
        self.reaction = None
        self.first_move_t = None   # set externally when cursor moves toward target

    @property
    def age(self):
        return time.time() - self.spawn_t

    @property
    def fraction(self):
        return min(1.0, self.age / self.lifetime)

    def contains(self, mx, my):
        return math.hypot(mx - self.x, my - self.y) <= self.radius

    def hit_score(self, mx, my):
        dist = math.hypot(mx - self.x, my - self.y)
        r    = self.radius
        if   dist <= r * 0.35: return "Perfect", dist
        elif dist <= r * 0.65: return "Great",   dist
        elif dist <= r:        return "Good",    dist
        else:                  return "Miss",    dist

    def draw(self, surf, glow_surf):
        t     = self.fraction
        # Easing out cubic for smoother fade and approach
        ease_out = 1.0 - pow(1.0 - t, 3)
        alpha = max(0, int(255 * (1.0 - ease_out)))
        pulse = 0.9 + 0.1 * math.sin(time.time() * 6)
        r     = int(self.radius * pulse)

        # Outer approach ring (shrinks toward target)
        approach_r = int(self.radius + (self.radius * 2.0 * (1.0 - ease_out)))
        approach_a = max(0, int(180 * (1 - ease_out)))
        _draw_circle_alpha(surf, (*CYAN, approach_a), (self.x, self.y), approach_r, 2)

        # Glow
        for gw in range(3, 0, -1):
            ga = max(0, int(40 * (1 - t) * gw))
            _draw_circle_alpha(glow_surf, (*CYAN, ga), (self.x, self.y), r + gw * 6, 0)

        # Core circle
        _draw_circle_alpha(surf, (*DARK_GREY, alpha), (self.x, self.y), r, 0)
        _draw_circle_alpha(surf, (*CYAN, alpha),      (self.x, self.y), r, 3)

        # Inner crosshair
        ca = max(0, int(180 * (1 - t)))
        half = r // 3
        pygame.draw.line(surf, (*CYAN, ca),
                         (self.x - half, self.y), (self.x + half, self.y), 1)
        pygame.draw.line(surf, (*CYAN, ca),
                         (self.x, self.y - half), (self.x, self.y + half), 1)

# ─────────────────────────────────────────────────────────────────────────────
# SLIDER / NEURAL PATH
# ─────────────────────────────────────────────────────────────────────────────
def _make_bezier(p0, p1, p2, steps=60):
    pts = []
    for i in range(steps + 1):
        t   = i / steps
        x   = (1-t)**2*p0[0] + 2*(1-t)*t*p1[0] + t**2*p2[0]
        y   = (1-t)**2*p0[1] + 2*(1-t)*t*p1[1] + t**2*p2[1]
        pts.append((int(x), int(y)))
    return pts

class Slider:
    _id_counter = 1000

    def __init__(self, params):
        Slider._id_counter += 1
        self.id    = Slider._id_counter
        self.pw    = params["path_width"]
        self.lifetime = params["lifetime"] * 1.8

        margin = 160
        x0 = random.randint(margin, SCREEN_W - margin)
        y0 = random.randint(margin, SCREEN_H - margin)
        cx = random.randint(margin, SCREEN_W - margin)
        cy = random.randint(margin, SCREEN_H - margin)
        x1 = random.randint(margin, SCREEN_W - margin)
        y1 = random.randint(margin, SCREEN_H - margin)
        self.path     = _make_bezier((x0, y0), (cx, cy), (x1, y1))
        self.spawn_t  = time.time()
        self.alive    = True
        self.active   = False    # user is currently dragging
        self.progress = 0        # path index reached
        self.deviations = []     # list of float distances from path
        self.first_move_t = None
        self.reaction = None

    @property
    def start(self):
        return self.path[0]

    @property
    def end(self):
        return self.path[-1]

    @property
    def age(self):
        return time.time() - self.spawn_t

    @property
    def fraction(self):
        return min(1.0, self.age / self.lifetime)

    def nearest_idx(self, mx, my):
        best_d, best_i = float("inf"), 0
        for i, (px, py) in enumerate(self.path):
            d = math.hypot(mx - px, my - py)
            if d < best_d:
                best_d, best_i = d, i
        return best_i, best_d

    def draw(self, surf, glow_surf):
        if len(self.path) < 2:
            return
        t  = self.fraction
        alpha_path = max(0, int(200 * (1 - t ** 2)))

        # Draw glow path
        for i in range(len(self.path) - 1):
            ga = max(0, int(30 * (1 - t)))
            pygame.draw.line(glow_surf, (*PINK, ga),
                             self.path[i], self.path[i+1], self.pw + 12)

        # Draw path body
        for i in range(len(self.path) - 1):
            pygame.draw.line(surf, (*DARK_GREY, alpha_path),
                             self.path[i], self.path[i+1], self.pw + 4)
            pygame.draw.line(surf, (*PINK, alpha_path),
                             self.path[i], self.path[i+1], 2)

        # Progress overlay
        if self.progress > 1:
            for i in range(min(self.progress - 1, len(self.path) - 1)):
                pygame.draw.line(surf, (*GREEN, 200),
                                 self.path[i], self.path[i+1], self.pw)

        # Start node
        _draw_circle_alpha(surf, (*CYAN, alpha_path), self.start, 14, 3)
        _draw_circle_alpha(surf, (*DARK_GREY, alpha_path), self.start, 11, 0)

        # End node
        _draw_circle_alpha(surf, (*YELLOW, alpha_path), self.end, 14, 3)

# ─────────────────────────────────────────────────────────────────────────────
# DRAWING HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _draw_circle_alpha(surf, color, center, radius, width):
    if radius <= 0:
        return
    if len(color) == 4:
        s = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(s, color, (radius + 2, radius + 2), radius, width)
        surf.blit(s, (center[0] - radius - 2, center[1] - radius - 2))
    else:
        pygame.draw.circle(surf, color, center, radius, width)

def draw_hud(surf, fonts, diff_mgr, score, combo, accuracy, elapsed, health):
    params = diff_mgr.params
    lbl    = params["label"]
    level  = diff_mgr.level

    # Top bar background
    pygame.draw.rect(surf, DARK_GREY, (0, 0, SCREEN_W, 54))
    pygame.draw.line(surf, CYAN, (0, 54), (SCREEN_W, 54), 1)

    # Health Bar (Osu Style)
    health_pct = max(0, min(100, health)) / 100.0
    bar_width = 300
    pygame.draw.rect(surf, BG_DARK, (SCREEN_W//2 - bar_width//2, 10, bar_width, 10))
    pygame.draw.rect(surf, PINK, (SCREEN_W//2 - bar_width//2, 10, bar_width * health_pct, 10))

    # Score
    score_txt = fonts["hud"].render(f"{score:,}", True, WHITE)
    surf.blit(score_txt, (20, 10))

    # Combo
    if combo > 1:
        combo_txt = fonts["hud"].render(f"×{combo}", True, PINK)
        surf.blit(combo_txt, (200, 10))

    # Accuracy
    acc_txt = fonts["small"].render(f"ACC {accuracy:.1f}%", True, CYAN)
    surf.blit(acc_txt, (SCREEN_W // 2 - acc_txt.get_width() // 2, 16))

    # Difficulty
    diff_col = [GREEN, CYAN, YELLOW, PINK, RED][level - 1]
    diff_txt = fonts["small"].render(lbl, True, diff_col)
    surf.blit(diff_txt, (SCREEN_W - diff_txt.get_width() - 20, 16))

    # Timer
    mins  = int(elapsed) // 60
    secs  = int(elapsed) % 60
    t_txt = fonts["small"].render(f"{mins:02d}:{secs:02d}", True, GREY)
    surf.blit(t_txt, (SCREEN_W - 90, 58))

def draw_grid(surf):
    """Subtle background grid for cyber aesthetic."""
    grid_color = (63, 60, 86) # Just slightly lighter than BG_DARK
    for x in range(0, SCREEN_W, 60):
        pygame.draw.line(surf, grid_color, (x, 0), (x, SCREEN_H), 1)
    for y in range(54, SCREEN_H, 60):
        pygame.draw.line(surf, grid_color, (0, y), (SCREEN_W, y), 1)

# ─────────────────────────────────────────────────────────────────────────────
# CLINICAL DASHBOARD (Matplotlib – runs in separate thread)
# ─────────────────────────────────────────────────────────────────────────────
_dashboard_stop = threading.Event()

def clinical_dashboard():
    try:
        plt.style.use("dark_background")
        fig = plt.figure(figsize=(12, 7), facecolor="#0d1117")
        fig.canvas.manager.set_window_title("Neuro-Osu  ▸  Clinical Dashboard")
        gs  = GridSpec(2, 3, figure=fig, hspace=0.45, wspace=0.4)

        ax_rt    = fig.add_subplot(gs[0, :2])   # Reaction Time trend
        ax_stab  = fig.add_subplot(gs[1, :2])   # Stability trend
        ax_diff  = fig.add_subplot(gs[0, 2])    # Difficulty gauge
        ax_info  = fig.add_subplot(gs[1, 2])    # Session info text

        NEON = "#00fff0"
        PINK_H = "#ff007f"

        def update(frame):
            if _dashboard_stop.is_set():
                return

            with shared.lock:
                trials   = list(shared.trial_numbers)
                rts      = list(shared.reaction_times)
                stabs    = list(shared.stabilities)
                diffs    = list(shared.difficulties)
                t_total  = shared.total_trials
                t_hits   = shared.total_hits
                diff_now = shared.current_diff
                elapsed  = time.time() - shared.session_start

            for ax in [ax_rt, ax_stab, ax_diff, ax_info]:
                ax.cla()
                ax.set_facecolor("#0d1117")
                for sp in ax.spines.values():
                    sp.set_color("#1e2533")

            # ── Reaction Time ──
            if trials:
                ax_rt.plot(trials, rts, color=NEON, lw=1.5, alpha=0.8)
                ax_rt.fill_between(trials, rts, alpha=0.15, color=NEON)
                if len(rts) >= 5:
                    import numpy as np
                    window = min(10, len(rts))
                    avg = [sum(rts[max(0,i-window):i+1])/len(rts[max(0,i-window):i+1])
                           for i in range(len(rts))]
                    ax_rt.plot(trials, avg, color=PINK_H, lw=2, linestyle="--", label="Rolling avg")
            ax_rt.set_title("Reaction Time per Trial (s)", color=NEON, fontsize=9, pad=6)
            ax_rt.set_xlabel("Trial #", color="#505a6e", fontsize=8)
            ax_rt.set_ylabel("Seconds", color="#505a6e", fontsize=8)
            ax_rt.tick_params(colors="#505a6e", labelsize=7)
            ax_rt.legend(fontsize=7, framealpha=0, loc='upper left')

            # ── Stability ──
            if trials:
                colors_s = ["#00e678" if s >= 0.7 else ("#ffdc32" if s >= 0.4 else "#ff3232")
                            for s in stabs]
                ax_stab.bar(trials, stabs, color=colors_s, alpha=0.7, width=0.8)
                ax_stab.axhline(0.7, color=NEON, lw=1, linestyle=":", alpha=0.6)
            ax_stab.set_ylim(0, 1.05)
            ax_stab.set_title("Stability Ratio per Trial", color=NEON, fontsize=9, pad=6)
            ax_stab.set_xlabel("Trial #", color="#505a6e", fontsize=8)
            ax_stab.set_ylabel("Stability (0–1)", color="#505a6e", fontsize=8)
            ax_stab.tick_params(colors="#505a6e", labelsize=7)

            # ── Difficulty gauge (radial) ──
            angle = (diff_now / 5) * 270 - 135
            theta = math.radians(angle)
            ax_diff.set_xlim(-1.3, 1.3); ax_diff.set_ylim(-1.3, 1.3)
            ax_diff.set_aspect("equal"); ax_diff.axis("off")
            from matplotlib.patches import Arc, FancyArrow
            arc_colors = ["#00e678", NEON, "#ffdc32", PINK_H, "#ff3232"]
            arc_col = arc_colors[diff_now - 1]
            arc = Arc((0,0), 2, 2, angle=0, theta1=-135, theta2=135,
                      color=arc_col, lw=8, alpha=0.7)
            ax_diff.add_patch(arc)
            needle_len = 0.75
            ax_diff.annotate("", xy=(needle_len*math.cos(theta), needle_len*math.sin(theta)),
                             xytext=(0, 0),
                             arrowprops=dict(arrowstyle="-|>", color="#f0f0ff", lw=2))
            ax_diff.text(0, -0.35, f"Level {diff_now}", ha="center", va="center",
                         color=arc_col, fontsize=14, fontweight="bold")
            ax_diff.text(0, -0.7, DIFFICULTY_LEVELS[diff_now]["label"].split("–")[1].strip(),
                         ha="center", color="#505a6e", fontsize=8)
            ax_diff.set_title("Difficulty", color=NEON, fontsize=9, pad=2)

            # ── Session info ──
            ax_info.axis("off")
            acc = (t_hits / t_total * 100) if t_total else 0
            mins = int(elapsed) // 60
            secs = int(elapsed) % 60
            lines = [
                ("SESSION METRICS", NEON, 11),
                (f"Duration      {mins:02d}:{secs:02d}", "#505a6e", 9),
                (f"Total Trials  {t_total}", "#505a6e", 9),
                (f"Hits          {t_hits}", "#00e678", 9),
                (f"Misses        {t_total - t_hits}", "#ff3232", 9),
                (f"Accuracy      {acc:.1f}%", NEON, 10),
            ]
            for i, (txt, col, fs) in enumerate(lines):
                ax_info.text(0.05, 0.92 - i * 0.16, txt, transform=ax_info.transAxes,
                             color=col, fontsize=fs,
                             fontweight="bold" if i == 0 else "normal")

            fig.suptitle("NEURO-OSU  ▸  Clinical Real-Time Dashboard",
                         color=NEON, fontsize=11, x=0.5, y=0.98)

        ani = animation.FuncAnimation(fig, update, interval=800, cache_frame_data=False)
        plt.show(block=False)  # Non-blocking display
        
        # Keep the window alive and responsive
        while not _dashboard_stop.is_set():
            try:
                fig.canvas.flush_events()
                time.sleep(0.05)
            except:
                break
    except Exception as e:
        print(f"Dashboard error (non-critical): {e}")
        # Keep the dashboard thread running even if there are errors
        while not _dashboard_stop.is_set():
            time.sleep(0.1)

# ─────────────────────────────────────────────────────────────────────────────
# SPAWN HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def spawn_circle(params):
    margin = params["circle_r"] + 20
    x = random.randint(margin, SCREEN_W - margin)
    y = random.randint(74, SCREEN_H - margin)
    return HitCircle(x, y, params)

# ─────────────────────────────────────────────────────────────────────────────
# MAIN GAME LOOP
# ─────────────────────────────────────────────────────────────────────────────
def main():
    init_csv()
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Neuro-Osu  ▸  Adaptive Kinetic Path-Finder")
    clock  = pygame.time.Clock()

    fonts = {
        "big":   pygame.font.SysFont("consolas", 52, bold=True),
        "hud":   pygame.font.SysFont("consolas", 28, bold=True),
        "small": pygame.font.SysFont("consolas", 18),
        "tiny":  pygame.font.SysFont("consolas", 14),
        "fb":    pygame.font.SysFont("consolas", 26, bold=True),
    }

    diff_mgr   = DifficultyManager()
    particles  = []
    float_texts = []

    score     = 0
    combo     = 0
    total_t   = 0
    total_h   = 0
    health   = 100

    # Object pools
    circles   = []
    sliders   = []

    # Timing
    session_start = time.time()
    last_spawn    = time.time()
    spawn_interval = 2.2   # seconds between new objects

    # Cursor tracking
    prev_mouse   = pygame.mouse.get_pos()
    mouse_vel    = 0.0
    cursor_trail = deque(maxlen=12)

    # Active slider drag
    dragging_slider = None
    last_cursor_pos = None

    # Start dashboard thread
    dash_thread = threading.Thread(target=clinical_dashboard, daemon=True)
    dash_thread.start()

    # ── Splash / Start Screen ──
    splash = True
    while splash:
        screen.fill(BG_DARK)
        draw_grid(screen)
        title = fonts["big"].render("NEURO-OSU", True, CYAN)
        sub   = fonts["hud"].render("Adaptive Kinetic Path-Finder", True, PINK)
        inst  = fonts["small"].render("Press  SPACE  to begin the session", True, WHITE)
        screen.blit(title, (SCREEN_W//2 - title.get_width()//2, SCREEN_H//2 - 100))
        screen.blit(sub,   (SCREEN_W//2 - sub.get_width()//2,   SCREEN_H//2 - 30))
        screen.blit(inst,  (SCREEN_W//2 - inst.get_width()//2,  SCREEN_H//2 + 60))
        pygame.display.flip()
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE:
                splash = False

    # ── Game Loop ──
    running = True
    while running:
        dt       = clock.tick(FPS) / 1000.0
        elapsed  = time.time() - session_start
        mx, my   = pygame.mouse.get_pos()

        # Cursor velocity
        dx = mx - prev_mouse[0]; dy = my - prev_mouse[1]
        mouse_vel  = math.hypot(dx, dy) / max(dt, 0.001)
        prev_mouse = (mx, my)
        cursor_trail.append((mx, my))

        # ── Events ──
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                running = False

            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                now = time.time()
                hit_any = False

                # Try circles first
                for circ in circles[:]:
                    if not circ.alive: continue
                    score_label, err = circ.hit_score(mx, my)
                    if score_label != "Miss":
                        circ.alive   = False
                        circ.clicked = True
                        rt = (now - circ.spawn_t) if circ.first_move_t is None \
                             else (circ.first_move_t - circ.spawn_t)
                        rt = max(0.0, rt)

                        # Score
                        pts = {"Perfect": 300, "Great": 200, "Good": 100}[score_label]
                        combo += 1
                        score += pts * combo
                        total_h += 1; total_t += 1
                        hp_gain = {"Perfect": 4.0, "Great": 2.0, "Good": 1.0}[score_label]
                        health = min(100.0, health + hp_gain) # Recover health on hit, more for better hits

                        # Motion variance from trail
                        mv = _trail_variance(cursor_trail)

                        log_trial(circ.id, rt, err, mouse_vel,
                                  diff_mgr.level, score_label, mv, "circle")
                        diff_mgr.record(score_label, mv)

                        # Particles & feedback
                        col = {"Perfect": CYAN, "Great": GREEN, "Good": YELLOW}[score_label]
                        for _ in range(22):
                            particles.append(Particle(circ.x, circ.y, col))
                        float_texts.append(FloatText(score_label, circ.x, circ.y - 40,
                                                     col, fonts["fb"]))
                        hit_any = True
                        break

                # Try slider start
                if not hit_any and not dragging_slider:
                    for sl in sliders:
                        if not sl.alive: continue
                        sx, sy = sl.start
                        if math.hypot(mx - sx, my - sy) <= 20:
                            dragging_slider = sl
                            sl.active = True
                            sl.first_move_t = now
                            break

                if not hit_any and not dragging_slider:
                    # Penalise empty click
                    combo = 0

            if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                if dragging_slider:
                    sl = dragging_slider
                    mean_dev  = (sum(sl.deviations) / len(sl.deviations)
                                 if sl.deviations else 999)
                    progress_pct = sl.progress / max(len(sl.path) - 1, 1)

                    if   progress_pct >= 0.85 and mean_dev < sl.pw:
                        s_label = "Perfect"; pts = 300
                    elif progress_pct >= 0.60 and mean_dev < sl.pw * 1.5:
                        s_label = "Great";   pts = 200
                    elif progress_pct >= 0.40:
                        s_label = "Good";    pts = 100
                    else:
                        s_label = "Miss";    pts = 0
                        combo = 0

                    if s_label != "Miss":
                        combo += 1
                        score += pts * combo
                        total_h += 1

                    total_t += 1
                    rt  = (sl.first_move_t - sl.spawn_t) if sl.first_move_t else 0
                    mv  = _trail_variance(cursor_trail)
                    col = {"Perfect": CYAN, "Great": GREEN, "Good": YELLOW,
                           "Miss": RED}[s_label]

                    log_trial(sl.id, rt, mean_dev, mouse_vel,
                              diff_mgr.level, s_label, mv, "slider")
                    diff_mgr.record(s_label, mv)

                    ex, ey = sl.end
                    for _ in range(18):
                        particles.append(Particle(ex, ey, col))
                    float_texts.append(FloatText(s_label, ex, ey - 40, col, fonts["fb"]))

                    sl.alive = False
                    dragging_slider = None

        # ── Update: mark circles as first-moved ──
        for circ in circles:
            if circ.alive and circ.first_move_t is None:
                dist = math.hypot(mx - circ.x, my - circ.y)
                if dist < circ.radius * 3 and mouse_vel > 5:
                    circ.first_move_t = time.time()

        # ── Update: slider dragging ──
        if dragging_slider and dragging_slider.alive:
            sl  = dragging_slider
            idx, dev = sl.nearest_idx(mx, my)
            if idx >= sl.progress:
                sl.progress = idx
            sl.deviations.append(dev)

        # ── Expire circles ──
        for circ in circles:
            if circ.alive and circ.age >= circ.lifetime:
                circ.alive = False
                combo      = 0
                total_t   += 1
                health    -= 12.0  # Deduct health on miss
                mv = _trail_variance(cursor_trail)
                log_trial(circ.id, circ.lifetime, circ.radius * 2,
                          0, diff_mgr.level, "Miss", mv, "circle")
                diff_mgr.record("Miss", mv)
                float_texts.append(FloatText("Miss", circ.x, circ.y - 20,
                                             RED, fonts["fb"]))

        # ── Expire sliders ──
        for sl in sliders:
            if sl.alive and not sl.active and sl.age >= sl.lifetime:
                sl.alive = False
                combo = 0
                total_t += 1
                mv = _trail_variance(cursor_trail)
                log_trial(sl.id, sl.lifetime, 999, 0,
                          diff_mgr.level, "Miss", mv, "slider")
                diff_mgr.record("Miss", mv)

        # ── Clean dead objects ──
        circles = [c for c in circles if c.alive]
        sliders = [s for s in sliders if s.alive]

        # ── Spawn new objects ──
        params = diff_mgr.params
        if time.time() - last_spawn >= spawn_interval:
            last_spawn = time.time()
            if random.random() < 0.60:
                circles.append(spawn_circle(params))
            else:
                sliders.append(Slider(params))

        # ── Update particles & texts ──
        for p in particles: p.update()
        for f in float_texts: f.update()
        particles  = [p for p in particles  if p.life > 0]
        float_texts = [f for f in float_texts if f.life > 0]

        # ─── DRAW ───────────────────────────────────────────────────────────
        # Game Over Condition
        if health <= 0:
            print("Game Over: Health depleted.")
            running = False

        screen.fill(BG_DARK)
        draw_grid(screen)

        # Glow layer
        glow = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)

        # Cursor trail
        for i, (tx, ty) in enumerate(cursor_trail):
            alpha = int(40 * i / len(cursor_trail))
            r     = max(1, 3 - i // 4)
            pygame.draw.circle(glow, (*CYAN, alpha), (tx, ty), r)

        # Draw sliders
        for sl in sliders:
            sl.draw(screen, glow)

        # Draw circles
        for circ in circles:
            circ.draw(screen, glow)

        screen.blit(glow, (0, 0))

        # Particles
        for p in particles: p.draw(screen)

        # Float feedback
        for f in float_texts: f.draw(screen)

        # HUD
        acc = (total_h / total_t * 100) if total_t else 100.0
        draw_hud(screen, fonts, diff_mgr, score, combo, acc, elapsed, health)

        # Custom cursor dot
        pygame.draw.circle(screen, CYAN, (mx, my), 5)
        pygame.draw.circle(screen, BG_DARK, (mx, my), 3)

        pygame.display.flip()

    # ── Cleanup ──
    _dashboard_stop.set()
    pygame.quit()
    print(f"\n Session ended. Data saved to: {CSV_PATH}")
    print(f"  Trials: {total_t}  |  Hits: {total_h}  |  "
          f"Accuracy: {(total_h/total_t*100) if total_t else 0:.1f}%")
    

# ─────────────────────────────────────────────────────────────────────────────
# UTILITY
# ─────────────────────────────────────────────────────────────────────────────
def _trail_variance(trail):
    pts = list(trail)
    if len(pts) < 2:
        return 0.0
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    mx_v = sum(xs) / len(xs)
    my_v = sum(ys) / len(ys)
    var  = sum((x - mx_v)**2 + (y - my_v)**2 for x, y in pts) / len(pts)
    return var

# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()