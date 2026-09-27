import io,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ai_provider import CompatibleProvider
class ProviderTests(unittest.TestCase):
 def test_contextually_invalid_plan_is_repaired_once(self):
  calls=[]
  def respond(request,**kwargs):
   calls.append(json.loads(request.data));plan={'actions':[{'op':'soften'}]} if len(calls)==1 else {'actions':[{'op':'lower','amount':'small'}]}
   return io.BytesIO(json.dumps({'choices':[{'message':{'content':json.dumps(plan)}}]}).encode())
  context={'request':'תנמיך בעדינות','last_change':None,'current_state':{'settings':{'bottom_margin_ratio':.23}}}
  with patch('urllib.request.urlopen',respond):plan=CompatibleProvider('http://localhost',local=True).interpret(context)
  self.assertEqual(plan['actions'][0]['op'],'lower');self.assertEqual(len(calls),2)
  self.assertIn('execution_feedback',json.loads(calls[1]['messages'][1]['content']));self.assertNotIn('execution_feedback',context)
 def test_valid_followup_does_not_retry(self):
  result={'choices':[{'message':{'content':json.dumps({'actions':[{'op':'repeat'}]})}}]}
  with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(result).encode())) as call:
   CompatibleProvider('http://localhost',local=True).interpret({'last_change':{'field':'font_size_ratio'}});self.assertEqual(call.call_count,1)
 def test_retry_is_bounded(self):
  def respond(*args,**kwargs):return io.BytesIO(json.dumps({'choices':[{'message':{'content':'{"actions":[{"op":"soften"}]}'}}]}).encode())
  with patch('urllib.request.urlopen',side_effect=respond) as call:
   CompatibleProvider('http://localhost',local=True).interpret({'last_change':None});self.assertEqual(call.call_count,2)
if __name__=='__main__':unittest.main()
