"""UI adapter. Existing engine modules are only read/imported, never edited."""
import os
import copy
import json
import re
import sys
from pathlib import Path
ROOT=Path(os.getenv('ONE_ENGINE_ROOT', Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(ROOT))
import captions as core
from domain import PRESETS,normalize_word,important_words


def dimensions(source):
 info=core.probe(source)
 video=next(s for s in info['streams'] if s['codec_type']=='video' and not s.get('disposition',{}).get('attached_pic'))
 if not any(s['codec_type']=='audio' for s in info['streams']):raise ValueError('לא נמצא אודיו בסרטון. בחרו סרטון עם דיבור.')
 width,height=int(video['width']),int(video['height'])
 rotation=next((float(s.get('rotation',0)) for s in video.get('side_data_list',[]) if 'rotation' in s),0)
 if abs(rotation)%180==90:width,height=height,width
 return {'width':width,'height':height,'duration':float(info['format']['duration'])}


def base_settings():
 result=core.load_preset('reels')
 result.update(PRESETS['Reels'])
 return result


def reflow(session):
 if not session.get('raw'):return
 # Preserve manually edited cue timings. Original words are resegmented only before manual edits.
 if session['manual']:
  from PIL import ImageFont
  font=core.caption_font(ROOT/'fonts'/session['settings']['font_file'],max(16,round(session['width']*session['settings']['font_size_ratio'])))
  rebuilt=[]
  for cue in session['cues']:
   tokens=' '.join(cue['lines']).split()
   groups=[];group=[]
   for token in tokens:
    proposed=group+[token]
    fits=core.layout_words([{'text':t} for t in proposed],font,session['width']*session['settings']['max_width_ratio'])
    if group and (len(proposed)>session['settings']['max_words'] or fits is None):
     groups.append(group);group=[]
    group.append(token)
   if group:groups.append(group)
   used=0
   for group in groups:
    start=cue['start']+(cue['end']-cue['start'])*used/max(1,len(tokens))
    used+=len(group)
    end=cue['start']+(cue['end']-cue['start'])*used/max(1,len(tokens))
    lines=core.layout_words([{'text':t} for t in group],font,session['width']*session['settings']['max_width_ratio'])
    rebuilt.append({'start':start,'end':end,'lines':lines or [' '.join(group)]})
  session['cues']=rebuilt
 else:
  session['cues'],_=core.make_cues(session['raw']['words'],session['settings'],session['width'],session['height'],session['duration'])



def decorated_ass(cues,path,preset,width,height,font,session):
 core.ass_write(cues,path,preset,width,height,font)
 from word_styles import resolve
 styles=resolve({**session,'cues':cues})
 lines=path.read_text().splitlines();output=[];ci=0
 def color(hex):return '&H'+hex[5:7]+hex[3:5]+hex[1:3]+'&'
 base_size=max(16,round(width*preset['font_size_ratio']))
 for line in lines:
  if line.startswith('Style:'):
   values=line.split(',');values[7]='-1' if preset.get('bold',True) else '0';values[8]='-1' if preset.get('italic') else '0';values[9]='-1' if preset.get('underline') else '0'
   line=','.join(values)
  elif line.startswith('Dialogue:'):
   fields=line.split(',',9);index=0;glows=[]
   def decorate(match):
    nonlocal index
    token=match.group(0)
    if not token.strip('\u202a\u202b\u202c\u202d\u202e\u200e\u200f'):return token
    st=styles[ci][index] if index<len(styles[ci]) else {};index+=1
    tags=[]
    for key,tag in [('bold','b'),('italic','i'),('underline','u')]:
     if key in st:tags.append('\\'+tag+str(int(st[key])))
    if 'color' in st:tags.append('\\c'+color(st['color']))
    if 'outline_color' in st:tags.append('\\3c'+color(st['outline_color']))
    if 'font_size' in st:tags.append('\\fs'+str(st['font_size']))
    if 'scale' in st:tags.extend(['\\fscx'+str(st['scale']*100),'\\fscy'+str(st['scale']*100)])
    for key,tag in [('outline','bord'),('shadow','shad')]:
     if key in st:tags.append('\\'+tag+str(st[key]))
    if 'opacity' in st:tags.append('\\alpha&H%02X&'%round((1-st['opacity']*preset.get('opacity',1))*255))
    glows.append(st.get('glow',preset.get('glow',0)))
    restore='\\b'+str(int(preset.get('bold',True)))+'\\i'+str(int(preset.get('italic',False)))+'\\u'+str(int(preset.get('underline',False)))+'\\c'+preset['primary_color']+'&\\3c'+preset['outline_color']+'&\\fs'+str(base_size)+'\\fscx100\\fscy100\\bord'+str(base_size*preset['outline_ratio'])+'\\shad'+str(preset.get('shadow',0))+global_tags
    return '{'+''.join(tags)+'}'+token+'{'+restore+'}' if tags else token
   global_tags='\\alpha&H%02X&'%round((1-preset.get('opacity',1))*255)
   position_tags='\\an2\\pos('+str(round(width*preset.get('center_x_ratio',.5)))+','+str(round(height*(1-preset['bottom_margin_ratio'])))+')' if 'center_x_ratio' in preset else ''
   pieces=re.split(r'(\{[^}]*\}|\\N)',fields[9])
   fields[9]='{'+position_tags+global_tags+'}'+''.join(p if p.startswith('{') or p=='\\N' else re.sub(r'[^\s\u202a-\u202e\u200e\u200f]+',decorate,p) for p in pieces)
   # Glow is a separate lightweight ASS layer behind the foreground. Shape/timing
   # are identical; transparent unstyled words keep their layout in the layer.
   if any(glows):
    glow_fields=line.split(',',9);idx=0
    def glow_token(match):
     nonlocal idx
     token=match.group(0)
     if not token.strip('\u202a\u202b\u202c\u202d\u202e\u200e\u200f'):return token
     st=styles[ci][idx] if idx<len(styles[ci]) else {};idx+=1
     g=st.get('glow',preset.get('glow',0));opacity=preset.get('opacity',1)*st.get('opacity',1)
     tags='\\alpha&HFF&' if not g or not opacity else ('\\alpha&H%02X&'%round((1-.5*opacity)*255))+'\\blur'+str(g)+'\\bord'+str(max(1,g/2))+'\\3c'+(color(st['color']) if 'color' in st else preset['primary_color']+'&')
     if 'scale' in st:tags+='\\fscx'+str(st['scale']*100)+'\\fscy'+str(st['scale']*100)
     if 'font_size' in st:tags+='\\fs'+str(st['font_size'])
     for key,tag in [('bold','b'),('italic','i'),('underline','u')]:
      if key in st:tags+='\\'+tag+str(int(st[key]))
     return '{\\rDefault'+tags+'}'+token
    glow_fields[9]='{'+position_tags+'}'+''.join(p if p.startswith('{') or p=='\\N' else re.sub(r'[^\s\u202a-\u202e\u200e\u200f]+',glow_token,p) for p in pieces)
    output.append(','.join(glow_fields));fields[0]='Dialogue: 1'
   line=','.join(fields);ci+=1
  output.append(line)
 path.write_text('\n'.join(output)+'\n',encoding='utf-8')
