"""Launch the packaged Electron shell and verify its bundled backend/UI."""
import json,os,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXE=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/('dist/win-unpacked/ONE Captions.exe' if os.name=='nt' else 'dist/mac/ONE Captions.app/Contents/MacOS/ONE Captions')
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
  with urllib.request.urlopen(base+'/') as response:html=response.read().decode('utf-8')
  assert '© 2027 PINI COHEN. All rights reserved.' in html,'Copyright footer missing from packaged UI'
  assert 'סטודיו לכתוביות' not in html and 'הפרויקטים שלי' not in html,'Welcome header contains removed labels'
  print('Packaged desktop app, backend, welcome and copyright footer: OK')
 finally:
  app.terminate()
  try:app.wait(timeout=10)
  except subprocess.TimeoutExpired:app.kill()
