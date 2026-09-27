"""First-launch model setup in user data; never downloads into the application or Git."""
import hashlib,json,os,shutil,sys
from pathlib import Path
from huggingface_hub import hf_hub_download,snapshot_download

WHISPER_REV='e9ed4a4a98d761b0f617d668303de2c514236c66'
QWEN_REV='bc640142c66e1fdd12af0bd68f40445458f3869b'
QWEN_SHA='7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5'

def status(text):print(json.dumps({'status':text},ensure_ascii=False),flush=True)
def link_or_copy(source,target):
 target.parent.mkdir(parents=True,exist_ok=True)
 try:os.link(source,target)
 except OSError:shutil.copy2(source,target)

def setup(data):
 data=Path(data);models=data/'models';models.mkdir(parents=True,exist_ok=True)
 whisper=models/'hebrew';qwen=models/'ai'/'Qwen3-4B-Q4_K_M.gguf'
 if not (whisper/'model.bin').is_file():
  status('מכין מודל תמלול עברית. ההורדה הראשונה גדולה ועשויה להימשך זמן מה…')
  try:source=Path(snapshot_download('ivrit-ai/whisper-large-v3-ct2',revision=WHISPER_REV,local_files_only=True))
  except Exception:source=Path(snapshot_download('ivrit-ai/whisper-large-v3-ct2',revision=WHISPER_REV))
  for item in source.iterdir():
   if item.is_file() and not (whisper/item.name).exists():link_or_copy(item.resolve(),whisper/item.name)
 if not qwen.is_file() or qwen.stat().st_size!=2497280256:
  status('מכין את העוזר בעברית. ההורדה הראשונה גדולה ועשויה להימשך זמן מה…')
  try:source=Path(hf_hub_download('Qwen/Qwen3-4B-GGUF','Qwen3-4B-Q4_K_M.gguf',revision=QWEN_REV,local_files_only=True))
  except Exception:source=Path(hf_hub_download('Qwen/Qwen3-4B-GGUF','Qwen3-4B-Q4_K_M.gguf',revision=QWEN_REV))
  link_or_copy(source.resolve(),qwen)
  with qwen.open('rb') as stream:
   digest=hashlib.file_digest(stream,'sha256').hexdigest()
  if digest!=QWEN_SHA:raise RuntimeError('assistant model checksum mismatch')
 if not (whisper/'model.bin').is_file() or not qwen.is_file():raise RuntimeError('model setup incomplete')
 status('המודלים מוכנים. פותח את ONE Captions…')

if __name__=='__main__':setup(sys.argv[1])
