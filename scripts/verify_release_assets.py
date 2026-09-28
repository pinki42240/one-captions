"""Fail release publication unless every named installer passed its build job."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
version = json.loads((root/'one_captions/package.json').read_text())['version']
expected = {
    f'ONE-Captions-macOS-Intel-x64-{version}.dmg',
    f'ONE-Captions-macOS-Apple-Silicon-arm64-{version}.dmg',
    f'ONE-Captions-Windows-x64-{version}.exe',
}
assets = {path.name for path in (root/'dist').iterdir() if path.is_file()}
if assets != expected:
    raise SystemExit(f'Release asset mismatch: expected {sorted(expected)}, found {sorted(assets)}')
for name in expected:
    if (root/'dist'/name).stat().st_size < 10_000_000:
        raise SystemExit(f'Installer is unexpectedly small: {name}')
print('All three verified installers are present:', *sorted(expected), sep='\n')
