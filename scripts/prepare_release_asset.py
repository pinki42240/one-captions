"""Copy one verified installer to a clear, architecture-specific release filename."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = sys.argv[1]
labels = {
    'macos-intel-x64': ('macOS-Intel-x64', '.dmg'),
    'macos-apple-silicon-arm64': ('macOS-Apple-Silicon-arm64', '.dmg'),
    'windows-x64': ('Windows-x64', '.exe'),
}
if target not in labels:
    raise SystemExit(f'Unknown release target: {target}')
label, extension = labels[target]
version = json.loads((root/'one_captions/package.json').read_text())['version']
sources = list((root/'dist').glob(f'*{extension}'))
if len(sources) != 1:
    raise SystemExit(f'Expected one {extension} installer; found {[p.name for p in sources]}')
destination = root/'release-assets'/f'ONE-Captions-{label}-{version}{extension}'
destination.parent.mkdir(exist_ok=True)
if destination.exists():
    raise SystemExit(f'Refusing to overwrite release asset: {destination}')
shutil.copy2(sources[0], destination)
with destination.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
print(f'Verified release asset: {destination.name} sha256:{digest}')
