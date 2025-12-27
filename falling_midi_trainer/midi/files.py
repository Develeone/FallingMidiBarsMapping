"""File discovery helpers."""

from __future__ import annotations

import os
from typing import List


def list_midi_files(folder: str) -> List[str]:
    """Return sorted list of MIDI files in *folder* (".mid" / ".midi")."""
    if not os.path.isdir(folder):
        return []

    midi_files = []
    for filename in sorted(os.listdir(folder)):
        if filename.lower().endswith((".mid", ".midi")):
            midi_files.append(os.path.join(folder, filename))
    return midi_files
