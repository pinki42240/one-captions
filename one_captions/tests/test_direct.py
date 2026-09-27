import sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_server as http_tests
from domain import execute,undo,redo,snapshot,command
from test_domain import session
from adapter import decorated_ass,ROOT
from PIL import ImageFont
class DirectStateTests(unittest.TestCase):
 def test_drag_chat_resize_history(self):
  s=session();execute(s,{'actions':[{'op':'set','field':'center_x_ratio','value':.31},{'op':'set','field':'bottom_margin_ratio','value':.36}]},'גרירה')
  drag=snapshot(s);command(s,'עוד קצת למעלה')
  self.assertAlmostEqual(s['settings']['bottom_margin_ratio'],.3825);self.assertEqual(s['settings']['center_x_ratio'],.31)
  undo(s);self.assertEqual(snapshot(s),drag);undo(s);self.assertNotIn('center_x_ratio',s['settings']);redo(s);self.assertEqual(snapshot(s),drag)
 def test_free_position_and_export(self):
  s=session();s['width']=1080
  execute(s,{'actions':[{'op':'set','field':'center_x_ratio','value':.25},{'op':'set','field':'bottom_margin_ratio','value':.4},{'op':'word_style','word':'קוקה','occurrence':1,'styles':{'font_size':90,'bold':False,'color':'#FF7D8C','outline':2,'shadow':2,'glow':3,'italic':True,'underline':True}}]})
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'direct.ass';decorated_ass(s['cues'],p,s['settings'],1080,1920,ImageFont.truetype(str(ROOT/'fonts/NotoSansHebrew.ttf'),63),s);ass=p.read_text()
   self.assertIn(r'\pos(270,1152)',ass);self.assertIn(r'\fs90',ass);self.assertIn(r'\u1',ass);self.assertIn(r'\blur3',ass)
class DirectHTTPTests(unittest.TestCase):
 setUp=http_tests.HTTPTests.setUp
 tearDown=http_tests.HTTPTests.tearDown
 request=http_tests.HTTPTests.request
 def test_atomic_direct_revision_and_chat_continuation(self):
  import ai_provider
  class Provider:
   def interpret(self,c):raise AssertionError('Manual edit must not call AI')
  ai_provider.DEFAULT=Provider()
  s=self.request('/api/direct',{'revision':0,'actions':[{'op':'set','field':'center_x_ratio','value':.35},{'op':'set','field':'bottom_margin_ratio','value':.4}]})
  self.assertEqual(s['revision'],1);self.assertEqual(len(__import__('server').load(self.sid)['history']),1)
  s=self.request('/api/chat',{'text':'קצת יותר למעלה'});self.assertAlmostEqual(s['settings']['bottom_margin_ratio'],.4225);self.assertEqual(s['settings']['center_x_ratio'],.35)
  s=self.request('/api/undo',{});self.assertAlmostEqual(s['settings']['bottom_margin_ratio'],.4)
  import urllib.error
  with self.assertRaises(urllib.error.HTTPError):self.request('/api/direct',{'revision':0,'actions':[{'op':'set','field':'font_size_ratio','value':.07}]})
  self.assertEqual(self.request('/api/session/'+self.sid)['settings']['font_size_ratio'],.058)
