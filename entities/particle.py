# entities/particle.py
# hit-burst particles — purely visual, no game logic

import math
import random
import pygame


class Particle:
    __slots__ = ["x", "y", "vx", "vy", "color", "life", "mlife", "sz", "shape"]

    def __init__(self, x: float, y: float, color: tuple):
        self.x     = x
        self.y     = y
        self.vx    = random.uniform(-4, 4)
        self.vy    = random.uniform(-5.5, -0.5)
        self.color = color
        self.life  = random.uniform(0.45, 1.0)
        self.mlife = self.life
        self.sz    = random.uniform(3, 9)
        self.shape = random.choice(["circle", "star"])

    def update(self, dt: float) -> bool:
        self.x  += self.vx
        self.y  += self.vy
        self.vy += 0.2
        self.life -= dt
        return self.life > 0

    def draw(self, surf: pygame.Surface):
        a = self.life / self.mlife
        c = (int(self.color[0] * a), int(self.color[1] * a), int(self.color[2] * a))
        if self.shape == "circle":
            pygame.draw.circle(surf, c, (int(self.x), int(self.y)), max(1, int(self.sz * a)))
        else:
            sz = max(2, int(self.sz * a))
            x2, y2 = int(self.x), int(self.y)
            pygame.draw.line(surf, c, (x2 - sz, y2), (x2 + sz, y2), 1)
            pygame.draw.line(surf, c, (x2, y2 - sz), (x2, y2 + sz), 1)


def burst(particles: list, x: float, y: float, color: tuple, n: int = 22):
    for _ in range(n):
        particles.append(Particle(x, y, color))


def ring_burst(particles: list, x: float, y: float, color: tuple, n: int = 18):
    for i in range(n):
        angle = 2 * math.pi * i / n
        speed = random.uniform(2.5, 5)
        p = Particle(x, y, color)
        p.vx = math.cos(angle) * speed
        p.vy = math.sin(angle) * speed
        particles.append(p)