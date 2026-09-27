"""Conservative compositional fast lane. Full utterances only; uncertainty => AI.
This is an optimization in front of the provider, never its replacement.
"""
import re
from domain import PRESETS
COLORS={'צהוב':'#F5D86A','לבן':'#FFFFFF','ירוק':'#CAED65','אדום':'#FF7D8C','כחול':'#79AEFF','שחור':'#101010','זהב':'#D4AF37','ורוד':'#FF7D8C'}
NUMBERS={'אחת':1,'אחד':1,'שתיים':2,'שתי':2,'שניים':2,'שלוש':3,'שלושה':3,'ארבע':4,'ארבעה':4,'חמש':5,'חמישה':5,'שש':6,'שישה':6}

def local_plan(session,text):
 t=re.sub(r'\s+',' ',text.strip().strip('.!?')).lower()
 def plan(**a):return {'actions':[a]}
 if session.get('manual') and t in ('זהו תיקנתי את מה שצריך','תיקנתי את מה שצריך','סיימתי לתקן','זהו סיימתי לתקן'):
  return plan(op='clarify',question='התיקונים שלך נשמרו. אפשר להמשיך לערוך או לייצא את הסרטון.')
 if t in ('undo','תבטל','בטל','תבטל את השינוי האחרון','תבטל שינוי אחרון','תחזיר למה שהיה קודם','תחזיר למצב הקודם','תחזיר למה שהיה','תבטל את זה'):return plan(op='undo')
 if t in ('redo','תחזיר אותו','בצע שוב','תעשה שוב','תעשה שוב את מה שביטלתי','תעשה שוב את השינוי שביטלתי','תחזיר את השינוי האחרון') and session.get('redo'):return plan(op='redo')
 m=re.fullmatch(r'(?:תחזיר|כמו שהיה) (?:למה שהיה )?לפני (שני|\d+) שינויים',t)
 if m:return plan(op='undo',steps=2 if m[1]=='שני' else int(m[1]))
 if t in ('עוד','עוד קצת','עוד מעט','קצת יותר') and session.get('last_change'):return plan(op='repeat',amount='small' if t!='עוד' else 'normal')
 if t in ('קצת פחות','לא כל כך הרבה','לא כל כך גדול','לא כל כך קטן') and session.get('last_change'):return plan(op='soften',**({'field':'font_size_ratio'} if ('גדול' in t or 'קטן' in t) and not session.get('last_change',{}).get('word') else {}))
 # Never partially consume a compound, scoped, temporal or subjective instruction.
 if re.search(r'\b(?:אבל|ואז|רק בפעם|השנייה|עדיין|מוגזם|עדין|כל פעם|בשניה|בשנייה)\b',t):return None
 for name in PRESETS:
  if t in (name.lower(),'בחר '+name.lower(),'סגנון '+name.lower(),'preset '+name.lower(),'תבחר '+name.lower()):return plan(op='preset',value=name)
 obj=r'(?:את )?(?:הכתוביות|כתוביות|אותן|אותם|הפונט|פונט|הטקסט|טקסט)'
 m=re.fullmatch(r'(?:זה|הכתוביות|הטקסט) לא מספיק (למטה|למעלה|גדול|קטן)',t)
 if m:return plan(op={'למטה':'lower','למעלה':'raise','גדול':'bigger','קטן':'smaller'}[m[1]])
 m=re.fullmatch(r'(?:שים|תשים|מקם) (?:'+obj+r' )?(למטה|למעלה|באמצע)',t)
 if m:return plan(op={'למטה':'bottom','למעלה':'top','באמצע':'center'}[m[1]])
 m=re.fullmatch(r'(?:תעשה|שים) (?:'+obj+r' )?(?:קצת )?(?:יותר )?(גדולות יותר|גדולות|קטנות יותר|קטנות)',t)
 if m:return plan(op='bigger' if m[1].startswith('גדולות') else 'smaller',amount='small' if 'קצת' in t else 'normal')
 m=re.fullmatch(r'(תדגיש|תעשה נטוי|תוסיף קו תחתון|תסיר הדגשה|תסיר קו תחתון) '+obj,t)
 if m:
  field='bold' if 'הדגש' in m[1] or m[1]=='תדגיש' else 'italic' if 'נטוי' in m[1] else 'underline'
  return plan(op='set',field=field,value=not m[1].startswith('תסיר'))
 m=re.fullmatch(r'(תגדיל|הגדל|תקטין|הקטן|תעלה|העלה|תוריד|הורד)(?: '+obj+r')?(?: (קצת|מעט))?',t)
 if m:return plan(op={'תגדיל':'bigger','הגדל':'bigger','תקטין':'smaller','הקטן':'smaller','תעלה':'raise','העלה':'raise','תוריד':'lower','הורד':'lower'}[m[1]],amount='small' if m[2] else 'normal')
 m=re.fullmatch(r'(?:עוד )?(?:קצת|מעט) (?:יותר )?(למעלה|למטה|גדול|קטן)',t)
 if m:return plan(op={'למעלה':'raise','למטה':'lower','גדול':'bigger','קטן':'smaller'}[m[1]],amount='small')
 m=re.fullmatch(r'(?:תעשה (?:'+obj+r' )?)?(קצת |מעט )?(?:עוד |יותר )?(גדול(?:ות)?|קטן(?:ות)?|למעלה|למטה)',t)
 if m:return plan(op={'גדול':'bigger','גדולות':'bigger','קטן':'smaller','קטנות':'smaller','למעלה':'raise','למטה':'lower'}[m[2]],amount='small' if m[1] else 'normal')
 m=re.fullmatch(r'(?:פונט|גודל פונט|פונט בגודל|תעשה פונט בגודל) (\d+(?:\.\d+)?)',t)
 if m:return plan(op='set',field='font_size_ratio',value=float(m[1])/session['width'])
 m=re.fullmatch(r'(?:תעשה |שים )?(?:מקסימום |עד )?(\d+|'+ '|'.join(NUMBERS)+r') מילים (?:בכל פעם|בכל כתובית|בכתובית)',t)
 if m:return plan(op='set',field='max_words',value=int(m[1]) if m[1].isdigit() else NUMBERS[m[1]])
 m=re.fullmatch(r'(?:שנה (?:את )?הצבע ל|שנה צבע ל|תעשה (?:'+obj+r' )?ב)(.+)',t)
 if m and m[1] in COLORS:return plan(op='set',field='primary_color',value=COLORS[m[1]])
 if t in ('תדגיש מילים חשובות','תדגיש את המילים החשובות','הדגש מילים חשובות'):return plan(op='highlight',value=True)
 m=re.fullmatch(r'(?:תעשה|שים) '+obj+r' (מודגשות|מודגש|נטויות|נטוי|עם קו תחתון)',t)
 if m:return plan(op='set',field='bold' if m[1].startswith('מודגש') else 'italic' if m[1].startswith('נטוי') else 'underline',value=True)
 # Target grammar: one explicit word/phrase, optional all-occurrences quantifier.
 m=re.fullmatch(r'(?:תעשה|שים|תדגיש|תגדיל|תקטין) (?:את )?(?:כל ההופעות של |רק )?(?:את )?(?:המילה |הביטוי )?(.+?) (ב(?:צהוב|לבן|ירוק|אדום|כחול|שחור|זהב|ורוד)|מודגש(?:ות)?|גדול יותר|קטן יותר|עם קו תחתון|נטוי)',t)
 if m:
  target=m[1].strip('״"');trait=m[2]
  if not target or len(target.split())>5 or any(w in target.split() for w in ('לא','יותר','אותן','הכתוביות','כתוביות','אותם')):return None
  if trait.startswith('ב'):
   color=COLORS[trait[1:]]
   if len(target.split())==1:return plan(op='word_color',word=target,color=color)
   return plan(op='word_style',word=target,styles={'color':color})
  styles={'bold':True} if trait.startswith('מודגש') else {'underline':True} if trait=='עם קו תחתון' else {'italic':True} if trait=='נטוי' else {'scale':1.15 if trait=='גדול יותר' else 1/1.15}
  return plan(op='word_style',word=target,styles=styles,mode='adjust' if 'scale' in styles else 'set')
 m=re.fullmatch(r'(תגדיל|תקטין|תדגיש) (?:את )?(?:רק |כל ההופעות של )?(?:את )?(?:המילה |הביטוי )?(.+)',t)
 if m:
  target=m[2].strip('״"')
  if not target or len(target.split())>5 or any(w in target.split() for w in ('לא','קצת','יותר','אותן','אותם','כתוביות','הכתוביות','הפונט')):return None
  return plan(op='word_style',word=target,styles={'bold':True} if m[1]=='תדגיש' else {'scale':1.15 if m[1]=='תגדיל' else 1/1.15},mode='set' if m[1]=='תדגיש' else 'adjust')
 traits={'תדגיש':('bold',True),'הדגש':('bold',True),'מודגש':('bold',True),'קו תחתון':('underline',True),'תוסיף קו תחתון':('underline',True),'italic':('italic',True),'נטוי':('italic',True),'תעשה נטוי':('italic',True),'תסיר קו תחתון':('underline',False),'תסיר הדגשה':('bold',False),'תדגיש מילים חשובות':('highlight',True),'תדגיש את המילים החשובות':('highlight',True)}
 if t in traits:
  field,value=traits[t];return plan(op='highlight',value=value) if field=='highlight' else plan(op='set',field=field,value=value)
 m=re.fullmatch(r'(?:תעשה |שנה |שים )?(opacity|אטימות|glow|זוהר|shadow|צל|outline|קו מתאר) (\d+(?:\.\d+)?)(%)?',t)
 if m:
  field={'אטימות':'opacity','זוהר':'glow','צל':'shadow','קו מתאר':'outline_ratio','outline':'outline_ratio'}.get(m[1],m[1]);value=float(m[2]);value=value/100 if m[3] or field=='opacity' and value>1 else value
  return plan(op='set',field=field,value=value)
 return None

def interpret(session,text,provider=None):
 p=local_plan(session,text)
 if p:return p,'fast'
 from ai_provider import DEFAULT,context
 return (provider or DEFAULT).interpret(context(session,text)),'ai'
