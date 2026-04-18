# audio/synth.py
# synthesizes all sounds at runtime — no asset files needed

import numpy as np
import pygame


def _tone(freq, dur, vol=0.35, wave="sine", attack=0.03, release=0.08):
    sr = 44100
    n  = int(sr * dur)
    t  = np.linspace(0, dur, n, False)
    w  = np.sin(2 * np.pi * freq * t) if wave == "sine" \
         else 2 * np.abs(2 * (t * freq - np.floor(t * freq + 0.5))) - 1
    env = np.ones(n)
    a   = min(int(sr * attack),  n // 4)
    r   = min(int(sr * release), n // 4)
    if a: env[:a]  = np.linspace(0, 1, a)
    if r: env[-r:] = np.linspace(1, 0, r)
    w = (w * env * vol * 32767).astype(np.int16)
    return pygame.sndarray.make_sound(np.column_stack([w, w]))


def _make_bgm(vol=0.06):
    # 70 bpm, gentler descending pentatonic — calmer for sustained attention sessions
    # high tempo / loud music increases arousal which can worsen adhd focus
    penta = [330, 294, 262, 247, 220, 247, 262, 294]
    bpm   = 70
    beat  = 60 / bpm / 1.1
    sr    = 44100
    total = int(sr * beat * len(penta) * 2)
    buf   = np.zeros(total)
    for rep in range(2):
        for i, freq in enumerate(penta):
            n    = int(sr * beat)
            t    = np.linspace(0, beat, n, False)
            note = np.sin(2 * np.pi * freq * t) * 0.7 + np.sin(2 * np.pi * freq * 2 * t) * 0.15
            fl   = n // 8
            note[:fl]  *= np.linspace(0, 1, fl)
            note[-fl:] *= np.linspace(1, 0, fl)
            start = (rep * len(penta) + i) * n
            buf[start:start + n] += note
    mx  = abs(buf).max()
    buf = (buf / (mx if mx else 1) * vol * 32767).astype(np.int16)
    return pygame.sndarray.make_sound(np.column_stack([buf, buf]))


class AudioManager:
    def __init__(self):
        self._hit  = None
        self._miss = None
        self._bgm  = None

    def init(self):
        """call after pygame.mixer.init()"""
        try:
            self._hit  = _tone(880, 0.09, 0.42)
            self._miss = _tone(200, 0.14, 0.28, "tri")
            self._bgm  = _make_bgm()
            self._bgm.play(-1)
        except Exception as e:
            print(f"audio init warning: {e}")

    def play_hit(self):
        if self._hit:  self._hit.play()

    def play_miss(self):
        if self._miss: self._miss.play()