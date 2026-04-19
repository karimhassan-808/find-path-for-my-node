# main.py
# architecture: pygame runs in a worker thread, matplotlib stays on main thread
# this is required on windows — Qt GUI must own the main thread

import math
import os
import shutil
import threading
import time
from datetime import datetime

import pygame

from core.constants import (
    SCREEN_W, SCREEN_H, FPS, BG_DARK,
    CYAN, WHITE, PINK, RED, GREEN, YELLOW, ORANGE,
    HP_GAIN, HP_LOSS_MISS, HIT_POINTS, SPAWN_INTERVAL,
)
from core.logger      import init_csv, log_trial, CSV_PATH
from core.shared_data import shared

from entities.particle   import burst, ring_burst
from entities.flash      import Flash
from entities.float_text import FloatText

from audio.synth  import AudioManager
from ui.hud       import draw_hud, draw_grid
from ui.screens   import draw_menu, draw_game_over
from ui.dashboard import run_dashboard

from utils import trail_variance, trail_velocity, spawn_circle, GameSession

SESSIONS_DIR = "savedSessions"


def _autosave_csv():
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    if not os.path.exists(CSV_PATH):
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst   = os.path.join(SESSIONS_DIR, f"session_{stamp}.csv")
    try:
        shutil.copy2(CSV_PATH, dst)
        print(f"session saved -> {dst}")
    except Exception as e:
        print(f"autosave failed: {e}")


def _pygame_worker():
    """entire pygame game loop runs here — off the main thread."""
    init_csv()
    pygame.init()
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

    screen     = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.RESIZABLE)
    fullscreen = False
    pygame.display.set_caption("neuro-osu  |  attention training")
    clock = pygame.time.Clock()
    pygame.mouse.set_visible(False)

    fonts = {
        "big":   pygame.font.SysFont("consolas", 52, bold=True),
        "hud":   pygame.font.SysFont("consolas", 28, bold=True),
        "small": pygame.font.SysFont("consolas", 18),
        "tiny":  pygame.font.SysFont("consolas", 14),
        "fb":    pygame.font.SysFont("consolas", 26, bold=True),
    }

    audio = AudioManager()
    audio.init()

    state   = "menu"
    pulse_t = 0.0
    gs      = GameSession()

    def start_game():
        gs.reset()
        shared.reset()

    def end_session():
        if gs.total_t > 0:
            _autosave_csv()

    def toggle_fullscreen():
        nonlocal fullscreen, screen
        fullscreen = not fullscreen
        if fullscreen:
            screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.RESIZABLE)

    running = True
    while running:
        dt      = clock.tick(FPS) / 1000.0
        pulse_t += dt
        mx, my  = pygame.mouse.get_pos()

        # ── menu ──────────────────────────────────────────────────────────────
        if state == "menu":
            play_rect = draw_menu(screen, fonts, pulse_t)
            pygame.draw.circle(screen, WHITE, (mx, my), 6)
            pygame.draw.circle(screen, CYAN,  (mx, my), 10, 1)
            pygame.display.flip()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:      running = False
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE: running = False
                    if ev.key == pygame.K_SPACE:  start_game(); state = "playing"
                    if ev.key == pygame.K_F11:    toggle_fullscreen()
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    if play_rect.collidepoint(ev.pos):
                        start_game(); state = "playing"
            continue

        # ── game over ─────────────────────────────────────────────────────────
        if state == "gameover":
            screen.fill(BG_DARK); draw_grid(screen)
            retry_rect, menu_rect = draw_game_over(
                screen, fonts, gs.score, gs.total_t, gs.total_h, gs.elapsed)
            pygame.draw.circle(screen, WHITE, (mx, my), 6)
            pygame.draw.circle(screen, CYAN,  (mx, my), 10, 1)
            pygame.display.flip()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:      running = False
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE: running = False
                    if ev.key == pygame.K_r:      start_game(); state = "playing"
                    if ev.key == pygame.K_m:      state = "menu"
                    if ev.key == pygame.K_F11:    toggle_fullscreen()
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    if retry_rect.collidepoint(ev.pos): start_game(); state = "playing"
                    elif menu_rect.collidepoint(ev.pos): state = "menu"
            continue

        # ── playing ───────────────────────────────────────────────────────────
        now_t = time.time()
        gs.prev_mouse  = (mx, my)
        gs.cursor_trail.append((mx, my, now_t))
        gs.mouse_vel = trail_velocity(gs.cursor_trail)

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                end_session(); running = False
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:  end_session(); running = False
                if ev.key == pygame.K_F11:     toggle_fullscreen()

            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                now     = time.time()
                hit_any = False
                for circ in gs.circles[:]:
                    if not circ.alive: continue
                    label, err = circ.hit_score(mx, my)
                    if label != "Miss":
                        circ.alive = False; circ.clicked = True
                        rt = (now - circ.spawn_t) if circ.first_move_t is None \
                             else (circ.first_move_t - circ.spawn_t)
                        rt = max(0.0, rt)

                        gs.combo  += 1
                        gs.score  += HIT_POINTS[label] * gs.combo
                        if gs.combo >= 5:
                            gs.score += int(HIT_POINTS[label] * 0.5)
                            gs.float_texts.append(
                                FloatText(circ.x, circ.y - 70, "x1.5!", ORANGE, 18))
                        gs.total_h += 1; gs.total_t += 1
                        gs.health   = min(100.0, gs.health + HP_GAIN[label])

                        mv = trail_variance(gs.cursor_trail)
                        log_trial(circ.id, rt, err, gs.mouse_vel,
                                  gs.diff_mgr.level, label, mv, "circle",
                                  current_combo=gs.combo,
                                  current_health=gs.health,
                                  current_score=gs.score)
                        gs.diff_mgr.record(label, mv)
                        gs.recent_rts.append(rt)

                        audio.play_hit()
                        c = {"Perfect": CYAN, "Great": GREEN, "Good": YELLOW}[label]
                        burst(gs.particles, circ.x, circ.y, c, 22)
                        ring_burst(gs.particles, circ.x, circ.y, WHITE, 10)
                        gs.float_texts.append(
                            FloatText(circ.x, circ.y - 40, label, c, 24))
                        hit_any = True
                        break

                if not hit_any:
                    gs.combo = 0
                    gs.flashes.append(Flash(PINK, 0.10))

        # first-move reaction time detection
        for circ in gs.circles:
            if circ.alive and circ.first_move_t is None:
                if math.hypot(mx - circ.x, my - circ.y) < circ.radius * 3 \
                        and gs.mouse_vel > 5:
                    circ.first_move_t = time.time()

        # expire missed circles → attention lapse
        for circ in gs.circles:
            if circ.alive and circ.age >= circ.lifetime:
                circ.alive = False; gs.combo = 0
                gs.total_t += 1; gs.health -= HP_LOSS_MISS
                audio.play_miss()
                gs.flashes.append(Flash(RED, 0.12))
                mv = trail_variance(gs.cursor_trail)
                log_trial(circ.id, circ.lifetime, circ.radius * 2, 0,
                          gs.diff_mgr.level, "Miss", mv, "circle",
                          current_combo=gs.combo,
                          current_health=gs.health,
                          current_score=gs.score)
                gs.diff_mgr.record("Miss", mv)
                gs.float_texts.append(FloatText(circ.x, circ.y - 20, "MISS", RED, 22))

        gs.circles[:] = [c for c in gs.circles if c.alive]

        if time.time() - gs.last_spawn >= SPAWN_INTERVAL:
            gs.last_spawn = time.time()
            sw, sh = screen.get_size()
            gs.circles.append(spawn_circle(gs.diff_mgr.params, sw, sh))

        gs.particles[:]   = [p for p in gs.particles   if p.update(dt)]
        gs.float_texts[:] = [f for f in gs.float_texts if f.update(dt)]
        gs.flashes[:]     = [f for f in gs.flashes     if f.update(dt)]

        if gs.health <= 0:
            gs.health = 0
            end_session()
            state = "gameover"
            continue

        # draw
        screen.fill(BG_DARK)
        draw_grid(screen)
        for circ in gs.circles:     circ.draw(screen)
        for p    in gs.particles:   p.draw(screen)
        for f    in gs.float_texts: f.draw(screen)
        for f    in gs.flashes:     f.draw(screen)

        trail_list = list(gs.cursor_trail)
        for i, (tx, ty, _t) in enumerate(trail_list):
            alpha = int(180 * i / max(len(trail_list), 1))
            r_sz  = max(1, 4 - i // 3)
            ts    = pygame.Surface((r_sz * 2, r_sz * 2), pygame.SRCALPHA)
            pygame.draw.circle(ts, (*CYAN, alpha), (r_sz, r_sz), r_sz)
            screen.blit(ts, (tx - r_sz, ty - r_sz))

        draw_hud(screen, fonts, gs.diff_mgr, gs.score, gs.combo,
                 gs.accuracy, gs.elapsed, gs.health, gs.recent_rts)

        pygame.draw.circle(screen, WHITE, (mx, my), 6)
        pygame.draw.circle(screen, CYAN,  (mx, my), 10, 1)
        pygame.display.flip()

    # pygame cleanup
    pygame.mouse.set_visible(True)
    pygame.quit()
    print(f"\ngame closed — trials: {gs.total_t} | "
          f"hits: {gs.total_h} | accuracy: {gs.accuracy:.1f}%")
    print("dashboard window remains open — close it when done.")


def main():
    # launch pygame in a worker thread
    game_thread = threading.Thread(target=_pygame_worker, daemon=True)
    game_thread.start()

    # run matplotlib dashboard on the main thread (Qt requires this on Windows)
    run_dashboard()

    # if user closes the dashboard before the game, wait for game to finish
    game_thread.join(timeout=2)


if __name__ == "__main__":
    main()