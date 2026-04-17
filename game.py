"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           NEURO-OSU: ADAPTIVE KINETIC PATH-FINDER                            ║
║           A Serious Game for Motor Recovery & Cognitive Training             ║
╚══════════════════════════════════════════════════════════════════════════════╝
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
from collections import deque
from datetime import datetime

import numpy as np

import matplotlib
try:
    matplotlib.use("Qt5Agg")
except Exception:
    matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Arc, Wedge, FancyBboxPatch
from matplotlib.collections import LineCollection

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS & PALETTE  (game2 dark style)
# ─────────────────────────────────────────────────────────────────────────────
SCREEN_W, SCREEN_H = 1280, 720
FPS = 60

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

CSV_PATH = "patient_performance.csv"
CSV_COLUMNS = [
    "Timestamp", "TargetID", "ReactionTime", "ErrorDistance",
    "Velocity", "CurrentDifficulty", "HitScore", "MotionVariance", "TargetType"
]

# ─────────────────────────────────────────────────────────────────────────────
# DIFFICULTY PRESETS
# ─────────────────────────────────────────────────────────────────────────────
DIFFICULTY_LEVELS = {
    1: {"circle_r": 55, "lifetime": 3.0, "label": "Level 1 - Introductory"},
    2: {"circle_r": 44, "lifetime": 2.5, "label": "Level 2 - Standard"},
    3: {"circle_r": 34, "lifetime": 2.0, "label": "Level 3 - Advanced"},
    4: {"circle_r": 26, "lifetime": 1.5, "label": "Level 4 - Expert"},
    5: {"circle_r": 18, "lifetime": 1.1, "label": "Level 5 - Elite"},
}

# ─────────────────────────────────────────────────────────────────────────────
# SHARED DATA STORE  (expanded for rich dashboard)
# ─────────────────────────────────────────────────────────────────────────────
class SharedData:
    def __init__(self):
        self.lock              = threading.Lock()
        self.trial_numbers     = deque(maxlen=500)
        self.reaction_times    = deque(maxlen=500)
        self.stabilities       = deque(maxlen=500)
        self.difficulties      = deque(maxlen=500)
        self.scores_binary     = deque(maxlen=500)
        self.score_labels      = deque(maxlen=500)
        self.velocities        = deque(maxlen=500)
        self.error_distances   = deque(maxlen=500)
        self.combo_at_trial    = deque(maxlen=500)
        self.health_at_trial   = deque(maxlen=500)
        self.cumulative_scores = deque(maxlen=500)
        self.total_trials      = 0
        self.total_hits        = 0
        self.current_diff      = 1
        self.session_start     = time.time()
        self.current_combo     = 0
        self.max_combo         = 0
        self.current_health    = 100.0
        self.current_score     = 0
        self.perfect_count     = 0
        self.great_count       = 0
        self.good_count        = 0
        self.miss_count        = 0

shared = SharedData()

# ─────────────────────────────────────────────────────────────────────────────
# CSV LOGGER
# ─────────────────────────────────────────────────────────────────────────────
def init_csv():
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, "w", newline="") as f:
            csv.writer(f).writerow(CSV_COLUMNS)

def log_trial(target_id, reaction_time, error_dist, velocity,
              difficulty, hit_score, motion_var, target_type,
              current_combo=0, current_health=100.0, current_score=0):
    row = [
        datetime.now().isoformat(timespec="milliseconds"),
        target_id, f"{reaction_time:.4f}", f"{error_dist:.2f}",
        f"{velocity:.2f}", difficulty, hit_score,
        f"{motion_var:.4f}", target_type,
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
        shared.velocities.append(velocity)
        shared.error_distances.append(error_dist)
        shared.combo_at_trial.append(current_combo)
        shared.health_at_trial.append(current_health)
        shared.current_score  = current_score
        shared.cumulative_scores.append(current_score)
        shared.current_diff   = difficulty
        shared.current_combo  = current_combo
        shared.current_health = current_health
        shared.score_labels.append(hit_score)

        if hit_score != "Miss":
            shared.total_hits += 1
            shared.scores_binary.append(1)
            shared.max_combo = max(shared.max_combo, current_combo)
        else:
            shared.scores_binary.append(0)

        if   hit_score == "Perfect": shared.perfect_count += 1
        elif hit_score == "Great":   shared.great_count   += 1
        elif hit_score == "Good":    shared.good_count    += 1
        elif hit_score == "Miss":    shared.miss_count    += 1

# ─────────────────────────────────────────────────────────────────────────────
# ADAPTIVE DIFFICULTY ENGINE
# ─────────────────────────────────────────────────────────────────────────────
class DifficultyManager:
    def __init__(self):
        self.level           = 1
        self.recent_scores   = deque(maxlen=3)
        self.recent_variance = deque(maxlen=3)

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
            self.recent_scores.clear(); self.recent_variance.clear()
        elif all_miss and self.level > 1:
            self.level -= 1
            self.recent_scores.clear(); self.recent_variance.clear()

# ─────────────────────────────────────────────────────────────────────────────
# AUDIO  (game2 synthesized style)
# ─────────────────────────────────────────────────────────────────────────────
def _tone(freq, dur, vol=0.35, wave="sine", attack=0.03, release=0.08):
    sr = 44100; n = int(sr * dur)
    t  = np.linspace(0, dur, n, False)
    if wave == "sine":  w = np.sin(2*np.pi*freq*t)
    elif wave == "tri": w = 2*np.abs(2*(t*freq - np.floor(t*freq+0.5))) - 1
    else:               w = np.sin(2*np.pi*freq*t)
    env = np.ones(n)
    a = min(int(sr*attack),  n//4)
    r = min(int(sr*release), n//4)
    if a: env[:a]  = np.linspace(0, 1, a)
    if r: env[-r:] = np.linspace(1, 0, r)
    w = (w * env * vol * 32767).astype(np.int16)
    return pygame.sndarray.make_sound(np.column_stack([w, w]))

def _chord(freqs, dur, vol=0.22):
    sr = 44100; n = int(sr * dur)
    t  = np.linspace(0, dur, n, False)
    w  = sum(np.sin(2*np.pi*f*t) for f in freqs) / len(freqs)
    r  = min(int(sr*0.06), n//4)
    if r:
        env = np.ones(n); env[-r:] = np.linspace(1, 0, r)
        w  *= env
    w = (w * vol * 32767).astype(np.int16)
    return pygame.sndarray.make_sound(np.column_stack([w, w]))

def _make_bgm(vol=0.10):
    penta  = [262, 330, 392, 440, 523, 440, 392, 330]
    bpm    = 92; beat = 60/bpm/1.5
    sr     = 44100
    total  = int(sr * beat * len(penta) * 2)
    buf    = np.zeros(total)
    for rep in range(2):
        for i, freq in enumerate(penta):
            n    = int(sr * beat)
            t    = np.linspace(0, beat, n, False)
            note = np.sin(2*np.pi*freq*t)*0.7 + np.sin(2*np.pi*freq*2*t)*0.15
            fl   = n//8
            note[:fl]  *= np.linspace(0,1,fl)
            note[-fl:] *= np.linspace(1,0,fl)
            start = (rep*len(penta) + i)*n
            buf[start:start+n] += note
    mx = abs(buf).max(); buf /= mx if mx else 1
    buf = (buf * vol * 32767).astype(np.int16)
    return pygame.sndarray.make_sound(np.column_stack([buf, buf]))

# ─────────────────────────────────────────────────────────────────────────────
# PARTICLES  (game2 style with shape variety)
# ─────────────────────────────────────────────────────────────────────────────
class Particle:
    __slots__ = ["x","y","vx","vy","color","life","mlife","sz","shape"]
    def __init__(self, x, y, color):
        self.x=x; self.y=y
        self.vx=random.uniform(-4,4); self.vy=random.uniform(-5.5,-0.5)
        self.color=color
        self.life=random.uniform(0.45,1.0); self.mlife=self.life
        self.sz=random.uniform(3,9)
        self.shape=random.choice(["circle","star"])
    def update(self, dt):
        self.x+=self.vx; self.y+=self.vy; self.vy+=0.2
        self.life-=dt; return self.life>0
    def draw(self, s):
        a=self.life/self.mlife; r2,g2,b2=self.color
        c=(int(r2*a),int(g2*a),int(b2*a))
        if self.shape=="circle":
            pygame.draw.circle(s,c,(int(self.x),int(self.y)),max(1,int(self.sz*a)))
        else:
            sz=max(2,int(self.sz*a)); x2,y2=int(self.x),int(self.y)
            pygame.draw.line(s,c,(x2-sz,y2),(x2+sz,y2),1)
            pygame.draw.line(s,c,(x2,y2-sz),(x2,y2+sz),1)

def burst(particles, x, y, color, n=22):
    for _ in range(n): particles.append(Particle(x,y,color))

def ring_burst(particles, x, y, color, n=18):
    for i in range(n):
        a=2*math.pi*i/n; sp=random.uniform(2.5,5)
        p=Particle(x,y,color); p.vx=math.cos(a)*sp; p.vy=math.sin(a)*sp
        particles.append(p)

# ─────────────────────────────────────────────────────────────────────────────
# SCREEN FLASH
# ─────────────────────────────────────────────────────────────────────────────
class Flash:
    def __init__(self,color,dur=0.13):
        self.color=color; self.life=dur; self.mlife=dur
    def update(self,dt):
        self.life-=dt; return self.life>0
    def draw(self,s):
        a=int(100*self.life/self.mlife); r2,g2,b2=self.color
        ov=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
        ov.fill((r2,g2,b2,a)); s.blit(ov,(0,0))

# ─────────────────────────────────────────────────────────────────────────────
# FLOATING FEEDBACK TEXT
# ─────────────────────────────────────────────────────────────────────────────
class FloatText:
    def __init__(self,x,y,txt,color,size=22):
        self.x=x; self.y=y; self.txt=txt; self.color=color
        self.life=1.3; self.mlife=1.3
        self.font=pygame.font.SysFont("consolas",size,bold=True)
    def update(self,dt):
        self.y-=1.1; self.life-=dt; return self.life>0
    def draw(self,s):
        a=self.life/self.mlife; r2,g2,b2=self.color
        c=(int(r2*a),int(g2*a),int(b2*a))
        surf=self.font.render(self.txt,True,c)
        s.blit(surf,(int(self.x)-surf.get_width()//2,int(self.y)))

# ─────────────────────────────────────────────────────────────────────────────
# HIT CIRCLE  (game2 Target-style drawing)
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
        self.first_move_t = None
        self.pulse    = 0.0

    @property
    def age(self):          return time.time() - self.spawn_t
    @property
    def fraction(self):     return min(1.0, self.age / self.lifetime)
    @property
    def time_left(self):    return max(0.0, self.lifetime - self.age)
    @property
    def frac_left(self):    return self.time_left / self.lifetime

    def contains(self, mx, my):
        return math.hypot(mx - self.x, my - self.y) <= self.radius

    def hit_score(self, mx, my):
        dist = math.hypot(mx - self.x, my - self.y)
        r = self.radius
        if   dist <= r * 0.35: return "Perfect", dist
        elif dist <= r * 0.65: return "Great",   dist
        elif dist <= r:        return "Good",     dist
        else:                  return "Miss",     dist

    def draw(self, surf):
        self.pulse = (self.pulse + 0.07) % (2*math.pi)
        pr  = self.radius + 3*math.sin(self.pulse)
        fl  = self.frac_left
        urg = 1.0 - fl

        base_c = CYAN
        c_r = min(255, int(base_c[0] + (RED[0]-base_c[0])*urg*0.6))
        c_g = max(0,   int(base_c[1] + (RED[1]-base_c[1])*urg*0.6))
        c_b = max(0,   int(base_c[2] + (RED[2]-base_c[2])*urg*0.6))
        draw_col = (c_r, c_g, c_b)

        for offset, alpha_base in [(14,60),(9,90),(5,130)]:
            ar = int(pr + offset)
            col = tuple(int(c*(alpha_base/255)) for c in base_c)
            pygame.draw.circle(surf, col, (self.x, self.y), ar, 2)

        approach_r = int(pr + 55*fl)
        ring_col = (
            int(255*urg + base_c[0]*(1-urg)),
            int(base_c[1]*(1-urg)),
            int(base_c[2]*(1-urg))
        )
        pygame.draw.circle(surf, ring_col, (self.x, self.y), approach_r, 2)

        pygame.draw.circle(surf, draw_col, (self.x, self.y), int(pr))
        pygame.draw.circle(surf, WHITE, (self.x, self.y), max(5, int(pr*0.28)))

        if fl > 0 and approach_r > 0:
            try:
                ar_rect = pygame.Rect(
                    self.x - approach_r, self.y - approach_r,
                    approach_r*2, approach_r*2
                )
                pygame.draw.arc(surf, WHITE, ar_rect,
                                math.pi/2, math.pi/2 + 2*math.pi*fl, 2)
            except:
                pass

        if fl < 0.3:
            p2 = (self.pulse*3) % (2*math.pi)
            pulse_extra = int(4*math.sin(p2)*fl/0.3)
            pygame.draw.circle(surf, RED, (self.x, self.y), int(pr)+pulse_extra, 1)

# ─────────────────────────────────────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _txt(s, text, font, color, cx=None, x=None, y=0):
    surf = font.render(str(text), True, color)
    bx = cx - surf.get_width()//2 if cx is not None else x
    s.blit(surf, (bx, y))
    return surf.get_width()

def _panel(s, rect, fill=None, border=None, r=10):
    if fill   is None: fill   = PANEL
    if border is None: border = BORDER
    pygame.draw.rect(s, fill,   rect, border_radius=r)
    pygame.draw.rect(s, border, rect, 1, border_radius=r)

def _pbar(s, x, y, w, h, frac, fg, bg=(28,36,60), r=5):
    bg_r = pygame.Rect(x,y,w,h)
    pygame.draw.rect(s, bg, bg_r, border_radius=r)
    fw = max(0, int(w*min(frac,1.0)))
    if fw:
        pygame.draw.rect(s, fg, pygame.Rect(x,y,fw,h), border_radius=r)
    pygame.draw.rect(s, BORDER, bg_r, 1, border_radius=r)

def draw_grid(surf):
    for x in range(0, SCREEN_W, 55):
        pygame.draw.line(surf, (16,20,34), (x, 0), (x, SCREEN_H))
    for y in range(90, SCREEN_H, 55):
        pygame.draw.line(surf, (16,20,34), (0, y), (SCREEN_W, y))

def _mini_spark(s, x, y, w, h, vals, color):
    if len(vals) < 2: return
    mn, mx = min(vals)*0.85, max(vals)*1.15
    if mx == mn: mx = mn + 0.1
    pts = [(x + int(i/(len(vals)-1)*w),
            y + h - int((v-mn)/(mx-mn)*h)) for i,v in enumerate(vals)]
    pygame.draw.lines(s, color, False, pts, 1)
    pygame.draw.circle(s, WHITE, pts[-1], 3)

# ─────────────────────────────────────────────────────────────────────────────
# HUD  (game2 style – organized top bar)
# ─────────────────────────────────────────────────────────────────────────────
def draw_hud(surf, fonts, diff_mgr, score, combo, accuracy, elapsed, health, recent_rts):
    params = diff_mgr.params
    level  = diff_mgr.level
    diff_cols = [GREEN, CYAN, YELLOW, PINK, RED]
    col = diff_cols[level - 1]

    _panel(surf, pygame.Rect(0, 0, SCREEN_W, 90), fill=(12,15,25), border=BORDER, r=0)

    _txt(surf, f"{score:,}", fonts["hud"], CYAN, x=18, y=8)
    _txt(surf, "SCORE", fonts["tiny"], GREY, x=18, y=50)

    lx = 215
    pygame.draw.rect(surf, col, pygame.Rect(lx, 10, 115, 34), border_radius=8)
    _txt(surf, f"LVL {level}", fonts["fb"], BG_DARK, cx=lx+57, y=16)
    short_label = params["label"].split("-")[1].strip() if "-" in params["label"] else params["label"]
    _txt(surf, short_label, fonts["tiny"], GREY, cx=lx+57, y=50)

    cx_c = lx + 145
    sc   = ORANGE if combo >= 5 else (WHITE if combo > 0 else GREY)
    _txt(surf, f"x{combo}", fonts["hud"], sc, x=cx_c, y=8)
    _txt(surf, "COMBO", fonts["tiny"], GREY, x=cx_c, y=50)

    ax  = cx_c + 115
    ac  = GREEN if accuracy > 80 else (YELLOW if accuracy > 55 else ORANGE)
    _txt(surf, f"{accuracy:.0f}%", fonts["hud"], ac, x=ax, y=8)
    _txt(surf, "ACCURACY", fonts["tiny"], GREY, x=ax, y=50)

    mins = int(elapsed)//60; secs = int(elapsed)%60
    tx   = ax + 140
    _txt(surf, f"{mins:02d}:{secs:02d}", fonts["hud"], LGREY, x=tx, y=8)
    _txt(surf, "TIME", fonts["tiny"], GREY, x=tx, y=50)

    hbar_x = SCREEN_W - 325
    hbar_w = 300
    health_pct = max(0, min(100, health)) / 100.0
    _txt(surf, "HP", fonts["tiny"], GREY, x=hbar_x, y=5)
    hp_col = GREEN if health > 60 else (YELLOW if health > 30 else RED)
    _pbar(surf, hbar_x, 22, hbar_w, 20, health_pct, hp_col, bg=(28,36,60), r=6)
    _txt(surf, f"{int(health)}%", fonts["tiny"], hp_col, x=hbar_x + hbar_w + 5, y=25)

    rts_list = list(recent_rts)
    if len(rts_list) >= 3:
        _mini_spark(surf, hbar_x, 50, hbar_w, 32, rts_list[-12:], CYAN)
        _txt(surf, "Reaction times (recent)", fonts["tiny"], (60,75,110), x=hbar_x, y=83)

    hint = fonts["tiny"].render("Click the circles  |  ESC to quit", True, (45,58,85))
    surf.blit(hint, (SCREEN_W//2 - hint.get_width()//2, SCREEN_H - 18))

# ─────────────────────────────────────────────────────────────────────────────
# ███  PREMIUM CLINICAL DASHBOARD  (9 panels, neon style)  ███
# ─────────────────────────────────────────────────────────────────────────────
_dashboard_stop = threading.Event()

# Hex colors for matplotlib
_NEON     = "#00d2ff"
_PINK_H   = "#ff3282"
_GREEN_H  = "#32e678"
_YELLOW_H = "#ffd21e"
_ORANGE_H = "#ff8c1e"
_RED_H    = "#ff4646"
_BG       = "#0e101a"
_PANEL_BG = "#0d1117"
_GRID_C   = "#1a2033"
_TEXT_DIM = "#505a6e"
_TEXT_MID = "#8892a6"
_WHITE_H  = "#e8eaf0"

def _rolling_average(vals, window=5):
    """Compute a rolling average over a list."""
    if len(vals) < window:
        window = max(1, len(vals))
    arr = np.array(vals, dtype=float)
    kernel = np.ones(window) / window
    return np.convolve(arr, kernel, mode='valid')

def _compute_radar_values(shared_snap):
    """
    Returns 5 metrics normalised to 0-1 for a radar/spider chart:
      - Accuracy, Reaction Speed, Stability, Consistency, Endurance
    """
    t_total = shared_snap["total_trials"]
    t_hits  = shared_snap["total_hits"]
    rts     = shared_snap["reaction_times"]
    stabs   = shared_snap["stabilities"]
    health  = shared_snap["current_health"]

    accuracy = (t_hits / t_total) if t_total else 0.0

    if rts:
        avg_rt = np.mean(rts)
        speed = max(0.0, min(1.0, 1.0 - (avg_rt / 3.0)))
    else:
        speed = 0.5

    stability = np.mean(stabs) if stabs else 0.5

    if len(rts) >= 3:
        std_rt = np.std(rts)
        consistency = max(0.0, min(1.0, 1.0 - std_rt / 1.5))
    else:
        consistency = 0.5

    endurance = health / 100.0

    return [accuracy, speed, stability, consistency, endurance]

def _style_ax(ax, title="", xlabel="", ylabel=""):
    """Apply consistent dark neon style to an axis."""
    ax.set_facecolor(_PANEL_BG)
    for spine in ax.spines.values():
        spine.set_color(_GRID_C)
        spine.set_linewidth(0.6)
    ax.tick_params(colors=_TEXT_DIM, labelsize=7, length=3, width=0.5)
    ax.xaxis.label.set_color(_TEXT_DIM)
    ax.yaxis.label.set_color(_TEXT_DIM)
    ax.grid(True, color=_GRID_C, linewidth=0.3, alpha=0.5)
    if title:
        ax.set_title(title, color=_NEON, fontsize=9, fontweight="bold",
                      pad=8, loc="left")
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=7, labelpad=4)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=7, labelpad=4)

def clinical_dashboard():
    """Premium 9-panel real-time clinical dashboard."""
    try:
        plt.style.use("dark_background")
        fig = plt.figure(figsize=(16, 9.5), facecolor=_BG)
        fig.canvas.manager.set_window_title("Neuro-Osu │ Premium Clinical Dashboard")

        gs = GridSpec(3, 4, figure=fig, hspace=0.52, wspace=0.42,
                      left=0.05, right=0.97, top=0.92, bottom=0.06)

        # Row 0
        ax_rt       = fig.add_subplot(gs[0, 0:2])   # Reaction Time
        ax_acc_roll = fig.add_subplot(gs[0, 2])      # Rolling Accuracy
        ax_radar    = fig.add_subplot(gs[0, 3], polar=True)  # Radar

        # Row 1
        ax_stab     = fig.add_subplot(gs[1, 0:2])   # Stability bars
        ax_combo    = fig.add_subplot(gs[1, 2])      # Combo / Health
        ax_diff     = fig.add_subplot(gs[1, 3])      # Difficulty gauge

        # Row 2
        ax_vel      = fig.add_subplot(gs[2, 0])      # Velocity
        ax_err      = fig.add_subplot(gs[2, 1])      # Error Distance
        ax_pie      = fig.add_subplot(gs[2, 2])      # Hit Breakdown pie
        ax_info     = fig.add_subplot(gs[2, 3])      # Session Metrics

        def _snapshot():
            """Thread-safe copy of shared data."""
            with shared.lock:
                return {
                    "trials":       list(shared.trial_numbers),
                    "rts":          list(shared.reaction_times),
                    "stabs":        list(shared.stabilities),
                    "diffs":        list(shared.difficulties),
                    "scores_bin":   list(shared.scores_binary),
                    "labels":       list(shared.score_labels),
                    "velocities":   list(shared.velocities),
                    "errors":       list(shared.error_distances),
                    "combos":       list(shared.combo_at_trial),
                    "healths":      list(shared.health_at_trial),
                    "cum_scores":   list(shared.cumulative_scores),
                    "total_trials": shared.total_trials,
                    "total_hits":   shared.total_hits,
                    "current_diff": shared.current_diff,
                    "elapsed":      time.time() - shared.session_start,
                    "current_combo":  shared.current_combo,
                    "max_combo":      shared.max_combo,
                    "current_health": shared.current_health,
                    "current_score":  shared.current_score,
                    "perfect":  shared.perfect_count,
                    "great":    shared.great_count,
                    "good":     shared.good_count,
                    "miss":     shared.miss_count,
                    "reaction_times": list(shared.reaction_times),
                    "stabilities":    list(shared.stabilities),
                    "current_health": shared.current_health,
                }

        def update(_frame):
            if _dashboard_stop.is_set():
                return

            snap = _snapshot()
            trials  = snap["trials"]
            rts     = snap["rts"]
            stabs   = snap["stabs"]
            diffs   = snap["diffs"]
            labels  = snap["labels"]
            vels    = snap["velocities"]
            errs    = snap["errors"]
            combos  = snap["combos"]
            healths = snap["healths"]
            cum_sc  = snap["cum_scores"]
            t_total = snap["total_trials"]
            t_hits  = snap["total_hits"]
            diff_now= snap["current_diff"]
            elapsed = snap["elapsed"]

            # ─── Clear all axes ──────────────────────────────
            all_axes = [ax_rt, ax_acc_roll, ax_stab, ax_combo,
                        ax_diff, ax_vel, ax_err, ax_pie, ax_info]
            for ax in all_axes:
                ax.cla()
                ax.set_facecolor(_PANEL_BG)
                for sp in ax.spines.values():
                    sp.set_color(_GRID_C)
            ax_radar.cla()
            ax_radar.set_facecolor(_PANEL_BG)

            # ═══════════════════════════════════════════════════
            # 1 ▸ REACTION TIME  (gradient fill + rolling avg)
            # ═══════════════════════════════════════════════════
            _style_ax(ax_rt, "⏱  Reaction Time", "Trial #", "Seconds")
            if trials:
                ax_rt.fill_between(trials, rts, alpha=0.12, color=_NEON)
                ax_rt.plot(trials, rts, color=_NEON, lw=1.2, alpha=0.6,
                           marker="o", markersize=2.5)
                if len(rts) >= 5:
                    ra = _rolling_average(rts, 5)
                    ra_x = trials[4:]
                    ax_rt.plot(ra_x, ra, color=_PINK_H, lw=2, alpha=0.9,
                               label="5-trial avg")
                    ax_rt.legend(fontsize=7, loc="upper right",
                                  facecolor=_PANEL_BG, edgecolor=_GRID_C,
                                  labelcolor=_TEXT_MID)
                avg_val = np.mean(rts)
                ax_rt.axhline(avg_val, color=_YELLOW_H, lw=0.8,
                               ls="--", alpha=0.5)
                ax_rt.text(trials[-1], avg_val,
                            f" μ={avg_val:.2f}s", color=_YELLOW_H,
                            fontsize=7, va="bottom")

            # ═══════════════════════════════════════════════════
            # 2 ▸ ROLLING ACCURACY  (area chart)
            # ═══════════════════════════════════════════════════
            _style_ax(ax_acc_roll, "🎯  Rolling Accuracy", "Trial #", "%")
            if len(snap["scores_bin"]) >= 3:
                sb = np.array(snap["scores_bin"], dtype=float)
                window = min(8, len(sb))
                kernel = np.ones(window)/window
                rolling_acc = np.convolve(sb, kernel, mode="valid") * 100
                rx = list(range(window, window + len(rolling_acc)))
                ax_acc_roll.fill_between(rx, rolling_acc, alpha=0.18,
                                          color=_GREEN_H)
                ax_acc_roll.plot(rx, rolling_acc, color=_GREEN_H, lw=2)
                ax_acc_roll.axhline(70, color=_YELLOW_H, lw=0.7,
                                     ls=":", alpha=0.5)
                ax_acc_roll.text(rx[-1]+0.3, rolling_acc[-1],
                                  f"{rolling_acc[-1]:.0f}%",
                                  color=_GREEN_H, fontsize=8,
                                  fontweight="bold", va="center")
            ax_acc_roll.set_ylim(0, 105)

            # ═══════════════════════════════════════════════════
            # 3 ▸ PERFORMANCE RADAR
            # ═══════════════════════════════════════════════════
            radar_labels = ["Accuracy", "Speed", "Stability",
                            "Consistency", "Endurance"]
            rv = _compute_radar_values(snap)
            N = len(radar_labels)
            angles = np.linspace(0, 2*np.pi, N, endpoint=False).tolist()
            rv_plot = rv + [rv[0]]
            angles += [angles[0]]

            ax_radar.set_facecolor(_PANEL_BG)
            ax_radar.plot(angles, rv_plot, color=_NEON, lw=2, alpha=0.9)
            ax_radar.fill(angles, rv_plot, color=_NEON, alpha=0.15)
            ax_radar.scatter(angles[:-1], rv[0:N], color=_NEON, s=30,
                              zorder=5, edgecolors=_WHITE_H, linewidths=0.5)
            ax_radar.set_xticks(angles[:-1])
            ax_radar.set_xticklabels(radar_labels, fontsize=7,
                                      color=_TEXT_MID)
            ax_radar.set_ylim(0, 1.0)
            ax_radar.set_yticks([0.25, 0.5, 0.75, 1.0])
            ax_radar.set_yticklabels(["25%","50%","75%","100%"],
                                      fontsize=6, color=_TEXT_DIM)
            ax_radar.yaxis.grid(True, color=_GRID_C, lw=0.4)
            ax_radar.xaxis.grid(True, color=_GRID_C, lw=0.4)
            ax_radar.set_title("🕸  Performance Radar", color=_NEON,
                                fontsize=9, fontweight="bold", pad=14)
            for spine in ax_radar.spines.values():
                spine.set_color(_GRID_C)

            # ═══════════════════════════════════════════════════
            # 4 ▸ STABILITY BARS  (colour-coded)
            # ═══════════════════════════════════════════════════
            _style_ax(ax_stab, "📊  Hand Stability", "Trial #", "Stability")
            if trials:
                bar_colors = []
                for s_val in stabs:
                    if   s_val >= 0.7: bar_colors.append(_GREEN_H)
                    elif s_val >= 0.4: bar_colors.append(_YELLOW_H)
                    else:              bar_colors.append(_RED_H)
                ax_stab.bar(trials, stabs, color=bar_colors, alpha=0.75,
                             width=0.8, edgecolor="none")
                ax_stab.axhline(0.7, color=_NEON, lw=1, ls=":",
                                 alpha=0.6, label="Target (0.7)")
                if len(stabs) >= 5:
                    sa = _rolling_average(stabs, 5)
                    sa_x = trials[4:]
                    ax_stab.plot(sa_x, sa, color=_PINK_H, lw=2,
                                  alpha=0.85, label="Trend")
                ax_stab.legend(fontsize=6, loc="lower right",
                                facecolor=_PANEL_BG, edgecolor=_GRID_C,
                                labelcolor=_TEXT_MID)
            ax_stab.set_ylim(0, 1.05)

            # ═══════════════════════════════════════════════════
            # 5 ▸ COMBO & HEALTH TIMELINE
            # ═══════════════════════════════════════════════════
            _style_ax(ax_combo, "❤️  Health & Combo", "Trial #", "")
            if trials:
                ax_combo.plot(trials, healths, color=_RED_H, lw=2,
                               alpha=0.85, label="Health %")
                ax_combo.fill_between(trials, healths, alpha=0.1,
                                       color=_RED_H)
                ax2 = ax_combo.twinx()
                ax2.set_facecolor("none")
                ax2.plot(trials, combos, color=_ORANGE_H, lw=1.5,
                          alpha=0.8, ls="--", label="Combo")
                ax2.tick_params(colors=_TEXT_DIM, labelsize=7)
                ax2.set_ylabel("Combo", fontsize=7, color=_TEXT_DIM)
                for sp in ax2.spines.values():
                    sp.set_color(_GRID_C)
                lines1, labels1 = ax_combo.get_legend_handles_labels()
                lines2, labels2 = ax2.get_legend_handles_labels()
                ax_combo.legend(lines1+lines2, labels1+labels2,
                                 fontsize=6, loc="upper left",
                                 facecolor=_PANEL_BG, edgecolor=_GRID_C,
                                 labelcolor=_TEXT_MID)
            ax_combo.set_ylim(0, 110)

            # ═══════════════════════════════════════════════════
            # 6 ▸ DIFFICULTY GAUGE  (arc gauge)
            # ═══════════════════════════════════════════════════
            ax_diff.set_xlim(-1.5, 1.5)
            ax_diff.set_ylim(-1.0, 1.5)
            ax_diff.set_aspect("equal")
            ax_diff.axis("off")
            ax_diff.set_facecolor(_PANEL_BG)

            arc_colors_hex = [_GREEN_H, _NEON, _YELLOW_H, _PINK_H, _RED_H]
            segment_span = 270 / 5
            for i in range(5):
                theta1 = -135 + i * segment_span
                theta2 = theta1 + segment_span - 2
                c = arc_colors_hex[i]
                alpha = 0.9 if (i+1) == diff_now else 0.25
                ax_diff.add_patch(Arc((0, 0), 2.2, 2.2, angle=0,
                                       theta1=theta1, theta2=theta2,
                                       color=c, lw=10, alpha=alpha))

            needle_angle_deg = -135 + (diff_now - 0.5) * segment_span
            needle_rad = math.radians(needle_angle_deg)
            nl = 0.8
            nx = nl * math.cos(needle_rad)
            ny = nl * math.sin(needle_rad)
            ax_diff.annotate("", xy=(nx, ny), xytext=(0, 0),
                              arrowprops=dict(arrowstyle="-|>",
                                               color=_WHITE_H, lw=2.5))
            ax_diff.plot(0, 0, "o", color=_TEXT_DIM, markersize=6)

            ac = arc_colors_hex[diff_now - 1]
            ax_diff.text(0, -0.30, f"Level {diff_now}", ha="center",
                          va="center", color=ac, fontsize=16,
                          fontweight="bold")
            lbl = DIFFICULTY_LEVELS[diff_now]["label"].split("-")[1].strip()
            ax_diff.text(0, -0.60, lbl, ha="center", color=_TEXT_DIM,
                          fontsize=8)
            ax_diff.set_title("⚙  Difficulty", color=_NEON, fontsize=9,
                               fontweight="bold", pad=4)

            # ═══════════════════════════════════════════════════
            # 7 ▸ CURSOR VELOCITY OVER TRIALS
            # ═══════════════════════════════════════════════════
            _style_ax(ax_vel, "🚀  Cursor Velocity", "Trial #", "px/s")
            if trials and vels:
                ax_vel.fill_between(trials, vels, alpha=0.12,
                                     color=_ORANGE_H)
                ax_vel.plot(trials, vels, color=_ORANGE_H, lw=1.5,
                             marker="o", markersize=2, alpha=0.8)
                if len(vels) >= 5:
                    va = _rolling_average(vels, 5)
                    va_x = trials[4:]
                    ax_vel.plot(va_x, va, color=_NEON, lw=2, alpha=0.9)

            # ═══════════════════════════════════════════════════
            # 8 ▸ ERROR DISTANCE HEATMAP STRIP
            # ═══════════════════════════════════════════════════
            _style_ax(ax_err, "📐  Click Precision", "Trial #",
                       "Error (px)")
            if trials and errs:
                scatter_colors = []
                for e in errs:
                    if   e < 10: scatter_colors.append(_GREEN_H)
                    elif e < 25: scatter_colors.append(_YELLOW_H)
                    elif e < 50: scatter_colors.append(_ORANGE_H)
                    else:        scatter_colors.append(_RED_H)
                ax_err.scatter(trials, errs, c=scatter_colors, s=25,
                                alpha=0.8, edgecolors="none", zorder=3)
                if len(errs) >= 3:
                    ea = _rolling_average(errs, 5 if len(errs)>=5 else len(errs))
                    ea_x = trials[len(trials)-len(ea):]
                    ax_err.plot(ea_x, ea, color=_PINK_H, lw=2,
                                 alpha=0.85)
                ax_err.axhline(25, color=_YELLOW_H, lw=0.7, ls=":",
                                alpha=0.5)

            # ═══════════════════════════════════════════════════
            # 9a ▸ HIT BREAKDOWN PIE
            # ═══════════════════════════════════════════════════
            ax_pie.set_facecolor(_PANEL_BG)
            ax_pie.axis("equal")
            counts = [snap["perfect"], snap["great"],
                      snap["good"], snap["miss"]]
            pie_labels  = ["Perfect", "Great", "Good", "Miss"]
            pie_colors  = [_NEON, _GREEN_H, _YELLOW_H, _RED_H]
            if sum(counts) > 0:
                wedges, texts, autotexts = ax_pie.pie(
                    counts, labels=pie_labels, colors=pie_colors,
                    autopct=lambda p: f"{p:.0f}%" if p > 0 else "",
                    startangle=90, pctdistance=0.75,
                    wedgeprops=dict(width=0.45, edgecolor=_PANEL_BG,
                                    linewidth=2))
                for t in texts:
                    t.set_color(_TEXT_MID); t.set_fontsize(7)
                for t in autotexts:
                    t.set_color(_WHITE_H); t.set_fontsize(7)
                    t.set_fontweight("bold")
            else:
                ax_pie.text(0, 0, "No data", ha="center", va="center",
                             color=_TEXT_DIM, fontsize=10)
            ax_pie.set_title("🏆  Hit Breakdown", color=_NEON, fontsize=9,
                              fontweight="bold", pad=8)

            # ═══════════════════════════════════════════════════
            # 9b ▸ SESSION METRICS PANEL
            # ═══════════════════════════════════════════════════
            ax_info.axis("off")
            ax_info.set_facecolor(_PANEL_BG)

            acc = (t_hits / t_total * 100) if t_total else 0
            mins = int(elapsed) // 60
            secs = int(elapsed) % 60
            avg_rt = f"{np.mean(rts):.3f}s" if rts else "—"
            best_rt = f"{min(rts):.3f}s" if rts else "—"
            avg_stab = f"{np.mean(stabs):.2f}" if stabs else "—"

            metrics = [
                ("SESSION METRICS", _NEON,     12, "bold"),
                ("─"*28,            _GRID_C,    8, "normal"),
                (f"Duration      {mins:02d}:{secs:02d}",
                                    _TEXT_MID,  9, "normal"),
                (f"Total Trials  {t_total}",
                                    _TEXT_MID,  9, "normal"),
                (f"Hits          {t_hits}",
                                    _GREEN_H,   9, "bold"),
                (f"Misses        {snap['miss']}",
                                    _RED_H,     9, "bold"),
                (f"Accuracy      {acc:.1f}%",
                                    _NEON,     10, "bold"),
                ("─"*28,            _GRID_C,    8, "normal"),
                (f"Avg RT        {avg_rt}",
                                    _YELLOW_H,  9, "normal"),
                (f"Best RT       {best_rt}",
                                    _GREEN_H,   9, "normal"),
                (f"Avg Stability {avg_stab}",
                                    _NEON,      9, "normal"),
                (f"Max Combo     {snap['max_combo']}",
                                    _ORANGE_H,  9, "bold"),
                (f"Score         {snap['current_score']:,}",
                                    _NEON,     10, "bold"),
            ]

            y_pos = 0.97
            for txt, color, fsize, weight in metrics:
                ax_info.text(0.05, y_pos, txt,
                              transform=ax_info.transAxes,
                              color=color, fontsize=fsize,
                              fontweight=weight,
                              fontfamily="monospace")
                y_pos -= 0.078

            # ═══════════════════════════════════════════════════
            # SUPER-TITLE
            # ═══════════════════════════════════════════════════
            fig.suptitle(
                "NEURO-OSU  ┃  Premium Clinical Dashboard",
                color=_NEON, fontsize=12, fontweight="bold",
                x=0.5, y=0.97,
                fontfamily="monospace"
            )

        ani = animation.FuncAnimation(fig, update, interval=700,
                                       cache_frame_data=False)
        plt.show(block=False)

        while not _dashboard_stop.is_set():
            try:
                fig.canvas.flush_events()
                time.sleep(0.05)
            except Exception:
                break

    except Exception as e:
        print(f"Dashboard error (non-critical): {e}")
        import traceback; traceback.print_exc()
        while not _dashboard_stop.is_set():
            time.sleep(0.1)

# ─────────────────────────────────────────────────────────────────────────────
# SPAWN HELPER
# ─────────────────────────────────────────────────────────────────────────────
def spawn_circle(params):
    margin = params["circle_r"] + 20
    x = random.randint(margin, SCREEN_W - margin)
    y = random.randint(100, SCREEN_H - margin)
    return HitCircle(x, y, params)

# ─────────────────────────────────────────────────────────────────────────────
# MENU SCREEN
# ─────────────────────────────────────────────────────────────────────────────
def draw_menu(screen, fonts, pulse_t):
    screen.fill(BG_DARK)
    for gx in range(0, SCREEN_W, 55):
        for gy in range(0, SCREEN_H, 55):
            pygame.draw.circle(screen, (20,26,44), (gx,gy), 1)

    cx = SCREEN_W // 2

    g2 = int(160 + 50*math.sin(pulse_t*1.2))
    b2 = int(200 + 40*math.sin(pulse_t*0.8))
    title_surf = fonts["big"].render("NEURO-OSU", True, (60, g2, b2))
    screen.blit(title_surf, (cx - title_surf.get_width()//2, 140))

    sub = fonts["small"].render("Adaptive Kinetic Path-Finder  |  Motor Training", True, GREY)
    screen.blit(sub, (cx - sub.get_width()//2, 215))

    _panel(screen, pygame.Rect(cx-340, 270, 680, 90), fill=PANEL, border=BORDER)
    for i, (line, col) in enumerate([
        ("Click the glowing circles before they expire to score points.", LGREY),
        ("Health drains on miss — keep your combo alive!", GREY),
    ]):
        s = fonts["tiny"].render(line, True, col)
        screen.blit(s, (cx - s.get_width()//2, 285 + i*30))

    for i in range(6):
        angle = pulse_t * 0.4 + i * math.pi/3
        ox = cx + int(350 * math.cos(angle))
        oy = SCREEN_H//2 + int(130 * math.sin(angle))
        alpha_surf = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.circle(alpha_surf, (*CYAN, 18), (40,40), 38, 2)
        screen.blit(alpha_surf, (ox-40, oy-40))

    for i in range(12):
        angle = pulse_t * 0.8 + i * math.pi/6
        ox = cx + int(420 * math.cos(angle))
        oy = SCREEN_H//2 + int(170 * math.sin(angle))
        a_s = pygame.Surface((20, 20), pygame.SRCALPHA)
        pygame.draw.circle(a_s, (*PINK, 25), (10,10), 9, 1)
        screen.blit(a_s, (ox-10, oy-10))

    pr = int(20*math.sin(pulse_t*2.2))
    play_rect = pygame.Rect(cx - 130, 395, 260, 58)
    pygame.draw.rect(screen, (0, 170+pr, 170+pr), play_rect, border_radius=10)
    play_txt = fonts["fb"].render("▶  PLAY", True, BG_DARK)
    screen.blit(play_txt, (cx - play_txt.get_width()//2, 410))

    hint = fonts["tiny"].render("Press SPACE or click PLAY to start", True, (38,48,72))
    screen.blit(hint, (cx - hint.get_width()//2, SCREEN_H - 45))

    return play_rect

# ─────────────────────────────────────────────────────────────────────────────
# GAME OVER SCREEN
# ─────────────────────────────────────────────────────────────────────────────
def draw_game_over(screen, fonts, score, total_t, total_h, elapsed):
    ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    ov.fill((6, 8, 16, 235))
    screen.blit(ov, (0, 0))

    cx = SCREEN_W // 2

    go_surf = fonts["big"].render("GAME  OVER", True, RED)
    screen.blit(go_surf, (cx - go_surf.get_width()//2, 100))

    acc = (total_h / total_t * 100) if total_t else 0.0
    mins = int(elapsed)//60; secs = int(elapsed)%60
    _panel(screen, pygame.Rect(cx-320, 185, 640, 180), fill=PANEL2, border=BORDER)

    stats = [
        ("Score",    f"{score:,}",             CYAN),
        ("Accuracy", f"{acc:.1f}%",            GREEN if acc>=70 else (YELLOW if acc>=50 else ORANGE)),
        ("Hits",     str(total_h),             GREEN),
        ("Misses",   str(total_t - total_h),   RED),
        ("Time",     f"{mins:02d}:{secs:02d}", LGREY),
    ]
    col_positions = [cx - 255, cx - 80, cx + 95]
    for i, (label, val, col) in enumerate(stats):
        col_x = col_positions[i % 3]
        row_y = 200 + (i // 3) * 80
        lb = fonts["tiny"].render(label, True, GREY)
        vl = fonts["fb"].render(val, True, col)
        screen.blit(lb, (col_x - lb.get_width()//2, row_y))
        screen.blit(vl, (col_x - vl.get_width()//2, row_y + 22))

    if   acc >= 90: grade, gc = "S", GOLD
    elif acc >= 80: grade, gc = "A", GREEN
    elif acc >= 65: grade, gc = "B", CYAN
    elif acc >= 50: grade, gc = "C", YELLOW
    else:           grade, gc = "D", ORANGE
    pygame.draw.circle(screen, gc, (cx + 260, 250), 48)
    pygame.draw.circle(screen, BG_DARK, (cx + 260, 250), 43)
    grade_surf = fonts["big"].render(grade, True, gc)
    screen.blit(grade_surf, (cx + 260 - grade_surf.get_width()//2, 230))

    retry_rect = pygame.Rect(cx - 215, 400, 190, 55)
    pygame.draw.rect(screen, GREEN, retry_rect, border_radius=10)
    rt = fonts["fb"].render("RETRY", True, BG_DARK)
    screen.blit(rt, (retry_rect.centerx - rt.get_width()//2, retry_rect.centery - rt.get_height()//2))

    menu_rect = pygame.Rect(cx + 25, 400, 190, 55)
    pygame.draw.rect(screen, CYAN, menu_rect, border_radius=10)
    mt = fonts["fb"].render("MAIN MENU", True, BG_DARK)
    screen.blit(mt, (menu_rect.centerx - mt.get_width()//2, menu_rect.centery - mt.get_height()//2))

    hint = fonts["tiny"].render("R = Retry   M = Menu   ESC = Quit", True, (45,58,85))
    screen.blit(hint, (cx - hint.get_width()//2, SCREEN_H - 45))

    return retry_rect, menu_rect

# ─────────────────────────────────────────────────────────────────────────────
# UTILITY
# ─────────────────────────────────────────────────────────────────────────────
def _trail_variance(trail):
    pts = list(trail)
    if len(pts) < 2: return 0.0
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    mx_v = sum(xs)/len(xs);   my_v = sum(ys)/len(ys)
    return sum((x-mx_v)**2 + (y-my_v)**2 for x,y in pts) / len(pts)

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    init_csv()
    pygame.init()
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Neuro-Osu  |  Adaptive Kinetic Path-Finder")
    clock  = pygame.time.Clock()
    pygame.mouse.set_visible(False)

    fonts = {
        "big":   pygame.font.SysFont("consolas", 52, bold=True),
        "hud":   pygame.font.SysFont("consolas", 28, bold=True),
        "small": pygame.font.SysFont("consolas", 18),
        "tiny":  pygame.font.SysFont("consolas", 14),
        "fb":    pygame.font.SysFont("consolas", 26, bold=True),
    }

    # Audio init
    SND_HIT = SND_MISS = None
    try:
        SND_HIT  = _tone(880, 0.09, 0.42)
        SND_MISS = _tone(200, 0.14, 0.28, "tri")
        bgm = _make_bgm()
        bgm.play(-1)
    except Exception as e:
        print(f"Audio init warning: {e}")

    # Start dashboard thread
    dash_thread = threading.Thread(target=clinical_dashboard, daemon=True)
    dash_thread.start()

    # ── Game state variables ──────────────────────────────────────────────────
    state   = "menu"
    pulse_t = 0.0

    # Forward-declare game vars (populated by reset_game)
    diff_mgr = DifficultyManager()
    particles = []; float_texts = []; flashes = []
    score = combo = total_t = total_h = 0
    health = 100.0
    circles = []
    session_start = time.time()
    last_spawn = time.time()
    spawn_interval = 2.2
    prev_mouse = pygame.mouse.get_pos()
    mouse_vel = 0.0
    cursor_trail = deque(maxlen=12)
    recent_rts   = deque(maxlen=20)

    def reset_game():
        nonlocal diff_mgr, particles, float_texts, flashes
        nonlocal score, combo, total_t, total_h, health, circles
        nonlocal session_start, last_spawn, prev_mouse, mouse_vel
        nonlocal cursor_trail, recent_rts
        diff_mgr      = DifficultyManager()
        particles     = []; float_texts = []; flashes = []
        score = combo = total_t = total_h = 0
        health        = 100.0
        circles       = []
        session_start = time.time()
        last_spawn    = time.time()
        prev_mouse    = pygame.mouse.get_pos()
        mouse_vel     = 0.0
        cursor_trail  = deque(maxlen=12)
        recent_rts    = deque(maxlen=20)
        shared.session_start = time.time()
        # Reset shared data for new session
        with shared.lock:
            shared.trial_numbers.clear()
            shared.reaction_times.clear()
            shared.stabilities.clear()
            shared.difficulties.clear()
            shared.scores_binary.clear()
            shared.score_labels.clear()
            shared.velocities.clear()
            shared.error_distances.clear()
            shared.combo_at_trial.clear()
            shared.health_at_trial.clear()
            shared.cumulative_scores.clear()
            shared.total_trials   = 0
            shared.total_hits     = 0
            shared.current_diff   = 1
            shared.current_combo  = 0
            shared.max_combo      = 0
            shared.current_health = 100.0
            shared.current_score  = 0
            shared.perfect_count  = 0
            shared.great_count    = 0
            shared.good_count     = 0
            shared.miss_count     = 0

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        pulse_t += dt
        mx, my = pygame.mouse.get_pos()

        # ──────────────────────────────────────────────────────
        # MENU STATE
        # ──────────────────────────────────────────────────────
        if state == "menu":
            play_rect = draw_menu(screen, fonts, pulse_t)
            # Draw custom cursor on menu too
            pygame.draw.circle(screen, WHITE, (mx, my), 6)
            pygame.draw.circle(screen, CYAN,  (mx, my), 10, 1)
            pygame.display.flip()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:      running = False
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE: running = False
                    if ev.key == pygame.K_SPACE:
                        reset_game(); state = "playing"
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    if play_rect.collidepoint(ev.pos):
                        reset_game(); state = "playing"
            continue

        # ──────────────────────────────────────────────────────
        # GAME OVER STATE
        # ──────────────────────────────────────────────────────
        if state == "gameover":
            elapsed_final = time.time() - session_start
            screen.fill(BG_DARK)
            draw_grid(screen)
            retry_rect, menu_rect = draw_game_over(
                screen, fonts, score, total_t, total_h, elapsed_final)
            # Draw custom cursor on game over too
            pygame.draw.circle(screen, WHITE, (mx, my), 6)
            pygame.draw.circle(screen, CYAN,  (mx, my), 10, 1)
            pygame.display.flip()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:      running = False
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE: running = False
                    if ev.key == pygame.K_r:      reset_game(); state = "playing"
                    if ev.key == pygame.K_m:      reset_game(); state = "menu"
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    if retry_rect.collidepoint(ev.pos): reset_game(); state = "playing"
                    elif menu_rect.collidepoint(ev.pos): reset_game(); state = "menu"
            continue

        # ──────────────────────────────────────────────────────
        # PLAYING STATE
        # ──────────────────────────────────────────────────────
        elapsed = time.time() - session_start

        # Cursor velocity
        dx = mx - prev_mouse[0]; dy = my - prev_mouse[1]
        mouse_vel  = math.hypot(dx, dy) / max(dt, 0.001)
        prev_mouse = (mx, my)
        cursor_trail.append((mx, my))

        # Events
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                running = False

            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                now     = time.time()
                hit_any = False

                for circ in circles[:]:
                    if not circ.alive: continue
                    score_label, err = circ.hit_score(mx, my)
                    if score_label != "Miss":
                        circ.alive = False; circ.clicked = True
                        rt = (now - circ.spawn_t) if circ.first_move_t is None \
                             else (circ.first_move_t - circ.spawn_t)
                        rt = max(0.0, rt)

                        pts = {"Perfect": 300, "Great": 200, "Good": 100}[score_label]
                        combo += 1
                        score += pts * combo
                        if combo >= 5:
                            score += int(pts * 0.5)
                            float_texts.append(FloatText(circ.x, circ.y-70, "x1.5!", ORANGE, 18))
                        total_h += 1; total_t += 1
                        hp_gain = {"Perfect": 4.0, "Great": 2.0, "Good": 1.0}[score_label]
                        health = min(100.0, health + hp_gain)

                        mv = _trail_variance(cursor_trail)
                        log_trial(circ.id, rt, err, mouse_vel,
                                  diff_mgr.level, score_label, mv, "circle",
                                  current_combo=combo,
                                  current_health=health,
                                  current_score=score)
                        diff_mgr.record(score_label, mv)
                        recent_rts.append(rt)

                        if SND_HIT: SND_HIT.play()
                        c_map = {"Perfect": CYAN, "Great": GREEN, "Good": YELLOW}
                        c = c_map[score_label]
                        burst(particles, circ.x, circ.y, c, 22)
                        ring_burst(particles, circ.x, circ.y, WHITE, 10)
                        float_texts.append(FloatText(circ.x, circ.y-40, score_label, c, 24))
                        hit_any = True
                        break

                if not hit_any:
                    combo = 0
                    flashes.append(Flash(PINK, 0.10))

        # Mark circles as first-moved
        for circ in circles:
            if circ.alive and circ.first_move_t is None:
                if math.hypot(mx-circ.x, my-circ.y) < circ.radius*3 and mouse_vel > 5:
                    circ.first_move_t = time.time()

        # Expire circles
        for circ in circles:
            if circ.alive and circ.age >= circ.lifetime:
                circ.alive = False; combo = 0
                total_t += 1; health -= 12.0
                if SND_MISS: SND_MISS.play()
                flashes.append(Flash(RED, 0.12))
                mv = _trail_variance(cursor_trail)
                log_trial(circ.id, circ.lifetime, circ.radius*2,
                          0, diff_mgr.level, "Miss", mv, "circle",
                          current_combo=combo,
                          current_health=health,
                          current_score=score)
                diff_mgr.record("Miss", mv)
                float_texts.append(FloatText(circ.x, circ.y-20, "MISS", RED, 22))

        # Clean dead circles
        circles = [c for c in circles if c.alive]

        # Spawn new circles
        params = diff_mgr.params
        if time.time() - last_spawn >= spawn_interval:
            last_spawn = time.time()
            circles.append(spawn_circle(params))

        # Update particles, floats, flashes
        particles[:]   = [p for p in particles   if p.update(dt)]
        float_texts[:] = [f for f in float_texts if f.update(dt)]
        flashes[:]     = [f for f in flashes     if f.update(dt)]

        # Game over check
        if health <= 0:
            health = 0
            state  = "gameover"
            continue

        # ── DRAW ─────────────────────────────────────────────
        screen.fill(BG_DARK)
        draw_grid(screen)

        # Draw circles
        for circ in circles:
            circ.draw(screen)

        # Particles
        for p in particles:
            p.draw(screen)

        # Float texts
        for f in float_texts:
            f.draw(screen)

        # Screen flashes
        for f in flashes:
            f.draw(screen)

        # Cursor trail
        trail_list = list(cursor_trail)
        for i, (tx, ty) in enumerate(trail_list):
            alpha = int(180 * i / max(len(trail_list), 1))
            r_sz  = max(1, 4 - i // 3)
            ts = pygame.Surface((r_sz*2, r_sz*2), pygame.SRCALPHA)
            pygame.draw.circle(ts, (*CYAN, alpha), (r_sz, r_sz), r_sz)
            screen.blit(ts, (tx - r_sz, ty - r_sz))

        # HUD
        acc = (total_h / total_t * 100) if total_t else 100.0
        draw_hud(screen, fonts, diff_mgr, score, combo, acc, elapsed, health, recent_rts)

        # Custom cursor (game2 style)
        pygame.draw.circle(screen, WHITE, (mx, my), 6)
        pygame.draw.circle(screen, CYAN,  (mx, my), 10, 1)

        pygame.display.flip()

    # Cleanup
    _dashboard_stop.set()
    pygame.mouse.set_visible(True)
    pygame.quit()
    print(f"\nSession ended. Data saved to: {CSV_PATH}")
    print(f"  Trials: {total_t} | Hits: {total_h} | "
          f"Accuracy: {(total_h/total_t*100) if total_t else 0:.1f}%")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()