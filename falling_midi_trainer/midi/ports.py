"""MIDI port selection utilities."""

from __future__ import annotations

import mido

from falling_midi_trainer import config


def pick_midi_input() -> str:
    names = mido.get_input_names()
    if not names:
        raise RuntimeError("No MIDI inputs found. Is your keyboard detected by OS as MIDI?")

    if config.MIDI_INPUT_NAME_CONTAINS:
        for name in names:
            if config.MIDI_INPUT_NAME_CONTAINS.lower() in name.lower():
                return name
    return names[0]


def pick_midi_output() -> str | None:
    names = mido.get_output_names()
    if not names and not config.VIRTUAL_OUT:
        raise RuntimeError("No MIDI outputs found (and VIRTUAL_OUT=False).")

    if config.MIDI_OUTPUT_NAME_CONTAINS:
        for name in names:
            if config.MIDI_OUTPUT_NAME_CONTAINS.lower() in name.lower():
                return name

    return names[0] if names else None
