"""Verbatim-first Hebrew STT. No text cleanup, deduplication or rewriting."""
import difflib
import os
from pathlib import Path
import re
import time

MODEL_ID = 'ivrit-ai/whisper-large-v3-ct2'
# Run the entire waveform: short utterances must not be removed by VAD.
OPTIONS = dict(language='he', task='transcribe', beam_size=10, patience=1.0,
               temperature=0.0, word_timestamps=True, vad_filter=False,
               no_speech_threshold=None, compression_ratio_threshold=None,
               log_prob_threshold=None, repetition_penalty=1.0,
               no_repeat_ngram_size=0, condition_on_previous_text=False,
               hallucination_silence_threshold=None, suppress_tokens=[-1])


def load_terms(path):
    terms = []
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        line = re.sub(r'\s+', ' ', line.strip())
        if line and not line.startswith('#'):
            if len(line) > 120:
                raise ValueError('A glossary entry must be at most 120 characters')
            if line not in terms:
                terms.append(line)
    return terms


def key(text):
    return ''.join(c.lower() for c in text if c.isalnum())


def segment_words(segment):
    """Keep every decoded text token, even when alignment omitted a token.

    Missing alignment is interpolated and explicitly marked, never discarded.
    Text is taken from the same model segment, not invented from the glossary.
    """
    tokens = segment.text.split()
    aligned = []
    for w in segment.words or []:
        parts = w.word.split()
        for i, text in enumerate(parts):
            span = max(0, w.end - w.start)
            aligned.append(dict(text=text, start=w.start + span * i / len(parts),
                                end=w.start + span * (i + 1) / len(parts),
                                probability=w.probability, timing_source='word_alignment'))
    result = [None] * len(tokens)
    matcher = difflib.SequenceMatcher(a=[key(t) for t in tokens],
                                     b=[key(w['text']) for w in aligned], autojunk=False)
    for block in matcher.get_matching_blocks():
        for i in range(block.size):
            result[block.a + i] = dict(aligned[block.b + i], text=tokens[block.a + i])
    i = 0
    while i < len(tokens):
        if result[i] is not None:
            i += 1
            continue
        j = i + 1
        while j < len(tokens) and result[j] is None:
            j += 1
        left = result[i - 1]['end'] if i else segment.start
        right = result[j]['start'] if j < len(tokens) else segment.end
        right = max(left, right)
        for k in range(i, j):
            result[k] = dict(text=tokens[k], start=left + (right - left) * (k - i) / (j - i),
                            end=left + (right - left) * (k - i + 1) / (j - i),
                            probability=None, timing_source='interpolated')
        i = j
    return result


class Engine:
    def __init__(self, root):
        self.root = Path(root)
        self.model = None

    def transcribe(self, audio, prompt='', terms_path=None):
        terms_path = Path(terms_path).expanduser() if terms_path else self.root / 'terms.txt'
        terms = load_terms(terms_path)
        if self.model is None:
            from faster_whisper import WhisperModel
            print('טוען מודל ivrit.ai קיים במצב דיוק float32…', flush=True)
            self.model = WhisperModel(str(Path(os.getenv('ONE_WHISPER_MODEL', self.root / 'models/hebrew'))), device='cpu',
                                      compute_type='float32', cpu_threads=min(8, os.cpu_count() or 4),
                                      local_files_only=True)
        # Reject overly long context instead of silently truncating the dictionary.
        hint = ', '.join(terms)
        context = 'תמלול מילולי בעברית, כולל חזרות ומילות מילוי.'
        if prompt.strip():
            context += ' ' + prompt.strip()
        tokens = self.model.hf_tokenizer.encode(' ' + hint).ids
        context_tokens = self.model.hf_tokenizer.encode(' ' + context).ids
        if len(tokens) + len(context_tokens) > 180:
            raise ValueError('מילון המונחים והרמז ארוכים מדי. צמצם לכ־180 טוקנים; לא יתבצע קיצוץ שקט.')
        settings = dict(OPTIONS, initial_prompt=context, hotwords=hint or None)
        started = time.monotonic()
        segments, info = self.model.transcribe(str(audio), **settings)
        words, raw = [], []
        for s in segments:
            print(f'תמלול מילולי: {s.end:.1f} שניות — {s.text.strip()}', flush=True)
            raw.append(dict(start=s.start, end=s.end, text=s.text,
                            avg_logprob=s.avg_logprob, no_speech_prob=s.no_speech_prob,
                            compression_ratio=s.compression_ratio))
            words.extend(segment_words(s))
        if not words:
            raise RuntimeError('לא זוהה טקסט. בדוק את האודיו; אין להוסיף מילים מהמילון ידנית.')
        expected = ' '.join(s['text'].strip() for s in raw).split()
        if [w['text'] for w in words] != expected:
            raise RuntimeError('Decoded-text/word alignment mismatch')
        metadata = dict(mode='verbatim', model=MODEL_ID,
                        model_path=str((self.root / 'models/hebrew').resolve()),
                        compute_type='float32', options=settings,
                        terms=terms, terms_file=str(terms_path.resolve()),
                        duration=info.duration, duration_after_vad=info.duration_after_vad,
                        elapsed_seconds=round(time.monotonic() - started, 2),
                        interpolated_words=sum(w['timing_source'] == 'interpolated' for w in words),
                        review_segments=[i for i,s in enumerate(raw) if s['avg_logprob'] < -1 or s['no_speech_prob'] > .6])
        return words, raw, metadata
