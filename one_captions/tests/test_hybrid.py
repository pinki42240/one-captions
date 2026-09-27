import copy,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_domain import session
from domain import execute,snapshot,undo,redo
from fast_commands import local_plan,interpret
from word_styles import resolve
from adapter import decorated_ass,ROOT
from PIL import ImageFont
class HybridTests(unittest.TestCase):
 def test_required_sequence(self):
  s=session();s.update(width=1080,height=1920,cues=[{'start':0,'end':2,'lines':['רפאל קוקו רפאל קוקו']}])
  states=[]
  for t in ['שים את הכתוביות למטה','עוד קצת','תגדיל אותן','קצת פחות','תעשה את רפאל בצהוב','תגדיל רק את רפאל','תבטל את השינוי האחרון','תחזיר אותו','תעשה את כל ההופעות של קוקו מודגשות']:
   p=local_plan(s,t);self.assertIsNotNone(p,t);execute(s,p,t);states.append(snapshot(s))
  self.assertLess(states[1]['settings']['bottom_margin_ratio'],states[0]['settings']['bottom_margin_ratio'])
  self.assertGreater(states[2]['settings']['font_size_ratio'],states[1]['settings']['font_size_ratio'])
  self.assertLess(states[3]['settings']['font_size_ratio'],states[2]['settings']['font_size_ratio'])
  self.assertEqual(states[4],states[6]);self.assertEqual(states[5],states[7])
  runs=resolve(s)[0];self.assertEqual(runs[0]['color'],'#F5D86A');self.assertGreater(runs[0]['scale'],1);self.assertTrue(runs[1]['bold']);self.assertTrue(runs[3]['bold'])
 def test_ambiguous_and_complex_fall_through(self):
  s=session()
  for text in ['עוד קצת','תעשה את רפאל יותר בולט אבל לא מוגזם','רק בפעם השנייה שמופיע רפאל תעשה אותו בזהב','תגדיל אותן אבל רק חלק','זה עדיין לא נראה טוב, תחזיר למה שהיה ותעשה משהו יותר עדין','כל פעם שאני אומר קוקו תעשה את המילה קצת יותר גדולה ובצהוב']:
   self.assertIsNone(local_plan(s,text),text)
  class Provider:
   def interpret(self,c):return {'actions':[{'op':'word_style','word':'רפאל','styles':{'scale':1.1}}]}
  s['width']=1080;p,route=interpret(s,'תעשה את רפאל יותר בולט אבל לא מוגזם',Provider());self.assertEqual(route,'ai')
 def test_word_followup_and_branch(self):
  s=session();s['width']=1080
  for text in ['תגדיל רק את רפאל','עוד קצת','קצת פחות']:execute(s,local_plan(s,text))
  self.assertGreater(s['word_styles'][0]['styles']['scale'],1.15)
  undo(s);redo(s);undo(s);execute(s,{'actions':[{'op':'word_style','word':'רפאל','styles':{'italic':True}}]});self.assertFalse(s['redo'])
 def test_phrase_ordinal_and_export(self):
  s=session();s.update(width=1080,cues=[{'start':0,'end':2,'lines':['רפאל כהן קוקו']},{'start':2,'end':4,'lines':['רפאל','כהן קוקו']}])
  style={'font_size':80,'bold':True,'underline':True,'italic':True,'color':'#D4AF37','outline':3,'shadow':2,'glow':4,'opacity':.7,'scale':1.2}
  execute(s,{'actions':[{'op':'word_style','word':'רפאל כהן','occurrence':2,'styles':style}]})
  runs=resolve(s);self.assertFalse(runs[0][0]);self.assertEqual(runs[1][0],style);self.assertEqual(runs[1][1],style);self.assertFalse(runs[1][2])
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'s.ass';font=ImageFont.truetype(str(ROOT/'fonts/NotoSansHebrew.ttf'),63);decorated_ass(s['cues'],path,s['settings'],1080,1920,font,s);ass=path.read_text()
   for tag in ['\\fs80','\\u1','\\i1','\\fscx120','\\bord3','\\shad2','\\alpha&H4D&','\\blur4','\\c&H37AFD4&']:self.assertIn(tag,ass)
  before=snapshot(s);undo(s);self.assertEqual(s.get('word_styles'),[]);redo(s);self.assertEqual(snapshot(s),before)
 def test_restore_and_subtle_edit_atomic(self):
  s=session();execute(s,{'actions':[{'op':'bigger'}]});before=snapshot(s)
  execute(s,{'actions':[{'op':'undo'},{'op':'bigger','amount':'small'}]})
  after=snapshot(s);self.assertLess(s['settings']['font_size_ratio'],before['settings']['font_size_ratio'])
  undo(s);self.assertEqual(snapshot(s),before);redo(s);self.assertEqual(snapshot(s),after)
 def test_color_update_overrides_prior_word_rule(self):
  s=session();s['width']=1080
  execute(s,{'actions':[{'op':'word_style','word':'קוקה','styles':{'color':'#FFFFFF','scale':1.2}}]})
  execute(s,local_plan(s,'תעשה את קוקה בצהוב'))
  self.assertEqual(resolve(s)[0][0]['color'],'#F5D86A');self.assertEqual(resolve(s)[0][0]['scale'],1.2)
 def test_latest_all_scope_color_keeps_ordinal_size(self):
  s=session();s.update(width=1080,cues=[{'start':0,'end':2,'lines':['רפאל רפאל']}])
  execute(s,{'actions':[{'op':'word_style','word':'רפאל','styles':{'color':'#FFFFFF'}}]})
  execute(s,{'actions':[{'op':'word_style','word':'רפאל','occurrence':2,'styles':{'color':'#D4AF37','scale':1.2}}]})
  execute(s,local_plan(s,'תעשה את רפאל בצהוב'));runs=resolve(s)[0]
  self.assertEqual(runs[0]['color'],runs[1]['color']);self.assertEqual(runs[1]['scale'],1.2)
 def test_all_global_fast_controls(self):
  s=session();s['width']=1080
  for t in ['פונט בגודל 72','שנה צבע לכחול','תדגיש את הכתוביות','תדגיש מילים חשובות','קו תחתון','italic','opacity 75%','glow 3','shadow 2','מקסימום 4 מילים בכל כתובית','Clean']:
   p=local_plan(s,t);self.assertIsNotNone(p,t);execute(s,p,t)
  self.assertTrue(s['important']);self.assertEqual(s['preset'],'Clean');self.assertEqual(s['settings']['opacity'],.75);self.assertTrue(s['settings']['italic']);self.assertTrue(s['settings']['underline'])
 def test_invalid_word_plan_atomic(self):
  s=session();s['width']=1080;old=copy.deepcopy(s)
  with self.assertRaises(ValueError):execute(s,{'actions':[{'op':'word_style','word':'רפאל','styles':{'bold':True}},{'op':'word_style','word':'קוקו','styles':{'scale':99}}]})
  self.assertEqual(s,old)
if __name__=='__main__':unittest.main()
