"""Lightweight sine-tone synthesis for feedback."""

from __future__ import annotations

import math
import struct

import pygame

from falling_midi_trainer import config


def midi_to_hz(note: int) -> float:
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


def make_sine_tone(note: int, sec: float = config.TONE_DURATION_SEC, vol: float = config.TONE_VOLUME) -> pygame.mixer.Sound:
    n_samples = int(config.SAMPLE_RATE * sec)
    freq = midi_to_hz(note)

    data = bytearray()
    for i in range(n_samples):
        t = i / config.SAMPLE_RATE
        sample = math.sin(2.0 * math.pi * freq * t)
        value = int(32767 * vol * sample)
        data += struct.pack("<h", value)

    return pygame.mixer.Sound(buffer=bytes(data))
