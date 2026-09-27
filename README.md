# ONE Captions

A local Hebrew subtitle studio for macOS Intel and Windows x64. Drop an MP4 or MOV, transcribe speech, edit captions in the preview or by chat, and export a burned-in MP4. The editor shares one project state across direct manipulation, chat, Undo/Redo and export.

## Download and first launch

Install the DMG on macOS or the Windows installer from [Releases](../../releases). No Terminal or separate Python installation is needed. The first launch prepares the Hebrew transcription and local assistant models in the user's application data. This is a multi-gigabyte download; the startup window explains the wait. Video projects, model weights, logs and exports stay on the user's computer and are never included in this repository.

The macOS build currently targets Intel. The Windows build targets x64. These builds are unsigned; macOS Gatekeeper and Windows SmartScreen may require the user to allow the application. A signed/notarized distribution requires publisher certificates.

## Development

Use Python 3.11 and Node 22. Install `requirements.lock` and `one_captions/package-lock.json`. Run the two unittest suites before building. `scripts/fetch_binaries.py` stages FFmpeg, ffprobe and llama-server for the host OS; `scripts/build_runtime.py` freezes the Python engine; `npm run build:mac` or `npm run build:win` under `one_captions` creates the installer. The tag-triggered workflow builds each platform on its own GitHub runner, smoke-tests its frozen backend and attaches the two successful installers to a Release.

The shared engine is `captions.py`, `stt.py` and `one_captions/*.py`; the Electron shell is `one_captions/desktop`. This repository is a clean release copy and does not modify the existing Pini-Captions installation. The source code contains no model weights or user projects. First-launch models: [ivrit-ai/whisper-large-v3-ct2](https://huggingface.co/ivrit-ai/whisper-large-v3-ct2) and [Qwen3-4B-GGUF](https://huggingface.co/Qwen/Qwen3-4B-GGUF). Third-party runtimes: [FFmpeg](https://ffmpeg.org), [llama.cpp](https://github.com/ggml-org/llama.cpp). Check their licenses before redistributing customized builds.

## Validation

`python -m unittest discover -s tests -p 'test_*.py'` and `python -m unittest discover -s one_captions/tests -p 'test_*.py'`. `scripts/smoke_runtime.py` checks the frozen backend and static UI on the build host. Video/AI fidelity should be reviewed with representative media before publishing to clients.
