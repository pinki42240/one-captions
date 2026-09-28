"""Fetch OS-specific, Redistributable FFmpeg/ffprobe and llama-server.
Build-time only. Models and personal data are never packaged.
"""
import hashlib,io,os,platform,subprocess,tarfile,time,urllib.error,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BIN=ROOT/'release/engine/bin';BIN.mkdir(parents=True,exist_ok=True)
LLAMA_TAG='b11223'
ARM_FFMPEG_BASE='https://ffmpeg.martin-riedl.de/download/macos/arm64/1789931890_9.0.2'
ARM_FFMPEG_SHA256={
 'ffmpeg':'c8ed4c4e6978a03c485edbfe4e0a5dc2380f8a30bba5150531b31b094492d924',
 'ffprobe':'fcbe839537485eaee7a7a8bc5cbc0f90d53617e80943e8a5b2e31cb851197ea6',
}
ARM_FFMPEG_FALLBACK='https://github.com/vanloctech/ffmpeg-macos/releases/download/ffmpeg-2026.06.11/ffmpeg-macos-arm64.tar.gz'
ARM_FFMPEG_FALLBACK_SHA256='26f5133f88d5ab1254cc03499acef42dae2dbc574dd26e0dade8c968420127e9'
WINDOWS_FFMPEG_FALLBACK='https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-09-28-13-06/ffmpeg-n9.0.2-14-gebafaee10a-win64-gpl-9.0.zip'
WINDOWS_FFMPEG_FALLBACK_SHA256='09170e52cb657f184ba4da2f42567cf2841b661cd9bb5f46ffe4481eb8e6d841'
ARM_LLAMA_SHA256='5bacea12237283699a196194b7f62a0e613438bd5feed694359ed6050492bb3e'
def get(url):
 for attempt in range(3):
  try:
   print('Downloading:',url,flush=True)
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ONE-Captions-build'}),timeout=180) as response:return response.read()
  except (urllib.error.URLError,TimeoutError):
   if attempt==2:raise
   time.sleep(2**attempt)
def verified(data,digest,label):
 if hashlib.sha256(data).hexdigest()!=digest:raise RuntimeError(f'{label} checksum mismatch')
 return data
def extract_zip(data,keep):
 with zipfile.ZipFile(io.BytesIO(data)) as archive:
  for name in archive.namelist():
   base=Path(name).name
   if base and keep(base):
    target=BIN/base;target.write_bytes(archive.read(name));target.chmod(0o755)
def extract_tar(data,keep):
 with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
  for member in archive:
   base=Path(member.name).name
   if member.isfile() and base and keep(base):
    source=archive.extractfile(member)
    if source:
     target=BIN/base;target.write_bytes(source.read());target.chmod(0o755)
  for member in archive:
   base=Path(member.name).name
   if member.issym() and base and keep(base):
    dest=Path(member.linkname).name
    if (BIN/dest).exists():
     link=BIN/base
     if not link.exists():link.symlink_to(dest)
if platform.system()=='Darwin':
 machine=platform.machine()
 if machine not in ('x86_64','arm64'):raise SystemExit(f'Unsupported macOS architecture: {machine}')
 if machine=='arm64':
  try:
   archives={tool:verified(get(f'{ARM_FFMPEG_BASE}/{tool}.zip'),ARM_FFMPEG_SHA256[tool],tool) for tool in ('ffmpeg','ffprobe')}
  except (urllib.error.URLError,TimeoutError) as error:
   print('Primary Apple Silicon FFmpeg source unavailable:',error,flush=True)
   data=verified(get(ARM_FFMPEG_FALLBACK),ARM_FFMPEG_FALLBACK_SHA256,'Apple Silicon FFmpeg fallback')
   extract_tar(data,lambda name:name in ('ffmpeg','ffprobe'))
  else:
   for tool,data in archives.items():extract_zip(data,lambda name:name==tool)
 else:
  for tool in ('ffmpeg','ffprobe'):
   extract_zip(get(f'https://evermeet.cx/ffmpeg/getrelease/{tool}/zip'),lambda name:name==tool)
 llama_arch='arm64' if machine=='arm64' else 'x64'
 data=get(f'https://github.com/ggml-org/llama.cpp/releases/download/{LLAMA_TAG}/llama-{LLAMA_TAG}-bin-macos-{llama_arch}.tar.gz')
 if machine=='arm64':verified(data,ARM_LLAMA_SHA256,'Apple Silicon llama.cpp')
 extract_tar(data,lambda name:name=='llama-server' or name.endswith('.dylib'))
elif platform.system()=='Windows':
 try:data=get('https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip')
 except (urllib.error.URLError,TimeoutError) as error:
  print('Primary Windows FFmpeg source unavailable:',error,flush=True)
  data=verified(get(WINDOWS_FFMPEG_FALLBACK),WINDOWS_FFMPEG_FALLBACK_SHA256,'Windows FFmpeg fallback')
 extract_zip(data,lambda name:name in ('ffmpeg.exe','ffprobe.exe'))
 extract_zip(get(f'https://github.com/ggml-org/llama.cpp/releases/download/{LLAMA_TAG}/llama-{LLAMA_TAG}-bin-win-cpu-x64.zip'),lambda name:name=='llama-server.exe' or name.endswith('.dll'))
else:raise SystemExit('Build on macOS Intel, macOS Apple Silicon or Windows x64.')
ff=BIN/('ffmpeg.exe' if os.name=='nt' else 'ffmpeg');fp=BIN/('ffprobe.exe' if os.name=='nt' else 'ffprobe');ll=BIN/('llama-server.exe' if os.name=='nt' else 'llama-server')
for file in (ff,fp,ll):
 assert file.is_file(),file
filters=subprocess.run([str(ff),'-hide_banner','-filters'],check=True,capture_output=True,text=True).stdout
assert ' ass ' in filters and ' subtitles ' in filters,'FFmpeg lacks subtitle filters'
subprocess.run([str(fp),'-version'],check=True,capture_output=True)
subprocess.run([str(ll),'--version'],check=True,capture_output=True)
print('Binaries ready:',*[p.name for p in BIN.iterdir()])
