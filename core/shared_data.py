# core/shared_data.py
# thread-safe store bridging the pygame loop and matplotlib dashboard

import threading
import time
from collections import deque

_MAXLEN = 500

class SharedData:
    def __init__(self):
        self.lock              = threading.Lock()
        self.trial_numbers     = deque(maxlen=_MAXLEN)
        self.reaction_times    = deque(maxlen=_MAXLEN)
        self.stabilities       = deque(maxlen=_MAXLEN)
        self.difficulties      = deque(maxlen=_MAXLEN)
        self.scores_binary     = deque(maxlen=_MAXLEN)
        self.score_labels      = deque(maxlen=_MAXLEN)
        self.velocities        = deque(maxlen=_MAXLEN)
        self.error_distances   = deque(maxlen=_MAXLEN)
        self.combo_at_trial    = deque(maxlen=_MAXLEN)
        self.health_at_trial   = deque(maxlen=_MAXLEN)
        self.cumulative_scores = deque(maxlen=_MAXLEN)
        self.total_trials      = 0
        self.total_hits        = 0
        self.current_diff      = 1
        self.session_start     = time.time()
        self.current_combo     = 0
        self.max_combo         = 0
        self.current_health    = 100.0
        self.current_score     = 0
        self.perfect_count     = 0
        self.great_count       = 0
        self.good_count        = 0
        self.miss_count        = 0
        self.attention_lapses  = 0   # missed targets = attention lapses (adhd metric)

    def reset(self):
        with self.lock:
            self.trial_numbers.clear()
            self.reaction_times.clear()
            self.stabilities.clear()
            self.difficulties.clear()
            self.scores_binary.clear()
            self.score_labels.clear()
            self.velocities.clear()
            self.error_distances.clear()
            self.combo_at_trial.clear()
            self.health_at_trial.clear()
            self.cumulative_scores.clear()
            self.total_trials    = 0
            self.total_hits      = 0
            self.current_diff    = 1
            self.current_combo   = 0
            self.max_combo       = 0
            self.current_health  = 100.0
            self.current_score   = 0
            self.perfect_count   = 0
            self.great_count     = 0
            self.good_count      = 0
            self.miss_count      = 0
            self.attention_lapses = 0
            self.session_start   = time.time()

    def snapshot(self):
        """returns a plain-dict copy — safe to read outside the lock."""
        with self.lock:
            return {
                "trials":          list(self.trial_numbers),
                "rts":             list(self.reaction_times),
                "stabs":           list(self.stabilities),
                "diffs":           list(self.difficulties),
                "scores_bin":      list(self.scores_binary),
                "labels":          list(self.score_labels),
                "velocities":      list(self.velocities),
                "errors":          list(self.error_distances),
                "combos":          list(self.combo_at_trial),
                "healths":         list(self.health_at_trial),
                "cum_scores":      list(self.cumulative_scores),
                "total_trials":    self.total_trials,
                "total_hits":      self.total_hits,
                "current_diff":    self.current_diff,
                "elapsed":         time.time() - self.session_start,
                "current_combo":   self.current_combo,
                "max_combo":       self.max_combo,
                "current_health":  self.current_health,
                "current_score":   self.current_score,
                "perfect":         self.perfect_count,
                "great":           self.great_count,
                "good":            self.good_count,
                "miss":            self.miss_count,
                "attention_lapses": self.attention_lapses,
                "reaction_times":  list(self.reaction_times),
                "stabilities":     list(self.stabilities),
            }

# module-level singleton — import this everywhere
shared = SharedData()