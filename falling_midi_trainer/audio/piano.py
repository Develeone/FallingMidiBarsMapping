"""Piano-inspired tone synthesis with lightweight reverb."""

from __future__ import annotations

import math
import struct
from typing import Iterable

import pygame

from falling_midi_trainer import config


def midi_to_hz(note: int) -> float:
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


def _soft_clip(x: float) -> float:
    return math.tanh(x)


def _adsr_envelope(t: float, duration: float) -> float:
    attack = 0.008
    decay = 0.12
    sustain_level = 0.7
    release = min(0.25, duration * 0.25)

    if t < attack:
        return t / attack
    if t < attack + decay:
        return 1.0 - ((1.0 - sustain_level) * ((t - attack) / decay))
    if t < duration - release:
        return sustain_level
    if t < duration:
        return sustain_level * (1.0 - ((t - (duration - release)) / release))
    return 0.0


def _apply_reverb(dry: Iterable[float], mix: float, predelay: float, time: float) -> list[float]:
    dry_samples = list(dry)
    tail_length = int(config.SAMPLE_RATE * time)
    output = [0.0] * (len(dry_samples) + tail_length + 1)

    taps = [
        predelay,
        predelay + 0.019,
        predelay + 0.031,
        predelay + 0.047,
    ]
    for i, sample in enumerate(dry_samples):
        dry_val = sample * (1.0 - mix)
        output[i] += dry_val

        for idx, tap in enumerate(taps):
            gain = mix * (0.55 ** (idx + 1))
            delay_samples = int(tap * config.SAMPLE_RATE)
            target_idx = i + delay_samples
            if target_idx < len(output):
                output[target_idx] += sample * gain

    # Add a subtle feedback tail
    feedback = min(0.76, 0.55 + mix * 0.35)
    for i in range(1, len(output)):
        output[i] += output[i - 1] * feedback * (1.0 - (i / len(output)))

    return [_soft_clip(value) for value in output]


def make_piano_tone(
    note: int,
    sec: float = config.TONE_DURATION_SEC,
    vol: float = config.TONE_VOLUME,
    reverb_mix: float | None = None,
) -> pygame.mixer.Sound:
    """Generate a piano-like tone with harmonic layers and smooth reverb."""

    reverb_mix = config.REVERB_MIX if reverb_mix is None else float(reverb_mix)
    freq = midi_to_hz(note)
    n_samples = int(config.SAMPLE_RATE * sec)

    partials = [
        (1.0, 1.0),
        (2.01, 0.45),
        (3.98, 0.32),
        (5.01, 0.2),
        (6.9, 0.12),
    ]

    dry_wave: list[float] = []
    for i in range(n_samples):
        t = i / config.SAMPLE_RATE
        envelope = _adsr_envelope(t, sec)
        sample = 0.0
        for harmonic, weight in partials:
            sample += math.sin(2.0 * math.pi * freq * harmonic * t) * weight
        # Add a tiny bit of inharmonicity for brightness
        sample += 0.15 * math.sin(2.0 * math.pi * freq * 1.512 * t + 1.3)
        sample = _soft_clip(sample * 0.35)
        dry_wave.append(sample * envelope)

    wet_wave = _apply_reverb(dry_wave, mix=max(0.0, min(1.0, reverb_mix)), predelay=config.REVERB_PREDELAY, time=config.REVERB_TIME)

    data = bytearray()
    for sample in wet_wave:
        value = int(32767 * vol * sample)
        data += struct.pack("<h", max(-32768, min(32767, value)))

    return pygame.mixer.Sound(buffer=bytes(data))
