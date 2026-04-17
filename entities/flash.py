# entities/flash.py
# full-screen color flash on hit or miss

import pygame
from core.constants import SCREEN_W, SCREEN_H


class Flash:
    def __init__(self, color: tuple, dur: float = 0.13):
        self.color = color
        self.life  = dur
        self.mlife = dur

    def update(self, dt: float) -> bool:
        self.life -= dt
        return self.life > 0

    def draw(self, surf: pygame.Surface):
        a  = int(100 * self.life / self.mlife)
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((*self.color, a))
        surf.blit(ov, (0, 0))