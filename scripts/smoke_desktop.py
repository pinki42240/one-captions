"""Launch the packaged Electron shell and verify its bundled backend/UI."""
import json,os,subprocess,tempfile,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXE=ROOT/('dist/win-unpacked/ONE Captions.exe' if os.name=='nt' else 'dist/mac/ONE Captions.app/Contents/MacOS/ONE Captions')
assert EXE.is_file(),EXE
with tempfile.TemporaryDirectory() as temp:
 env={**os.environ,'ONE_USER_DATA_DIR':temp,'ONE_SKIP_SETUP_TEST':'1'}
 app=subprocess.Popen([str(EXE)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  for _ in range(150):
   files=list((Path(temp)/'projects').glob('runtime-*.json'))
   if files:break
   if app.poll() is not None:raise RuntimeError(f'Desktop process exited: {app.returncode}')
   time.sleep(.2)
  else:raise RuntimeError('Desktop backend did not start')
  state=json.loads(files[0].read_text());base=f"http://127.0.0.1:{state['port']}"
  request=urllib.request.Request(base+'/api/health',headers={'X-One-Token':state['token']})
  with urllib.request.urlopen(request,timeout=5) as response:assert json.load(response)['ready']
  with urllib.request.urlopen(base+'/') as response:assert b'ONE' in response.read()
  print('Packaged desktop app and backend: OK')
 finally:
  app.terminate()
  try:app.wait(timeout=10)
  except subprocess.TimeoutExpired:app.kill()
