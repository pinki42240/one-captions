"""Smoke a frozen backend without requiring a video or downloading model weights."""
import json,os,subprocess,tempfile,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];ENGINE=ROOT/'release/engine';BIN=ENGINE/'bin'
EXE=ROOT/'release/runtime/one-backend'/('one-backend.exe' if os.name=='nt' else 'one-backend')
subprocess.run([str(EXE),'--check-dependencies'],check=True,timeout=60)
with tempfile.TemporaryDirectory() as temp:
 work=Path(temp)
 (work/'smoke.ass').write_text('''[Script Info]
ScriptType: v4.00+
PlayResX: 64
PlayResY: 64

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,14,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,ONE
''',encoding='utf-8')
 ff=BIN/('ffmpeg.exe' if os.name=='nt' else 'ffmpeg')
 fp=BIN/('ffprobe.exe' if os.name=='nt' else 'ffprobe')
 subprocess.run([str(ff),'-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=black:s=64x64:r=1:d=1','-vf','ass=filename=smoke.ass','-frames:v','1','-c:v','libx264','-pix_fmt','yuv420p','smoke.mp4'],cwd=work,check=True,timeout=60)
 probe=subprocess.run([str(fp),'-v','error','-select_streams','v:0','-show_entries','stream=codec_name','-of','default=nw=1:nk=1','smoke.mp4'],cwd=work,check=True,capture_output=True,text=True,timeout=30)
 assert probe.stdout.strip()=='h264',probe.stdout
 print('FFmpeg ASS subtitle burn-in, H.264 encode and FFprobe: OK')
with tempfile.TemporaryDirectory() as temp:
 data=Path(temp);runtime=data/'runtime.json'
 env={**os.environ,'ONE_ENGINE_ROOT':str(ENGINE),'ONE_DATA_DIR':str(data),'ONE_OUTPUT_DIR':str(data/'output'),'PINI_FFMPEG':str(BIN/('ffmpeg.exe' if os.name=='nt' else 'ffmpeg')),'PINI_FFPROBE':str(BIN/('ffprobe.exe' if os.name=='nt' else 'ffprobe')),'ONE_LLAMA_SERVER':str(BIN/('llama-server.exe' if os.name=='nt' else 'llama-server'))}
 process=subprocess.Popen([str(EXE),'--runtime',str(runtime)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
 try:
  for _ in range(100):
   if runtime.is_file():break
   if process.poll() is not None:raise RuntimeError(process.stderr.read()[-3000:])
   time.sleep(.1)
  else:raise RuntimeError('Backend did not start')
  state=json.loads(runtime.read_text());base=f"http://127.0.0.1:{state['port']}"
  request=urllib.request.Request(base+'/api/health',headers={'X-One-Token':state['token']})
  with urllib.request.urlopen(request,timeout=5) as response:assert json.load(response)['ready']
  with urllib.request.urlopen(base+'/') as response:assert b'ONE' in response.read()
  with urllib.request.urlopen(base+'/app.js') as response:assert b'recent-project' in response.read()
  print('Frozen backend, static UI and authenticated health: OK')
 finally:
  process.terminate()
  try:process.wait(timeout=10)
  except subprocess.TimeoutExpired:process.kill()
