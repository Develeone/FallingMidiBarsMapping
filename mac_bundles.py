"""Give the two Python GUI processes proper macOS application identities."""
from pathlib import Path
import os
import plistlib
import shutil
import sys
import sysconfig

ROOT = Path(__file__).resolve().parent


def executable(name, identifier):
    contents = ROOT / '.runtime' / (name + '.app') / 'Contents'
    binary = contents / 'MacOS' / name
    binary.parent.mkdir(parents=True, exist_ok=True)
    if not binary.exists():
        shutil.copy2(Path(sys.executable).resolve(), binary)
    library = contents / 'lib'
    if not library.exists():
        library.symlink_to(Path(sys.base_prefix) / 'lib')
    (contents / 'Info.plist').write_bytes(plistlib.dumps({
        'CFBundleExecutable': name,
        'CFBundleIdentifier': identifier,
        'CFBundleName': name,
        'CFBundleDisplayName': name,
        'CFBundlePackageType': 'APPL',
        'CFBundleVersion': '1',
        'NSHighResolutionCapable': True,
        'LSUIElement': False,
    }))
    env = os.environ.copy()
    env['PYTHONHOME'] = sys.base_prefix
    env['PYTHONPATH'] = os.pathsep.join((str(ROOT), sysconfig.get_path('purelib')))
    return str(binary), env
