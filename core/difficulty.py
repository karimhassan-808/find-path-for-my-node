# core/difficulty.py
# dda engine — watches recent trial results and adjusts level up/down

from collections import deque
from core.constants import DIFFICULTY_LEVELS, DDA_WINDOW, IMPULSIVITY_VAR_THRESH


class DifficultyManager:
    def __init__(self):
        self.level           = 1
        self.recent_scores   = deque(maxlen=DDA_WINDOW)
        self.recent_variance = deque(maxlen=DDA_WINDOW)

    @property
    def params(self):
        return DIFFICULTY_LEVELS[self.level]

    def record(self, hit_score: str, motion_var: float):
        self.recent_scores.append(hit_score)
        self.recent_variance.append(motion_var)
        if len(self.recent_scores) == DDA_WINDOW:
            self._evaluate()

    def _evaluate(self):
        all_good  = all(s in ("Perfect", "Great", "Good") for s in self.recent_scores)
        low_impul = all(v < IMPULSIVITY_VAR_THRESH for v in self.recent_variance)
        all_miss  = all(s == "Miss" for s in self.recent_scores)

        if all_good and low_impul and self.level < 5:
            self.level += 1
            self._clear()
        elif all_miss and self.level > 1:
            self.level -= 1
            self._clear()

    def _clear(self):
        self.recent_scores.clear()
        self.recent_variance.clear()