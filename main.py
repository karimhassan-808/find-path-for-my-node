# main.py
# entry point — event loop only, all logic delegated to modules

import math
import threading
import time
import pygame

from core.constants import (
    SCREEN_W, SCREEN_H, FPS, BG_DARK,
    CYAN, WHITE, PINK, RED, GREEN, YELLOW, ORANGE,
    HP_GAIN, HP_LOSS_MISS, HIT_POINTS, SPAWN_INTERVAL,
)
from core.logger   import init_csv, log_trial
from core.shared_data import shared

from entities.particle  import burst, ring_burst
from entities.flash     import Flash
from entities.float_text import FloatText

from audio.synth import AudioManager
from ui.hud      import draw_hud, draw_grid
from ui.screens  import draw_menu, draw_game_over
from ui.dashboard import clinical_dashboard, dashboard_stop

from utils import trail_variance, spawn_circle, GameSession


def main():
    init_csv()
    pygame.init()
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("neuro-osu  |  attention training")
    clock  = pygame.time.Clock()
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

    dash_thread = threading.Thread(target=clinical_dashboard, daemon=True)
    dash_thread.start()

    state   = "menu"
    pulse_t = 0.0
    gs      = GameSession()

    def start_game():
        gs.reset()
        shared.reset()

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
                if ev.type == pygame.QUIT: running = False
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE: running = False
                    if ev.key == pygame.K_SPACE:  start_game(); state = "playing"
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    if play_rect.collidepoint(ev.pos): start_game(); state = "playing"
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
                if ev.type == pygame.QUIT: running = False
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE: running = False
                    if ev.key == pygame.K_r: start_game(); state = "playing"
                    if ev.key == pygame.K_m: start_game(); state = "menu"
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    if retry_rect.collidepoint(ev.pos): start_game(); state = "playing"
                    elif menu_rect.collidepoint(ev.pos): start_game(); state = "menu"
            continue

        # ── playing ───────────────────────────────────────────────────────────
        # cursor velocity
        dx = mx - gs.prev_mouse[0]; dy = my - gs.prev_mouse[1]
        gs.mouse_vel   = math.hypot(dx, dy) / max(dt, 0.001)
        gs.prev_mouse  = (mx, my)
        gs.cursor_trail.append((mx, my))

        # events
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: running = False
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE: running = False

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

                        gs.combo   += 1
                        gs.score   += HIT_POINTS[label] * gs.combo
                        if gs.combo >= 5:
                            gs.score += int(HIT_POINTS[label] * 0.5)
                            gs.float_texts.append(FloatText(circ.x, circ.y - 70, "x1.5!", ORANGE, 18))
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
                        gs.float_texts.append(FloatText(circ.x, circ.y - 40, label, c, 24))
                        hit_any = True
                        break

                if not hit_any:
                    gs.combo = 0
                    gs.flashes.append(Flash(PINK, 0.10))

        # first-move reaction time detection
        for circ in gs.circles:
            if circ.alive and circ.first_move_t is None:
                if math.hypot(mx - circ.x, my - circ.y) < circ.radius * 3 and gs.mouse_vel > 5:
                    circ.first_move_t = time.time()

        # expire missed circles
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

        # spawn
        if time.time() - gs.last_spawn >= SPAWN_INTERVAL:
            gs.last_spawn = time.time()
            gs.circles.append(spawn_circle(gs.diff_mgr.params))

        # update fx
        gs.particles[:]   = [p for p in gs.particles   if p.update(dt)]
        gs.float_texts[:] = [f for f in gs.float_texts if f.update(dt)]
        gs.flashes[:]     = [f for f in gs.flashes     if f.update(dt)]

        if gs.health <= 0:
            gs.health = 0; state = "gameover"; continue

        # ── draw ──────────────────────────────────────────────────────────────
        screen.fill(BG_DARK)
        draw_grid(screen)

        for circ in gs.circles:    circ.draw(screen)
        for p    in gs.particles:  p.draw(screen)
        for f    in gs.float_texts: f.draw(screen)
        for f    in gs.flashes:    f.draw(screen)

        # cursor trail
        trail_list = list(gs.cursor_trail)
        for i, (tx, ty) in enumerate(trail_list):
            alpha = int(180 * i / max(len(trail_list), 1))
            r_sz  = max(1, 4 - i // 3)
            ts = pygame.Surface((r_sz * 2, r_sz * 2), pygame.SRCALPHA)
            pygame.draw.circle(ts, (*CYAN, alpha), (r_sz, r_sz), r_sz)
            screen.blit(ts, (tx - r_sz, ty - r_sz))

        draw_hud(screen, fonts, gs.diff_mgr, gs.score, gs.combo,
                 gs.accuracy, gs.elapsed, gs.health, gs.recent_rts)

        pygame.draw.circle(screen, WHITE, (mx, my), 6)
        pygame.draw.circle(screen, CYAN,  (mx, my), 10, 1)
        pygame.display.flip()

    # cleanup
    dashboard_stop.set()
    pygame.mouse.set_visible(True)
    pygame.quit()
    print(f"\nsession ended — data saved to patient_performance.csv")
    print(f"trials: {gs.total_t}  |  hits: {gs.total_h}  |  accuracy: {gs.accuracy:.1f}%")


if __name__ == "__main__":
    main()