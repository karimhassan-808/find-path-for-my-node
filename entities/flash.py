# entities/flash.py
import pygame

class Flash:
    def __init__(self, color: tuple, dur: float = 0.13):
        self.color = color
        self.life  = dur
        self.mlife = dur

    def update(self, dt: float) -> bool:
        self.life -= dt
        return self.life > 0

    def draw(self, surf: pygame.Surface):
        sw, sh = surf.get_size()                      # ← live size, no constants
        a  = int(100 * self.life / self.mlife)
        ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
        ov.fill((*self.color, a))
        surf.blit(ov, (0, 0))