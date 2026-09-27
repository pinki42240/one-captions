"""Portable session/edit model and replaceable Hebrew intent interpreter."""
import copy
import math
import re
from collections import Counter

PRESETS = {
 'Clean': dict(font_size_ratio=.047, bottom_margin_ratio=.17, primary_color='&H00FFFFFF', outline_ratio=.035, shadow=0, bold=False),
 'Reels': dict(font_size_ratio=.058, bottom_margin_ratio=.23, primary_color='&H00FFFFFF', outline_ratio=.065, shadow=1, bold=True),
 'Bold': dict(font_size_ratio=.068, bottom_margin_ratio=.23, primary_color='&H0065EDCA', outline_ratio=.065, shadow=1, bold=True),
 'Minimal': dict(font_size_ratio=.039, bottom_margin_ratio=.13, primary_color='&H00FFFFFF', outline_ratio=.025, shadow=0, bold=False),
}
EDIT_FIELDS = ('settings','preset','cues','colors','important','pending','manual','word_styles')
STOPWORDS=set('אני אתה את הוא היא זה זו של על עם לא כן גם או אבל כי אם מה מי איך עוד יותר קצת כל פעם שים תעשה כתוביות הנה כמה'.split())


def snapshot(session):
 return {k:copy.deepcopy(session.get(k,[] if k=='word_styles' else None)) for k in EDIT_FIELDS}


def checkpoint(session,label):
 session.setdefault('redo',[]).clear()
 session['history'].append({'label':label,'snapshot':snapshot(session),'last_change':copy.deepcopy(session.get('last_change'))})


def restore(session,direction,steps=1):
 source=session.setdefault('history' if direction=='undo' else 'redo',[])
 destination=session.setdefault('redo' if direction=='undo' else 'history',[])
 if not source:return 'אין שינוי שאפשר '+('לבטל.' if direction=='undo' else 'לבצע מחדש.')
 count=min(steps,len(source))
 for _ in range(count):
  item=source.pop()
  destination.append({'label':item['label'],'snapshot':snapshot(session),'last_change':copy.deepcopy(session.get('last_change'))})
  session['word_styles']=copy.deepcopy(item['snapshot'].get('word_styles',[]));session.update(copy.deepcopy(item['snapshot']));session['last_change']=copy.deepcopy(item['last_change']) if 'last_change' in item else infer_last_change(session)
 return ('החזרתי למצב הקודם.' if count==1 else f'החזרתי למצב שלפני {count} שינויים.') if direction=='undo' else ('ביצעתי מחדש את השינוי.' if count==1 else f'ביצעתי מחדש {count} שינויים.')


def undo(session):return restore(session,'undo')
def redo(session):return restore(session,'redo')


def normalize_word(text):return ''.join(c for c in text if c.isalnum()).lower()


def important_words(session):
 if not session['important']:return []
 tokens=[normalize_word(w) for c in session['cues'] for w in ' '.join(c['lines']).split()]
 counts=Counter(t for t in tokens if len(t)>=4 and t not in STOPWORDS)
 return [t for t,_ in counts.most_common(6)]


def replace_cues(cues,old,new,time=None):
 count=0
 pattern=re.compile(r'(?<!\w)'+re.escape(old)+r'(?!\w)')
 for cue in cues:
  if time is not None and not cue['start']-.35<=time<=cue['end']+.35:continue
  text=' '.join(cue['lines'])
  text,n=pattern.subn(new,text)
  if n:
   cue['lines']=[text]
   count+=n
 return count


LIMITS={'bottom_margin_ratio':(0,1),'center_x_ratio':(0,1),'font_size_ratio':(.025,.12),'max_words':(1,12),'max_width_ratio':(.3,.95),'outline_ratio':(0,.15),'shadow':(0,5),'opacity':(0,1),'glow':(0,15)}

def infer_last_change(session):
 if not session.get('history'):return None
 before=session['history'][-1]['snapshot']['settings'];after=session['settings']
 fields=[k for k in LIMITS if before.get(k)!=after.get(k)]
 if len(fields)!=1:return None
 field=fields[0];a,b=before.get(field),after.get(field)
 if type(a) not in (int,float) or type(b) not in (int,float):return None
 return {'field':field,'before':a,'after':b,'direction':1 if b>a else -1}

def last_numeric_change(session,field=None):
 last=session.get('last_change')
 if field is None or (last and last.get('field')==field):return last
 if field not in LIMITS:return None
 history=session.get('history',[])
 for i in range(len(history)-1,-1,-1):
  before=history[i]['snapshot']['settings'];after=history[i+1]['snapshot']['settings'] if i+1<len(history) else session['settings']
  a,b=before.get(field),after.get(field)
  if type(a) in (int,float) and type(b) in (int,float) and a!=b:return {'field':field,'before':a,'after':b,'direction':1 if b>a else -1}
 return None

def ass_color(value):
 if not isinstance(value,str) or not re.fullmatch(r'#[0-9A-Fa-f]{6}',value):raise ValueError('הצבע אינו תקין.')
 return '&H00'+value[5:7]+value[3:5]+value[1:3]

def execute(session,plan,label='שינוי'):
 """Validate a complete AI plan on a copy, then commit one reversible edit."""
 actions=plan.get('actions') if isinstance(plan,dict) else None
 if not isinstance(actions,list) or not 1<=len(actions)<=8:raise ValueError('לא הצלחתי להבין את השינוי. לא שיניתי דבר.')
 if len(actions)>1 and any(isinstance(a,dict) and a.get('op')=='clarify' for a in actions):raise ValueError('הבקשה אינה חד־משמעית. לא שיניתי דבר.')
 if len(actions)>1 and isinstance(actions[0],dict) and actions[0].get('op') in ('undo','redo'):
  # Composite restoration + edits is one atomic, undoable transaction.
  trial=copy.deepcopy(session);first=actions[0];steps=first.get('steps',1)
  if type(steps)!=int or not 1<=steps<=20:raise ValueError('מספר השינויים אינו תקין.')
  reply=restore(trial,first['op'],steps)
  follow,_=execute(trial,{'actions':actions[1:]},label)
  changed=snapshot(trial)!=snapshot(session)
  if changed:
   checkpoint(session,label);session.update(snapshot(trial));session['last_change']=trial.get('last_change')
  return reply+' '+follow,changed
 trial={**session,**snapshot(session)};notes=[];last=copy.deepcopy(session.get('last_change'))
 before=snapshot(session)
 for action in actions:
  if not isinstance(action,dict):raise ValueError('הפעולה אינה תקינה.')
  action=copy.deepcopy(action);op=action.get('op')
  if op in ('bottom','center','top'):
   action.update(op='set',field='bottom_margin_ratio',value={'bottom':.13,'center':.46,'top':.75}[op]);op='set'
  elif op in ('lower','raise','bigger','smaller'):
   action.update(op='adjust',field='bottom_margin_ratio' if op in ('lower','raise') else 'font_size_ratio',direction=-1 if op in ('lower','smaller') else 1);op='adjust'
  if op in ('undo','redo'):
   if len(actions)!=1:raise ValueError('אפשר לבטל או לבצע מחדש בנפרד משינוי אחר.')
   steps=action.get('steps',1)
   if type(steps)!=int or not 1<=steps<=20:raise ValueError('מספר השינויים אינו תקין.')
   reply=restore(session,op,steps);return reply,snapshot(session)!=before
  if op=='clarify':
   if len(actions)!=1:raise ValueError('הבקשה אינה חד־משמעית. לא שיניתי דבר.')
   return 'לא שיניתי דבר. '+str(action.get('question','מה תרצו לשנות?'))[:500],False
  if op in ('set','adjust','repeat','soften'):
   field=action.get('field');value=action.get('value')
   if op in ('repeat','soften'):
    previous=last_numeric_change(trial,action.get('field'))
    if previous and previous.get('word'):
     from word_styles import edit
     current=next(r for r in trial.get('word_styles',[]) if r['target']==previous['word'] and r.get('occurrence')==previous.get('occurrence'))['styles'][previous['field']]
     amount={'small':.5,'normal':1,'large':2}.get(action.get('amount','normal'),1)
     value=current+(previous['before']-current)*.5 if op=='soften' else current+(previous['after']-previous['before'])*amount
     from word_styles import NUMERIC
     lo,hi=NUMERIC[previous['field']];value=max(lo,min(hi,value))
     last=edit(trial,{'word':previous['word'],'occurrence':previous.get('occurrence'),'styles':{previous['field']:value}});trial['last_change']=last;notes.append('עדכנתי את העיצוב של ״'+previous['word']+'״.');continue
    if not previous or previous.get('field') not in LIMITS:return 'לאיזה שינוי התכוונת? אפשר לציין מיקום או גודל.',False
    field=previous['field']
   if field not in LIMITS and not (op=='set' and field in ('bold','italic','underline','primary_color','outline_color')):raise ValueError('ההגדרה הזו אינה נתמכת כרגע.')
   old=trial['settings'].get(field,1 if field=='opacity' else .5 if field=='center_x_ratio' else 0)
   if op=='set':
    if field in ('primary_color','outline_color'):value=ass_color(value)
    elif field in ('bold','italic','underline'):
     if type(value)!=bool:raise ValueError('ההגדרה אינה תקינה.')
    elif type(value) not in (int,float) or not math.isfinite(value):raise ValueError('הערך אינו תקין.')
   elif op=='soften':value=old+(previous['before']-old)*.5
   else:
    direction=action.get('direction') if op=='adjust' else previous['direction']
    if direction not in (-1,1):raise ValueError('כיוון השינוי אינו תקין.')
    amount=action.get('amount','normal')
    if amount not in ('small','normal','large'):raise ValueError('גודל השינוי אינו תקין.')
    scale={'small':.5,'normal':1,'large':2}[amount]
    delta={'bottom_margin_ratio':.045,'center_x_ratio':.045,'font_size_ratio':old*.15,'max_words':1,'max_width_ratio':.05,'outline_ratio':.01,'shadow':1,'opacity':.1,'glow':1}[field]
    value=old+direction*delta*scale
   if field in LIMITS:
    lo,hi=LIMITS[field]
    if op=='set' and not lo<=value<=hi:raise ValueError('הערך המבוקש מחוץ לטווח האפשרי. לא שיניתי דבר.')
    value=max(lo,min(hi,value))
    if field in ('max_words','shadow'):value=int(round(value))
   trial['settings'][field]=value
   if field not in LIMITS:last=None;trial['last_change']=None
   if value!=old:
    if field in LIMITS:
     last={'field':field,'before':old,'after':value,'direction':1 if value>old else -1};trial['last_change']=last
    if field=='bottom_margin_ratio':notes.append('העליתי אותן מעט.' if value>old else 'הורדתי אותן עוד קצת.')
    elif field=='center_x_ratio':notes.append('הזזתי אותן ימינה.' if value>old else 'הזזתי אותן שמאלה.')
    elif field=='font_size_ratio':notes.append('הגדלתי מעט.' if value>old else 'הקטנתי מעט.')
    elif field=='max_words':notes.append(f'הגבלתי כל כתובית לעד {value} מילים.')
    else:notes.append('עדכנתי את הסגנון.')
  elif op=='preset':
   value=action.get('value')
   if value not in PRESETS:raise ValueError('הסגנון אינו זמין.')
   trial['preset']=value;trial['settings'].update(PRESETS[value]);last=None;trial['last_change']=None;notes.append(f'בחרתי בסגנון {value}.')
  elif op=='highlight':
   if type(action.get('value'))!=bool:raise ValueError('ההדגשה אינה תקינה.')
   trial['important']=action['value'];notes.append('הדגשתי מילים מרכזיות.' if action['value'] else 'הסרתי את ההדגשות.')
  elif op=='word_style':
   from word_styles import edit
   word_change=edit(trial,action)
   last=word_change;trial['last_change']=last
   notes.append('עדכנתי את העיצוב של ״'+str(action.get('word'))+'״.')
  elif op=='word_color':
   word=normalize_word(str(action.get('word','')));color=action.get('color');ass_color(color)
   if not word:raise ValueError('ציינו איזו מילה לצבוע.')
   trial['colors'][word]=color
   from word_styles import edit
   edit(trial,{'word':str(action['word']),'styles':{'color':color}})
   last=None;trial['last_change']=None;notes.append(f'עדכנתי את הצבע של ״{word}״.')
  elif op=='replace':
   old,new=action.get('old'),action.get('new');t=action.get('time')
   if not isinstance(old,str) or not isinstance(new,str) or not old or not new or max(len(old),len(new))>500:raise ValueError('התיקון אינו תקין.')
   if t is not None and (type(t) not in (int,float) or t<0):raise ValueError('הזמן אינו תקין.')
   correction={'old':old,'new':new,'time':t}
   if trial['cues']:
    if not replace_cues(trial['cues'],**correction):raise ValueError('לא מצאתי את הטקסט באזור המבוקש. לא שיניתי דבר.')
    trial['manual']=True
   else:trial['pending'].append(correction)
   notes.append(f'החלפתי את ״{old}״ ב־״{new}״. התזמון נשמר.' if trial['cues'] else f'אתקן ל־״{new}״ אחרי יצירת הכתוביות.')
  else:raise ValueError('הפעולה הזו אינה נתמכת. לא שיניתי דבר.')
 changed=snapshot(trial)!=before
 if changed:
  checkpoint(session,label);session.update(snapshot(trial));session['last_change']=last
 return (' '.join(notes) or 'עדכנתי את הכתוביות.') if changed else 'ההגדרות כבר במצב הזה; לא היה שינוי נוסף.',changed

def command(session,text,provider=None):
 text=text.strip()
 if not text or len(text)>1200:raise ValueError('כתבו הוראה קצרה לעיצוב או לתיקון הכתוביות.')
 # Exact preset buttons are typed local operations. Free conversation uses AI.
 if text in PRESETS:return execute(session,{'actions':[{'op':'preset','value':text}]},text)
 from fast_commands import interpret
 # Explicitly injected providers are used by provider contract tests.
 if provider:
  from ai_provider import context
  plan=provider.interpret(context(session,text))
 else:plan,_=interpret(session,text)
 return execute(session,plan,text)
