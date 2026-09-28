# Third-party software and model notices

ONE Captions bundles open-source components in its installers and downloads models on first launch. This notice is also included in the desktop resources.

- FFmpeg and ffprobe: [FFmpeg](https://ffmpeg.org/) via [evermeet.cx macOS Intel build](https://evermeet.cx/ffmpeg/), [Martin Riedl's macOS Apple Silicon build](https://ffmpeg.martin-riedl.de/), or [gyan.dev Windows build](https://www.gyan.dev/ffmpeg/builds/). If a primary source is unreachable, the build uses a SHA-256-pinned [Youwee macOS arm64 build](https://github.com/vanloctech/ffmpeg-macos/releases/tag/ffmpeg-2026.06.11) or [BtbN Windows x64 build](https://github.com/BtbN/FFmpeg-Builds/releases/tag/autobuild-2026-09-28-13-06). FFmpeg builds with libx264 are distributed under GPL; source and license information are available from those providers and [FFmpeg](https://ffmpeg.org/legal.html). The build script checks the actual tools used.
- llama.cpp: [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp), official `b11223` CPU binaries, MIT license.
- Noto Sans Hebrew: [Google Fonts](https://github.com/google/fonts/tree/main/ofl/notosanshebrew), SIL Open Font License 1.1. The complete font license is at `fonts/OFL.txt`.
- ivrit-ai Whisper: [ivrit-ai/whisper-large-v3-ct2](https://huggingface.co/ivrit-ai/whisper-large-v3-ct2), downloaded to local application data at first launch; not in this repository or installer.
- Qwen3-4B-GGUF: [Qwen/Qwen3-4B-GGUF](https://huggingface.co/Qwen/Qwen3-4B-GGUF), Apache-2.0, downloaded to local application data at first launch; not in this repository or installer.
- Electron, Python libraries and their transitive dependencies retain their respective upstream licenses.
