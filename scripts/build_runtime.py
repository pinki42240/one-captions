"""Build the shared Python engine as a native executable and stage clean resources."""
import os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ENGINE=ROOT/'release/engine';RUNTIME=ROOT/'release/runtime'
for name in ('captions.py','stt.py','terms.txt'):
 target=ENGINE/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
for folder in ('fonts','presets'):
 if (ENGINE/folder).exists():shutil.rmtree(ENGINE/folder)
 shutil.copytree(ROOT/folder,ENGINE/folder)
for name in ('adapter.py','ai_provider.py','fast_commands.py','server.py','worker.py','domain.py','word_styles.py','setup_models.py'):
 target=ENGINE/'one_captions'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/'one_captions'/name,target)
if (ENGINE/'one_captions/static').exists():shutil.rmtree(ENGINE/'one_captions/static')
shutil.copytree(ROOT/'one_captions/static',ENGINE/'one_captions/static')
assert (ENGINE/'bin'/('ffmpeg.exe' if os.name=='nt' else 'ffmpeg')).is_file(),'Run fetch_binaries.py first.'
args=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--contents-directory','.','--name','one-backend','--paths',str(ROOT),'--paths',str(ROOT/'one_captions'),'--distpath',str(RUNTIME),'--workpath',str(ROOT/'build/pyinstaller'),'--specpath',str(ROOT/'build'),
 '--collect-all','faster_whisper','--collect-all','ctranslate2','--collect-all','onnxruntime','--collect-all','tokenizers','--collect-all','huggingface_hub','--collect-all','av','--collect-all','PIL',str(ROOT/'one_captions/backend_entry.py')]
subprocess.run(args,check=True)
exe=RUNTIME/'one-backend'/('one-backend.exe' if os.name=='nt' else 'one-backend')
assert exe.is_file(),exe
print('Runtime ready:',exe)
