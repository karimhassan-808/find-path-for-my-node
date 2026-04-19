# NEURO-OSU — Adaptive Kinetic Path-Finder
### A Serious Game for Motor Recovery & Cognitive Training (e.g. ADHD patients)

---

## Quick Start

```bash
# 1. Install dependencies
pip install pygame matplotlib

# 2. Run the game
python neuro_osu.py
```

> **Requirements:** Python 3.9+, `pygame`, `matplotlib` (TkAgg backend — ships with most distros)

---

## Project Description

### Overview
Neuro-Osu is a neon, rhythm-inspired focus game where glowing targets bloom and fade
across the screen. The goal is simple: stay calm, move with purpose, and tap each
circle before it disappears. As you find your groove, the game quietly adapts to keep
things exciting without becoming overwhelming.

### What You Do
- Track glowing circles as they appear and fade.
- Click quickly but precisely to keep your streak alive.
- Ride the adaptive pace as the game learns your rhythm.

If you want the full technical details and data definitions, scroll down to the
data and metrics sections.

### Screenshots
- Gameplay (HUD + targets)
  - `docs/screenshots/gameplay.png`
- Dashboard (clinical view)
  - `docs/screenshots/dashboard.png`
- Game Over summary
  - `docs/screenshots/game_over.png`

### Demo
- Short gameplay clip
  - `docs/demo/neuro-osu-demo.mp4`

### Data Captured → `patient_performance.csv`

| Column | Type | Description |
|---|---|---|
| `Timestamp` | ISO-8601 | Wall-clock time of event |
| `TargetID` | int | Unique target identifier |
| `ReactionTime` | float (s) | Δ between spawn and first directed cursor move |
| `ErrorDistance` | float (px) | Cursor distance from ideal target centre or path |
| `Velocity` | float (px/s) | Average cursor speed over the recent trail window |
| `CurrentDifficulty` | int 1–5 | Active difficulty level |
| `HitScore` | str | Perfect / Great / Good / Miss |
| `MotionVariance` | float | X,Y variance of cursor trail (tremor proxy) |
| `TargetType` | str | `circle` or `slider` |

### Output
- **Pygame window** — patient-facing gameplay (1280×720, 60 fps)
- **Matplotlib dashboard (can be exported as png)** — doctor-facing, updates every 800 ms; shows
  Reaction Time trend, Stability Ratio bars, Difficulty gauge, and Session KPIs
- **CSV export** — every interaction appended in real time

---

## Adaptive Difficulty System

The **Stability Ratio** is defined as:

```
Stability = 1 - min(MotionVariance / 500, 1.0)
```

**Escalation:** If 3 consecutive trials are all `Perfect/Great/Good` **and**
`MotionVariance < 120` → level increases (smaller targets, faster fade, narrower paths).

**De-escalation:** If 3 consecutive trials are all `Miss` → level decreases.

| Level | Circle Radius | Lifetime | Path Width |
|---|---|---|---|
| 1 – Introductory | 55 px | 3.0 s | 28 px |
| 2 – Standard     | 44 px | 2.5 s | 22 px |
| 3 – Advanced     | 34 px | 2.0 s | 16 px |
| 4 – Expert       | 26 px | 1.5 s | 11 px |
| 5 – Elite        | 18 px | 1.1 s |  7 px |

---

## Keyboard Controls

| Key | Action |
|---|---|
| `SPACE` | Start session from splash |
| `ESC`   | End session and save CSV |

---

## Architecture

```
neuro_osu/
├── main.py              # ~100 lines, event loop only
├── utils.py             # trail_variance, spawn_circle, GameSession
├── core/
│   ├── constants.py     # all magic numbers
│   ├── shared_data.py   # SharedData + .reset() + .snapshot()
│   ├── difficulty.py    # DifficultyManager
│   └── logger.py        # init_csv, log_trial
├── entities/
│   ├── hit_circle.py    # HitCircle (id injected, no class counter)
│   ├── particle.py      # Particle, burst, ring_burst
│   ├── flash.py         # Flash
│   └── float_text.py    # FloatText
├── audio/
│   └── synth.py         # AudioManager
└── ui/
    ├── hud.py           # draw_hud + primitives
    ├── screens.py       # draw_menu, draw_game_over
    └── dashboard.py     # clinical_dashboard thread
```

---

## Clinical Notes
- This project is scoped for attention and impulse-control training contexts (e.g. ADHD).
- The app can help track focus, response speed, and consistency over time,
  giving a simple progress snapshot across sessions.
- `ReactionTime` is measured as the delta from target spawn to the moment
  the cursor first moves toward the target (within 3× radius, velocity > 5 px/s),
  capturing *true* reaction latency rather than click time.
- The CSV is append-only across sessions; filter by `Timestamp` date to
  isolate individual sessions.