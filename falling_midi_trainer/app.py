"""Main application loop for the MIDI trainer."""

from __future__ import annotations

import os
from typing import Dict, Set

import mido
import pygame
import threading

from falling_midi_trainer import config
from falling_midi_trainer.audio.piano import make_piano_tone
from falling_midi_trainer.game.state import GameState
from falling_midi_trainer.midi.files import list_midi_files
from falling_midi_trainer.midi.parsing import group_chords, parse_notes
from falling_midi_trainer.midi.ports import pick_midi_input, pick_midi_output
from falling_midi_trainer.ui.topbar import draw_topbar
from falling_midi_trainer.utils.math_utils import clamp


class TrainerApp:
    def __init__(self) -> None:
        pygame.mixer.pre_init(config.SAMPLE_RATE, size=-16, channels=1, buffer=512)
        pygame.init()
        pygame.mixer.init()
        pygame.mixer.set_num_channels(64)

        display_info = pygame.display.Info()
        target_size = (display_info.current_w, display_info.current_h)
        flags = pygame.FULLSCREEN | pygame.SCALED if config.FULLSCREEN else pygame.RESIZABLE
        self.screen = pygame.display.set_mode(target_size, flags)
        config.WINDOW_WIDTH, config.WINDOW_HEIGHT = self.screen.get_size()
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, config.FONT_SIZE)

        self.key_count = config.NOTE_MAX - config.NOTE_MIN + 1
        self.key_width = config.WINDOW_WIDTH / self.key_count

        self.pressed: Set[int] = set()
        self.reverb_mix = config.REVERB_MIX
        self.reverb_rect = pygame.Rect(0, 0, 0, 0)
        self.tone_cache: Dict[tuple[int, float], pygame.mixer.Sound] = {}
        self._tone_lock = threading.Lock()
        self._pending_tones: Set[tuple[int, float]] = set()
        self._start_warmup_thread()
        self.note_channels: Dict[int, pygame.mixer.Channel] = {}

        self.internal_enabled = True
        self.midi_out_enabled = True

        self.midi_in_name = pick_midi_input()
        self.inport = mido.open_input(self.midi_in_name)

        self.midi_out_name: str | None = None
        self.outport: mido.ports.BaseOutput | None = None
        self._setup_midi_out()
        self.midi_out_enabled = self.outport is not None

        files = list_midi_files(config.MIDI_DIR)
        self.state = GameState(files)
        self._initial_load()

    def _setup_midi_out(self) -> None:
        try:
            if config.VIRTUAL_OUT:
                self.outport = mido.open_output(config.VIRTUAL_OUT_NAME, virtual=True)
                self.midi_out_name = config.VIRTUAL_OUT_NAME
            else:
                self.midi_out_name = pick_midi_output()
                if self.midi_out_name:
                    self.outport = mido.open_output(self.midi_out_name)
        except Exception:
            self.midi_out_name = pick_midi_output()
            if self.midi_out_name:
                self.outport = mido.open_output(self.midi_out_name)

    def _initial_load(self) -> None:
        try:
            self.state.load_current()
        except Exception:
            notes, total_length, mid = parse_notes(config.MIDI_PATH, track_index=0)
            self.state.current_path = config.MIDI_PATH
            self.state.chords = group_chords(notes)
            self.state.total_length = total_length
            self.state.mid = mid
            self.state.track_count = len(mid.tracks) if mid else 0
            self.state.track_idx = 0
        if self.state.track_count:
            self.state.track_idx = int(clamp(self.state.track_idx, 0, self.state.track_count - 1))

    def run(self) -> None:
        running = True
        while running:
            dt = self.clock.tick(config.FPS) / 1000.0
            self._process_midi()
            running = self._process_events()
            self._update_game_time(dt)
            self._draw()
            if self.state.total_length and self.state.game_time > self.state.total_length + 2:
                running = False

        self._cleanup()

    def _process_midi(self) -> None:
        for msg in self.inport.iter_pending():
            if self.outport is not None and self.midi_out_enabled:
                try:
                    self.outport.send(msg)
                except Exception:
                    pass

            if msg.type == "note_on" and msg.velocity > 0:
                self.pressed.add(msg.note)
                if msg.note not in self.note_channels and self.internal_enabled:
                    channel = pygame.mixer.find_channel(True)
                    self.note_channels[msg.note] = channel
                    tone = self._get_tone(msg.note)
                    channel.play(tone, loops=0, fade_ms=8)
            elif msg.type in ("note_off", "note_on") and (msg.type == "note_off" or getattr(msg, "velocity", 0) == 0):
                self.pressed.discard(msg.note)
                channel = self.note_channels.pop(msg.note, None)
                if channel is not None:
                    channel.fadeout(25)

    def _process_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.MOUSEWHEEL:
                if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                    self.state.file_scroll_x = max(0, self.state.file_scroll_x - int(event.y * 60))
                else:
                    self.state.file_scroll_x = max(0, self.state.file_scroll_x - int(event.x * 60))
                if self.reverb_rect.collidepoint(pygame.mouse.get_pos()):
                    self._nudge_reverb(event.y * 0.02)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFTBRACKET and self.state.track_count:
                    self.state.previous_track()
                elif event.key == pygame.K_RIGHTBRACKET and self.state.track_count:
                    self.state.next_track()
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    self._nudge_reverb(-0.05)
                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    self._nudge_reverb(0.05)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._handle_topbar_click(event.pos):
                    continue
        return True

    def _handle_topbar_click(self, position: tuple[int, int]) -> bool:
        mx, my = position
        if my > config.TOPBAR_HEIGHT:
            return False

        chips, left_btn, right_btn, reverb_rect, internal_btn, midi_btn = draw_topbar(
            self.screen,
            self.font,
            self.state.files,
            self.state.selected_file_idx,
            self.state.file_scroll_x,
            self.state.track_idx,
            self.state.track_count,
            self.reverb_mix,
            self.internal_enabled,
            self.midi_out_enabled,
        )

        for rect, idx in chips:
            if rect.collidepoint(mx, my):
                self.state.selected_file_idx = idx
                try:
                    mid_tmp = mido.MidiFile(self.state.files[self.state.selected_file_idx])
                    self.state.track_count = len(mid_tmp.tracks)
                    self.state.track_idx = int(clamp(self.state.track_idx, 0, max(0, self.state.track_count - 1)))
                except Exception:
                    pass
                self.state.load_current()
                return True

        if left_btn.collidepoint(mx, my) and self.state.track_count:
            self.state.previous_track()
            return True
        if right_btn.collidepoint(mx, my) and self.state.track_count:
            self.state.next_track()
            return True
        if internal_btn.collidepoint(mx, my):
            self._toggle_internal_synth()
            return True
        if midi_btn.collidepoint(mx, my):
            self._toggle_midi_out()
            return True
        if reverb_rect.collidepoint(mx, my):
            rel = (mx - reverb_rect.x) / max(1, reverb_rect.w)
            self._set_reverb_mix(rel)
            return True
        return False

    def _nudge_reverb(self, delta: float) -> None:
        self._set_reverb_mix(self.reverb_mix + delta)

    def _set_reverb_mix(self, value: float) -> None:
        self.reverb_mix = clamp(value, 0.0, 1.0)
        with self._tone_lock:
            self.tone_cache.clear()
            self._pending_tones.clear()
        self._start_warmup_thread()

    def _toggle_internal_synth(self) -> None:
        self.internal_enabled = not self.internal_enabled
        if not self.internal_enabled:
            for channel in self.note_channels.values():
                channel.fadeout(25)
            self.note_channels.clear()

    def _toggle_midi_out(self) -> None:
        if self.outport is None:
            self.midi_out_enabled = False
            return
        self.midi_out_enabled = not self.midi_out_enabled

    def _update_game_time(self, dt: float) -> None:
        if self.state.chord_idx < len(self.state.chords):
            current_chord = self.state.chords[self.state.chord_idx]
            required_notes = {note for (note, _, _, _) in current_chord}
            required_time = current_chord[0][1]
        else:
            required_notes = set()
            required_time = self.state.total_length

        if self.state.chord_idx < len(self.state.chords) and self.state.game_time >= required_time:
            if config.STRICT:
                chord_ok = self.pressed == required_notes
            else:
                chord_ok = required_notes.issubset(self.pressed)
            self.state.paused = not chord_ok
            if chord_ok:
                self.state.chord_idx += 1
        else:
            self.state.paused = False

        if not self.state.paused:
            self.state.game_time += dt

    def _draw(self) -> None:
        self._draw_background()
        chips, left_btn, right_btn, reverb_rect, internal_btn, midi_btn = draw_topbar(
            self.screen,
            self.font,
            self.state.files,
            self.state.selected_file_idx,
            self.state.file_scroll_x,
            self.state.track_idx,
            self.state.track_count,
            self.reverb_mix,
            self.internal_enabled,
            self.midi_out_enabled,
        )
        self.reverb_rect = reverb_rect
        _ = (chips, left_btn, right_btn, internal_btn, midi_btn)

        view_start = self.state.game_time
        visible_height = config.WINDOW_HEIGHT - config.KEYSTRIP_HEIGHT - config.TOPBAR_HEIGHT
        lookahead_sec = visible_height / config.PIXELS_PER_SEC
        view_end = self.state.game_time + lookahead_sec

        for chord in self.state.chords:
            chord_start = chord[0][1]
            if chord_start > view_end:
                break
            for note, start, end, velocity in chord:
                if end < view_start or start > view_end:
                    continue

                draw_start = max(start, view_start)
                draw_end = min(end, view_end)
                x = (note - config.NOTE_MIN) * self.key_width

                y_top = config.TOPBAR_HEIGHT + (view_end - draw_end) * config.PIXELS_PER_SEC
                y_bottom = config.TOPBAR_HEIGHT + (view_end - draw_start) * config.PIXELS_PER_SEC
                height = max(2, y_bottom - y_top)

                color = config.PITCH_CLASS_COLORS.get(note % 12, (200, 200, 200))
                width = max(2, int((velocity / 127) * self.key_width))
                x_offset = (self.key_width - width) * 0.5

                note_rect = pygame.Rect(x + x_offset, y_top, width - 1, height)
                pygame.draw.rect(self.screen, color, note_rect, border_radius=6)
                pygame.draw.rect(self.screen, config.NOTE_BORDER_COLOR, note_rect, 1, border_radius=6)

        hit_line_y = (config.WINDOW_HEIGHT - config.KEYSTRIP_HEIGHT) - 2
        pygame.draw.line(
            self.screen,
            config.HIT_LINE_COLOR,
            (config.SAFE_MARGIN, hit_line_y),
            (config.WINDOW_WIDTH - config.SAFE_MARGIN, hit_line_y),
            3,
        )

        key_strip_y = config.WINDOW_HEIGHT - config.KEYSTRIP_HEIGHT
        for note in self.pressed:
            if config.NOTE_MIN <= note <= config.NOTE_MAX:
                x = (note - config.NOTE_MIN) * self.key_width
                pygame.draw.rect(
                    self.screen,
                    (235, 244, 255),
                    pygame.Rect(x + 1, key_strip_y + 1, self.key_width - 3, config.KEYSTRIP_HEIGHT - 2),
                    border_radius=3,
                )

        status = "PAUSED (press chord)" if self.state.paused else "PLAYING"
        base_name = os.path.basename(self.state.current_path) if self.state.current_path else "-"
        info_text = (
            f"{status} • {base_name} • Track {self.state.track_idx + 1}/{self.state.track_count or 0} • "
            f"MIDI IN: {self.midi_in_name} • "
            f"Internal: {'On' if self.internal_enabled else 'Off'} • "
            f"MIDI OUT: {self.midi_out_name or 'None'} ({'On' if self.midi_out_enabled and self.outport else 'Off'})"
        )
        self.screen.blit(self.font.render(info_text, True, config.HUD_COLOR), (16, config.TOPBAR_HEIGHT + 12))

        if self.state.chord_idx < len(self.state.chords):
            required_notes = sorted({note for (note, _, _, _) in self.state.chords[self.state.chord_idx]})
            self.screen.blit(
                self.font.render(f"Next chord: {required_notes}", True, config.MUTED_TEXT),
                (16, config.TOPBAR_HEIGHT + 38),
            )

        self.screen.blit(
            self.font.render(
                f"Reverb: {int(self.reverb_mix * 100)}%  (scroll or +/-)", True, (180, 205, 232)
            ),
            (config.WINDOW_WIDTH - 360, config.WINDOW_HEIGHT - config.KEYSTRIP_HEIGHT - 34),
        )

        hint_text = "Fullscreen experience • Click files, scroll to pan, +/- to shape the hall"
        hint_render = self.font.render(hint_text, True, (120, 138, 158))
        self.screen.blit(hint_render, (16, config.WINDOW_HEIGHT - config.KEYSTRIP_HEIGHT - 32))

        pygame.display.flip()

    def _draw_background(self) -> None:
        top = pygame.Color(*config.BACKGROUND_COLOR_TOP)
        bottom = pygame.Color(*config.BACKGROUND_COLOR_BOTTOM)
        for y in range(config.WINDOW_HEIGHT):
            lerp = y / max(1, config.WINDOW_HEIGHT - 1)
            r = int(top.r + (bottom.r - top.r) * lerp)
            g = int(top.g + (bottom.g - top.g) * lerp)
            b = int(top.b + (bottom.b - top.b) * lerp)
            pygame.draw.line(self.screen, (r, g, b), (0, y), (config.WINDOW_WIDTH, y))

        spacing = max(42, int(self.key_width * 1.5))
        grid_color = config.BACKGROUND_GRID
        for x in range(0, config.WINDOW_WIDTH, spacing):
            pygame.draw.line(self.screen, grid_color, (x, 0), (x, config.WINDOW_HEIGHT))
        for y in range(config.TOPBAR_HEIGHT + 20, config.WINDOW_HEIGHT, spacing):
            pygame.draw.line(self.screen, grid_color, (0, y), (config.WINDOW_WIDTH, y))

    def _cleanup(self) -> None:
        self.inport.close()
        if self.outport is not None:
            self.outport.close()
        pygame.mixer.quit()
        pygame.quit()

    def _start_warmup_thread(self) -> None:
        threading.Thread(target=self._warmup_tones, daemon=True).start()

    def _warmup_tones(self) -> None:
        tone_key_mix = round(self.reverb_mix, 2)
        center = (config.NOTE_MIN + config.NOTE_MAX) // 2
        notes = sorted(range(config.NOTE_MIN, config.NOTE_MAX + 1), key=lambda n: abs(n - center))
        for note in notes:
            key = (note, tone_key_mix)
            with self._tone_lock:
                if key in self.tone_cache or key in self._pending_tones:
                    continue
                self._pending_tones.add(key)
            try:
                tone = make_piano_tone(note, reverb_mix=self.reverb_mix)
            except Exception:
                with self._tone_lock:
                    self._pending_tones.discard(key)
                continue
            with self._tone_lock:
                if round(self.reverb_mix, 2) == tone_key_mix:
                    self.tone_cache[key] = tone
                self._pending_tones.discard(key)

    def _get_tone(self, note: int) -> pygame.mixer.Sound:
        tone_key = (note, round(self.reverb_mix, 2))
        with self._tone_lock:
            if tone_key in self.tone_cache:
                return self.tone_cache[tone_key]

        tone = make_piano_tone(note, reverb_mix=tone_key[1])
        with self._tone_lock:
            self.tone_cache[tone_key] = tone
        return tone


if __name__ == "__main__":
    TrainerApp().run()


def main() -> None:
    """Console entrypoint for the trainer."""
    TrainerApp().run()
