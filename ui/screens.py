# ui/screens.py
import math
import pygame
from core.constants import (
    SCREEN_W, SCREEN_H, BG_DARK, PANEL, PANEL2, BORDER,
    CYAN, PINK, GREEN, YELLOW, ORANGE, RED, GOLD,
    WHITE, GREY, LGREY,
)
from ui.hud import _panel, _txt


def draw_menu(screen, fonts, pulse_t: float):
    sw, sh = screen.get_size()          # ← live size
    screen.fill(BG_DARK)

    for gx in range(0, sw, 55):
        for gy in range(0, sh, 55):
            pygame.draw.circle(screen, (20, 26, 44), (gx, gy), 1)

    cx = sw // 2                        # ← live centre

    g2 = int(160 + 50 * math.sin(pulse_t * 1.2))
    b2 = int(200 + 40 * math.sin(pulse_t * 0.8))
    title = fonts["big"].render("NEURO-OSU", True, (60, g2, b2))
    screen.blit(title, (cx - title.get_width() // 2, sh * 0.22))   # ← proportional y

    sub = fonts["small"].render("adaptive kinetic path-finder  |  attention training", True, GREY)
    screen.blit(sub, (cx - sub.get_width() // 2, sh * 0.32))

    _panel(screen, pygame.Rect(cx - 340, sh * 0.38, 680, 90), fill=PANEL, border=BORDER)
    for i, (line, col) in enumerate([
        ("click the glowing circles before they expire to score points.", LGREY),
        ("health drains on miss — keep your focus and combo alive!", GREY),
    ]):
        s = fonts["tiny"].render(line, True, col)
        screen.blit(s, (cx - s.get_width() // 2, sh * 0.40 + i * 30))

    for i in range(6):
        angle = pulse_t * 0.4 + i * math.pi / 3
        ox = cx + int(sw * 0.27 * math.cos(angle))   # ← proportional orbit radius
        oy = sh // 2 + int(sh * 0.18 * math.sin(angle))
        a_s = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.circle(a_s, (*CYAN, 18), (40, 40), 38, 2)
        screen.blit(a_s, (ox - 40, oy - 40))

    for i in range(12):
        angle = pulse_t * 0.8 + i * math.pi / 6
        ox = cx + int(sw * 0.33 * math.cos(angle))
        oy = sh // 2 + int(sh * 0.24 * math.sin(angle))
        a_s = pygame.Surface((20, 20), pygame.SRCALPHA)
        pygame.draw.circle(a_s, (*PINK, 25), (10, 10), 9, 1)
        screen.blit(a_s, (ox - 10, oy - 10))

    pr = int(20 * math.sin(pulse_t * 2.2))
    play_y = int(sh * 0.55)
    play_rect = pygame.Rect(cx - 130, play_y, 260, 58)
    pygame.draw.rect(screen, (0, 170 + pr, 170 + pr), play_rect, border_radius=10)
    play_txt = fonts["fb"].render("▶  PLAY", True, BG_DARK)
    screen.blit(play_txt, (cx - play_txt.get_width() // 2, play_y + 15))

    fs_hint = fonts["tiny"].render("F11 — toggle fullscreen", True, (45, 58, 85))
    screen.blit(fs_hint, (cx - fs_hint.get_width() // 2, play_y + 72))

    hint = fonts["tiny"].render("press space or click play to start  |  esc to quit", True, (38, 48, 72))
    screen.blit(hint, (cx - hint.get_width() // 2, sh - 45))

    return play_rect


def draw_game_over(screen, fonts, score, total_t, total_h, elapsed):
    sw, sh = screen.get_size()          # ← live size
    cx = sw // 2                        # ← live centre

    ov = pygame.Surface((sw, sh), pygame.SRCALPHA)
    ov.fill((6, 8, 16, 235))
    screen.blit(ov, (0, 0))

    acc = (total_h / total_t * 100) if total_t else 0.0

    go_surf = fonts["big"].render("GAME  OVER", True, RED)
    screen.blit(go_surf, (cx - go_surf.get_width() // 2, sh * 0.13))

    mins = int(elapsed) // 60
    secs = int(elapsed) % 60

    panel_y = int(sh * 0.25)
    _panel(screen, pygame.Rect(cx - 320, panel_y, 640, 180), fill=PANEL2, border=BORDER)

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
        row_y = panel_y + 15 + (i // 3) * 80
        lb = fonts["tiny"].render(label, True, GREY)
        vl = fonts["fb"].render(val, True, col)
        screen.blit(lb, (col_x - lb.get_width() // 2, row_y))
        screen.blit(vl, (col_x - vl.get_width() // 2, row_y + 22))

    # grade circle — right side of panel
    if   acc >= 90: grade, gc = "S", GOLD
    elif acc >= 80: grade, gc = "A", GREEN
    elif acc >= 65: grade, gc = "B", CYAN
    elif acc >= 50: grade, gc = "C", YELLOW
    else:           grade, gc = "D", ORANGE
    grade_cx = cx + 260
    grade_cy = panel_y + 65
    pygame.draw.circle(screen, gc,      (grade_cx, grade_cy), 48)
    pygame.draw.circle(screen, BG_DARK, (grade_cx, grade_cy), 43)
    gs = fonts["big"].render(grade, True, gc)
    screen.blit(gs, (grade_cx - gs.get_width() // 2, grade_cy - gs.get_height() // 2))

    # buttons — centred horizontally, proportional y
    btn_y = int(sh * 0.55)
    retry_rect = pygame.Rect(cx - 215, btn_y, 190, 55)
    menu_rect  = pygame.Rect(cx + 25,  btn_y, 190, 55)
    pygame.draw.rect(screen, GREEN, retry_rect, border_radius=10)
    pygame.draw.rect(screen, CYAN,  menu_rect,  border_radius=10)
    rt = fonts["fb"].render("RETRY",     True, BG_DARK)
    mt = fonts["fb"].render("MAIN MENU", True, BG_DARK)
    screen.blit(rt, (retry_rect.centerx - rt.get_width() // 2, retry_rect.centery - rt.get_height() // 2))
    screen.blit(mt, (menu_rect.centerx  - mt.get_width() // 2, menu_rect.centery  - mt.get_height() // 2))

    hint = fonts["tiny"].render("r = retry   m = menu   esc = quit", True, (45, 58, 85))
    screen.blit(hint, (cx - hint.get_width() // 2, sh - 45))

    return retry_rect, menu_rect