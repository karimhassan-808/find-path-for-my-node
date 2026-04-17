# core/logger.py
# handles csv init and per-trial logging — also pushes data into shared store

import csv
import os
import numpy as np
from datetime import datetime

from core.constants import CSV_PATH, CSV_COLUMNS, STABILITY_VARIANCE_CAP
from core.shared_data import shared


def init_csv():
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, "w", newline="") as f:
            csv.writer(f).writerow(CSV_COLUMNS)


def log_trial(
    target_id, reaction_time, error_dist, velocity,
    difficulty, hit_score, motion_var, target_type,
    current_combo=0, current_health=100.0, current_score=0,
):
    # attention_lapse = 1 if the target was missed (focus failure)
    lapse = 1 if hit_score == "Miss" else 0

    row = [
        datetime.now().isoformat(timespec="milliseconds"),
        target_id,
        f"{reaction_time:.4f}",
        f"{error_dist:.2f}",
        f"{velocity:.2f}",
        difficulty,
        hit_score,
        f"{motion_var:.4f}",
        target_type,
        lapse,
    ]
    with open(CSV_PATH, "a", newline="") as f:
        csv.writer(f).writerow(row)

    stability = max(0.0, 1.0 - min(motion_var / STABILITY_VARIANCE_CAP, 1.0))

    with shared.lock:
        shared.total_trials += 1
        shared.trial_numbers.append(shared.total_trials)
        shared.reaction_times.append(reaction_time)
        shared.stabilities.append(stability)
        shared.difficulties.append(difficulty)
        shared.velocities.append(velocity)
        shared.error_distances.append(error_dist)
        shared.combo_at_trial.append(current_combo)
        shared.health_at_trial.append(current_health)
        shared.current_score   = current_score
        shared.cumulative_scores.append(current_score)
        shared.current_diff    = difficulty
        shared.current_combo   = current_combo
        shared.current_health  = current_health
        shared.score_labels.append(hit_score)

        if hit_score != "Miss":
            shared.total_hits += 1
            shared.scores_binary.append(1)
            shared.max_combo = max(shared.max_combo, current_combo)
        else:
            shared.scores_binary.append(0)
            shared.attention_lapses += 1

        if   hit_score == "Perfect": shared.perfect_count += 1
        elif hit_score == "Great":   shared.great_count   += 1
        elif hit_score == "Good":    shared.good_count    += 1
        elif hit_score == "Miss":    shared.miss_count    += 1