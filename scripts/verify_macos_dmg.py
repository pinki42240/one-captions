"""Mount, audit and launch the app as distributed inside a macOS DMG."""
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
arch = sys.argv[1]
dmgs = list((root/'dist').glob('*.dmg'))
if len(dmgs) != 1:
    raise SystemExit(f'Expected one DMG, found {[path.name for path in dmgs]}')
dmg = dmgs[0].resolve(strict=True)
subprocess.run(['hdiutil', 'verify', str(dmg)], check=True)
with tempfile.TemporaryDirectory(prefix='one-captions-dmg-') as directory:
    mount = Path(directory)
    subprocess.run(['hdiutil', 'attach', '-readonly', '-nobrowse', '-mountpoint', str(mount), str(dmg)], check=True)
    try:
        app = mount / 'ONE Captions.app'
        subprocess.run([sys.executable, str(root/'scripts/audit_package.py'), str(app), arch], check=True)
        subprocess.run([sys.executable, str(root/'scripts/smoke_desktop.py'), str(app/'Contents/MacOS/ONE Captions')], check=True)
    finally:
        subprocess.run(['hdiutil', 'detach', str(mount)], check=True)
