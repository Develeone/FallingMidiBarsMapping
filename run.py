"""Launch the Falling MIDI Bars trainer."""
from falling_midi_trainer.app import TrainerApp

if __name__ == '__main__':
    app = TrainerApp()
    print('READY:', app.midi_in_name, '->', app.midi_out_name,
          'view:', app.screen.get_size(), 'zoom:', app.keyboard_zoom,
          'pan:', app.keyboard_pan_x, flush=True)
    app.run()
