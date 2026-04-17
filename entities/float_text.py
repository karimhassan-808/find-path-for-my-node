# entities/float_text.py
# floating "perfect / great / miss" labels that drift upward and fade

import pygame


class FloatText:
    def __init__(self, x: float, y: float, txt: str, color: tuple, size: int = 22):
        self.x     = x
        self.y     = y
        self.txt   = txt
        self.color = color
        self.life  = 1.3
        self.mlife = 1.3
        self.font  = pygame.font.SysFont("consolas", size, bold=True)

    def update(self, dt: float) -> bool:
        self.y    -= 1.1
        self.life -= dt
        return self.life > 0

    def draw(self, surf: pygame.Surface):
        a = self.life / self.mlife
        c = (int(self.color[0] * a), int(self.color[1] * a), int(self.color[2] * a))
        s = self.font.render(self.txt, True, c)
        surf.blit(s, (int(self.x) - s.get_width() // 2, int(self.y)))