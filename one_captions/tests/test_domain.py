import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from domain import execute,command,snapshot,undo,redo,checkpoint,infer_last_change
from adapter import base_settings,reflow

def session():
 return {'settings':base_settings(),'preset':'Reels','cues':[{'start':11,'end':13,'lines':['קוקה זה מבצע']}],'colors':{},'important':False,'pending':[],'manual':False,'history':[],'messages':[]}
def run(s,**action):return execute(s,{'actions':[action]})
class IntentTests(unittest.TestCase):
 def test_relative_sequence(self):
  s=session();run(s,op='set',field='bottom_margin_ratio',value=.13)
  run(s,op='adjust',field='bottom_margin_ratio',direction=-1);self.assertAlmostEqual(s['settings']['bottom_margin_ratio'],.085)
  run(s,op='repeat',amount='small');self.assertAlmostEqual(s['settings']['bottom_margin_ratio'],.0625)
  run(s,op='adjust',field='font_size_ratio',direction=1);large=s['settings']['font_size_ratio']
  run(s,op='soften');small=s['settings']['font_size_ratio'];self.assertLess(small,large)
  undo(s);self.assertEqual(s['settings']['font_size_ratio'],large)
  redo(s);self.assertEqual(s['settings']['font_size_ratio'],small)
 def test_undo_two_branch_and_context(self):
  s=session();run(s,op='adjust',field='bottom_margin_ratio',direction=-1);first=snapshot(s)
  run(s,op='repeat');run(s,op='repeat');run(s,op='undo',steps=2);self.assertEqual(snapshot(s),first)
  self.assertEqual(len(s['redo']),2);run(s,op='adjust',field='font_size_ratio',direction=1);self.assertFalse(s['redo'])
 def test_restore_full_editable_state(self):
  s=session();old=snapshot(s)
  execute(s,{'actions':[{'op':'preset','value':'Bold'},{'op':'word_color','word':'מבצע','color':'#F5D86A'},{'op':'replace','old':'קוקה','new':'קוקו קוקו','time':12},{'op':'highlight','value':True}]})
  edited=snapshot(s);undo(s);self.assertEqual(snapshot(s),old);redo(s);self.assertEqual(snapshot(s),edited)
  self.assertEqual((s['cues'][0]['start'],s['cues'][0]['end']),(11,13))
 def test_invalid_plan_atomic(self):
  s=session();old=copy.deepcopy(s)
  with self.assertRaises(ValueError):execute(s,{'actions':[{'op':'adjust','field':'font_size_ratio','direction':1},{'op':'set','field':'max_words','value':999}]})
  self.assertEqual(s,old)
 def test_noop_and_ambiguity(self):
  s=session();run(s,op='set',field='bottom_margin_ratio',value=0);n=len(s['history'])
  reply,changed=run(s,op='adjust',field='bottom_margin_ratio',direction=-1);self.assertFalse(changed);self.assertEqual(len(s['history']),n)
  s=session();reply,changed=run(s,op='repeat');self.assertFalse(changed)
 def test_provider_receives_context(self):
  s=session();s['messages']=[{'role':'user','text':'שים למטה'}]
  class Provider:
   def interpret(self,context):
    self.context=context;return {'actions':[{'op':'adjust','field':'bottom_margin_ratio','direction':-1}]}
  p=Provider();command(s,'זה לא מספיק למטה',p);self.assertEqual(p.context['conversation'],s['messages']);self.assertIn('colors',p.context['current_state'])
 def test_feedback_references_earlier_property(self):
  s=session();run(s,op='bigger');font=s['settings']['font_size_ratio'];run(s,op='lower');position=s['settings']['bottom_margin_ratio']
  run(s,op='soften',field='font_size_ratio');self.assertLess(s['settings']['font_size_ratio'],font);self.assertEqual(s['settings']['bottom_margin_ratio'],position)
 def test_existing_history_context_migration(self):
  s=session();old=snapshot(s);s['history'].append({'label':'old UI change','snapshot':old});s['settings']['bottom_margin_ratio']=.18
  inferred=infer_last_change(s);self.assertEqual(inferred['direction'],-1);self.assertEqual(inferred['field'],'bottom_margin_ratio')
  s['last_change']=inferred;run(s,op='repeat',amount='small');self.assertAlmostEqual(s['settings']['bottom_margin_ratio'],.1575)
 def test_edit_checkpoint_redo(self):
  s=session();checkpoint(s,'edit');s['cues'][0]['lines']=['קוקו קוקו'];s['manual']=True
  undo(s);redo(s);self.assertEqual(s['cues'][0]['lines'],['קוקו קוקו'])
class AdapterTests(unittest.TestCase):
 def test_manual_words_and_timestamps(self):
  s=session();s.update(raw={'words':[]},width=1080,height=1920,duration=20,manual=True)
  s['settings']['max_words']=4;s['cues']=[{'start':11,'end':13,'lines':['קוקו קוקו זה מבצע חדש עכשיו כאן']}]
  reflow(s);self.assertEqual(' '.join(' '.join(c['lines']) for c in s['cues']),'קוקו קוקו זה מבצע חדש עכשיו כאן')
  self.assertTrue(all(len(' '.join(c['lines']).split())<=4 for c in s['cues']));self.assertEqual((s['cues'][0]['start'],s['cues'][-1]['end']),(11,13))
if __name__=='__main__':unittest.main()
