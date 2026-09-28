"""Smoke a frozen backend without requiring a video or downloading model weights."""
import json,os,subprocess,tempfile,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];ENGINE=ROOT/'release/engine';BIN=ENGINE/'bin'
EXE=ROOT/'release/runtime/one-backend'/('one-backend.exe' if os.name=='nt' else 'one-backend')
subprocess.run([str(EXE),'--check-dependencies'],check=True,timeout=60)
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
