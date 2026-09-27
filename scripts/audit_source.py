"""Fail closed before pushing private source or publishing a release."""
import re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
paths=subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines()
for name in paths:
 p=ROOT/name
 if p.is_symlink():raise SystemExit(f'Symlink forbidden: {name}')
 if not p.is_file():raise SystemExit(f'Missing file: {name}')
 if p.stat().st_size>5_000_000:raise SystemExit(f'Large file: {name}')
 if re.search(r'\.(mp4|mov|wav|gguf|bin|log|srt|ass|env|p12|pem|key)$',name,re.I):raise SystemExit(f'Private/build artifact: {name}')
 if name.startswith(('one_captions/data/','release/','dist/','build/','models/','output/')):raise SystemExit(f'Runtime artifact: {name}')
 if p.suffix.lower() in {'.py','.js','.cjs','.json','.md','.txt','.yml','.yaml','.css','.html'}:
  text=p.read_text(errors='ignore')
  for pattern in (r'/Users/[A-Za-z0-9_-]+/',r'gh[opusr]_[A-Za-z0-9]{20,}',r'sk-(?:proj-)?[A-Za-z0-9]{20,}',r'AIza[A-Za-z0-9_-]{20,}',r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----'):
   if re.search(pattern,text):raise SystemExit(f'Potential credential or personal path in {name}')
print(f'Privacy audit passed: {len(paths)} tracked source files, no media, models, secrets or runtime data.')
