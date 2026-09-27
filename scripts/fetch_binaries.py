"""Fetch OS-specific, Redistributable FFmpeg/ffprobe and llama-server.
Build-time only. Models and personal data are never packaged.
"""
import io,os,platform,subprocess,tarfile,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BIN=ROOT/'release/engine/bin';BIN.mkdir(parents=True,exist_ok=True)
LLAMA_TAG='b11223'
def get(url):
 print('Downloading:',url,flush=True)
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ONE-Captions-build'}),timeout=180) as response:return response.read()
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
 for tool in ('ffmpeg','ffprobe'):
  extract_zip(get(f'https://evermeet.cx/ffmpeg/getrelease/{tool}/zip'),lambda name:name==tool)
 extract_tar(get(f'https://github.com/ggml-org/llama.cpp/releases/download/{LLAMA_TAG}/llama-{LLAMA_TAG}-bin-macos-x64.tar.gz'),lambda name:name=='llama-server' or name.endswith('.dylib'))
elif platform.system()=='Windows':
 extract_zip(get('https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'),lambda name:name in ('ffmpeg.exe','ffprobe.exe'))
 extract_zip(get(f'https://github.com/ggml-org/llama.cpp/releases/download/{LLAMA_TAG}/llama-{LLAMA_TAG}-bin-win-cpu-x64.zip'),lambda name:name=='llama-server.exe' or name.endswith('.dll'))
else:raise SystemExit('Build on macOS Intel or Windows x64.')
ff=BIN/('ffmpeg.exe' if os.name=='nt' else 'ffmpeg');fp=BIN/('ffprobe.exe' if os.name=='nt' else 'ffprobe');ll=BIN/('llama-server.exe' if os.name=='nt' else 'llama-server')
for file in (ff,fp,ll):
 assert file.is_file(),file
filters=subprocess.run([str(ff),'-hide_banner','-filters'],check=True,capture_output=True,text=True).stdout
assert ' ass ' in filters and ' subtitles ' in filters,'FFmpeg lacks subtitle filters'
subprocess.run([str(fp),'-version'],check=True,capture_output=True)
subprocess.run([str(ll),'--version'],check=True,capture_output=True)
print('Binaries ready:',*[p.name for p in BIN.iterdir()])
