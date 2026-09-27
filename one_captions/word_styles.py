"""Portable, declarative word/phrase styles shared by live Preview and ASS export.
Rules carry scope and an effects slot for future animation adapters.
"""
import math,re,copy
NUMERIC={'font_size':(16,250),'scale':(.5,3),'outline':(0,15),'shadow':(0,10),'glow':(0,15),'opacity':(0,1)}
BOOL=('bold','underline','italic')
COLOR=('color','outline_color')

def normalized(text):return ''.join(c for c in text if c.isalnum()).lower()
def validate(styles):
 if not isinstance(styles,dict) or not styles:raise ValueError('לא צוין עיצוב למילה.')
 for k,v in styles.items():
  if k in NUMERIC:
   lo,hi=NUMERIC[k]
   if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('ערך העיצוב למילה אינו תקין.')
  elif k in BOOL:
   if type(v)!=bool:raise ValueError('ערך העיצוב למילה אינו תקין.')
  elif k in COLOR:
   if not isinstance(v,str) or not re.fullmatch('#[0-9a-fA-F]{6}',v):raise ValueError('הצבע אינו תקין.')
  else:raise ValueError('האפקט הזה אינו נתמך עדיין.')
 return copy.deepcopy(styles)

def edit(session,action):
 target=action.get('word');occurrence=action.get('occurrence');incoming=action.get('styles')
 if action.get('mode')=='adjust' and isinstance(incoming,dict):
  for k,v in incoming.items():
   if k in NUMERIC and (type(v) not in (int,float) or not math.isfinite(v) or k=='scale' and v<=0):raise ValueError('השינוי היחסי אינו תקין.')
  checked={k:(max(NUMERIC[k][0],min(NUMERIC[k][1],v)) if k in NUMERIC else v) for k,v in incoming.items()}
  validate(checked);styles=copy.deepcopy(incoming)
 else:styles=validate(incoming)
 if not isinstance(target,str) or not target.strip() or len(target)>150:raise ValueError('ציינו מילה או ביטוי לעיצוב.')
 tokens=[normalized(t) for t in target.split()]
 if not all(tokens):raise ValueError('המילה אינה תקינה.')
 if occurrence is not None and (type(occurrence)!=int or not 1<=occurrence<=10000):raise ValueError('מספר ההופעה אינו תקין.')
 rules=session.setdefault('word_styles',[])
 sequence=0
 for existing in rules:
  for field in existing['styles']:
   existing.setdefault('priorities',{}).setdefault(field,sequence+1);sequence=max(sequence,existing['priorities'][field])
 rule=next((r for r in rules if r['tokens']==tokens and r.get('occurrence')==occurrence),None)
 if rule is None:
  rule={'target':target,'tokens':tokens,'occurrence':occurrence,'styles':{},'effects':[]};rules.append(rule)
 previous=None
 if action.get('mode','set') not in ('set','adjust'):raise ValueError('אופן השינוי אינו תקין.')
 for field,value in styles.items():
  old=rule['styles'].get(field,1 if field in ('scale','opacity') else session['width']*session['settings']['font_size_ratio'] if field=='font_size' else session['width']*session['settings']['font_size_ratio']*session['settings']['outline_ratio'] if field=='outline' else session['settings'].get(field,False if field in BOOL else 0))
  if action.get('mode')=='adjust' and field in NUMERIC:
   value=old*value if field=='scale' else old+value
   lo,hi=NUMERIC[field];value=max(lo,min(hi,value))
  rule['styles'][field]=value;sequence+=1;rule.setdefault('priorities',{})[field]=sequence
  if field in NUMERIC and old!=value:previous={'field':field,'word':target,'occurrence':occurrence,'before':old,'after':value,'direction':1 if value>old else -1}
 return previous

def resolve(session):
 # A flattened token stream makes ordinal scopes stable across cue resegmentation.
 stream=[];result=[]
 important=set(__import__('domain').important_words(session))
 for ci,cue in enumerate(session['cues']):
  cue_styles=[];result.append(cue_styles)
  for line in cue['lines']:
   for token in line.split():
    k=normalized(token);style={}
    color=session.get('colors',{}).get(k,'#CAED65' if k in important else None)
    if color:style.update(color=color,bold=True)
    cue_styles.append(style);stream.append((k,style,{}))
 for rule_index,rule in enumerate(session.get('word_styles',[])):
  target=rule['tokens'];count=0;i=0
  while i<=len(stream)-len(target):
   if [p[0] for p in stream[i:i+len(target)]]==target:
    count+=1
    if rule.get('occurrence') in (None,count):
     for _,style,priorities in stream[i:i+len(target)]:
      for field,value in rule['styles'].items():
       priority=rule.get('priorities',{}).get(field,rule_index+1)
       if priority>=priorities.get(field,0):style[field]=value;priorities[field]=priority
    i+=len(target)
   else:i+=1
 return result
