"""Game session state and loaders."""

from __future__ import annotations

import mido

from falling_midi_trainer import config
from falling_midi_trainer.midi.parsing import NoteEntry, group_chords, parse_notes
from falling_midi_trainer.utils.math_utils import clamp


class GameState:
    """Track currently loaded MIDI file, track selection and chord progression."""

    def __init__(self, files: list[str]):
        self.files = files
        self.selected_file_idx = 0
        self.file_scroll_x = 0

        self.current_path: str | None = None
        self.mid: mido.MidiFile | None = None
        self.track_count = 0
        self.track_idx = 0
        self.chords: list[list[NoteEntry]] = []
        self.total_length = 0.0

        self.game_time = 0.0
        self.chord_idx = 0
        self.paused = False

    def load_current(self) -> None:
        """Load the selected MIDI file and active track into the session state."""
        if self.files:
            self.current_path = self.files[self.selected_file_idx]
        else:
            self.current_path = config.MIDI_PATH

        mid_meta = mido.MidiFile(self.current_path)
        self.track_count = len(mid_meta.tracks)
        self.track_idx = int(clamp(self.track_idx, 0, max(0, self.track_count - 1)))

        notes, total_length, mid = parse_notes(self.current_path, track_index=self.track_idx)
        self.mid = mid
        self.total_length = total_length
        self.chords = group_chords(notes)

        self.game_time = 0.0
        self.chord_idx = 0
        self.paused = False

    def next_track(self) -> None:
        if self.track_count:
            self.track_idx = int(clamp(self.track_idx + 1, 0, self.track_count - 1))
            self.load_current()

    def previous_track(self) -> None:
        if self.track_count:
            self.track_idx = int(clamp(self.track_idx - 1, 0, self.track_count - 1))
            self.load_current()

    def select_file(self, index: int) -> None:
        self.selected_file_idx = index
        self.track_idx = int(clamp(self.track_idx, 0, max(0, self.track_count - 1)))
        self.load_current()
