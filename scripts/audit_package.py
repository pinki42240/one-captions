"""Audit the exact packaged app tree before uploading a release installer."""
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve(strict=True)
arch = sys.argv[2]
if arch not in ('x64', 'arm64'):
    raise SystemExit(f'Unsupported target architecture: {arch}')
if not root.is_dir():
    raise SystemExit(f'Package is missing: {root}')
mac = sys.platform == 'darwin'
if mac and arch == 'arm64' and os.uname().machine != 'arm64':
    raise SystemExit('Apple Silicon packages must be audited on an arm64 runner')
resources = root / ('Contents/Resources' if mac else 'resources')
engine = resources / 'engine/bin'
runtime = resources / 'runtime'
required = [
    engine / ('ffmpeg' if mac else 'ffmpeg.exe'),
    engine / ('ffprobe' if mac else 'ffprobe.exe'),
    engine / ('llama-server' if mac else 'llama-server.exe'),
    runtime / ('one-backend' if mac else 'one-backend.exe'),
    root / ('Contents/MacOS/ONE Captions' if mac else 'ONE Captions.exe'),
]
for path in required:
    if not path.is_file():
        raise SystemExit(f'Required bundled executable is missing: {path}')

mach_magics = {b'\xfe\xed\xfa\xce', b'\xce\xfa\xed\xfe', b'\xfe\xed\xfa\xcf',
               b'\xcf\xfa\xed\xfe', b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca',
               b'\xca\xfe\xba\xbf', b'\xbf\xba\xfe\xca'}
native_count = 0
python_native_count = 0
for path in root.rglob('*'):
    if path.is_symlink():
        target = path.resolve(strict=True)
        if not target.is_relative_to(root):
            raise SystemExit(f'Symlink escapes app bundle: {path}')
        continue
    if not path.is_file():
        continue
    relative = path.relative_to(root)
    if path.suffix.lower() in {'.mp4', '.mov', '.wav', '.gguf', '.safetensors', '.env'} or re.fullmatch(r'runtime-\d+\.json|desktop\.log', path.name):
        raise SystemExit(f'Private media, model or runtime data in package: {relative}')
    with path.open('rb') as stream:
        head = stream.read(4)
        if head[:2] == b'MZ':
            stream.seek(0x3c)
            offset = struct.unpack('<I', stream.read(4))[0]
            stream.seek(offset)
            signature = stream.read(4)
            machine = struct.unpack('<H', stream.read(2))[0]
            if signature != b'PE\0\0' or machine != 0x8664 or mac:
                raise SystemExit(f'Unexpected PE architecture in {relative}: {machine:#x}')
            native_count += 1
        elif head in mach_magics:
            if not mac:
                raise SystemExit(f'macOS binary in Windows package: {relative}')
            result = subprocess.run(['lipo', '-archs', str(path)], check=True, capture_output=True, text=True)
            expected = 'arm64' if arch == 'arm64' else 'x86_64'
            if expected not in result.stdout.split():
                raise SystemExit(f'Incompatible Mach-O in {relative}: {result.stdout.strip()}')
            native_count += 1
        elif path.suffix.lower() in ({'.so', '.dylib', '.node'} if mac else {'.exe', '.dll', '.pyd', '.node'}):
            raise SystemExit(f'Unrecognized native binary in {relative}')
    if path.suffix.lower() in ({'.so', '.pyd'} if not mac else {'.so'}) and 'runtime' in path.parts:
        python_native_count += 1
    if path.suffix.lower() in {'.js', '.cjs', '.json', '.html', '.css', '.md', '.txt'} and path.stat().st_size < 5_000_000:
        data = path.read_text(errors='ignore')
        for pattern in (r'/Users/(?!runner/)[A-Za-z0-9_-]+/', r'gh[opusr]_[A-Za-z0-9]{20,}',
                        r'sk-(?:proj-)?[A-Za-z0-9]{20,}', r'AIza[A-Za-z0-9_-]{20,}',
                        r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----'):
            if re.search(pattern, data):
                raise SystemExit(f'Potential private path or credential in {relative}')
if native_count < 5 or python_native_count == 0:
    raise SystemExit(f'Native dependency inventory is incomplete: {native_count} binaries, {python_native_count} Python modules')
print(f'Package security/privacy and {arch} architecture audit passed: {native_count} native binaries, {python_native_count} Python modules; required tools present; no private media, models, credentials or runtime data.')
