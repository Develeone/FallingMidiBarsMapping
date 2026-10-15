"""Keep both applications alive outside the initiating terminal/tool session."""
from pathlib import Path
import os
import subprocess
import sys
import time
import signal
from mac_bundles import executable


def stop(*_):
    raise SystemExit(0)


signal.signal(signal.SIGTERM, stop)

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
ready = ROOT / '.serum-host.ready'
ready.unlink(missing_ok=True)
with open(ROOT / 'serum.log', 'a', buffering=1) as sound_log, open(ROOT / 'trainer.log', 'a', buffering=1) as trainer_log:
    host_exe, host_env = executable('Serum 2 Live', 'local.fallingbars.serum')
    trainer_exe, trainer_env = executable('Falling Bars MIDI', 'local.fallingbars.trainer')
    host = subprocess.Popen([host_exe, '-u', 'serum_host.py'], env=host_env, stdout=sound_log, stderr=subprocess.STDOUT)
    trainer = None
    try:
        for _ in range(360):
            if host.poll() is not None:
                raise RuntimeError('Serum stopped; see serum.log')
            if ready.exists():
                break
            time.sleep(0.5)
        else:
            raise RuntimeError('Serum startup timed out; see serum.log')
        trainer = subprocess.Popen([trainer_exe, '-u', 'run.py'], env=trainer_env, stdout=trainer_log, stderr=subprocess.STDOUT)
        time.sleep(3)
        if host.poll() is None and trainer.poll() is None:
            os.kill(host.pid, signal.SIGUSR1)
        trainer.wait()
        # Closing the trainer is an explicit end of the practice session.
    finally:
        if trainer is not None and trainer.poll() is None:
            trainer.terminate()
        host.terminate()
        host.wait()
