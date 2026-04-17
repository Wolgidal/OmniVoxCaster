# OmniVox Caster — Voxcaster Imperialis

An AI-powered screen reader that reads any text area on your screen aloud — using your own cloned voice.

## Features

- **Voice Cloning** — Record your own voice or upload a WAV/MP3 sample (5–30 sec). The AI replicates the voice using Coqui XTTSv2.
- **Screen OCR** — Select any region on screen with a hotkey. EasyOCR extracts the text automatically.
- **Translation** — Optionally translate recognized text to German or English before reading (via Google Translate).
- **Multiple Voices** — Store and manage several voice profiles, switchable at any time.
- **Adjustable Speed** — Speaking rate from 0.5× to 2.0×.
- **Warhammer 40K UI** — Dark Gothic design with brass accents.

## Installation

### Requirements

- Windows 10/11
- Python 3.10+
- NVIDIA GPU recommended (CUDA), CPU works but is slower

### Setup

```bash
# Clone repository
git clone https://github.com/Wolgidal/OmniVoxCaster.git
cd OmniVoxCaster

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Run

```bash
venv\Scripts\activate
python main_overlay.py
```

Or use the included `start.bat`.

## Usage

1. **Add a voice** — Click "🎤 Aufnehmen" to record, or "📁 Hinzufügen" to import a WAV/MP3 file.
2. **Start** — Click "▶ AKTIVIEREN" (available after models have loaded).
3. **Select text** — Press the hotkey (default: `ALT+Q`) and drag a box around the text on screen.
4. OmniVox Caster reads the text aloud in the chosen voice.

Press `?` in the app header for the full in-app tutorial.

## User Data

All user data is stored locally on your machine:

```
%APPDATA%\OmniVox Caster\
├── config.ini        ← Settings
├── voices\           ← Voice profile files
└── quest_output.wav  ← Temporary audio (deleted on exit)
```

No data is sent to external servers except the text content when the translation feature is used (Google Translate).

## Legal Notice — Voice Cloning

This software enables voice cloning using AI. By using this application you confirm that:

- You only use voice recordings of yourself or persons who have given explicit consent.
- You will not use cloned voices to deceive, impersonate, or defraud others.
- You are aware that cloning the voices of public figures without consent may violate personality rights and applicable law.
- The developer assumes no liability for misuse. Full responsibility lies with the user.

The application provides no built-in voice samples. Any voice files uploaded by the user are their sole responsibility.

## License

This project's source code is licensed under the **MIT License** — see [LICENSE](LICENSE).

---

## Open Source Notices

This software includes components under the following licenses:

| Component | License | Notes |
|---|---|---|
| [Coqui TTS / XTTSv2](https://github.com/coqui-ai/TTS) | Coqui Public Model License (CPML) | Non-commercial use only |
| [EasyOCR](https://github.com/JaidedAI/EasyOCR) | Apache License 2.0 | |
| [deep-translator](https://github.com/nidhaloff/deep-translator) | MIT License | |
| [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) | MIT License | |
| [PyTorch](https://pytorch.org) | BSD 3-Clause License | |
| [sounddevice](https://github.com/spatialaudio/python-sounddevice) | MIT License | |
| [soundfile](https://github.com/bastibe/python-soundfile) | BSD 3-Clause License | |
| [mss](https://github.com/BoboTiG/python-mss) | MIT License | |
| [keyboard](https://github.com/boppreh/keyboard) | MIT License | |
| [NumPy](https://numpy.org) | BSD 3-Clause License | |

Full license texts are provided in [NOTICE](NOTICE).

> **Note on Coqui CPML:** The XTTSv2 model weights are licensed under the Coqui Public Model License, which permits non-commercial use. For commercial applications, a separate license from Coqui AI is required.
