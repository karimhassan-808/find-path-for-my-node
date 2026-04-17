# ui/hud.py
# draws the top bar hud and all its helper primitives

import pygame
from core.constants import (
    SCREEN_W, SCREEN_H, BG_DARK, PANEL, BORDER,
    CYAN, GREEN, YELLOW, ORANGE, RED, PINK, WHITE, GREY, LGREY,
    DIFF_COLORS,
)


# ── primitives ────────────────────────────────────────────────────────────────

def _txt(surf, text, font, color, cx=None, x=None, y=0):
    s  = font.render(str(text), True, color)
    bx = cx - s.get_width() // 2 if cx is not None else x
    surf.blit(s, (bx, y))
    return s.get_width()


def _panel(surf, rect, fill=None, border=None, r=10):
    fill   = fill   or PANEL
    border = border or BORDER
    pygame.draw.rect(surf, fill,   rect, border_radius=r)
    pygame.draw.rect(surf, border, rect, 1, border_radius=r)


def _pbar(surf, x, y, w, h, frac, fg, bg=(28, 36, 60), r=5):
    bg_r = pygame.Rect(x, y, w, h)
    pygame.draw.rect(surf, bg, bg_r, border_radius=r)
    fw = max(0, int(w * min(frac, 1.0)))
    if fw:
        pygame.draw.rect(surf, fg, pygame.Rect(x, y, fw, h), border_radius=r)
    pygame.draw.rect(surf, BORDER, bg_r, 1, border_radius=r)


def _mini_spark(surf, x, y, w, h, vals, color):
    if len(vals) < 2:
        return
    mn, mx = min(vals) * 0.85, max(vals) * 1.15
    if mx == mn:
        mx = mn + 0.1
    pts = [
        (x + int(i / (len(vals) - 1) * w),
         y + h - int((v - mn) / (mx - mn) * h))
        for i, v in enumerate(vals)
    ]
    pygame.draw.lines(surf, color, False, pts, 1)
    pygame.draw.circle(surf, WHITE, pts[-1], 3)


def draw_grid(surf):
    for x in range(0, SCREEN_W, 55):
        pygame.draw.line(surf, (16, 20, 34), (x, 0), (x, SCREEN_H))
    for y in range(90, SCREEN_H, 55):
        pygame.draw.line(surf, (16, 20, 34), (0, y), (SCREEN_W, y))


# ── main hud ──────────────────────────────────────────────────────────────────

def draw_hud(surf, fonts, diff_mgr, score, combo, accuracy, elapsed, health, recent_rts):
    level  = diff_mgr.level
    params = diff_mgr.params
    col    = DIFF_COLORS[level]

    _panel(surf, pygame.Rect(0, 0, SCREEN_W, 90), fill=(12, 15, 25), border=BORDER, r=0)

    # score
    _txt(surf, f"{score:,}", fonts["hud"], CYAN, x=18, y=8)
    _txt(surf, "SCORE", fonts["tiny"], GREY, x=18, y=50)

    # level badge
    lx = 215
    pygame.draw.rect(surf, col, pygame.Rect(lx, 10, 115, 34), border_radius=8)
    _txt(surf, f"LVL {level}", fonts["fb"], (14, 16, 26), cx=lx + 57, y=16)
    short = params["label"].split("-")[1].strip() if "-" in params["label"] else params["label"]
    _txt(surf, short, fonts["tiny"], GREY, cx=lx + 57, y=50)

    # combo
    cx_c = lx + 145
    sc   = ORANGE if combo >= 5 else (WHITE if combo > 0 else GREY)
    _txt(surf, f"x{combo}", fonts["hud"], sc, x=cx_c, y=8)
    _txt(surf, "COMBO", fonts["tiny"], GREY, x=cx_c, y=50)

    # accuracy
    ax  = cx_c + 115
    ac  = GREEN if accuracy > 80 else (YELLOW if accuracy > 55 else ORANGE)
    _txt(surf, f"{accuracy:.0f}%", fonts["hud"], ac, x=ax, y=8)
    _txt(surf, "ACCURACY", fonts["tiny"], GREY, x=ax, y=50)

    # timer
    mins = int(elapsed) // 60
    secs = int(elapsed) % 60
    tx   = ax + 140
    _txt(surf, f"{mins:02d}:{secs:02d}", fonts["hud"], LGREY, x=tx, y=8)
    _txt(surf, "TIME", fonts["tiny"], GREY, x=tx, y=50)

    # health bar
    hbar_x = SCREEN_W - 325
    hbar_w = 300
    hp_col = GREEN if health > 60 else (YELLOW if health > 30 else RED)
    _txt(surf, "HP", fonts["tiny"], GREY, x=hbar_x, y=5)
    _pbar(surf, hbar_x, 22, hbar_w, 20, health / 100.0, hp_col, r=6)
    _txt(surf, f"{int(health)}%", fonts["tiny"], hp_col, x=hbar_x + hbar_w + 5, y=25)

    # reaction time sparkline
    rts_list = list(recent_rts)
    if len(rts_list) >= 3:
        _mini_spark(surf, hbar_x, 50, hbar_w, 32, rts_list[-12:], CYAN)
        _txt(surf, "reaction times (recent)", fonts["tiny"], (60, 75, 110), x=hbar_x, y=83)

    hint = fonts["tiny"].render("click the circles  |  esc to quit", True, (45, 58, 85))
    surf.blit(hint, (SCREEN_W // 2 - hint.get_width() // 2, SCREEN_H - 18))