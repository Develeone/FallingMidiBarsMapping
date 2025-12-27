import math
import os
import struct
from collections import defaultdict

import mido
import pygame

# ----------------- CONFIG -----------------
MIDI_DIR = "midi"            # folder with .mid/.midi files
MIDI_PATH = "song.mid"       # fallback if MIDI_DIR empty / file missing

MIDI_INPUT_NAME_CONTAINS = ""  # "" = first device

# MIDI output to send what you play into FL Studio
# Windows tip: use loopMIDI and set VIRTUAL_OUT=False + MIDI_OUTPUT_NAME_CONTAINS to loopMIDI port.
MIDI_OUTPUT_NAME_CONTAINS = ""
VIRTUAL_OUT = True
VIRTUAL_OUT_NAME = "Python Trainer Out"

NOTE_MIN, NOTE_MAX = 21, 108  # piano range
W, H = 1100, 650
FPS = 60

PX_PER_SEC = 240.0
HIT_WINDOW_SEC = 0.08
STRICT = False  # False = can press extra notes

TOPBAR_H = 40
KEYSTRIP_H = 14

SAMPLE_RATE = 44100
TONE_SEC = 1.0
TONE_VOL = 0.18

# ----------------- MIDI FILE LIST -----------------

def list_midi_files(folder: str):
    out = []
    if os.path.isdir(folder):
        for fn in sorted(os.listdir(folder)):
            if fn.lower().endswith((".mid", ".midi")):
                out.append(os.path.join(folder, fn))
    return out

# ----------------- MIDI PARSE (TRACK-AWARE) -----------------

def build_tempo_map(mid: mido.MidiFile):
    """Return sorted tempo changes as (abs_tick, tempo_us_per_beat) with a default at tick 0."""
    tpq = mid.ticks_per_beat
    changes = [(0, 500000)]  # default 120 bpm

    # collect from all tracks (tempo usually in track 0)
    for tr in mid.tracks:
        abs_tick = 0
        for msg in tr:
            abs_tick += msg.time
            if msg.type == "set_tempo":
                changes.append((abs_tick, msg.tempo))

    # sort and dedupe keeping last tempo at same tick
    changes.sort(key=lambda x: x[0])
    dedup = []
    for t, tempo in changes:
        if dedup and dedup[-1][0] == t:
            dedup[-1] = (t, tempo)
        else:
            dedup.append((t, tempo))

    # precompute cumulative seconds at each change
    # map: (tick, tempo, sec_at_tick)
    out = []
    sec = 0.0
    last_tick, last_tempo = dedup[0]
    out.append((last_tick, last_tempo, 0.0))

    for tick, tempo in dedup[1:]:
        dt_ticks = tick - last_tick
        sec += mido.tick2second(dt_ticks, tpq, last_tempo)
        out.append((tick, tempo, sec))
        last_tick, last_tempo = tick, tempo

    return out


def ticks_to_seconds(abs_tick: int, tempo_map, tpq: int) -> float:
    """Convert absolute tick to seconds given tempo_map entries (tick, tempo, sec_at_tick)."""
    # find last tempo change <= abs_tick (linear is fine for small maps)
    idx = 0
    for i in range(len(tempo_map)):
        if tempo_map[i][0] <= abs_tick:
            idx = i
        else:
            break

    tick0, tempo0, sec0 = tempo_map[idx]
    return sec0 + mido.tick2second(abs_tick - tick0, tpq, tempo0)


def parse_notes(path: str, track_index: int | None = None):
    mid = mido.MidiFile(path)
    tpq = mid.ticks_per_beat
    tempo_map = build_tempo_map(mid)

    # choose track
    tracks = mid.tracks
    if track_index is None:
        # merge all tracks: easiest way is to parse each track separately and combine
        all_notes = []
        total_len = 0.0
        for ti in range(len(tracks)):
            notes_t, len_t = parse_notes(path, track_index=ti)
            all_notes.extend(notes_t)
            total_len = max(total_len, len_t)
        all_notes.sort(key=lambda x: x[1])
        return all_notes, total_len, mid

    if track_index < 0 or track_index >= len(tracks):
        raise ValueError("track_index out of range")

    tr = tracks[track_index]
    abs_tick = 0
    on = defaultdict(list)  # (ch, note) -> [(t_start_sec, vel), ...]
    notes = []              # (note, t_start_sec, t_end_sec, vel)

    for msg in tr:
        abs_tick += msg.time
        t = ticks_to_seconds(abs_tick, tempo_map, tpq)

        if msg.type == "note_on" and msg.velocity > 0:
            on[(getattr(msg, "channel", 0), msg.note)].append((t, msg.velocity))
        elif msg.type in ("note_off", "note_on") and (msg.type == "note_off" or getattr(msg, "velocity", 0) == 0):
            key = (getattr(msg, "channel", 0), msg.note)
            if on[key]:
                ts, vel = on[key].pop(0)
                notes.append((msg.note, ts, t, vel))

    notes.sort(key=lambda x: x[1])
    total_len = 0.0
    if notes:
        total_len = max(te for _, _, te, _ in notes)
    return notes, total_len, mid


def group_chords(notes, window=HIT_WINDOW_SEC):
    groups = []
    i = 0
    n = len(notes)
    while i < n:
        base_t = notes[i][1]
        chord = []
        j = i
        while j < n and abs(notes[j][1] - base_t) <= window:
            chord.append(notes[j])
            j += 1
        groups.append(chord)
        i = j
    return groups

# ----------------- MIDI IO -----------------

def pick_midi_input():
    names = mido.get_input_names()
    if not names:
        raise RuntimeError("No MIDI inputs found. Is your keyboard detected by OS as MIDI?")
    if MIDI_INPUT_NAME_CONTAINS:
        for name in names:
            if MIDI_INPUT_NAME_CONTAINS.lower() in name.lower():
                return name
    return names[0]


def pick_midi_output():
    names = mido.get_output_names()
    if not names and not VIRTUAL_OUT:
        raise RuntimeError("No MIDI outputs found (and VIRTUAL_OUT=False).")

    if MIDI_OUTPUT_NAME_CONTAINS:
        for name in names:
            if MIDI_OUTPUT_NAME_CONTAINS.lower() in name.lower():
                return name

    return names[0] if names else None

# ----------------- SIMPLE SINE TONE (LOOPED WHILE HELD) -----------------

def midi_to_hz(note: int) -> float:
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


def make_sine_tone(note: int, sec: float = TONE_SEC, vol: float = TONE_VOL):
    n_samples = int(SAMPLE_RATE * sec)
    freq = midi_to_hz(note)

    out = bytearray()
    for i in range(n_samples):
        t = i / SAMPLE_RATE
        s = math.sin(2.0 * math.pi * freq * t)
        val = int(32767 * vol * s)
        out += struct.pack('<h', val)

    return pygame.mixer.Sound(buffer=bytes(out))

# ----------------- UI HELPERS -----------------

def clamp(v, a, b):
    return a if v < a else b if v > b else v


def draw_topbar(screen, font, files, selected_idx, scroll_x, track_idx, track_count):
    # background
    pygame.draw.rect(screen, (25, 25, 28), pygame.Rect(0, 0, W, TOPBAR_H))
    pygame.draw.line(screen, (45, 45, 50), (0, TOPBAR_H - 1), (W, TOPBAR_H - 1), 1)

    # track selector (right side)
    sel_w = 220
    sel_x = W - sel_w - 10
    sel_y = 6
    sel_h = TOPBAR_H - 12

    pygame.draw.rect(screen, (35, 35, 40), pygame.Rect(sel_x, sel_y, sel_w, sel_h), border_radius=8)
    pygame.draw.rect(screen, (70, 70, 80), pygame.Rect(sel_x, sel_y, sel_w, sel_h), 1, border_radius=8)

    # arrows
    btn_w = 28
    left_btn = pygame.Rect(sel_x + 8, sel_y + 6, btn_w, sel_h - 12)
    right_btn = pygame.Rect(sel_x + sel_w - btn_w - 8, sel_y + 6, btn_w, sel_h - 12)
    pygame.draw.rect(screen, (55, 55, 65), left_btn, border_radius=6)
    pygame.draw.rect(screen, (55, 55, 65), right_btn, border_radius=6)

    screen.blit(font.render("<", True, (230, 230, 235)), (left_btn.x + 9, left_btn.y + 2))
    screen.blit(font.render(">", True, (230, 230, 235)), (right_btn.x + 9, right_btn.y + 2))

    label = f"Track: {track_idx + 1}/{track_count}" if track_count else "Track: -"
    screen.blit(font.render(label, True, (230, 230, 235)), (sel_x + 50, sel_y + 8))

    # file chips (scrollable)
    x = 10 - scroll_x
    chips = []  # (rect, index)

    # available width excludes track selector
    max_x = sel_x - 10

    for i, path in enumerate(files):
        name = os.path.basename(path)
        txt = font.render(name, True, (240, 240, 245))
        pad_x = 14
        w = txt.get_width() + pad_x * 2
        h = TOPBAR_H - 12
        r = pygame.Rect(x, 6, w, h)

        if r.right < 0:
            x += w + 8
            continue
        if r.left > max_x:
            break

        bg = (60, 60, 70) if i == selected_idx else (40, 40, 48)
        bd = (110, 110, 130) if i == selected_idx else (70, 70, 85)
        pygame.draw.rect(screen, bg, r, border_radius=10)
        pygame.draw.rect(screen, bd, r, 1, border_radius=10)
        screen.blit(txt, (r.x + pad_x, r.y + 6))

        chips.append((r, i))
        x += w + 8

    return chips, left_btn, right_btn

# ----------------- MAIN LOOP -----------------

def run():
    pygame.init()
    pygame.mixer.pre_init(SAMPLE_RATE, size=-16, channels=1, buffer=512)
    pygame.mixer.init()
    pygame.mixer.set_num_channels(64)

    screen = pygame.display.set_mode((W, H))
    clock = pygame.time.Clock()

    key_count = NOTE_MAX - NOTE_MIN + 1
    key_w = W / key_count

    pressed = set()
    tone_cache = {}
    note_channels = {}  # note -> pygame.mixer.Channel

    in_name = pick_midi_input()
    inport = mido.open_input(in_name)

    # MIDI OUT: forward what you play into a virtual/external MIDI port for FL Studio
    out_name = None
    outport = None
    try:
        if VIRTUAL_OUT:
            outport = mido.open_output(VIRTUAL_OUT_NAME, virtual=True)
            out_name = VIRTUAL_OUT_NAME
        else:
            out_name = pick_midi_output()
            outport = mido.open_output(out_name)
    except Exception:
        out_name = pick_midi_output()
        outport = mido.open_output(out_name) if out_name else None

    font = pygame.font.SysFont(None, 22)

    files = list_midi_files(MIDI_DIR)
    selected_file_idx = 0
    file_scroll_x = 0

    # state that depends on current midi/track
    current_path = None
    mid = None
    track_count = 0
    track_idx = 0
    chords = []
    total_len = 0.0

    def load_current():
        nonlocal current_path, mid, track_count, track_idx, chords, total_len
        nonlocal game_time, chord_idx, paused

        if files:
            current_path = files[selected_file_idx]
        else:
            current_path = MIDI_PATH

        notes, total_len2, mid2 = parse_notes(current_path, track_index=track_idx)
        chords2 = group_chords(notes)

        mid = mid2
        track_count = len(mid.tracks) if mid else 0
        total_len = total_len2
        chords[:] = chords2

        # reset play
        game_time = 0.0
        chord_idx = 0
        paused = False

    # initial track_count guess from fallback file, then load
    game_time = 0.0
    chord_idx = 0
    paused = False

    # try to load, clamp track index afterwards
    try:
        load_current()
    except Exception:
        # fallback: try MIDI_PATH if directory selection failed
        current_path = MIDI_PATH
        notes, total_len, mid = parse_notes(current_path, track_index=0)
        chords = group_chords(notes)
        track_count = len(mid.tracks) if mid else 0
        track_idx = 0

    # ensure track_idx in bounds
    if track_count:
        track_idx = clamp(track_idx, 0, track_count - 1)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        # --- MIDI input ---
        for msg in inport.iter_pending():
            # forward EVERYTHING to MIDI OUT (so FL can hear what you play)
            if outport is not None:
                try:
                    outport.send(msg)
                except Exception:
                    pass

            if msg.type == "note_on" and msg.velocity > 0:
                pressed.add(msg.note)

                # sound (looped tone while held)
                if msg.note not in note_channels:
                    if msg.note not in tone_cache:
                        tone_cache[msg.note] = make_sine_tone(msg.note)
                    ch = pygame.mixer.find_channel(True)
                    note_channels[msg.note] = ch
                    ch.play(tone_cache[msg.note], loops=-1, fade_ms=8)

            elif msg.type in ("note_off", "note_on") and (msg.type == "note_off" or getattr(msg, "velocity", 0) == 0):
                pressed.discard(msg.note)
                ch = note_channels.pop(msg.note, None)
                if ch is not None:
                    ch.fadeout(25)

        # --- window events ---
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False

            elif e.type == pygame.MOUSEWHEEL:
                # horizontal scroll for file list (shift-wheel behaviour)
                if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    file_scroll_x = max(0, file_scroll_x - int(e.y * 60))
                else:
                    file_scroll_x = max(0, file_scroll_x - int(e.x * 60))

            elif e.type == pygame.KEYDOWN:
                # quick track switching
                if e.key == pygame.K_LEFTBRACKET and track_count:
                    track_idx = clamp(track_idx - 1, 0, track_count - 1)
                    load_current()
                elif e.key == pygame.K_RIGHTBRACKET and track_count:
                    track_idx = clamp(track_idx + 1, 0, track_count - 1)
                    load_current()

            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                if my <= TOPBAR_H:
                    # click topbar items
                    # chips + track selector are computed during draw; we recompute quickly here
                    chips, left_btn, right_btn = draw_topbar(screen, font, files, selected_file_idx, file_scroll_x, track_idx, track_count)
                    for r, idx in chips:
                        if r.collidepoint(mx, my):
                            selected_file_idx = idx
                            # keep track_idx in bounds of new file
                            try:
                                # pre-read track_count
                                mid_tmp = mido.MidiFile(files[selected_file_idx])
                                track_count = len(mid_tmp.tracks)
                                track_idx = clamp(track_idx, 0, max(0, track_count - 1))
                            except Exception:
                                pass
                            load_current()
                            break

                    if left_btn.collidepoint(mx, my) and track_count:
                        track_idx = clamp(track_idx - 1, 0, track_count - 1)
                        load_current()
                    if right_btn.collidepoint(mx, my) and track_count:
                        track_idx = clamp(track_idx + 1, 0, track_count - 1)
                        load_current()

        # --- required chord logic ---
        if chord_idx < len(chords):
            cur = chords[chord_idx]
            req = {note for (note, ts, te, vel) in cur}
            req_t = cur[0][1]
        else:
            req = set()
            req_t = total_len

        # pause when reached next chord start
        if chord_idx < len(chords) and game_time >= req_t:
            if STRICT:
                ok = (pressed == req)
            else:
                ok = req.issubset(pressed)
            paused = not ok
            if ok:
                chord_idx += 1
        else:
            paused = False

        # advance only when not paused
        if not paused:
            game_time += dt

        # ----------------- DRAW -----------------
        screen.fill((15, 15, 18))

        # top bar
        chips, left_btn, right_btn = draw_topbar(screen, font, files, selected_file_idx, file_scroll_x, track_idx, track_count)

        view_start = game_time
        visible_h = H - KEYSTRIP_H - TOPBAR_H
        lookahead_sec = visible_h / PX_PER_SEC
        view_end = game_time + lookahead_sec

        # falling bars
        for chord in chords:
            chord_ts = chord[0][1]
            if chord_ts > view_end:
                break
            for note, ts, te, vel in chord:
                if te < view_start or ts > view_end:
                    continue

                draw_ts = max(ts, view_start)
                draw_te = min(te, view_end)

                x = (note - NOTE_MIN) * key_w

                # Falling top->bottom: top shows farther future, bottom shows "now"
                y_top = TOPBAR_H + (view_end - draw_te) * PX_PER_SEC
                y_bot = TOPBAR_H + (view_end - draw_ts) * PX_PER_SEC
                y = y_top
                h = max(2, y_bot - y_top)

                # pitch-class color mapping (C D E F G A B) — fully saturated colors
                pc = note % 12
                pc_colors = {
                    0:  (255, 0, 0),      # C  - red
                    2:  (255, 128, 0),    # D  - orange
                    4:  (255, 255, 0),    # E  - yellow
                    5:  (0, 255, 0),      # F  - green
                    7:  (0, 255, 255),    # G  - cyan
                    9:  (0, 0, 255),      # A  - blue
                    11: (180, 0, 255),    # B  - violet
                }
                color = pc_colors.get(pc, (200, 200, 200))

                # velocity -> bar width (not brightness)
                w = max(2, int((vel / 127) * key_w))
                x_off = (key_w - w) * 0.5

                pygame.draw.rect(screen, color, pygame.Rect(x + x_off, y, w - 1, h))

        # hit line (near bottom, above key strip)
        hit_y = (H - KEYSTRIP_H) - 2
        pygame.draw.line(screen, (255, 255, 255), (0, hit_y), (W, hit_y), 2)

        # bottom pressed keys strip (thin white glow)
        y0 = H - KEYSTRIP_H
        for note in pressed:
            if NOTE_MIN <= note <= NOTE_MAX:
                x = (note - NOTE_MIN) * key_w
                pygame.draw.rect(screen, (255, 255, 255), pygame.Rect(x, y0, key_w - 1, KEYSTRIP_H))

        # UI text
        status = "PAUSED (press chord)" if paused else "PLAYING"
        base = os.path.basename(current_path) if current_path else "-"
        txt = f"{status} | {base} | Track {track_idx + 1}/{track_count or 0} | MIDI IN: {in_name} | MIDI OUT: {out_name or 'None'}"
        screen.blit(font.render(txt, True, (220, 220, 220)), (12, TOPBAR_H + 10))

        if chord_idx < len(chords):
            need = sorted(list(req))
            screen.blit(font.render(f"Need: {need}", True, (220, 220, 220)), (12, TOPBAR_H + 34))

        pygame.display.flip()

        if total_len and game_time > total_len + 2:
            running = False

    inport.close()
    if outport is not None:
        outport.close()
    pygame.mixer.quit()
    pygame.quit()


if __name__ == "__main__":
    run()
