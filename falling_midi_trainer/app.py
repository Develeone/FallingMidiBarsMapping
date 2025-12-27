"""Main application loop for the MIDI trainer."""

from __future__ import annotations

import os
from typing import Dict, Set

import mido
import pygame

from falling_midi_trainer import config
from falling_midi_trainer.audio.sine import make_sine_tone
from falling_midi_trainer.game.state import GameState
from falling_midi_trainer.midi.files import list_midi_files
from falling_midi_trainer.midi.parsing import group_chords, parse_notes
from falling_midi_trainer.midi.ports import pick_midi_input, pick_midi_output
from falling_midi_trainer.ui.topbar import draw_topbar
from falling_midi_trainer.utils.math_utils import clamp


class TrainerApp:
    def __init__(self) -> None:
        pygame.init()
        pygame.mixer.pre_init(config.SAMPLE_RATE, size=-16, channels=1, buffer=512)
        pygame.mixer.init()
        pygame.mixer.set_num_channels(64)

        self.screen = pygame.display.set_mode((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, config.FONT_SIZE)

        self.key_count = config.NOTE_MAX - config.NOTE_MIN + 1
        self.key_width = config.WINDOW_WIDTH / self.key_count

        self.pressed: Set[int] = set()
        self.tone_cache: Dict[int, pygame.mixer.Sound] = {}
        self.note_channels: Dict[int, pygame.mixer.Channel] = {}

        self.midi_in_name = pick_midi_input()
        self.inport = mido.open_input(self.midi_in_name)

        self.midi_out_name: str | None = None
        self.outport: mido.ports.BaseOutput | None = None
        self._setup_midi_out()

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
            if self.outport is not None:
                try:
                    self.outport.send(msg)
                except Exception:
                    pass

            if msg.type == "note_on" and msg.velocity > 0:
                self.pressed.add(msg.note)
                if msg.note not in self.note_channels:
                    if msg.note not in self.tone_cache:
                        self.tone_cache[msg.note] = make_sine_tone(msg.note)
                    channel = pygame.mixer.find_channel(True)
                    self.note_channels[msg.note] = channel
                    channel.play(self.tone_cache[msg.note], loops=-1, fade_ms=8)
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
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFTBRACKET and self.state.track_count:
                    self.state.previous_track()
                elif event.key == pygame.K_RIGHTBRACKET and self.state.track_count:
                    self.state.next_track()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._handle_topbar_click(event.pos):
                    continue
        return True

    def _handle_topbar_click(self, position: tuple[int, int]) -> bool:
        mx, my = position
        if my > config.TOPBAR_HEIGHT:
            return False

        chips, left_btn, right_btn = draw_topbar(
            self.screen,
            self.font,
            self.state.files,
            self.state.selected_file_idx,
            self.state.file_scroll_x,
            self.state.track_idx,
            self.state.track_count,
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
        return False

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
        self.screen.fill(config.BACKGROUND_COLOR)
        chips, left_btn, right_btn = draw_topbar(
            self.screen,
            self.font,
            self.state.files,
            self.state.selected_file_idx,
            self.state.file_scroll_x,
            self.state.track_idx,
            self.state.track_count,
        )
        _ = (chips, left_btn, right_btn)  # appease linters for unused variables when drawing only

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

                pygame.draw.rect(self.screen, color, pygame.Rect(x + x_offset, y_top, width - 1, height))

        hit_line_y = (config.WINDOW_HEIGHT - config.KEYSTRIP_HEIGHT) - 2
        pygame.draw.line(self.screen, (255, 255, 255), (0, hit_line_y), (config.WINDOW_WIDTH, hit_line_y), 2)

        key_strip_y = config.WINDOW_HEIGHT - config.KEYSTRIP_HEIGHT
        for note in self.pressed:
            if config.NOTE_MIN <= note <= config.NOTE_MAX:
                x = (note - config.NOTE_MIN) * self.key_width
                pygame.draw.rect(
                    self.screen, (255, 255, 255), pygame.Rect(x, key_strip_y, self.key_width - 1, config.KEYSTRIP_HEIGHT)
                )

        status = "PAUSED (press chord)" if self.state.paused else "PLAYING"
        base_name = os.path.basename(self.state.current_path) if self.state.current_path else "-"
        info_text = (
            f"{status} | {base_name} | Track {self.state.track_idx + 1}/{self.state.track_count or 0} | "
            f"MIDI IN: {self.midi_in_name} | MIDI OUT: {self.midi_out_name or 'None'}"
        )
        self.screen.blit(self.font.render(info_text, True, (220, 220, 220)), (12, config.TOPBAR_HEIGHT + 10))

        if self.state.chord_idx < len(self.state.chords):
            required_notes = sorted({note for (note, _, _, _) in self.state.chords[self.state.chord_idx]})
            self.screen.blit(self.font.render(f"Need: {required_notes}", True, (220, 220, 220)), (12, config.TOPBAR_HEIGHT + 34))

        pygame.display.flip()

    def _cleanup(self) -> None:
        self.inport.close()
        if self.outport is not None:
            self.outport.close()
        pygame.mixer.quit()
        pygame.quit()


if __name__ == "__main__":
    TrainerApp().run()


def main() -> None:
    """Console entrypoint for the trainer."""
    TrainerApp().run()
