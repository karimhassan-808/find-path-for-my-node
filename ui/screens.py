# ui/screens.py
# splash menu and game-over screen — no game logic, pure drawing

import math
import pygame
from core.constants import (
    SCREEN_W, SCREEN_H, BG_DARK, PANEL, PANEL2, BORDER,
    CYAN, PINK, GREEN, YELLOW, ORANGE, RED, GOLD,
    WHITE, GREY, LGREY,
)
from ui.hud import _panel, _txt


def draw_menu(screen, fonts, pulse_t: float):
    screen.fill(BG_DARK)

    # dot grid background
    for gx in range(0, SCREEN_W, 55):
        for gy in range(0, SCREEN_H, 55):
            pygame.draw.circle(screen, (20, 26, 44), (gx, gy), 1)

    cx = SCREEN_W // 2

    # pulsing title
    g2 = int(160 + 50 * math.sin(pulse_t * 1.2))
    b2 = int(200 + 40 * math.sin(pulse_t * 0.8))
    title = fonts["big"].render("NEURO-OSU", True, (60, g2, b2))
    screen.blit(title, (cx - title.get_width() // 2, 140))

    sub = fonts["small"].render("adaptive kinetic path-finder  |  attention training", True, GREY)
    screen.blit(sub, (cx - sub.get_width() // 2, 215))

    # instruction panel
    _panel(screen, pygame.Rect(cx - 340, 270, 680, 90), fill=PANEL, border=BORDER)
    for i, (line, col) in enumerate([
        ("click the glowing circles before they expire to score points.", LGREY),
        ("health drains on miss — keep your focus and combo alive!", GREY),
    ]):
        s = fonts["tiny"].render(line, True, col)
        screen.blit(s, (cx - s.get_width() // 2, 285 + i * 30))

    # orbiting decorative circles
    for i in range(6):
        angle = pulse_t * 0.4 + i * math.pi / 3
        ox = cx + int(350 * math.cos(angle))
        oy = SCREEN_H // 2 + int(130 * math.sin(angle))
        a_s = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.circle(a_s, (*CYAN, 18), (40, 40), 38, 2)
        screen.blit(a_s, (ox - 40, oy - 40))

    for i in range(12):
        angle = pulse_t * 0.8 + i * math.pi / 6
        ox = cx + int(420 * math.cos(angle))
        oy = SCREEN_H // 2 + int(170 * math.sin(angle))
        a_s = pygame.Surface((20, 20), pygame.SRCALPHA)
        pygame.draw.circle(a_s, (*PINK, 25), (10, 10), 9, 1)
        screen.blit(a_s, (ox - 10, oy - 10))

    # play button
    pr = int(20 * math.sin(pulse_t * 2.2))
    play_rect = pygame.Rect(cx - 130, 395, 260, 58)
    pygame.draw.rect(screen, (0, 170 + pr, 170 + pr), play_rect, border_radius=10)
    play_txt = fonts["fb"].render("▶  PLAY", True, BG_DARK)
    screen.blit(play_txt, (cx - play_txt.get_width() // 2, 410))

    hint = fonts["tiny"].render("press space or click play to start", True, (38, 48, 72))
    screen.blit(hint, (cx - hint.get_width() // 2, SCREEN_H - 45))

    return play_rect


def draw_game_over(screen, fonts, score, total_t, total_h, elapsed):
    ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    ov.fill((6, 8, 16, 235))
    screen.blit(ov, (0, 0))

    cx  = SCREEN_W // 2
    acc = (total_h / total_t * 100) if total_t else 0.0

    go_surf = fonts["big"].render("GAME  OVER", True, RED)
    screen.blit(go_surf, (cx - go_surf.get_width() // 2, 100))

    mins = int(elapsed) // 60
    secs = int(elapsed) % 60
    _panel(screen, pygame.Rect(cx - 320, 185, 640, 180), fill=PANEL2, border=BORDER)

    stats = [
        ("Score",    f"{score:,}",           CYAN),
        ("Accuracy", f"{acc:.1f}%",          GREEN if acc >= 70 else (YELLOW if acc >= 50 else ORANGE)),
        ("Hits",     str(total_h),           GREEN),
        ("Misses",   str(total_t - total_h), RED),
        ("Time",     f"{mins:02d}:{secs:02d}", LGREY),
    ]
    col_positions = [cx - 255, cx - 80, cx + 95]
    for i, (label, val, col) in enumerate(stats):
        col_x = col_positions[i % 3]
        row_y = 200 + (i // 3) * 80
        lb = fonts["tiny"].render(label, True, GREY)
        vl = fonts["fb"].render(val, True, col)
        screen.blit(lb, (col_x - lb.get_width() // 2, row_y))
        screen.blit(vl, (col_x - vl.get_width() // 2, row_y + 22))

    # grade circle
    if   acc >= 90: grade, gc = "S", GOLD
    elif acc >= 80: grade, gc = "A", GREEN
    elif acc >= 65: grade, gc = "B", CYAN
    elif acc >= 50: grade, gc = "C", YELLOW
    else:           grade, gc = "D", ORANGE
    pygame.draw.circle(screen, gc,      (cx + 260, 250), 48)
    pygame.draw.circle(screen, BG_DARK, (cx + 260, 250), 43)
    gs = fonts["big"].render(grade, True, gc)
    screen.blit(gs, (cx + 260 - gs.get_width() // 2, 230))

    # buttons
    retry_rect = pygame.Rect(cx - 215, 400, 190, 55)
    menu_rect  = pygame.Rect(cx + 25,  400, 190, 55)
    pygame.draw.rect(screen, GREEN, retry_rect, border_radius=10)
    pygame.draw.rect(screen, CYAN,  menu_rect,  border_radius=10)
    rt = fonts["fb"].render("RETRY",     True, BG_DARK)
    mt = fonts["fb"].render("MAIN MENU", True, BG_DARK)
    screen.blit(rt, (retry_rect.centerx - rt.get_width() // 2, retry_rect.centery - rt.get_height() // 2))
    screen.blit(mt, (menu_rect.centerx  - mt.get_width() // 2, menu_rect.centery  - mt.get_height() // 2))

    hint = fonts["tiny"].render("r = retry   m = menu   esc = quit", True, (45, 58, 85))
    screen.blit(hint, (cx - hint.get_width() // 2, SCREEN_H - 45))

    return retry_rect, menu_rect