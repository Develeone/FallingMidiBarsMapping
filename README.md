# Falling Bars MIDI

Launch `Start Falling Bars.command` to start the trainer and Serum 2 editor.
The launcher uses the local `.venv312` Python environment and runs the session
independently of the initiating terminal. Closing the trainer ends the session.

- Input: Popupiano → trainer → IAC Driver Bus 1 → Serum 2.
- Output: MacBook Air Speakers, 48 kHz, 256-frame audio blocks.
- `S`: open/reopen Serum's preset editor; closing the editor keeps sound playing.
- `Esc`: close the trainer and stop the session.
- `O`: load MIDI; arrows pan; comma/period zoom; `0` resets the view.

For the bundled `avril-14th-aphex-twin.mid`, small neutral Л/П labels beside the bars
mean left/right hand. Original pitch colors, stripes, zoom, and pan remain unchanged.
The MIDI merges both hands; `midi/hands.py` defines a suggested practice
assignment by phrase, including the lower melody in the middle and the
crossing accompaniment near the ending. Notes and timing are unchanged.
The two hand buttons select both hands, left only, or right only. A blue outline
means enabled. Disabled-hand notes stay visible at 20% opacity and are not
required to advance. Selection is saved alongside the existing zoom and pan.
Other MIDI files do not receive this arrangement-specific annotation.

Serum's selected sound is saved locally on closing its editor or ending the
session. Runtime logs are `serum.log`, `trainer.log`, and `launcher.log`.

Dependencies: `uv pip install --python .venv312/bin/python -e .`.
Tests: `.venv312/bin/python -m unittest discover -s tests -v`.
Serum 2 VST3 must already be installed at the standard macOS plugin location.
