#!/usr/bin/env python3
"""Local Hebrew captions: logical Unicode text → word cues → libass → MP4."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime

ROOT = Path(os.getenv('ONE_ENGINE_ROOT', Path(__file__).resolve().parent))
MODEL_ID = 'ivrit-ai/whisper-large-v3-ct2'
from stt import Engine
ENGINE = Engine(ROOT)
EXTENSIONS = {'.mp4', '.mov', '.mkv', '.m4v', '.webm', '.avi'}


def ffmpeg():
    candidates = [os.environ.get('PINI_FFMPEG'), '/usr/local/opt/ffmpeg-full/bin/ffmpeg', str(ROOT / 'bin/ffmpeg'), shutil.which('ffmpeg')]
    for item in candidates:
        if item and Path(item).is_file():
            filters = subprocess.run([item, '-hide_banner', '-filters'], capture_output=True, text=True, check=True).stdout
            if re.search(r'\bass\s+V->V', filters):
                return item
    raise RuntimeError('FFmpeg with libass is missing. Run setup.sh.')


def run(command, **kwargs):
    subprocess.run([str(x) for x in command], check=True, **kwargs)


def probe(path):
    return json.loads(subprocess.check_output([os.getenv('PINI_FFPROBE') or shutil.which('ffprobe') or 'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]))


def load_preset(name):
    path = ROOT / 'presets' / (name + '.json')
    if Path(name).name != name:
        raise ValueError('Preset must be a name from presets/.')
    preset = json.loads(path.read_text())
    if preset['animation'] not in {'none', 'fade', 'pop'}:
        raise ValueError('Supported animations: none, fade, pop')
    if not 0.02 <= preset['font_size_ratio'] <= 0.15 or not 0.3 <= preset['max_width_ratio'] <= 0.9:
        raise ValueError('Invalid font size / caption width')
    if preset['max_words'] < 1 or preset['max_duration'] <= 0:
        raise ValueError('Invalid cue limits')
    return preset


def caption_font(path,size):
    from PIL import ImageFont
    font=ImageFont.truetype(str(path),size)
    if Path(path).name=='NotoSansHebrew.ttf':font.set_variation_by_axes([700,100])
    return font


def layout_words(words, font, width):
    """Measure shaped text, choose a balanced break, never exceed two lines."""
    tokens = [w['text'] for w in words]
    def fits(text):
        return font.getlength(text) <= width
    joined = ' '.join(tokens)
    if fits(joined):
        return [joined]
    choices = []
    for i in range(1, len(tokens)):
        a, b = ' '.join(tokens[:i]), ' '.join(tokens[i:])
        if fits(a) and fits(b):
            # Prefer balanced lines and a break after punctuation.
            score = abs(font.getlength(a) - font.getlength(b))
            if a.endswith((',', ':', ';', '.', '!', '?')):
                score *= 0.7
            choices.append((score, [a, b]))
    return min(choices, key=lambda x: x[0])[1] if choices else None


def make_cues(words, preset, width, height, duration):
    from PIL import ImageFont
    size = max(16, round(width * preset['font_size_ratio']))
    font = caption_font(ROOT / 'fonts' / preset['font_file'], size)
    max_width = width * preset['max_width_ratio']
    normalized = []
    for word in words:
        text = re.sub(r'\s+', ' ', word['text']).strip()
        if not text:
            continue
        start, end = float(word['start']), float(word['end'])
        if not math.isfinite(start) or not math.isfinite(end):
            raise ValueError('Non-finite word timestamps')
        normalized.append({'text': text, 'start': max(0, start), 'end': max(0, end)})
    if normalized:
        if duration <= 0:
            raise ValueError('Video duration must be positive')
        epsilon = min(.01, duration / (len(normalized) * 2))
        # Backward pass reserves time for every word at the end of the clip.
        boundary = duration
        for word in reversed(normalized):
            word['end'] = min(boundary, max(word['start'] + epsilon, word['end']))
            word['start'] = min(word['start'], word['end'] - epsilon)
            boundary = word['start']
        # Forward pass removes overlaps without dropping any text.
        boundary = 0
        for i, word in enumerate(normalized):
            latest_end = duration - epsilon * (len(normalized) - i - 1)
            word['start'] = min(latest_end - epsilon, max(boundary, word['start']))
            word['end'] = min(latest_end, max(word['start'] + epsilon, word['end']))
            boundary = word['end']
    # Split clauses first, then optimize every clause jointly to avoid orphan words.
    chunks, chunk = [], []
    for word in normalized:
        if chunk and word['start'] - chunk[-1]['end'] > preset['pause_break']:
            chunks.append(chunk)
            chunk = []
        chunk.append(word)
        if re.search(r'[.!?…,;:]["״]?$', word['text']):
            chunks.append(chunk)
            chunk = []
    if chunk:
        chunks.append(chunk)
    cues = []
    function_words = {'את', 'של', 'עם', 'על', 'אל', 'או', 'אבל', 'כי', 'אם', 'זה', 'גם'}
    for chunk in chunks:
        n = len(chunk)
        costs, choices = [float('inf')] * (n + 1), [None] * n
        costs[n] = 0
        for i in range(n - 1, -1, -1):
            for j in range(i + 1, min(n, i + preset['max_words']) + 1):
                part = chunk[i:j]
                lines = layout_words(part, font, max_width)
                if j > i + 1 and (lines is None or part[-1]['end'] - part[0]['start'] > preset['max_duration']):
                    break
                if lines is None:
                    lines = [part[0]['text']]
                count = j - i
                cost = 4 + max(0, 3 - count) ** 2 * 5
                if j < n and part[-1]['text'] in function_words:
                    cost += 10
                # Prefer a modest reading pace without inventing new words.
                seconds = max(.35, part[-1]['end'] - part[0]['start'])
                cost += max(0, count / seconds - 4) * 2
                cost += costs[j]
                if cost < costs[i]:
                    costs[i], choices[i] = cost, (j, lines)
        i = 0
        while i < n:
            j, lines = choices[i]
            cues.append({'start': chunk[i]['start'], 'end': chunk[j - 1]['end'], 'lines': lines})
            i = j
    for i, cue in enumerate(cues):
        boundary = cues[i + 1]['start'] if i + 1 < len(cues) else duration
        cue['end'] = min(boundary, duration, max(cue['end'] + .10, cue['start'] + .35))
    if ' '.join(w['text'] for w in normalized).split() != ' '.join(' '.join(c['lines']) for c in cues).split():
        raise RuntimeError('Caption layout lost decoded words')
    return cues, font


def stamp(seconds, ass=False):
    scale = 100 if ass else 1000
    value = max(0, round(seconds * scale))
    hours, rem = divmod(value, 3600 * scale)
    minutes, rem = divmod(rem, 60 * scale)
    secs, frac = divmod(rem, scale)
    return f'{hours}:{minutes:02}:{secs:02}.{frac:02}' if ass else f'{hours:02}:{minutes:02}:{secs:02},{frac:03}'


def srt_write(cues, path):
    path.write_text('\n\n'.join(f'{i}\n{stamp(c["start"])} --> {stamp(c["end"])}\n' + '\n'.join(c['lines']) for i, c in enumerate(cues, 1)) + '\n', encoding='utf-8')


def srt_read(path):
    def seconds(t):
        h, m, s, ms = map(int, re.split('[:,.]', t))
        return h * 3600 + m * 60 + s + ms / 1000
    cues = []
    for block in re.split(r'\n\s*\n', path.read_text(encoding='utf-8-sig').replace('\r\n', '\n').strip()):
        rows = block.splitlines()
        if len(rows) < 3:
            raise ValueError('Invalid SRT block')
        a, b = rows[1].split(' --> ')
        lines = rows[2:]
        start, end = seconds(a), seconds(b)
        if len(lines) > 2 or end <= start or (cues and start < cues[-1]['end']):
            raise ValueError('SRT needs non-overlapping cues with 1–2 lines')
        cues.append({'start': start, 'end': end, 'lines': lines})
    return cues


def ass_write(cues, path, preset, width, height, font):
    size = font.size
    margin = round(width * (1 - preset['max_width_ratio']) / 2)
    header = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{preset['font']},{size},{preset['primary_color']},&H000000FF,{preset['outline_color']},&H80000000,-1,0,0,0,100,100,0,0,1,{size * preset['outline_ratio']:.2f},{preset['shadow']},2,{margin},{margin},{round(height * preset['bottom_margin_ratio'])},-1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    rows = []
    for cue in cues:
        # Logical order stays editable. libass/FriBidi handles RTL and mixed digits.
        lines = [line.replace('\\', '／').replace('{', '(').replace('}', ')') for line in cue['lines']]
        tags = ''
        available = width * preset['max_width_ratio']
        longest = max(font.getlength(line) for line in lines)
        if longest > available:
            tags += r'\fs' + str(max(8, math.floor(size * available / longest)))
        fade = min(preset['fade_ms'], int((cue['end'] - cue['start']) * 1000 / 4))
        if preset['animation'] == 'fade':
            tags += f'\\fad({fade},{fade})'
        elif preset['animation'] == 'pop':
            tags += r'\fscx92\fscy92' + f'\\t(0,{fade},\\fscx100\\fscy100)'
        text = (('{' + tags + '}') if tags else '') + r'\N'.join('\u200f' + line for line in lines)
        rows.append(f'Dialogue: 0,{stamp(cue["start"], True)},{stamp(cue["end"], True)},Default,,0,0,0,,{text}')
    path.write_text(header + '\n'.join(rows) + '\n', encoding='utf-8')


def transcribe(audio, prompt, terms_path=None):
    return ENGINE.transcribe(audio, prompt, terms_path)


def process(source, args):
    from PIL import ImageFont
    source = source.expanduser().resolve()
    if not source.is_file():
        raise ValueError(f'Video not found: {source}')
    engine = ffmpeg()
    preset = load_preset(args.preset)
    info = probe(source)
    video = next((s for s in info['streams'] if s['codec_type'] == 'video' and not s.get('disposition', {}).get('attached_pic')), None)
    audio = next((s for s in info['streams'] if s['codec_type'] == 'audio'), None)
    if not video or not audio:
        raise ValueError('הקובץ חייב לכלול וידאו ואודיו.')
    duration = float(info['format']['duration'])
    width, height = int(video['width']), int(video['height'])
    rotation = next((float(s.get('rotation', 0)) for s in video.get('side_data_list', []) if 'rotation' in s), 0)
    if abs(rotation) % 180 == 90:
        width, height = height, width
    # libx264 4:2:0 needs even dimensions; pad at most one pixel.
    width, height = width + width % 2, height + height % 2
    color = video.get('color_transfer', '')
    hdr = color in {'smpte2084', 'arib-std-b67'}
    tone_map = ''
    if hdr:
        print('סרטון HDR: ממיר צבעים ל־SDR/Rec.709 עבור צפייה ברשתות חברתיות.', flush=True)
        tone_map = 'zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=mobius:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,'
    token = hashlib.sha256((str(source) + str(source.stat().st_mtime_ns)).encode()).hexdigest()[:8]
    job = Path(os.getenv('ONE_OUTPUT_DIR', ROOT / 'output')) / f'{source.stem}-{datetime.now():%Y%m%d-%H%M%S-%f}-{token}'
    job.mkdir(parents=True)
    try:
        with tempfile.TemporaryDirectory(prefix='pini-captions-') as temp:
            work = Path(temp)
            if args.srt:
                cues = srt_read(Path(args.srt).expanduser())
                if any(c['end'] > duration + .05 for c in cues):
                    raise ValueError('SRT extends beyond video duration')
                font = caption_font(ROOT / 'fonts' / preset['font_file'], max(16, round(width * preset['font_size_ratio'])))
            else:
                print('מחלץ אודיו לתמלול…', flush=True)
                run([engine, '-v', 'error', '-y', '-i', source, '-map', '0:a:0', '-vn', '-ar', '16000', '-ac', '1', work / 'speech.wav'])
                words, segments, transcription = transcribe(work / 'speech.wav', args.prompt, args.terms)
                (job / 'transcript.json').write_text(json.dumps({'model': MODEL_ID, 'source': str(source), 'words': words, 'segments': segments, 'transcription': transcription}, ensure_ascii=False, indent=2))
                (job / 'transcript.txt').write_text('\n'.join(s['text'].strip() for s in segments), encoding='utf-8')
                cues, font = make_cues(words, preset, width, height, duration)
            srt_write(cues, job / 'captions.srt')
            ass_write(cues, job / 'captions.ass', preset, width, height, font)
            shutil.copy(job / 'captions.ass', work / 'captions.ass')
            shutil.copytree(ROOT / 'fonts', work / 'fonts')
            (job / 'preset.json').write_text(json.dumps(preset, ensure_ascii=False, indent=2))
            print('צורב כתוביות באמצעות FFmpeg…', flush=True)
            audio_codec = ['-c:a', 'copy'] if audio['codec_name'] in {'aac', 'mp3', 'alac'} else ['-c:a', 'aac', '-b:a', '256k']
            run([engine, '-hide_banner', '-v', 'warning', '-stats', '-y', '-i', source,
                 '-map', f'0:{video["index"]}', '-map', f'0:{audio["index"]}',
                 '-vf', tone_map + 'pad=ceil(iw/2)*2:ceil(ih/2)*2,ass=filename=captions.ass:fontsdir=fonts',
                 '-c:v', 'libx264', '-crf', str(preset['crf']), '-preset', preset['encoder_preset'],
                 '-pix_fmt', 'yuv420p', '-fps_mode', 'passthrough', *(['-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709'] if hdr else []), *audio_codec,
                 '-movflags', '+faststart', work / 'render.mp4'], cwd=work)
            rendered = probe(work / 'render.mp4')
            if abs(float(rendered['format']['duration']) - duration) > .25:
                raise RuntimeError('Output duration differs from source; output retained for inspection in job folder')
            shutil.move(work / 'render.mp4', job / 'captioned.mp4')
        (job / 'complete.json').write_text(json.dumps({'source': str(source), 'duration': duration, 'cues': len(cues), 'audio': audio_codec, 'width': width, 'height': height, 'hdr_to_sdr': hdr}, indent=2))
        print(f'מוכן: {job / "captioned.mp4"}', flush=True)
        return job
    except Exception as exc:
        (job / 'error.txt').write_text(str(exc), encoding='utf-8')
        raise


def fingerprint(path):
    s = path.stat()
    return f'{path.resolve()}:{s.st_size}:{s.st_mtime_ns}'


def watch(args):
    state_path = ROOT / '.watch-state.json'
    done = set(json.loads(state_path.read_text())) if state_path.exists() else set()
    pending, failed = {}, set()
    print(f'ממתין לסרטונים ב־{ROOT / "input"}. לעצירה: Ctrl+C', flush=True)
    while True:
        for path in sorted((ROOT / 'input').iterdir()):
            if path.suffix.lower() not in EXTENSIONS or not path.is_file():
                continue
            key = fingerprint(path)
            if key in done or key in failed:
                continue
            old_key, since = pending.get(path, (None, time.monotonic()))
            if old_key != key:
                pending[path] = (key, time.monotonic())
                continue
            if time.monotonic() - since < 10:
                continue
            try:
                process(path, args)
                done.add(key)
                tmp = state_path.with_suffix('.tmp')
                tmp.write_text(json.dumps(sorted(done)))
                tmp.replace(state_path)
            except Exception as exc:
                failed.add(key)
                print(f'שגיאה ב־{path.name}: {exc}. להפעלה חוזרת: הפעל מחדש את המעקב.', file=sys.stderr, flush=True)
        time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description='כתוביות עברית מקומיות לסרטונים')
    parser.add_argument('video', nargs='?', type=Path, help='Video path; otherwise process input/')
    parser.add_argument('--watch', action='store_true', help='Monitor input/ continuously')
    parser.add_argument('--preset', default='reels')
    parser.add_argument('--prompt', default='', help='Extra transcription context')
    parser.add_argument('--terms', type=Path, help='UTF-8 glossary file (default: terms.txt)')
    parser.add_argument('--srt', help='Render edited SRT instead of retranscribing')
    args = parser.parse_args()
    if args.watch and (args.video or args.srt):
        parser.error('--watch cannot be combined with video or --srt')
    if args.srt and not args.video:
        parser.error('--srt requires a video path')
    try:
        if args.watch:
            watch(args)
        elif args.video:
            process(args.video, args)
        else:
            videos = sorted(p for p in (ROOT / 'input').iterdir() if p.suffix.lower() in EXTENSIONS and p.is_file())
            if not videos:
                print(f'אין סרטונים. הכנס סרטון ל־{ROOT / "input"} והפעל שוב.')
                return
            failures = 0
            for path in videos:
                try:
                    process(path, args)
                except Exception as exc:
                    failures += 1
                    print(f'{path.name}: {exc}', file=sys.stderr)
            if failures:
                raise RuntimeError(f'{failures} video(s) failed; see output/*/error.txt')
    except KeyboardInterrupt:
        print('\nנעצר.')
    except Exception as exc:
        print(f'שגיאה: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
