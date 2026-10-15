"""Serum 2 editor and live IAC MIDI host, independent of the visualizer."""
from pathlib import Path
from queue import SimpleQueue, Empty
import os
import signal
import threading
import time
import traceback

import mido
import numpy as np
import pedalboard
import sounddevice as sd
from AppKit import NSApplication, NSApplicationActivationPolicyRegular

ROOT = Path(__file__).resolve().parent
PID = ROOT / '.serum-host.pid'
READY = ROOT / '.serum-host.ready'
SR, BLOCK = 48000, 256
DEVICE = 'MacBook Air Speakers'


# Pedalboard 0.9.26 scans every parameter even for an empty override map.
# Serum exposes thousands; the native editor does not need that Python map.
_set_parameters = pedalboard.VST3Plugin.__set_initial_parameter_values__


def _set_requested_parameters(plugin, values):
    if values:
        _set_parameters(plugin, values)


pedalboard.VST3Plugin.__set_initial_parameter_values__ = _set_requested_parameters


def main():
    reopen = threading.Event()
    close_editor = threading.Event()
    stopping = threading.Event()

    def show_editor(*_):
        reopen.set()
        close_editor.set()

    def stop(*_):
        stopping.set()
        show_editor()

    signal.signal(signal.SIGUSR1, show_editor)
    signal.signal(signal.SIGTERM, stop)
    PID.write_text(str(os.getpid()))
    READY.unlink(missing_ok=True)
    application = NSApplication.sharedApplication()
    application.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    application.finishLaunching()
    print('Loading Serum', flush=True)
    synth = pedalboard.VST3Plugin('/Library/Audio/Plug-Ins/VST3/Serum2.vst3', plugin_name='Serum 2')
    print('Serum loaded', flush=True)
    # Restore the last selected sound without forcing a particular preset.
    state_path = ROOT / '.serum-state.bin'
    if state_path.exists():
        try:
            pedalboard.VST3Plugin.raw_state.__set__(synth, state_path.read_bytes())
        except Exception:
            traceback.print_exc()
    messages = SimpleQueue()
    errors = SimpleQueue()
    counters = {'blocks': 0, 'notes': 0, 'peak': 0.0, 'underflows': 0}

    def receive(msg):
        if not msg.is_meta:
            messages.put(msg.copy(time=0))

    def audio(outdata, frames, timing, status):
        try:
            batch = []
            # Bound work per audio block even if a device floods MIDI messages.
            for _ in range(256):
                try:
                    batch.append(messages.get_nowait())
                except Empty:
                    break
            rendered = synth(batch, duration=frames/SR, sample_rate=SR,
                             num_channels=2, buffer_size=BLOCK, reset=False)
            outdata[:] = rendered.T * 0.25
            counters['blocks'] += 1
            counters['notes'] += sum(m.type == 'note_on' and m.velocity > 0 for m in batch)
            counters['peak'] = max(counters['peak'], float(np.abs(outdata).max()))
            counters['underflows'] += bool(status.output_underflow)
        except Exception:
            outdata.fill(0)
            errors.put(traceback.format_exc())

    def monitor():
        while True:
            time.sleep(5)
            while not errors.empty():
                print('AUDIO ERROR:', errors.get(), flush=True)
            print('AUDIO:', counters, flush=True)

    threading.Thread(target=monitor, daemon=True).start()
    with mido.open_input('IAC Driver Bus 1', callback=receive):
        with sd.OutputStream(device=DEVICE, samplerate=SR, blocksize=BLOCK,
                             latency='low', channels=2, dtype='float32', callback=audio) as stream:
            READY.write_text(str(os.getpid()))
            print('READY: Serum 2 ->', sd.query_devices(stream.device)['name'],
                  'latency:', stream.latency, flush=True)
            while not stopping.is_set():
                reopen.clear()
                close_editor.clear()
                application.activateIgnoringOtherApps_(True)
                print('Opening Serum editor', flush=True)
                synth.show_editor(close_editor)
                state_path.write_bytes(synth.raw_state)
                print('Editor closed; audio stays active. Press S in Falling Bars to reopen.', flush=True)
                if not stopping.is_set():
                    reopen.wait()


if __name__ == '__main__':
    try:
        main()
    finally:
        PID.unlink(missing_ok=True)
        READY.unlink(missing_ok=True)
