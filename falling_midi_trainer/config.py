"""Centralized configuration for the MIDI trainer."""

from __future__ import annotations

# File handling
MIDI_DIR = "midi"  # Folder with .mid/.midi files
MIDI_PATH = "song.mid"  # Fallback file if the folder is empty
STATE_PATH = ".trainer_state.json"

# MIDI device selection
MIDI_INPUT_NAME_CONTAINS = ""  # First device if empty
MIDI_OUTPUT_NAME_CONTAINS = "IAC Driver Bus 1"
VIRTUAL_OUT = False
VIRTUAL_OUT_NAME = "Python Trainer Out"

# Visual dimensions
NOTE_MIN, NOTE_MAX = 21, 108  # Piano range
WINDOW_WIDTH, WINDOW_HEIGHT = 1100, 650
FULLSCREEN = True
SAFE_MARGIN = 18
FPS = 60
TOPBAR_HEIGHT = 40
KEYSTRIP_HEIGHT = 14
PIXELS_PER_SEC = 240.0
KEYBOARD_ZOOM_MIN = 0.4
KEYBOARD_ZOOM_MAX = 3.0
KEYBOARD_ZOOM_STEP = 0.08
KEYBOARD_PAN_STEP = 24

# Gameplay
HIT_WINDOW_SEC = 0.08
STRICT = False  # False = can press extra notes

# Audio synthesis
SAMPLE_RATE = 44100
TONE_DURATION_SEC = 2.0
TONE_VOLUME = 0.2
REVERB_MIX = 0.35
REVERB_TIME = 0.85
REVERB_PREDELAY = 0.02

# Colors
BACKGROUND_COLOR_TOP = (9, 12, 18)
BACKGROUND_COLOR_BOTTOM = (18, 20, 28)
BACKGROUND_GRID = (30, 34, 45)
TOPBAR_BG = (22, 26, 33)
TOPBAR_BG_ACCENT = (36, 48, 66)
TOPBAR_BORDER = (70, 88, 118)
TOPBAR_GLOW = (60, 140, 255)

# Pitch-class color mapping (all 12 semitones)
PITCH_CLASS_COLORS = {
    0: (255, 0, 0),      # C
    1: (255, 64, 0),     # C#/Db
    2: (255, 128, 0),    # D
    3: (255, 192, 0),    # D#/Eb
    4: (255, 255, 0),    # E
    5: (0, 255, 0),      # F
    6: (0, 255, 128),    # F#/Gb
    7: (0, 255, 255),    # G
    8: (0, 128, 255),    # G#/Ab
    9: (0, 0, 255),      # A
    10: (96, 0, 255),    # A#/Bb
    11: (180, 0, 255),   # B
}
ACCIDENTAL_PITCH_CLASSES = {1, 3, 6, 8, 10}

# UI
FONT_SIZE = 22
HUD_COLOR = (225, 233, 246)
MUTED_TEXT = (165, 175, 189)
HIT_LINE_COLOR = (240, 248, 255)
NOTE_BORDER_COLOR = (10, 10, 14)
