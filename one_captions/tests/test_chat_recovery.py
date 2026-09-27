"""Manual spelling edit -> bounded AI -> preserved state -> successful retry."""
import threading,time
from unittest.mock import patch
import test_server
import ai_provider,server

class ChatRecoveryTests(test_server.HTTPTests):
 # Reuse the real HTTP fixture, without rerunning inherited cases.
 test_chat_history_state_and_redo_persist=None
 test_playback_polling_remains_available_during_inference=None
 test_fast_style_never_calls_ai_or_reflows=None
 test_failed_plan_does_not_claim_or_commit_changes=None
 def test_spelling_edit_acknowledgement_stays_local(self):
  class Provider:
   def interpret(self,context):raise AssertionError('Acknowledgement must not invoke AI')
  ai_provider.DEFAULT=Provider()
  edited=self.request('/api/edit',{'index':0,'text':'קוקו רפאל'})
  started=time.monotonic();reply=self.request('/api/chat',{'text':'זהו תיקנתי את מה שצריך'})
  self.assertLess(time.monotonic()-started,.5)
  self.assertEqual(reply['revision'],edited['revision']);self.assertEqual(reply['cues'],edited['cues'])
  self.assertFalse(reply['thinking']);self.assertIn('התיקונים שלך נשמרו',reply['messages'][-1]['text'])
 def test_timeout_after_edit_preserves_state_and_ignores_late_result(self):
  entered=threading.Event();release=threading.Event();done=threading.Event()
  class Provider:
   def interpret(self,context):
    self.context=context;entered.set();release.wait(3);done.set()
    return {'actions':[{'op':'bigger'}]}
  provider=Provider();ai_provider.DEFAULT=provider
  edited=self.request('/api/edit',{'index':0,'text':'קוקו רפאל'})
  try:
   with patch('ai_provider.CHAT_TIMEOUT',.1):
    response=self.request('/api/chat',{'text':'תעשה את הטקסט בולט יותר אבל לא מוגזם'})
   self.assertTrue(entered.is_set());self.assertFalse(response['thinking'])
   self.assertIn('לא השיב בזמן',response['chat_error'])
   self.assertEqual(response['revision'],edited['revision']);self.assertEqual(response['cues'],edited['cues'])
   self.assertEqual(provider.context['current_state']['cues'],edited['cues'])
   retry=self.request('/api/chat',{'text':'תגדיל אותן'})
   self.assertNotIn('chat_error',retry);self.assertFalse(retry['thinking']);self.assertEqual(retry['revision'],edited['revision']+1)
  finally:release.set();done.wait(2)
  self.assertEqual(self.request('/api/session/'+self.sid)['revision'],retry['revision'])
  undo=self.request('/api/undo',{});self.assertEqual(undo['cues'],edited['cues'])
 def test_provider_crash_clears_pending_and_allows_retry(self):
  class Provider:
   def interpret(self,context):raise RuntimeError('internal failure')
  ai_provider.DEFAULT=Provider()
  result=self.request('/api/chat',{'text':'תעשה את הטקסט בולט יותר אבל לא מוגזם'})
  self.assertFalse(result['thinking']);self.assertIn('אפשר לשלוח שוב',result['chat_error'])
  self.assertFalse(self.request('/api/chat',{'text':'עוד למטה'})['thinking'])
 def test_context_failure_does_not_leave_chat_busy(self):
  with patch('ai_provider.context',side_effect=ValueError('context failure')):
   from urllib.error import HTTPError
   with self.assertRaises(HTTPError):self.request('/api/chat',{'text':'test'})
  self.assertNotIn(self.sid,server.CHATS)
  self.assertFalse(self.request('/api/chat',{'text':'עוד למטה'})['thinking'])
