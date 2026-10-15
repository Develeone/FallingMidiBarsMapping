import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
import unittest
from unittest.mock import patch
import mido
import pygame
from falling_midi_trainer.app import TrainerApp
from falling_midi_trainer.game.state import GameState
from falling_midi_trainer.midi.parsing import parse_notes
from falling_midi_trainer.midi.hands import assign_hands

PATH = 'midi/avril-14th-aphex-twin.mid'


class PracticeTests(unittest.TestCase):
    def test_hand_annotation_preserves_all_notes_and_timing(self):
        original, length, _ = parse_notes(PATH, 0)
        state = GameState([PATH])
        state.load_current()
        self.assertCountEqual(original, [n for c in state.chords for n in c])
        self.assertEqual(state.total_length, length)
        self.assertEqual(set(state.note_hands), set(original))
        self.assertEqual(set(state.note_hands.values()), {'Л', 'П'})
        self.assertFalse(assign_hands('midi/demo.mid', original))

    def test_low_melody_and_crossing_accompaniment(self):
        notes, _, _ = parse_notes(PATH, 0)
        hands = assign_hands(PATH, notes)
        def hand_near(pitch, at):
            note = next(n for n in notes if n[0] == pitch and abs(n[1]-at) < 0.03)
            return hands[note]
        self.assertEqual(hand_near(60, 24), 'П')
        self.assertEqual(hand_near(44, 24), 'Л')
        self.assertEqual(hand_near(58, 25.5), 'П')
        self.assertEqual(hand_near(65, 100.125), 'Л')
        self.assertEqual(hand_near(68, 101.625), 'Л')

    def test_accidental_stripes_match_original_pixels(self):
        pygame.init()
        try:
            for width, height in ((12, 40), (25, 180), (4, 3)):
                original = pygame.Surface((width, height), pygame.SRCALPHA)
                original.fill((0, 0, 0, 10))
                for offset in range(-height, width + height, 7):
                    pygame.draw.line(original, (0, 0, 0, 255),
                                     (offset, height), (offset + height, 0), 6)
                actual = TrainerApp._accidental_pattern(width, height)
                self.assertEqual(pygame.image.tostring(original, 'RGBA'),
                                 pygame.image.tostring(actual, 'RGBA'))
        finally:
            pygame.quit()

    def test_serum_mode_does_not_generate_unused_piano_tones(self):
        port = unittest.mock.MagicMock()
        with patch('falling_midi_trainer.app.make_piano_tone') as synth, \
             patch('mido.get_input_names', return_value=['Popupiano']), \
             patch('mido.get_output_names', return_value=['IAC Driver Bus 1']), \
             patch('mido.open_input', return_value=port), \
             patch('mido.open_output', return_value=port):
            app = TrainerApp()
            try:
                self.assertFalse(app.internal_enabled)
                with patch.object(app, '_build_background', wraps=app._build_background) as build:
                    for _ in range(60):
                        app._draw()
                    self.assertEqual(build.call_count, 1)
                synth.assert_not_called()
            finally:
                app._cleanup()


class HandSelectionTests(unittest.TestCase):
    def setUp(self):
        self.state = GameState([PATH])
        self.state.load_current()
        self.app = TrainerApp.__new__(TrainerApp)
        self.app.state = self.state
        self.app.pressed = set()

    def test_one_hand_chord_does_not_require_other_hand(self):
        self.state.toggle_hand('П')
        self.app.pressed = {44}
        self.app._update_game_time(0.01)
        self.assertEqual(self.state.chord_idx, 1)
        self.assertFalse(self.state.paused)
        self.state.load_current()
        self.state.toggle_hand('П')  # Both hands again.
        self.state.toggle_hand('Л')  # Right only.
        self.app.pressed = {72}
        self.app._update_game_time(0.01)
        self.assertEqual(self.state.chord_idx, 1)
        self.assertFalse(self.state.paused)

    def test_both_hands_still_require_both_notes(self):
        self.app.pressed = {44}
        self.app._update_game_time(0.01)
        self.assertTrue(self.state.paused)
        self.assertEqual(self.state.chord_idx, 0)
        self.app.pressed.add(72)
        self.app._update_game_time(0.01)
        self.assertFalse(self.state.paused)

    def test_other_hand_only_chord_advances_without_press(self):
        self.state.toggle_hand('Л')
        self.state.chord_idx = 1  # G# accompaniment phrase, left hand only.
        self.state.game_time = self.state.chords[1][0][1]
        with patch('falling_midi_trainer.config.STRICT', True):
            self.app._update_game_time(0.01)
        self.assertEqual(self.state.chord_idx, 2)
        self.assertFalse(self.state.paused)
        self.assertFalse(self.state.toggle_hand('П'))
        self.assertEqual(self.state.enabled_hands, {'П'})

    def test_selection_preserves_view_and_other_saved_settings(self):
        import tempfile, json
        from pathlib import Path
        self.app.keyboard_zoom = 1.48
        self.app.keyboard_pan_x = -504.0
        self.state.toggle_hand('Л')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            path.write_text(json.dumps({'custom_setting': 123}))
            with patch('falling_midi_trainer.config.STATE_PATH', str(path)):
                self.app._save_ui_state()
                saved = json.loads(path.read_text())
                self.assertEqual(saved['keyboard_zoom'], 1.48)
                self.assertEqual(saved['keyboard_pan_x'], -504.0)
                self.assertEqual(saved['custom_setting'], 123)
                self.assertEqual(saved['enabled_hands'], ['П'])
                self.app._load_ui_state()
                self.assertEqual(self.app._saved_hands, {'П'})

    def test_disabled_note_is_twenty_percent_alpha(self):
        pygame.init()
        try:
            self.app.screen = pygame.Surface((100, 100))
            self.app.hand_labels = {}
            background = (20, 30, 40)
            rect = pygame.Rect(10, 10, 20, 50)
            self.app.screen.fill(background)
            self.app._draw_note_bar(rect, 60, (255, 0, 0), None, True)
            self.assertEqual(self.app.screen.get_at((20, 30))[:3], (255, 0, 0))
            self.app.screen.fill(background)
            self.app._draw_note_bar(rect, 60, (255, 0, 0), None, False)
            reference = pygame.Surface((1, 1))
            reference.fill(background)
            overlay = pygame.Surface((1, 1), pygame.SRCALPHA)
            overlay.fill((255, 0, 0, 255))
            overlay.set_alpha(51)
            reference.blit(overlay, (0, 0))
            self.assertEqual(self.app.screen.get_at((20, 30)), reference.get_at((0, 0)))
        finally:
            pygame.quit()


if __name__ == '__main__':
    unittest.main()
