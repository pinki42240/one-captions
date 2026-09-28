"""One frozen executable serves setup, backend and workers."""
import sys
if len(sys.argv)>1 and sys.argv[1]=='--check-dependencies':
 import av,ctranslate2,faster_whisper,numpy,onnxruntime,tokenizers
 from PIL import ImageFont
 assert 'float32' in ctranslate2.get_supported_compute_types('cpu')
 assert 'CPUExecutionProvider' in onnxruntime.get_available_providers()
 assert faster_whisper.WhisperModel and av.open and numpy.ndarray and tokenizers.Tokenizer and ImageFont.truetype
 print('Frozen Python, Whisper, CTranslate2, PyAV, ONNX Runtime, NumPy, Pillow and tokenizers: OK')
elif len(sys.argv)>1 and sys.argv[1]=='--setup':
 from one_captions.setup_models import setup
 setup(sys.argv[2])
elif len(sys.argv)>1 and sys.argv[1]=='--worker':
 sys.argv.pop(1)
 from one_captions import worker
else:
 from one_captions import server
 server.main()
