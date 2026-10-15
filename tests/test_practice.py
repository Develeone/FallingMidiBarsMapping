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


if __name__ == '__main__':
    unittest.main()
