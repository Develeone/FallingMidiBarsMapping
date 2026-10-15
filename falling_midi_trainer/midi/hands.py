"""Practice fingering for the bundled, single-track Avril 14th arrangement.

MIDI contains no hand metadata. These are phrase-specific performance choices,
not recovered author annotations. Keep every original note and its timing.
"""
from pathlib import Path
from falling_midi_trainer.midi.parsing import NoteEntry


def assign_hands(path: str, notes: list[NoteEntry]) -> dict[NoteEntry, str]:
    if Path(path).name.lower() != 'avril-14th-aphex-twin.mid':
        return {}
    result = {}
    for entry in notes:
        pitch, start, end, velocity = entry
        # Central phrase: C4/Bb3/Db4 are melody, above the bass arpeggios.
        split = 57 if 24.0 <= start < 48.0 else 64
        hand = 'Л' if pitch < split else 'П'
        # Pick-up melody into the following phrase.
        if pitch == 61 and abs(start - 48.0) < 0.03:
            hand = 'П'
        # The ending's rising accompaniment crosses the ordinary split.
        for onset, accompaniment in ((100.125, 65), (101.625, 68),
                                     (106.125, 65), (107.25, 68)):
            if pitch == accompaniment and abs(start - onset) < 0.03:
                hand = 'Л'
        result[entry] = hand
    return result
