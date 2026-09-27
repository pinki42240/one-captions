"""Loopback-only portable backend. Desktop shell owns all native dialogs."""
import argparse
import copy
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs,unquote
from adapter import ROOT,core,dimensions,base_settings,reflow
from domain import command,checkpoint,undo,redo,execute,infer_last_change,replace_cues,important_words,snapshot

HERE=Path(os.getenv('ONE_ENGINE_ROOT', Path(__file__).resolve().parents[1]))/'one_captions'
DATA=Path(os.getenv('ONE_DATA_DIR', HERE/'data'))/'sessions'
DATA.mkdir(parents=True,exist_ok=True)
TOKEN=os.getenv('ONE_TOKEN') or secrets.token_urlsafe(32)
LOCK=threading.RLock()
JOBS={}
CHATS=set()

def write(path,data):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False));tmp.replace(path)

def folder(sid):
 if not re.fullmatch(r'[0-9a-f]{32}',sid):raise ValueError('הסרטון אינו זמין.')
 d=DATA/sid
 if not (d/'session.json').is_file():raise ValueError('הסרטון אינו זמין.')
 return d

def save(s):
 s['updated']=time.time()
 write(folder(s['id'])/'session.json',s)

def synchronize(s):
 d=folder(s['id']);dirty=False
 if (d/'preview.mp4').is_file() and not s.get('preview_ready'):s['preview_ready']=True;dirty=True
 if (d/'preview-error.json').is_file() and not s.get('preview_error'):
  dirty=True;s['preview_error']='לא ניתן להציג את הסרטון הזה. אפשר עדיין לנסות ליצור כתוביות.'
 if (d/'progress.json').is_file():
  p=json.loads((d/'progress.json').read_text())
  process=JOBS.get(s['id'])
  if p.get('status')=='running' and process and process.poll() is not None:
   p.update(status='error',percent=0,error='העיבוד נעצר. אפשר לנסות שוב.');write(d/'progress.json',p)
  if s.get('job')!=p:dirty=True
  s['job']=p
  if p['status']=='complete' and p.get('mode')=='transcribe' and not s.get('raw'):
   dirty=True;s['raw']=json.loads((d/'raw-transcript.json').read_text())
   reflow(s)
   # Rebase pre-transcription Undo snapshots onto the newly generated captions.
   for item in s['history']+s.get('redo',[]):
    historical=copy.deepcopy(s);historical.update(item['snapshot']);historical['manual']=False;reflow(historical)
    for edit in historical['pending']:
     if replace_cues(historical['cues'],**edit):historical['manual']=True
    historical['pending']=[]
    item['snapshot']['cues']=historical['cues'];item['snapshot']['pending']=[];item['snapshot']['manual']=historical['manual']
   corrections=copy.deepcopy(s['pending']);s['pending']=[]
   for edit in corrections:
    n=replace_cues(s['cues'],**edit)
    if n:s['manual']=True
    s['messages'].append({'role':'assistant','text':f'תיקנתי את ״{edit["old"]}״ ב־{n} מקומות.' if n else f'לא מצאתי את ״{edit["old"]}״ באזור המבוקש. אפשר לתקן את השורה ישירות.'})
   if corrections:reflow(s)
   s['messages'].append({'role':'assistant','text':'הכתוביות מוכנות. אפשר לצפות, לתקן שורה או לבקש ממני לשנות את הסגנון.'})
  if p['status']=='complete' and p.get('mode')=='export' and (d/'export-result.json').exists():
   result=json.loads((d/'export-result.json').read_text())
   if not s['exports'] or s['exports'][-1]!=result:
    dirty=True;s['exports'].append(result);s['messages'].append({'role':'assistant','text':'הסרטון מוכן! אפשר לפתוח אותו או להציג אותו בתיקיית השמירה.'})
 if dirty:save(s)
 return s

def load(sid):
 s=synchronize(json.loads((folder(sid)/'session.json').read_text()))
 s.setdefault('redo',[])
 if 'last_change' not in s:s['last_change']=infer_last_change(s)
 s['thinking']=sid in CHATS
 return s

def public(s):
 out={k:v for k,v in s.items() if k not in ('raw','history','redo','exports')}
 from word_styles import resolve
 out['word_runs']=resolve(s)
 out['can_redo']=bool(s.get('redo'));out['can_undo']=bool(s['history']);out['has_captions']=bool(s['cues']);out['important_words']=important_words(s)
 out['has_export']=bool(s['exports']) and s['exports'][-1].get('revision',0)==s.get('revision',0);out['export_name']=s['exports'][-1]['name'] if s['exports'] else None
 return out

def preview(d):
 try:
  info=core.probe(d/'source');v=next(s for s in info['streams'] if s['codec_type']=='video')
  tone=''
  if v.get('color_transfer') in {'smpte2084','arib-std-b67'}:
   tone='zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=mobius:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,'
  temp=d/'preview.partial.mp4'
  subprocess.run([core.ffmpeg(),'-v','error','-y','-i',str(d/'source'),'-map','0:v:0','-map','0:a:0','-vf',tone+"scale=w='min(960,iw)':h=-2",'-c:v','libx264','-preset','ultrafast','-crf','24','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart',str(temp)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  temp.replace(d/'preview.mp4')
 except Exception:
  write(d/'preview-error.json',{'error':'לא ניתן להכין תצוגה מקדימה לסרטון הזה.'})

def create(source,name=None):
 source=Path(source).expanduser().resolve()
 if source.suffix.lower() not in {'.mp4','.mov'} or not source.is_file():raise ValueError('בחרו סרטון MP4 או MOV.')
 sid=uuid.uuid4().hex;d=DATA/sid;d.mkdir()
 try:
  shutil.copy2(source,d/'source')
  details=dimensions(d/'source')
  s=dict(id=sid,name=name or source.name,created=time.time(),revision=0,preset='Reels',settings=base_settings(),cues=[],raw=None,colors={},important=False,pending=[],manual=False,history=[],exports=[],preview_ready=False,job={'status':'idle','percent':0},messages=[{'role':'assistant','text':'הסרטון כאן. איזה סגנון מתאים לך? אפשר לבחור סגנון, לבקש שינוי או להתחיל ליצור כתוביות.'}],**details)
  write(d/'session.json',s)
  threading.Thread(target=preview,args=(d,),daemon=True).start()
  return public(s)
 except Exception:
  shutil.rmtree(d);raise

def busy(s):return s['job'].get('status')=='running'

def start(s,mode,target=None):
 if busy(s):raise ValueError('הסרטון עדיין בעיבוד. אפשר להמשיך לערוך מיד כשנסיים.')
 if any(p.poll() is None for p in JOBS.values()):raise ValueError('סרטון אחר עדיין בעיבוד. נסיים אותו ואז נמשיך.')
 if mode=='export' and not s['cues']:raise ValueError('צרו כתוביות לפני הייצוא.')
 d=folder(s['id'])
 write(d/'job-request.json',{'session':s,'target':target})
 write(d/'progress.json',{'mode':mode,'status':'running','phase':'מתחילים','percent':1})
 s['job']={'mode':mode,'status':'running','phase':'מתחילים','percent':1};save(s)
 log=(d/'worker.log').open('a')
 JOBS[s['id']]=subprocess.Popen(([os.environ['ONE_WORKER_BINARY'],'--worker',str(d),mode] if os.getenv('ONE_WORKER_BINARY') else [sys.executable,str(HERE/'worker.py'),str(d),mode]),stdout=log,stderr=log,cwd=HERE)
 log.close()
 return public(s)

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send_json(self,data,code=200):
  blob=json.dumps(data,ensure_ascii=False).encode();self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(blob)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(blob)
 def authorized(self):
  url=urlparse(self.path)
  token=self.headers.get('X-One-Token') or parse_qs(url.query).get('token',[''])[0]
  host=self.headers.get('Host','').split(':')[0]
  return secrets.compare_digest(token,TOKEN) and host in {'127.0.0.1','localhost'}
 def file(self,path,mime=None):
  if not path.is_file():self.send_error(404);return
  size=path.stat().st_size;start,end=0,size-1;status=200
  m=re.fullmatch(r'bytes=(\d*)-(\d*)',self.headers.get('Range',''))
  if m:
   if m.group(1):start=int(m.group(1));end=min(end,int(m.group(2))) if m.group(2) else end
   elif m.group(2):start=max(0,size-int(m.group(2)))
   if start>=size or end<start:self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.end_headers();return
   status=206
  self.send_response(status);self.send_header('Content-Type',mime or mimetypes.guess_type(path.name)[0] or 'application/octet-stream');self.send_header('Content-Length',str(end-start+1));self.send_header('Accept-Ranges','bytes');self.send_header('Cache-Control','no-store')
  if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
  self.end_headers()
  try:
   with path.open('rb') as f:
    f.seek(start);remaining=end-start+1
    while remaining:
     chunk=f.read(min(256*1024,remaining))
     if not chunk:break
     self.wfile.write(chunk);remaining-=len(chunk)
  except (BrokenPipeError,ConnectionResetError):pass
 def do_GET(self):
  path=urlparse(self.path).path
  if path in ['/','/app.js','/style.css','/direct.js','/direct.css']:
   self.file(HERE/'static'/({'/':'index.html'}.get(path,path[1:])));return
  if not self.authorized():self.send_json({'error':'החיבור לאפליקציה פג. פתחו אותה מחדש.'},403);return
  try:
   with LOCK:
    if path=='/api/health':self.send_json({'app':'ONE Captions','ready':True});return
    if path=='/api/sessions':
     items=[]
     for d in DATA.iterdir():
      if (d/'session.json').is_file():
       s=json.loads((d/'session.json').read_text());items.append({'id':s['id'],'name':s['name'],'created':s['created'],'updated':s.get('updated', (d/'session.json').stat().st_mtime)})
     self.send_json(sorted(items,key=lambda x:x['updated'],reverse=True));return
    parts=path.strip('/').split('/')
    if len(parts)==3 and parts[:2]==['api','session']:self.send_json(public(load(parts[2])));return
    if len(parts)==3 and parts[0]=='media':
     s=load(parts[1]);d=folder(s['id'])
     if parts[2]=='thumbnail':
      file=d/'thumbnail.jpg'
      if not file.is_file():
       source=d/'preview.mp4' if (d/'preview.mp4').is_file() else d/'source'
       subprocess.run([core.ffmpeg(),'-v','error','-y','-ss','0.5','-i',str(source),'-frames:v','1','-vf','scale=320:-2',str(file)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20)
     elif parts[2]=='preview':file=d/'preview.mp4'
     elif parts[2]=='export' and s['exports']:file=Path(s['exports'][-1]['video'])
     else:raise ValueError('הסרטון אינו זמין.')
    else:self.send_error(404);return
   self.file(file,'image/jpeg' if file.suffix=='.jpg' else 'video/mp4')
  except Exception:self.send_json({'error':'לא ניתן לפתוח את הסרטון או את הפרויקט.'},400)
 def do_POST(self):
  if not self.authorized():self.send_json({'error':'החיבור לאפליקציה פג. פתחו אותה מחדש.'},403);return
  path=urlparse(self.path).path
  try:
   length=int(self.headers.get('Content-Length','0'))
   if path=='/api/upload':
    if not 0<length<=2*1024**3:raise ValueError('בחרו סרטון בגודל של עד 2GB.')
    name=Path(unquote(self.headers.get('X-Filename','video.mp4'))).name
    if Path(name).suffix.lower() not in {'.mp4','.mov'}:raise ValueError('בחרו סרטון MP4 או MOV.')
    import tempfile
    with tempfile.TemporaryDirectory() as td:
     source=Path(td)/name
     with source.open('wb') as f:
      remaining=length
      while remaining:
       chunk=self.rfile.read(min(1024*1024,remaining))
       if not chunk:raise ValueError('העלאת הסרטון נעצרה. נסו שוב.')
       f.write(chunk);remaining-=len(chunk)
     with LOCK:self.send_json(create(source,name))
    return
   if length>64*1024:raise ValueError('הבקשה ארוכה מדי.')
   data=json.loads(self.rfile.read(length) or '{}')
   if path=='/api/chat':
    from ai_provider import DEFAULT,context,interpret_bounded
    sid=data['id'];text=str(data['text']).strip()
    if not text or len(text)>1200:raise ValueError('כתבו הוראה קצרה לעיצוב או לתיקון הכתוביות.')
    with LOCK:
     s=load(sid)
     if busy(s) or sid in CHATS:raise ValueError('אני עדיין מסיים את הפעולה הקודמת.')
     # Prepare first: context/persistence failures must not leave a busy lease.
     s['messages'].append({'role':'user','text':text});s.pop('chat_error',None)
     request=context(s,text);revision=s['revision'];save(s);CHATS.add(sid)
    try:
     # Inference must not hold the session/video lock: playback and polling continue.
     from fast_commands import local_plan
     started=time.perf_counter();plan=local_plan(s,text);route='fast' if plan else 'ai'
     if plan is None:plan=interpret_bounded(DEFAULT,request)
     interpreted=time.perf_counter()
     with LOCK:
      s=load(sid)
      if s['revision']!=revision:raise ValueError('הסרטון השתנה בזמן הבקשה. נסו שוב.')
      old_settings=dict(s['settings']);reply,changed=execute(s,plan,text)
      if changed:
       if (len(plan['actions'])>1 or plan['actions'][0]['op'] not in ('undo','redo')) and (any(old_settings.get(k)!=s['settings'].get(k) for k in ('font_size_ratio','max_words','max_width_ratio')) or any(a['op']=='replace' for a in plan['actions'])):reflow(s)
       s['revision']+=1
      s['messages'].append({'role':'assistant','text':reply});s['chat_timing']={'route':route,'interpret_ms':(interpreted-started)*1000,'apply_ms':(time.perf_counter()-interpreted)*1000};save(s)
    except Exception as exc:
     message=str(exc) if isinstance(exc,ValueError) else 'העוזר לא הצליח להשלים את הבקשה. התיקונים נשמרו. אפשר לשלוח שוב.'
     with LOCK:
      s=load(sid);s['chat_error']=message;s['messages'].append({'role':'assistant','text':message});save(s)
    finally:
     with LOCK:
      CHATS.discard(sid);save(load(sid))
    with LOCK:self.send_json(public(load(sid)))
    return
   with LOCK:
    if path=='/api/import':self.send_json(create(data['path']));return
    if path=='/api/native-result':
     s=load(data['id'])
     self.send_json({'path':s['exports'][-1]['video'] if s['exports'] else None});return
    sid=data['id'];s=load(sid);before=snapshot(s)
    if (busy(s) or sid in CHATS) and path in {'/api/direct','/api/chat','/api/preset','/api/edit','/api/undo','/api/redo','/api/transcribe','/api/export'}:raise ValueError('הסרטון בעיבוד. אפשר להמשיך לערוך כשנסיים.')
    if path=='/api/direct':
     if data.get('revision')!=s['revision']:raise ValueError('הסרטון השתנה. נסו את העריכה שוב.')
     actions=data.get('actions')
     if not isinstance(actions,list) or any(not isinstance(a,dict) or a.get('op') not in ('set','word_style') for a in actions):raise ValueError('העריכה אינה תקינה.')
     old_settings=dict(s['settings']);reply,changed=execute(s,{'actions':actions},str(data.get('label','עריכה ישירה'))[:150])
     if changed:
      if any(old_settings.get(k)!=s['settings'].get(k) for k in ('font_size_ratio','max_words','max_width_ratio')):reflow(s)
      s['messages'].append({'role':'assistant','text':reply})
    elif path=='/api/preset':
     reply,_=execute(s,{'actions':[{'op':'preset','value':data['preset']}]},'בחירת סגנון');reflow(s)
     s['messages'].append({'role':'assistant','text':reply})
    elif path=='/api/edit':
     index=int(data['index']);text=str(data['text']).strip()
     if not text or len(text)>500:raise ValueError('כתבו עד 500 תווים בשורה.')
     if not 0<=index<len(s['cues']):raise ValueError('השורה אינה זמינה.')
     if ' '.join(s['cues'][index]['lines'])!=text:
      checkpoint(s,'עריכת שורת כתוביות');s['last_change']=None;s['cues'][index]['lines']=[text];s['manual']=True;reflow(s)
    elif path in ('/api/undo','/api/redo'):
     reply=undo(s) if path=='/api/undo' else redo(s)
     s['messages'].append({'role':'assistant','text':reply})
    elif path=='/api/transcribe':self.send_json(start(s,'transcribe'));return
    elif path=='/api/export':
     target=Path(data['target']).expanduser().resolve()
     if target.suffix.lower()!='.mp4':raise ValueError('בחרו שם קובץ MP4.')
     self.send_json(start(s,'export',str(target)));return
    else:self.send_error(404);return
    if snapshot(s)!=before:s['revision']=s.get('revision',0)+1
    save(s);self.send_json(public(s))
  except ValueError as exc:self.send_json({'error':str(exc)},400)
  except Exception as exc:
   print(type(exc).__name__,str(exc),file=sys.stderr,flush=True)
   self.send_json({'error':'לא הצלחנו להשלים את הפעולה. נסו שוב.'},400)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=0);parser.add_argument('--runtime',type=Path)
 args=parser.parse_args();server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
 runtime={'port':server.server_port,'token':TOKEN}
 if args.runtime:write(args.runtime,runtime)
 print(json.dumps(runtime),flush=True)
 import signal
 from ai_provider import DEFAULT
 def stop(*_):
  if hasattr(DEFAULT,'close'):DEFAULT.close()
  raise SystemExit(0)
 signal.signal(signal.SIGTERM,stop)
 server.serve_forever()

if __name__=='__main__':main()
