# entities/hit_circle.py
# the main target — spawns, pulses, scores clicks, and expires

import math
import time
import pygame
from core.constants import CYAN, RED, WHITE


class HitCircle:
    def __init__(self, x: int, y: int, params: dict, target_id: int):
        self.id       = target_id
        self.x        = x
        self.y        = y
        self.radius   = params["circle_r"]
        self.lifetime = params["lifetime"]
        self.spawn_t  = time.time()
        self.alive    = True
        self.clicked  = False
        self.first_move_t = None
        self.pulse    = 0.0

    @property
    def age(self):       return time.time() - self.spawn_t
    @property
    def fraction(self):  return min(1.0, self.age / self.lifetime)
    @property
    def time_left(self): return max(0.0, self.lifetime - self.age)
    @property
    def frac_left(self): return self.time_left / self.lifetime

    def contains(self, mx: int, my: int) -> bool:
        return math.hypot(mx - self.x, my - self.y) <= self.radius

    def hit_score(self, mx: int, my: int) -> tuple[str, float]:
        dist = math.hypot(mx - self.x, my - self.y)
        r    = self.radius
        if   dist <= r * 0.35: return "Perfect", dist
        elif dist <= r * 0.65: return "Great",   dist
        elif dist <= r:        return "Good",     dist
        else:                  return "Miss",     dist

    def draw(self, surf: pygame.Surface):
        self.pulse = (self.pulse + 0.07) % (2 * math.pi)
        pr  = self.radius + 3 * math.sin(self.pulse)
        fl  = self.frac_left
        urg = 1.0 - fl

        # color shifts toward red as time runs out
        c_r = min(255, int(CYAN[0] + (RED[0] - CYAN[0]) * urg * 0.6))
        c_g = max(0,   int(CYAN[1] + (RED[1] - CYAN[1]) * urg * 0.6))
        c_b = max(0,   int(CYAN[2] + (RED[2] - CYAN[2]) * urg * 0.6))
        draw_col = (c_r, c_g, c_b)

        # glow rings
        for offset, ab in [(14, 60), (9, 90), (5, 130)]:
            col = tuple(int(c * (ab / 255)) for c in CYAN)
            pygame.draw.circle(surf, col, (self.x, self.y), int(pr + offset), 2)

        # approach ring
        approach_r = int(pr + 55 * fl)
        ring_col = (
            int(255 * urg + CYAN[0] * (1 - urg)),
            int(CYAN[1] * (1 - urg)),
            int(CYAN[2] * (1 - urg)),
        )
        pygame.draw.circle(surf, ring_col, (self.x, self.y), approach_r, 2)

        # main body + centre dot
        pygame.draw.circle(surf, draw_col, (self.x, self.y), int(pr))
        pygame.draw.circle(surf, WHITE,    (self.x, self.y), max(5, int(pr * 0.28)))

        # arc progress indicator
        if fl > 0 and approach_r > 0:
            try:
                ar_rect = pygame.Rect(
                    self.x - approach_r, self.y - approach_r,
                    approach_r * 2, approach_r * 2,
                )
                pygame.draw.arc(surf, WHITE, ar_rect,
                                math.pi / 2, math.pi / 2 + 2 * math.pi * fl, 2)
            except Exception:
                pass

        # urgent pulse ring when < 30% time left
        if fl < 0.3:
            p2 = (self.pulse * 3) % (2 * math.pi)
            extra = int(4 * math.sin(p2) * fl / 0.3)
            pygame.draw.circle(surf, RED, (self.x, self.y), int(pr) + extra, 1)