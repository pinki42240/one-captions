"""Exercise real HTTP/session persistence, with a controlled AI boundary."""
import copy,json,sys,tempfile,threading,unittest,urllib.request,urllib.error,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server,ai_provider
from adapter import base_settings

class HTTPTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old_data=server.DATA;server.DATA=Path(self.tmp.name)
  self.old_provider=ai_provider.DEFAULT;self.sid=uuid.uuid4().hex
  d=server.DATA/self.sid;d.mkdir();server.write(d/'session.json',dict(id=self.sid,name='test.mp4',created=0,revision=0,settings=base_settings(),preset='Reels',cues=[{'start':0,'end':2,'lines':['קוקו קוקו']}],raw=None,manual=True,colors={},important=False,pending=[],history=[],exports=[],messages=[],job={'status':'idle'},preview_ready=False,duration=2,width=1080,height=1920))
  self.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
 def tearDown(self):
  self.http.shutdown();self.http.server_close();self.thread.join();server.DATA=self.old_data;ai_provider.DEFAULT=self.old_provider;server.CHATS.clear();self.tmp.cleanup()
 def request(self,path,data=None):
  request=urllib.request.Request(f'http://127.0.0.1:{self.http.server_port}'+path,data=json.dumps({'id':self.sid,**data}).encode() if data is not None else None,headers={'X-One-Token':server.TOKEN,'Content-Type':'application/json'})
  with urllib.request.urlopen(request,timeout=5) as r:return json.load(r)
 def test_last_project_metadata_and_complete_resume(self):
  first=self.request('/api/sessions');self.assertEqual(len(first),1)
  self.assertEqual(first[0]['id'],self.sid);self.assertIn('updated',first[0])
  edited=self.request('/api/edit',{'index':0,'text':'קוקו רפאל'})
  listed=self.request('/api/sessions');self.assertGreaterEqual(listed[0]['updated'],first[0]['updated'])
  resumed=self.request('/api/session/'+listed[0]['id'])
  self.assertEqual(resumed['cues'],edited['cues']);self.assertEqual(resumed['settings'],edited['settings'])
  self.assertTrue(resumed['can_undo']);self.assertEqual(resumed['messages'],edited['messages'])
 def test_chat_history_state_and_redo_persist(self):
  class Provider:
   def interpret(self,context):
    assert context['conversation'][-1]['text']=='הטקסט גבוה לי מדי, תנמיך אותו בעדינות.'
    return {'actions':[{'op':'lower'}]}
  ai_provider.DEFAULT=Provider();s=self.request('/api/chat',{'text':'הטקסט גבוה לי מדי, תנמיך אותו בעדינות.'})
  self.assertAlmostEqual(s['settings']['bottom_margin_ratio'],.185);self.assertEqual(s['revision'],1);self.assertFalse(s['thinking'])
  self.assertEqual(len(s['messages']),2);self.assertTrue(s['can_undo']);self.assertFalse(s['can_redo'])
  s=self.request('/api/undo',{});self.assertAlmostEqual(s['settings']['bottom_margin_ratio'],.23);self.assertTrue(s['can_redo'])
  s=self.request('/api/redo',{});self.assertAlmostEqual(s['settings']['bottom_margin_ratio'],.185)
  self.assertEqual(s['cues'][0]['lines'],['קוקו קוקו']);self.assertEqual(self.request('/api/session/'+self.sid)['revision'],3)
 def test_playback_polling_remains_available_during_inference(self):
  entered=threading.Event();release=threading.Event();responses=[]
  class Provider:
   def interpret(self,context):entered.set();release.wait(5);return {'actions':[{'op':'bigger'}]}
  ai_provider.DEFAULT=Provider();chat=threading.Thread(target=lambda:responses.append(self.request('/api/chat',{'text':'תעשה את הטקסט בולט יותר אבל לא מוגזם'})));chat.start();self.assertTrue(entered.wait(2))
  try:
   s=self.request('/api/session/'+self.sid);self.assertTrue(s['thinking'])
   with self.assertRaises(urllib.error.HTTPError):self.request('/api/preset',{'preset':'Bold'})
  finally:release.set();chat.join(5)
  self.assertEqual(len(responses),1);self.assertGreater(responses[0]['settings']['font_size_ratio'],.058)
 def test_fast_style_never_calls_ai_or_reflows(self):
  from unittest.mock import patch
  class Provider:
   def interpret(self,context):raise AssertionError('AI should not be invoked')
  ai_provider.DEFAULT=Provider()
  with patch('server.reflow') as flow:
   s=self.request('/api/chat',{'text':'תוריד אותן'})
   self.assertEqual(s['chat_timing']['route'],'fast');flow.assert_not_called()
   s=self.request('/api/chat',{'text':'עוד'})
   self.assertAlmostEqual(s['settings']['bottom_margin_ratio'],.14);flow.assert_not_called()
   s=self.request('/api/chat',{'text':'תגדיל אותן'});flow.assert_called_once()
 def test_failed_plan_does_not_claim_or_commit_changes(self):
  class Provider:
   def interpret(self,context):return {'actions':[{'op':'bigger'},{'op':'set','field':'max_words','value':999}]}
  ai_provider.DEFAULT=Provider();s=self.request('/api/chat',{'text':'invalid'})
  self.assertEqual(s['revision'],0);self.assertEqual(s['settings']['font_size_ratio'],.058);self.assertFalse(s['can_undo']);self.assertIn('לא שיניתי',s['messages'][-1]['text'])
if __name__=='__main__':unittest.main()
