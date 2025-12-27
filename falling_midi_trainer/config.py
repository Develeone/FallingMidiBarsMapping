"""Centralized configuration for the MIDI trainer."""

from __future__ import annotations

# File handling
MIDI_DIR = "midi"  # Folder with .mid/.midi files
MIDI_PATH = "song.mid"  # Fallback file if the folder is empty

# MIDI device selection
MIDI_INPUT_NAME_CONTAINS = ""  # First device if empty
MIDI_OUTPUT_NAME_CONTAINS = ""
VIRTUAL_OUT = True
VIRTUAL_OUT_NAME = "Python Trainer Out"

# Visual dimensions
NOTE_MIN, NOTE_MAX = 21, 108  # Piano range
WINDOW_WIDTH, WINDOW_HEIGHT = 1100, 650
FPS = 60
TOPBAR_HEIGHT = 40
KEYSTRIP_HEIGHT = 14
PIXELS_PER_SEC = 240.0

# Gameplay
HIT_WINDOW_SEC = 0.08
STRICT = False  # False = can press extra notes

# Audio synthesis
SAMPLE_RATE = 44100
TONE_DURATION_SEC = 1.0
TONE_VOLUME = 0.18

# Colors
BACKGROUND_COLOR = (15, 15, 18)
TOPBAR_BG = (25, 25, 28)
TOPBAR_BORDER = (45, 45, 50)

# Pitch-class color mapping (C D E F G A B) — fully saturated colors
PITCH_CLASS_COLORS = {
    0: (255, 0, 0),  # C - red
    2: (255, 128, 0),  # D - orange
    4: (255, 255, 0),  # E - yellow
    5: (0, 255, 0),  # F - green
    7: (0, 255, 255),  # G - cyan
    9: (0, 0, 255),  # A - blue
    11: (180, 0, 255),  # B - violet
}

# UI
FONT_SIZE = 22
