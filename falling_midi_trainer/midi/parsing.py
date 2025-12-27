"""MIDI parsing helpers: tempo map, tick-to-second conversion, chord grouping."""

from __future__ import annotations

import mido
from collections import defaultdict
from typing import List, Tuple

from falling_midi_trainer import config

TempoMapEntry = Tuple[int, int, float]
NoteEntry = Tuple[int, float, float, int]


def build_tempo_map(mid: mido.MidiFile) -> List[TempoMapEntry]:
    """Return sorted tempo changes as (abs_tick, tempo_us_per_beat, sec_at_tick)."""
    tpq = mid.ticks_per_beat
    changes: list[tuple[int, int]] = [(0, 500_000)]  # default 120 bpm

    for track in mid.tracks:
        abs_tick = 0
        for msg in track:
            abs_tick += msg.time
            if msg.type == "set_tempo":
                changes.append((abs_tick, msg.tempo))

    changes.sort(key=lambda item: item[0])

    dedup: list[tuple[int, int]] = []
    for tick, tempo in changes:
        if dedup and dedup[-1][0] == tick:
            dedup[-1] = (tick, tempo)
        else:
            dedup.append((tick, tempo))

    tempo_map: list[TempoMapEntry] = []
    cumulative_seconds = 0.0
    last_tick, last_tempo = dedup[0]
    tempo_map.append((last_tick, last_tempo, cumulative_seconds))

    for tick, tempo in dedup[1:]:
        dt_ticks = tick - last_tick
        cumulative_seconds += mido.tick2second(dt_ticks, tpq, last_tempo)
        tempo_map.append((tick, tempo, cumulative_seconds))
        last_tick, last_tempo = tick, tempo

    return tempo_map


def ticks_to_seconds(abs_tick: int, tempo_map: list[TempoMapEntry], tpq: int) -> float:
    """Convert *abs_tick* to seconds based on the provided tempo map."""
    index = 0
    for i, (tick, _, _) in enumerate(tempo_map):
        if tick <= abs_tick:
            index = i
        else:
            break

    tick0, tempo0, sec0 = tempo_map[index]
    return sec0 + mido.tick2second(abs_tick - tick0, tpq, tempo0)


def parse_notes(path: str, track_index: int | None = None) -> tuple[list[NoteEntry], float, mido.MidiFile]:
    mid = mido.MidiFile(path)
    tpq = mid.ticks_per_beat
    tempo_map = build_tempo_map(mid)

    tracks = mid.tracks
    if track_index is None:
        all_notes: list[NoteEntry] = []
        total_length = 0.0
        for idx in range(len(tracks)):
            track_notes, track_length, _ = parse_notes(path, track_index=idx)
            all_notes.extend(track_notes)
            total_length = max(total_length, track_length)
        all_notes.sort(key=lambda item: item[1])
        return all_notes, total_length, mid

    if track_index < 0 or track_index >= len(tracks):
        raise ValueError("track_index out of range")

    track = tracks[track_index]
    abs_tick = 0
    note_on_events: defaultdict[tuple[int, int], list[tuple[float, int]]] = defaultdict(list)
    notes: list[NoteEntry] = []

    for msg in track:
        abs_tick += msg.time
        current_time = ticks_to_seconds(abs_tick, tempo_map, tpq)

        if msg.type == "note_on" and msg.velocity > 0:
            note_on_events[(getattr(msg, "channel", 0), msg.note)].append((current_time, msg.velocity))
        elif msg.type in ("note_off", "note_on") and (msg.type == "note_off" or getattr(msg, "velocity", 0) == 0):
            key = (getattr(msg, "channel", 0), msg.note)
            if note_on_events[key]:
                start_time, velocity = note_on_events[key].pop(0)
                notes.append((msg.note, start_time, current_time, velocity))

    notes.sort(key=lambda item: item[1])
    total_length = max((end for _, _, end, _ in notes), default=0.0)
    return notes, total_length, mid


def group_chords(notes: list[NoteEntry], window: float = config.HIT_WINDOW_SEC) -> list[list[NoteEntry]]:
    chords: list[list[NoteEntry]] = []
    index = 0
    while index < len(notes):
        base_time = notes[index][1]
        chord: list[NoteEntry] = []
        cursor = index
        while cursor < len(notes) and abs(notes[cursor][1] - base_time) <= window:
            chord.append(notes[cursor])
            cursor += 1
        chords.append(chord)
        index = cursor
    return chords
