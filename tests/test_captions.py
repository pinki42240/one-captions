import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from captions import load_preset, make_cues, srt_write, srt_read, ass_write

class CaptionTests(unittest.TestCase):
    def test_timing_layout_and_word_preservation(self):
        tokens = 'שלום לכולם, היום אנחנו יוצרים כתוביות מקצועיות בעברית. עכשיו אפשר לערוך את הטקסט ולשמור את הסרטון.'.split()
        words = [{'text': w, 'start': i * .4, 'end': i * .4 + .35} for i, w in enumerate(tokens)]
        p = load_preset('reels')
        cues, font = make_cues(words, p, 720, 1280, 20)
        self.assertEqual(' '.join(' '.join(c['lines']) for c in cues), ' '.join(tokens))
        self.assertTrue(all(1 <= len(c['lines']) <= 2 for c in cues))
        self.assertTrue(all(c['start'] < c['end'] for c in cues))
        self.assertTrue(all(a['end'] <= b['start'] for a,b in zip(cues,cues[1:])))
        self.assertTrue(all(font.getlength(line) <= 720 * p['max_width_ratio'] for c in cues for line in c['lines']))
        self.assertTrue(all(c['end'] - c['start'] <= p['max_duration'] + .11 for c in cues))
        self.assertEqual(cues[0]['lines'], ['שלום לכולם,'])
        self.assertGreater(len(' '.join(cues[-1]['lines']).split()), 1)
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'captions.srt'
            srt_write(cues, f)
            self.assertEqual([c['lines'] for c in srt_read(f)], [c['lines'] for c in cues])

    def test_edited_srt_mixed_language_and_animations(self):
        cues=[{'start': 0, 'end': 2, 'lines': ['שלום TikTok 2026', 'מחיר: 150 ₪']}]
        p=load_preset('reels')
        _, font=make_cues([],p,720,1280,3)
        with tempfile.TemporaryDirectory() as d:
            for mode in ('none', 'fade', 'pop'):
                p['animation']=mode
                path=Path(d)/(mode+'.ass')
                ass_write(cues,path,p,720,1280,font)
                text=path.read_text()
                self.assertIn('שלום TikTok 2026',text)
                self.assertEqual(next(line for line in text.splitlines() if line.startswith('Style:')).split(',')[-1], '-1')
                self.assertIn('\\N',text)
                self.assertIn('\\t(',text) if mode=='pop' else None

    def test_invalid_edited_srt_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'bad.srt'
            f.write_text('1\n00:00:00,000 --> 00:00:01,000\na\nb\nc\n')
            with self.assertRaises(ValueError): srt_read(f)

if __name__=='__main__': unittest.main()
