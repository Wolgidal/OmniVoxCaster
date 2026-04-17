# OmniVox Caster — Voxcaster Imperialis

An AI-powered screen reader that reads any text area on your screen aloud — using your own cloned voice.

> **Language / Sprache:** The app supports German and English. Switch via the DE/EN button in the header.  
> **Sprache:** Die App unterstützt Deutsch und Englisch. Umschalten über den DE/EN-Knopf im Header.

---

## Features

- **Voice Cloning** — Record your own voice or upload a WAV/MP3 sample (5–30 sec). The AI replicates it using Coqui XTTSv2.
- **Screen OCR** — Select any region on screen with a hotkey. EasyOCR extracts the text automatically.
- **Translation** — Optionally translate recognized text to German or English before reading (via Google Translate).
- **Multiple Voices** — Store and manage several voice profiles, switchable at any time.
- **Adjustable Speed** — Speaking rate from 0.5× to 2.0×.

---

## Installation (Windows)

### Requirements

| | |
|---|---|
| OS | Windows 10 / 11 |
| Python | 3.10 or newer |
| GPU | NVIDIA GPU recommended (CUDA). CPU works but is slower. |
| Disk space | ~5 GB (dependencies + AI models) |
| Internet | Required once for downloading AI models (~2 GB) |

---

### Step 1 — Install Python

Download Python 3.10+ from **https://www.python.org/downloads/**

> ⚠️ During installation, check **"Add Python to PATH"**

---

### Step 2 — Download OmniVox Caster

**Option A — via Git:**
```
git clone https://github.com/Wolgidal/OmniVoxCaster.git
```

**Option B — as ZIP:**  
Click **Code → Download ZIP** on GitHub, then extract the folder.

---

### Step 3 — Run install.bat

Double-click **`install.bat`** in the extracted folder.

The installer will:
1. Create a virtual Python environment (`venv\`)
2. Detect your GPU and install the correct PyTorch version (CUDA or CPU)
3. Install all other dependencies

This takes a few minutes. Internet connection required.

---

### Step 4 — Start the app

Double-click **`start.bat`**

On first launch, the AI models are downloaded automatically (~2 GB). This happens only once.

---

## Usage

1. **Accept** the terms of use (first launch only)
2. **Add a voice** — Click `🎤 Record` to record your voice, or `📁 Add File` to import a WAV/MP3
3. **Wait** for models to load (status bar shows when ready)
4. **Activate** — Click `▶ ACTIVATE`
5. **Select text** — Press the hotkey (default: `ALT+Q`) and drag a box around any text on screen
6. OmniVox Caster reads the text aloud in your chosen voice

Press `?` in the app header for the full in-app tutorial.

---

## User Data

All data is stored locally on your machine:

```
%APPDATA%\OmniVoxCaster\
├── config.ini        ← Settings
├── voices\           ← Voice profile files (.wav)
└── quest_output.wav  ← Temporary audio (deleted on exit)
```

No data is sent to external servers, except the text content when the optional translation feature is used (Google Translate API).

---

## Legal Notice — Voice Cloning

This software enables AI voice cloning. By using it you confirm that:

- You only use voice recordings of yourself or persons who have given explicit consent.
- You will not use cloned voices to deceive, impersonate, or defraud others.
- Cloning the voices of public figures without consent may violate personality rights and applicable law.
- The developer assumes no liability for misuse. Full responsibility lies with the user.

The application provides no built-in voice samples. Any voice files used are the user's sole responsibility.

---

## License

This project's source code is licensed under the **MIT License** — see [LICENSE](LICENSE).

---

## Open Source Components

| Component | License |
|---|---|
| [Coqui TTS / XTTSv2](https://github.com/coqui-ai/TTS) | Coqui Public Model License (CPML) — non-commercial use only |
| [EasyOCR](https://github.com/JaidedAI/EasyOCR) | Apache License 2.0 |
| [deep-translator](https://github.com/nidhaloff/deep-translator) | MIT License |
| [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) | MIT License |
| [PyTorch](https://pytorch.org) | BSD 3-Clause License |
| [sounddevice](https://github.com/spatialaudio/python-sounddevice) | MIT License |
| [soundfile](https://github.com/bastibe/python-soundfile) | BSD 3-Clause License |
| [mss](https://github.com/BoboTiG/python-mss) | MIT License |
| [keyboard](https://github.com/boppreh/keyboard) | MIT License |
| [NumPy](https://numpy.org) | BSD 3-Clause License |

Full license texts: [NOTICE](NOTICE)

> **Note on Coqui CPML:** The XTTSv2 model weights are licensed under the Coqui Public Model License, which permits non-commercial use only. A separate license from Coqui AI is required for commercial applications.
