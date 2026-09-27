"""One isolated background job; shared engine remains unmodified."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from adapter import ROOT,core,decorated_ass

DIR=Path(sys.argv[1])
MODE=sys.argv[2]
request=json.loads((DIR/'job-request.json').read_text())
session=request['session']

def atomic(path,data):
 temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False));temp.replace(path)

def progress(phase,percent,status='running',**extra):
 atomic(DIR/'progress.json',dict(phase=phase,percent=percent,status=status,mode=MODE,**extra))

class ProgressWriter:
 def __init__(self,stream):self.stream=stream
 def write(self,text):
  self.stream.write(text);self.stream.flush()
  m=re.search(r'תמלול(?: מילולי)?:\s*(\d+(?:\.\d+)?)',text)
  if m:progress('יוצר כתוביות',min(88,12+float(m.group(1))/session['duration']*74))
  return len(text)
 def flush(self):self.stream.flush()

try:
 progress('מכין את הסרטון',4)
 if MODE=='transcribe':
  with tempfile.TemporaryDirectory(prefix='one-captions-') as td:
   audio=Path(td)/'speech.wav'
   core.run([core.ffmpeg(),'-v','error','-y','-i',DIR/'source','-map','0:a:0','-vn','-ar','16000','-ac','1',audio])
   progress('מקשיב לסרטון',12)
   sys.stdout=ProgressWriter(sys.stdout)
   words,segments,metadata=core.transcribe(audio,'')
   atomic(DIR/'raw-transcript.json',{'model':core.MODEL_ID,'words':words,'segments':segments,'transcription':metadata})
   progress('הכתוביות מוכנות',100,'complete')
 else:
  progress('מכין לייצוא',5)
  with tempfile.TemporaryDirectory(prefix='one-export-') as td:
   srt=Path(td)/'edited.srt'
   core.srt_write(session['cues'],srt)
   # Adapt in this worker process only. No global preset or engine files are changed.
   original_ass=core.ass_write
   def custom_ass(cues,path,preset,width,height,font):
    core.ass_write=original_ass
    try:decorated_ass(cues,path,preset,width,height,font,session)
    finally:core.ass_write=custom_ass
   core.ass_write=custom_ass
   core.load_preset=lambda _:dict(session['settings'])
   original_run=core.run
   def render_progress(command,**kwargs):
    if str(command[-1]).endswith('render.mp4'):
     cmd=[str(x) for x in command]
     cmd[1:1]=['-progress','pipe:1','-nostats']
     with subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,**kwargs) as proc:
      # stderr is drained separately so long jobs cannot deadlock.
      import threading
      errors=[]
      reader=threading.Thread(target=lambda:errors.extend(proc.stderr.readlines()),daemon=True);reader.start()
      for line in proc.stdout:
       if line.startswith('out_time_us='):
        value=line.split('=',1)[1].strip()
        if value.isdigit():progress('מייצא את הסרטון',min(96,8+int(value)/1e6/session['duration']*86))
      code=proc.wait();reader.join()
      if code:raise RuntimeError(''.join(errors)[-2000:])
    else:original_run(command,**kwargs)
   core.run=render_progress
   job=core.process(DIR/'source',SimpleNamespace(preset='ui',srt=str(srt),prompt='',terms=None))
   target=Path(request['target'])
   target.parent.mkdir(parents=True,exist_ok=True)
   tmp=target.with_name(target.name+'.one-partial')
   shutil.copy2(job/'captioned.mp4',tmp)
   os.replace(tmp,target)
   (job/'one-session.json').write_text(json.dumps(session,ensure_ascii=False,indent=2))
   # Store a portable editable sidecar with each exported video.
   sidecar=target.with_suffix('.srt')
   if not sidecar.exists():shutil.copy2(job/'captions.srt',sidecar)
   atomic(DIR/'export-result.json',{'video':str(target),'job':str(job),'name':target.name,'revision':session.get('revision',0)})
   progress('הסרטון מוכן',100,'complete')
except Exception as exc:
 import traceback
 traceback.print_exc()
 progress('לא הצלחנו להשלים את הפעולה',0,'error',error='לא הצלחנו לעבד את הסרטון. אפשר לנסות שוב או לבחור סרטון אחר.')
 sys.exit(1)
