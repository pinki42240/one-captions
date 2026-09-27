import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stt import segment_words, load_terms, OPTIONS
from captions import make_cues, load_preset, srt_write, srt_read

class VerbatimTests(unittest.TestCase):
    def test_repetitions_fillers_and_zero_duration_tail_reach_srt(self):
        text='אה אממ קוקו קוקו כן כן רגע רגע'
        tokens=text.split()
        words=[{'text':w,'start':i*.25,'end':(i+1)*.25} for i,w in enumerate(tokens)]
        words[-2]['start']=words[-2]['end']=2
        words[-1]['start']=words[-1]['end']=2
        cues,_=make_cues(words,load_preset('reels'),1080,1920,2)
        self.assertEqual(' '.join(' '.join(c['lines']) for c in cues),text)
        self.assertTrue(all(0<=c['start']<c['end']<=2 for c in cues))
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'captions.srt'
            srt_write(cues,path)
            self.assertEqual(' '.join(' '.join(c['lines']) for c in srt_read(path)),text)

    def test_missing_alignment_does_not_remove_second_repetition(self):
        s=NS(text='אה קוקו קוקו כן',start=0,end=2,
             words=[NS(word='אה',start=0,end=.2,probability=.9),
                    NS(word='קוקו',start=.3,end=.6,probability=.9),
                    NS(word='כן',start=1.8,end=2,probability=.9)])
        words=segment_words(s)
        self.assertEqual([w['text'] for w in words],s.text.split())
        self.assertEqual(sum(w['text']=='קוקו' for w in words),2)
        self.assertEqual(words[2]['timing_source'],'interpolated')

    def test_no_alignment_still_keeps_all_decoded_words(self):
        s=NS(text='קוקו קוקו',start=1,end=2,words=[])
        words=segment_words(s)
        self.assertEqual([w['text'] for w in words],['קוקו','קוקו'])
        self.assertEqual(words[0]['start'],1)
        self.assertEqual(words[-1]['end'],2)

    def test_glossary_is_context_only_and_utf8(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'terms.txt'
            path.write_text('# הערה\nקוקו\nרפאל\nקוקו\nמוצר  מיוחד\n',encoding='utf-8-sig')
            self.assertEqual(load_terms(path),['קוקו','רפאל','מוצר מיוחד'])
        self.assertFalse(OPTIONS['vad_filter'])
        self.assertIsNone(OPTIONS['no_speech_threshold'])
        self.assertEqual(OPTIONS['repetition_penalty'],1)
        self.assertEqual(OPTIONS['no_repeat_ngram_size'],0)

if __name__=='__main__': unittest.main()
