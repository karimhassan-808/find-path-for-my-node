# utils.py
# small helpers — trail variance, spawner, and the gamesession dataclass

import math
import random
import time
from collections import deque
from dataclasses import dataclass, field

from core.constants import SCREEN_W, SCREEN_H, SPAWN_INTERVAL
from core.difficulty import DifficultyManager
from entities.hit_circle import HitCircle


def trail_variance(trail) -> float:
    """cursor movement variance — proxy for impulsive/erratic movement in adhd."""
    pts = list(trail)
    if len(pts) < 2:
        return 0.0
    mx = sum(p[0] for p in pts) / len(pts)
    my = sum(p[1] for p in pts) / len(pts)
    return sum((p[0] - mx) ** 2 + (p[1] - my) ** 2 for p in pts) / len(pts)


def trail_velocity(trail) -> float:
    """average cursor speed (px/s) over the trail window."""
    pts = list(trail)
    if len(pts) < 2:
        return 0.0
    total_dist = 0.0
    total_dt = 0.0
    for i in range(1, len(pts)):
        x1, y1, t1 = pts[i - 1]
        x2, y2, t2 = pts[i]
        dt = t2 - t1
        if dt <= 0:
            continue
        total_dist += math.hypot(x2 - x1, y2 - y1)
        total_dt += dt
    return total_dist / total_dt if total_dt > 0 else 0.0


_id_counter = 0

def spawn_circle(params: dict, sw: int = 1280, sh: int = 720) -> HitCircle:
    global _id_counter
    _id_counter += 1
    margin = params["circle_r"] + 20
    x = random.randint(margin, sw - margin)
    y = random.randint(100, sh - margin)
    return HitCircle(x, y, params, target_id=_id_counter)


@dataclass
class GameSession:
    """all mutable game state in one place — replaces 15 nonlocal declarations."""
    diff_mgr:     DifficultyManager = field(default_factory=DifficultyManager)
    particles:    list = field(default_factory=list)
    float_texts:  list = field(default_factory=list)
    flashes:      list = field(default_factory=list)
    circles:      list = field(default_factory=list)
    score:        int   = 0
    combo:        int   = 0
    total_t:      int   = 0
    total_h:      int   = 0
    health:       float = 100.0
    session_start: float = field(default_factory=time.time)
    last_spawn:   float  = field(default_factory=time.time)
    prev_mouse:   tuple  = (0, 0)
    mouse_vel:    float  = 0.0
    cursor_trail: deque  = field(default_factory=lambda: deque(maxlen=12))
    recent_rts:   deque  = field(default_factory=lambda: deque(maxlen=20))

    def reset(self):
        self.diff_mgr      = DifficultyManager()
        self.particles     = []
        self.float_texts   = []
        self.flashes       = []
        self.circles       = []
        self.score         = 0
        self.combo         = 0
        self.total_t       = 0
        self.total_h       = 0
        self.health        = 100.0
        self.session_start = time.time()
        self.last_spawn    = time.time()
        self.mouse_vel     = 0.0
        self.cursor_trail  = deque(maxlen=12)
        self.recent_rts    = deque(maxlen=20)

    @property
    def elapsed(self) -> float:
        return time.time() - self.session_start

    @property
    def accuracy(self) -> float:
        return (self.total_h / self.total_t * 100) if self.total_t else 100.0