import time
import os
import threading
import queue
import configparser
import shutil
import re
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="TTS")
warnings.filterwarnings("ignore", category=UserWarning, module="transformers")

import torch
import torchaudio

_orig_torch_load = torch.load
def _patched_torch_load(f, *args, **kwargs):
    kwargs.setdefault("weights_only", False)
    return _orig_torch_load(f, *args, **kwargs)
torch.load = _patched_torch_load

# torchaudio 2.5+ uses torchcodec by default which is not installed.
# Replace torchaudio.load with a soundfile-based version that has the same interface.
try:
    import soundfile as _sf

    def _torchaudio_load_sf(path, *_):
        data, sr = _sf.read(str(path), dtype="float32", always_2d=True)
        return torch.from_numpy(data.T), sr  # (channels, samples), sample_rate

    torchaudio.load = _torchaudio_load_sf
except Exception:
    pass

import numpy as np
import mss
import easyocr
import keyboard
from TTS.api import TTS

import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import sounddevice as sd
import soundfile as sf

# ============================================================
#  KONSTANTEN
# ============================================================
APP_DIR     = os.path.dirname(os.path.abspath(__file__))
APPDATA_DIR = os.path.join(os.environ.get("APPDATA", APP_DIR), "OmniVoxCaster")
os.makedirs(APPDATA_DIR, exist_ok=True)
SAMPLE_RATE = 22050
VERSION     = "0.5"

COLORS = {
    "bg":       "#09070a",
    "surface":  "#120e0f",
    "border":   "#3a2810",
    "accent":   "#c8a44a",
    "accent2":  "#9b1a1a",
    "green":    "#3d7a35",
    "red":      "#cc2200",
    "yellow":   "#c8960a",
    "text":     "#e0d4b8",
    "text_dim": "#6e5e42",
    "ornament": "#5a3c15",
}

DEFAULT_CONFIG = """\
[Einstellungen]
hotkey = alt+q
sprache = de
stimme_datei = stimme_vorlage.wav
ausgabe_datei = quest_output.wav
ausgabesprache = auto
geschwindigkeit = 1.0
ui_sprache = de

[WoW_Woerterbuch]
# Korrekturen für OCR-Fehler oder WoW-Begriffe
# Beispiel:
# Hollschrei = Höllschrei
"""

# ============================================================
#  ÜBERSETZUNGEN
# ============================================================
TRANSLATIONS = {
    "de": {
        # RecordDialog
        "rec_title":    "OmniVox Caster — Stimmvorlage aufnehmen",
        "rec_heading":  "☩   S T I M M V O R L A G E",
        "rec_desc":     "Sprich 5–15 Sekunden in dein Mikrofon.\nDie Aufnahme wird als Stimmvorlage gespeichert.",
        "rec_ready":    "◈  Bereit",
        "rec_start":    "🎤  Aufnahme starten",
        "rec_stop":     "⏹  Aufnahme stoppen",
        "rec_redo":     "🔄  Neu aufnehmen",
        "rec_running":  "◈  Aufnahme läuft ...",
        "rec_done":     "◈  Aufnahme bereit  ({:.1f} s)",
        "rec_no_data":  "◈  Keine Daten erfasst",
        "rec_save":     "💾  Speichern",
        "rec_cancel":   "Abbrechen",
        # DisclaimerDialog
        "disc_title":   "OmniVox Caster — Nutzungsvereinbarung",
        "disc_heading": "☩   N U T Z U N G S V E R E I N B A R U N G",
        "disc_subtitle":"OmniVox Caster — Voxcaster Imperialis",
        "disc_text": (
            "STIMMKLONIERUNG — RECHTLICHE HINWEISE\n\n"
            "Diese Software verwendet KI-Technologie zur Stimmklonierung (Voice Cloning). "
            "Durch die Nutzung dieser Software erklärst du dich mit folgenden Bedingungen einverstanden:\n\n"
            "1.  EINWILLIGUNG\n"
            "Du verwendest ausschließlich Stimmaufnahmen von Personen, die dir ihre ausdrückliche "
            "Einwilligung zur Nutzung ihrer Stimme erteilt haben — oder deine eigene Stimme.\n\n"
            "2.  KEINE TÄUSCHUNG\n"
            "Du wirst die geklonte Stimme nicht einsetzen, um Personen zu täuschen, zu manipulieren "
            "oder in die Irre zu führen (z. B. Deepfake-Betrug, Identitätsdiebstahl, Missbrauch).\n\n"
            "3.  URHEBERRECHT & PERSÖNLICHKEITSRECHTE\n"
            "Prominente Stimmen, Synchronsprecher und andere öffentliche Persönlichkeiten sind "
            "rechtlich geschützt. Das unerlaubte Klonen und Verwenden solcher Stimmen kann "
            "zivil- und strafrechtliche Konsequenzen haben.\n\n"
            "4.  LIZENZ DES KI-MODELLS\n"
            "Das verwendete TTS-Modell (Coqui XTTSv2) steht unter der Coqui Public Model License "
            "(CPML), welche die nicht-kommerzielle Nutzung erlaubt. Für kommerzielle Anwendungen "
            "ist eine separate Lizenz bei Coqui AI erforderlich.\n\n"
            "5.  HAFTUNGSAUSSCHLUSS\n"
            "Der Entwickler dieser Software übernimmt keinerlei Haftung für missbräuchliche "
            "Verwendung. Die vollständige Verantwortung für eine rechtskonforme Nutzung liegt "
            "beim Anwender.\n\n"
            "6.  DATENSCHUTZ\n"
            "Alle Stimmdaten werden ausschließlich lokal auf deinem Computer gespeichert "
            "(%APPDATA%\\OmniVoxCaster\\). Es werden keine Stimm- oder Audiodaten an externe Server "
            "übertragen. Die optionale Übersetzungsfunktion sendet ausschließlich den erkannten "
            "Text an die Google Translate API."
        ),
        "disc_accept":  "✔   Ich stimme zu und akzeptiere die Bedingungen",
        "disc_decline": "✖   Ablehnen & Beenden",
        # HelpDialog
        "help_title":   "OmniVox Caster — Hilfe & Tutorial",
        "help_heading": "☩   H I L F E  &  T U T O R I A L",
        "help_subtitle":"OmniVox Caster — Voxcaster Imperialis",
        "help_close":   "✔   Schließen",
        "help_sections": [
            ("❖  WAS IST OMNIVOX?",
             "OmniVox Caster ist ein KI-gestützter Bildschirm-Vorleser. Er liest Text aus jedem Bereich "
             "deines Bildschirms vor — in deiner eigenen Stimme oder einer hochgeladenen "
             "Stimmvorlage. Ideal zum Vorlesen von Quest-Texten, Dialogen oder Untertiteln in Spielen."),
            ("❖  SCHRITT 1 — STIMMVORLAGE EINRICHTEN",
             "Du benötigst eine kurze Sprachaufnahme (5–30 Sek.) als Vorlage.\n\n"
             "🎤 Aufnehmen  — Nimm direkt über dein Mikrofon auf (5–15 Sek. laut und deutlich sprechen).\n"
             "📁 Hinzufügen — Lade eine vorhandene WAV- oder MP3-Datei.\n\n"
             "Mehrere Stimmen können gespeichert und per Dropdown gewechselt werden.\n"
             "Stimmen werden lokal in %APPDATA%\\OmniVoxCaster\\voices\\ gespeichert."),
            ("❖  SCHRITT 2 — EINSTELLUNGEN",
             "AUSGABESPRACHE\n"
             "Wähle ob der Text in der Originalsprache vorgelesen oder vorher übersetzt werden soll "
             "(Deutsch / Englisch / Original).\n\n"
             "ÜBERTRAGUNGSRATE\n"
             "Stellt die Sprechgeschwindigkeit ein (0.5× bis 2.0×).\n\n"
             "AKTIVIERUNGS-RUNE\n"
             "Der Tastatur-Hotkey zum Auslösen der Texterkennung. Standard: ALT+Q.\n"
             "Klicke auf den Hotkey-Button und drücke die gewünschte Tastenkombination."),
            ("❖  SCHRITT 3 — VERWENDEN",
             "1. Klicke auf ▶ AKTIVIEREN (erst verfügbar, nachdem die KI-Modelle geladen sind).\n"
             "2. Drücke den Hotkey (z. B. ALT+Q).\n"
             "3. Ziehe mit der Maus einen Rahmen um den Text, den du vorlesen möchtest.\n"
             "4. OmniVox Caster erkennt den Text und liest ihn in der gewählten Stimme vor."),
            ("❖  STEUERUNG WÄHREND DER WIEDERGABE",
             "⏸  Pause        — Wiedergabe pausieren / fortsetzen.\n"
             "🔁  Wiederholen — Letzten Text nochmals vorlesen.\n"
             "⏹  Stoppen     — Klicke erneut auf Wiederholen während der Wiedergabe.\n"
             "ESC              — Aktuelle Wiedergabe sofort abbrechen.\n"
             "ESC (inaktiv)   — App deaktivieren."),
            ("❖  TECHNISCHE HINWEISE",
             "• Beim ersten Start werden KI-Modelle heruntergeladen und geladen "
             "(EasyOCR + Coqui XTTSv2). Dies kann einige Minuten dauern.\n"
             "• Alle Nutzerdaten werden lokal gespeichert: %APPDATA%\\OmniVoxCaster\\\n"
             "• Internetverbindung wird nur für die optionale Übersetzung (Google Translate) benötigt.\n"
             "• Das temporäre Ausgabe-Audio wird beim Beenden automatisch gelöscht."),
        ],
        # Main UI
        "section_voice":    "STIMMVORLAGE",
        "btn_record":       "🎤  Aufnehmen",
        "btn_add":          "📁  Hinzufügen",
        "section_outlang":  "AUSGABESPRACHE",
        "lang_original":    "Original",
        "lang_de":          "Deutsch",
        "lang_en":          "Englisch",
        "lang_values":      ["Original", "Deutsch", "Englisch"],
        "section_speed":    "ÜBERTRAGUNGSRATE",
        "section_hotkey":   "AKTIVIERUNGS-RUNE",
        "btn_activate":     "▶   A K T I V I E R E N",
        "btn_deactivate":   "■   D E A K T I V I E R E N",
        "btn_pause":        "⏸   Pause",
        "btn_resume":       "▶   Weiter",
        "btn_repeat":       "🔁   Wiederholen",
        "btn_stop_repeat":  "⏹   Stoppen",
        "footer_esc":       "✠   ESC — Übertragung abbrechen   ✠",
        # Status messages
        "status_loading":        "◈  Lade Modelle ...",
        "status_ready":          "◈  Systeme bereit — Voxcaster online",
        "status_load_error":     "◈  Ladefehler! Konsole prüfen.",
        "status_active":         "◈  Aktiv  —  [{}] zum Auswählen",
        "status_deactivated":    "◈  Deaktiviert",
        "status_selecting":      "◈  Bereich auswählen ...",
        "status_ocr":            "◈  Erkenne Text ...",
        "status_translating":    "◈  Übersetze Text ...",
        "status_generating":     "◈  Generiere Vox-Signal ...",
        "status_playing":        "◈  Übertragung läuft ...",
        "status_paused":         "◈  Übertragung pausiert",
        "status_no_translator":  "◈  Übersetzungs-Modul fehlt",
        "status_translate_fail": "◈  Übersetzung fehlgeschlagen",
        "status_voice_changed":  "◈  Stimme gewechselt ... bereite vor",
        "status_renamed":        "◈  Umbenannt zu '{}'",
        "status_voice_deleted":  "◈  Stimme gelöscht",
        "status_hotkey_wait":    "◈  Warte auf neue Aktivierungs-Rune ...",
        "status_hotkey_saved":   "◈  Rune gespeichert: {}",
        "status_repeating":      "◈  Wiederhole Übertragung ...",
        # Messageboxes
        "no_voice_title":           "Keine Stimmvorlage",
        "no_voice_msg":             "Bitte erst eine Stimmvorlage aufnehmen oder eine Datei laden.",
        "wait_models_title":        "Bitte warten",
        "wait_models_msg":          "Die KI-Modelle werden noch geladen ...",
        "wait_voice_msg":           "Stimmvorlage wird noch vorbereitet ...",
        "hotkey_active_title":      "Hinweis",
        "hotkey_active_msg":        "Bitte stoppe zuerst die Anwendung (auf 'STOP' klicken), um den Hotkey zu ändern.",
        "rename_dialog_text":       "Neuer Name für die Stimme (ohne .wav):",
        "rename_title":             "Umbenennen",
        "rename_exists_title":      "Fehler",
        "rename_exists_msg":        "Eine Stimme mit diesem Namen existiert bereits.",
        "delete_title":             "Löschen",
        "delete_msg":               "Soll die Stimme '{}' wirklich gelöscht werden?",
        "save_dialog_text":         "Name für die neue Aufnahme:",
        "save_title":               "Aufnahme speichern",
        "voice_file_title":         "Stimmvorlage wählen",
        "pydub_error_title":        "Fehler",
        "pydub_error_msg":          "pydub ist nicht installiert.\nInstalliere es mit:\n  pip install pydub\n\nFür MP3-Support wird außerdem ffmpeg benötigt.",
        "mp3_error_title":          "Fehler",
        "mp3_error_msg":            "MP3-Konvertierung fehlgeschlagen:\n{}",
        "translator_missing_title": "Fehlendes Modul",
        "translator_missing_msg":   "Das Modul 'deep-translator' wurde nicht gefunden.\nFehler: {}\n\nBitte starte das Programm neu. Achte darauf, es innerhalb deiner '(venv)' Umgebung zu starten!",
        "no_voice_found":           "Keine Stimme gefunden",
        "hotkey_input":             "Eingabe...",
    },
    "en": {
        # RecordDialog
        "rec_title":    "OmniVox Caster — Record Voice Sample",
        "rec_heading":  "☩   V O I C E   S A M P L E",
        "rec_desc":     "Speak for 5–15 seconds into your microphone.\nThe recording will be saved as a voice sample.",
        "rec_ready":    "◈  Ready",
        "rec_start":    "🎤  Start Recording",
        "rec_stop":     "⏹  Stop Recording",
        "rec_redo":     "🔄  Record Again",
        "rec_running":  "◈  Recording ...",
        "rec_done":     "◈  Recording ready  ({:.1f} s)",
        "rec_no_data":  "◈  No data captured",
        "rec_save":     "💾  Save",
        "rec_cancel":   "Cancel",
        # DisclaimerDialog
        "disc_title":   "OmniVox Caster — Terms of Use",
        "disc_heading": "☩   T E R M S   O F   U S E",
        "disc_subtitle":"OmniVox Caster — Voxcaster Imperialis",
        "disc_text": (
            "VOICE CLONING — LEGAL NOTICE\n\n"
            "This software uses AI technology for voice cloning. "
            "By using this software you agree to the following terms:\n\n"
            "1.  CONSENT\n"
            "You only use voice recordings of persons who have given their explicit consent "
            "to the use of their voice — or your own voice.\n\n"
            "2.  NO DECEPTION\n"
            "You will not use the cloned voice to deceive, manipulate, or mislead people "
            "(e.g. deepfake fraud, identity theft, abuse).\n\n"
            "3.  COPYRIGHT & PERSONALITY RIGHTS\n"
            "Celebrity voices, voice actors, and other public figures are legally protected. "
            "Unauthorized cloning and use of such voices may have civil and criminal consequences.\n\n"
            "4.  AI MODEL LICENSE\n"
            "The TTS model used (Coqui XTTSv2) is licensed under the Coqui Public Model License "
            "(CPML), which permits non-commercial use. A separate license from Coqui AI is required "
            "for commercial applications.\n\n"
            "5.  DISCLAIMER\n"
            "The developer of this software accepts no liability for misuse. "
            "Full responsibility for lawful use lies with the user.\n\n"
            "6.  PRIVACY\n"
            "All voice data is stored exclusively locally on your computer "
            "(%APPDATA%\\OmniVoxCaster\\). No voice or audio data is transmitted to external servers. "
            "The optional translation function only sends the recognized text to the Google Translate API."
        ),
        "disc_accept":  "✔   I agree and accept the terms",
        "disc_decline": "✖   Decline & Exit",
        # HelpDialog
        "help_title":   "OmniVox Caster — Help & Tutorial",
        "help_heading": "☩   H E L P  &  T U T O R I A L",
        "help_subtitle":"OmniVox Caster — Voxcaster Imperialis",
        "help_close":   "✔   Close",
        "help_sections": [
            ("❖  WHAT IS OMNIVOX?",
             "OmniVox Caster is an AI-powered screen reader. It reads text from any area of your "
             "screen aloud — in your own voice or an uploaded voice sample. Ideal for reading "
             "quest texts, dialogues, or subtitles in games."),
            ("❖  STEP 1 — SET UP VOICE SAMPLE",
             "You need a short voice recording (5–30 sec.) as a template.\n\n"
             "🎤 Record  — Record directly via your microphone (5–15 sec., speak clearly and loudly).\n"
             "📁 Add File — Load an existing WAV or MP3 file.\n\n"
             "Multiple voices can be saved and switched via the dropdown.\n"
             "Voices are stored locally in %APPDATA%\\OmniVoxCaster\\voices\\."),
            ("❖  STEP 2 — SETTINGS",
             "OUTPUT LANGUAGE\n"
             "Choose whether the text is read in the original language or translated first "
             "(German / English / Original).\n\n"
             "TRANSMISSION RATE\n"
             "Sets the speaking speed (0.5× to 2.0×).\n\n"
             "ACTIVATION RUNE\n"
             "The keyboard hotkey to trigger text recognition. Default: ALT+Q.\n"
             "Click the hotkey button and press the desired key combination."),
            ("❖  STEP 3 — USING",
             "1. Click ▶ ACTIVATE (only available after AI models have loaded).\n"
             "2. Press the hotkey (e.g. ALT+Q).\n"
             "3. Drag a frame around the text you want to read.\n"
             "4. OmniVox Caster recognizes the text and reads it in the selected voice."),
            ("❖  CONTROLS DURING PLAYBACK",
             "⏸  Pause       — Pause / resume playback.\n"
             "🔁  Repeat      — Re-read the last text.\n"
             "⏹  Stop        — Click Repeat again during playback.\n"
             "ESC             — Immediately abort current playback.\n"
             "ESC (inactive)  — Deactivate the app."),
            ("❖  TECHNICAL NOTES",
             "• On first launch, AI models are downloaded and loaded "
             "(EasyOCR + Coqui XTTSv2). This may take a few minutes.\n"
             "• All user data is stored locally: %APPDATA%\\OmniVoxCaster\\\n"
             "• Internet connection is only needed for the optional translation (Google Translate).\n"
             "• The temporary output audio is automatically deleted on exit."),
        ],
        # Main UI
        "section_voice":    "VOICE SAMPLE",
        "btn_record":       "🎤  Record",
        "btn_add":          "📁  Add File",
        "section_outlang":  "OUTPUT LANGUAGE",
        "lang_original":    "Original",
        "lang_de":          "German",
        "lang_en":          "English",
        "lang_values":      ["Original", "German", "English"],
        "section_speed":    "TRANSMISSION RATE",
        "section_hotkey":   "ACTIVATION RUNE",
        "btn_activate":     "▶   A C T I V A T E",
        "btn_deactivate":   "■   D E A C T I V A T E",
        "btn_pause":        "⏸   Pause",
        "btn_resume":       "▶   Resume",
        "btn_repeat":       "🔁   Repeat",
        "btn_stop_repeat":  "⏹   Stop",
        "footer_esc":       "✠   ESC — Abort Transmission   ✠",
        # Status messages
        "status_loading":        "◈  Loading models ...",
        "status_ready":          "◈  Systems ready — Voxcaster online",
        "status_load_error":     "◈  Load error! Check console.",
        "status_active":         "◈  Active  —  [{}] to select",
        "status_deactivated":    "◈  Deactivated",
        "status_selecting":      "◈  Select region ...",
        "status_ocr":            "◈  Recognizing text ...",
        "status_translating":    "◈  Translating text ...",
        "status_generating":     "◈  Generating vox signal ...",
        "status_playing":        "◈  Transmission running ...",
        "status_paused":         "◈  Transmission paused",
        "status_no_translator":  "◈  Translation module missing",
        "status_translate_fail": "◈  Translation failed",
        "status_voice_changed":  "◈  Voice changed ... preparing",
        "status_renamed":        "◈  Renamed to '{}'",
        "status_voice_deleted":  "◈  Voice deleted",
        "status_hotkey_wait":    "◈  Waiting for new activation rune ...",
        "status_hotkey_saved":   "◈  Rune saved: {}",
        "status_repeating":      "◈  Repeating transmission ...",
        # Messageboxes
        "no_voice_title":           "No Voice Sample",
        "no_voice_msg":             "Please record a voice sample or load a file first.",
        "wait_models_title":        "Please wait",
        "wait_models_msg":          "AI models are still loading ...",
        "wait_voice_msg":           "Voice sample is still being prepared ...",
        "hotkey_active_title":      "Note",
        "hotkey_active_msg":        "Please stop the application first (click 'STOP') to change the hotkey.",
        "rename_dialog_text":       "New name for the voice (without .wav):",
        "rename_title":             "Rename",
        "rename_exists_title":      "Error",
        "rename_exists_msg":        "A voice with this name already exists.",
        "delete_title":             "Delete",
        "delete_msg":               "Really delete voice '{}'?",
        "save_dialog_text":         "Name for the new recording:",
        "save_title":               "Save Recording",
        "voice_file_title":         "Select Voice Sample",
        "pydub_error_title":        "Error",
        "pydub_error_msg":          "pydub is not installed.\nInstall it with:\n  pip install pydub\n\nFFmpeg is also required for MP3 support.",
        "mp3_error_title":          "Error",
        "mp3_error_msg":            "MP3 conversion failed:\n{}",
        "translator_missing_title": "Missing Module",
        "translator_missing_msg":   "The module 'deep-translator' was not found.\nError: {}\n\nPlease restart the program. Make sure to start it within your '(venv)' environment!",
        "no_voice_found":           "No voice found",
        "hotkey_input":             "Input...",
    },
}

_ui_lang = "de"

def t(key):
    return TRANSLATIONS[_ui_lang].get(key, key)


# ============================================================
#  AUFNAHME-DIALOG
# ============================================================
class RecordDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_save_callback):
        super().__init__(parent)
        self.on_save = on_save_callback
        self.recording = False
        self.audio_chunks = []
        self.stream = None
        self.recorded_data = None

        self.title(t("rec_title"))
        self.geometry("420x320")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["surface"])
        self.attributes("-topmost", True)
        self.grab_set()
        self._build()

    def _build(self):
        ctk.CTkFrame(self, fg_color=COLORS["accent"], height=2, corner_radius=0).pack(fill="x")

        ctk.CTkLabel(
            self,
            text=t("rec_heading"),
            font=("Palatino Linotype", 16, "bold"),
            text_color=COLORS["accent"],
        ).pack(pady=(14, 2))

        ctk.CTkLabel(
            self,
            text=t("rec_desc"),
            font=("Palatino Linotype", 12),
            text_color=COLORS["text_dim"],
            justify="center",
        ).pack(pady=(0, 14))

        self.indicator = ctk.CTkLabel(
            self,
            text=t("rec_ready"),
            font=("Palatino Linotype", 14, "bold"),
            text_color=COLORS["text_dim"],
        )
        self.indicator.pack(pady=4)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=14)

        self.rec_btn = ctk.CTkButton(
            btn_row,
            text=t("rec_start"),
            width=190, height=40,
            fg_color=COLORS["border"], hover_color=COLORS["ornament"],
            text_color=COLORS["accent"],
            font=("Palatino Linotype", 13, "bold"),
            command=self._toggle_recording,
        )
        self.rec_btn.grid(row=0, column=0, padx=6)

        self.save_btn = ctk.CTkButton(
            btn_row,
            text=t("rec_save"),
            width=150, height=40,
            state="disabled",
            fg_color=COLORS["green"], hover_color="#2d5c27",
            text_color=COLORS["text"],
            font=("Palatino Linotype", 13, "bold"),
            command=self._save,
        )
        self.save_btn.grid(row=0, column=1, padx=6)

        ctk.CTkButton(
            self,
            text=t("rec_cancel"),
            width=120, height=32,
            fg_color=COLORS["border"], hover_color=COLORS["ornament"],
            text_color=COLORS["text_dim"],
            font=("Palatino Linotype", 12),
            command=self.destroy,
        ).pack(pady=(0, 6))

        ctk.CTkFrame(self, fg_color=COLORS["accent"], height=2, corner_radius=0).pack(fill="x", side="bottom")

    def _toggle_recording(self):
        if not self.recording:
            self._start()
        else:
            self._stop()

    def _start(self):
        self.recording = True
        self.audio_chunks = []
        self.rec_btn.configure(text=t("rec_stop"), fg_color=COLORS["accent2"], hover_color="#6b1010")
        self.indicator.configure(text=t("rec_running"), text_color=COLORS["red"])
        self.save_btn.configure(state="disabled")

        def callback(indata, *_):
            if self.recording:
                self.audio_chunks.append(indata.copy())

        self.stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=callback)
        self.stream.start()

    def _stop(self):
        self.recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        if self.audio_chunks:
            self.recorded_data = np.concatenate(self.audio_chunks, axis=0)
            duration = len(self.recorded_data) / SAMPLE_RATE
            self.indicator.configure(
                text=t("rec_done").format(duration),
                text_color=COLORS["green"],
            )
            self.rec_btn.configure(
                text=t("rec_redo"),
                fg_color=COLORS["border"], hover_color=COLORS["ornament"],
                text_color=COLORS["accent"],
            )
            self.save_btn.configure(state="normal")
        else:
            self.indicator.configure(text=t("rec_no_data"), text_color=COLORS["yellow"])
            self.rec_btn.configure(
                text=t("rec_start"),
                fg_color=COLORS["border"], hover_color=COLORS["ornament"],
                text_color=COLORS["accent"],
            )

    def _save(self):
        if self.recorded_data is not None:
            dest = os.path.join(APP_DIR, "temp_rec.wav")
            sf.write(dest, self.recorded_data, SAMPLE_RATE)
            self.on_save(dest)
            self.destroy()

    def destroy(self):
        if self.recording and self.stream:
            self.recording = False
            self.stream.stop()
            self.stream.close()
        super().destroy()


# ============================================================
#  DISCLAIMER-DIALOG  (Erststart)
# ============================================================
class DisclaimerDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.accepted = False
        self.title(t("disc_title"))
        self.geometry("640x740")
        self.resizable(False, True)
        self.configure(fg_color=COLORS["surface"])
        self.attributes("-topmost", True)
        self.grab_set()
        self._build()

    def _build(self):
        ctk.CTkFrame(self, fg_color=COLORS["accent"], height=2, corner_radius=0).pack(fill="x")

        hdr_row = ctk.CTkFrame(self, fg_color="transparent")
        hdr_row.pack(fill="x", padx=16, pady=(12, 0))

        self._lbl_heading = ctk.CTkLabel(
            hdr_row, text=t("disc_heading"),
            font=("Palatino Linotype", 17, "bold"),
            text_color=COLORS["accent"],
        )
        self._lbl_heading.pack(side="left")

        self._lang_btn = ctk.CTkButton(
            hdr_row,
            text="DE" if _ui_lang == "de" else "EN",
            width=44, height=32, corner_radius=6,
            fg_color=COLORS["ornament"], hover_color=COLORS["border"],
            text_color=COLORS["accent"],
            font=("Palatino Linotype", 12, "bold"),
            command=self._toggle_language,
        )
        self._lang_btn.pack(side="right")

        self._lbl_sub = ctk.CTkLabel(
            self, text=t("disc_subtitle"),
            font=("Palatino Linotype", 11), text_color=COLORS["text_dim"],
        )
        self._lbl_sub.pack(pady=(2, 8))

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["border"], corner_radius=8)
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        self._lbl_text = ctk.CTkLabel(
            scroll, text=t("disc_text"),
            font=("Palatino Linotype", 14),
            text_color=COLORS["text"], justify="left",
            wraplength=570, anchor="w",
        )
        self._lbl_text.pack(anchor="w", padx=12, pady=10)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=(0, 10))

        self._btn_accept = ctk.CTkButton(
            btn_row, text=t("disc_accept"),
            height=48, fg_color=COLORS["green"], hover_color="#2d5c27",
            text_color=COLORS["text"], font=("Palatino Linotype", 14, "bold"),
            command=self._accept,
        )
        self._btn_accept.pack(padx=8, pady=(0, 6))

        self._btn_decline = ctk.CTkButton(
            btn_row, text=t("disc_decline"),
            height=40, fg_color=COLORS["border"], hover_color=COLORS["accent2"],
            text_color=COLORS["text_dim"], font=("Palatino Linotype", 13),
            command=self.destroy,
        )
        self._btn_decline.pack(padx=8)

        ctk.CTkFrame(self, fg_color=COLORS["accent"], height=2, corner_radius=0).pack(fill="x", side="bottom")

    def _toggle_language(self):
        global _ui_lang
        _ui_lang = "en" if _ui_lang == "de" else "de"
        self.title(t("disc_title"))
        self._lang_btn.configure(text="DE" if _ui_lang == "de" else "EN")
        self._lbl_heading.configure(text=t("disc_heading"))
        self._lbl_sub.configure(text=t("disc_subtitle"))
        self._lbl_text.configure(text=t("disc_text"))
        self._btn_accept.configure(text=t("disc_accept"))
        self._btn_decline.configure(text=t("disc_decline"))

    def _accept(self):
        self.accepted = True
        self.destroy()

    def destroy(self):
        try:
            self.grab_release()
        except Exception:
            pass
        super().destroy()


# ============================================================
#  HILFE-DIALOG
# ============================================================
class HelpDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title(t("help_title"))
        self.geometry("640x720")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["surface"])
        self.attributes("-topmost", True)
        self._build()

    def _build(self):
        ctk.CTkFrame(self, fg_color=COLORS["accent"], height=2, corner_radius=0).pack(fill="x")

        ctk.CTkLabel(self, text=t("help_heading"),
                     font=("Palatino Linotype", 16, "bold"),
                     text_color=COLORS["accent"]).pack(pady=(14, 2))
        ctk.CTkLabel(self, text=t("help_subtitle"),
                     font=("Palatino Linotype", 11), text_color=COLORS["text_dim"]).pack(pady=(0, 8))

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["border"], corner_radius=8, height=560)
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        for title, body in t("help_sections"):
            ctk.CTkLabel(scroll, text=title, font=("Palatino Linotype", 14, "bold"),
                         text_color=COLORS["accent"], anchor="w",
                         justify="left").pack(anchor="w", padx=10, pady=(14, 2))
            ctk.CTkLabel(scroll, text=body, font=("Palatino Linotype", 13),
                         text_color=COLORS["text"], justify="left",
                         wraplength=570, anchor="w").pack(anchor="w", padx=16, pady=(0, 2))
            ctk.CTkFrame(scroll, fg_color=COLORS["ornament"], height=1,
                         corner_radius=0).pack(fill="x", padx=10, pady=(8, 0))

        ctk.CTkButton(self, text=t("help_close"), height=40, width=170,
                      fg_color=COLORS["border"], hover_color=COLORS["ornament"],
                      text_color=COLORS["accent"], font=("Palatino Linotype", 14, "bold"),
                      command=self.destroy).pack(pady=8)

        ctk.CTkFrame(self, fg_color=COLORS["accent"], height=2, corner_radius=0).pack(fill="x", side="bottom")


# ============================================================
#  REGION-SELECTOR
# ============================================================
class RegionSelector:
    def __init__(self, parent):
        self.selection_box = None
        self.top = tk.Toplevel(parent)
        self.top.attributes("-alpha", 0.4)
        self.top.attributes("-fullscreen", True)
        self.top.attributes("-topmost", True)
        self.top.overrideredirect(True)

        self.canvas = tk.Canvas(self.top, cursor="none", bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.cursor_v = self.canvas.create_line(0, 0, 0, 0, fill=COLORS["accent"], width=2)
        self.cursor_h = self.canvas.create_line(0, 0, 0, 0, fill=COLORS["accent"], width=2)
        self.cursor_size = 20

        self.start_x = self.start_y = self.rect = None
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.top.bind("<Escape>", lambda *_: self.top.destroy())

    def _on_mouse_move(self, event):
        x, y = event.x, event.y
        self.canvas.coords(self.cursor_v, x, y - self.cursor_size, x, y + self.cursor_size)
        self.canvas.coords(self.cursor_h, x - self.cursor_size, y, x + self.cursor_size, y)

    def _on_press(self, event):
        self.start_x, self.start_y = event.x, event.y
        self.rect = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline=COLORS["accent"], width=3, dash=(6, 2)
        )

    def _on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)
        self._on_mouse_move(event)

    def _on_release(self, event):
        self.canvas.itemconfigure(self.cursor_v, state='hidden')
        self.canvas.itemconfigure(self.cursor_h, state='hidden')
        left = min(self.start_x, event.x)
        top  = min(self.start_y, event.y)
        w    = abs(event.x - self.start_x)
        h    = abs(event.y - self.start_y)
        if w > 10 and h > 10:
            self.selection_box = {
                "top": int(top), "left": int(left),
                "width": int(w), "height": int(h),
            }
        self.top.destroy()

    def select_region(self):
        self.top.wait_window()
        return self.selection_box


# ============================================================
#  HAUPT-APP
# ============================================================
class OmniVoxCasterApp(ctk.CTk):
    def __init__(self):
        global _ui_lang
        ctk.set_appearance_mode("dark")
        super().__init__()
        self.withdraw()
        self.update_idletasks()

        self.cfg = self._load_config()

        _ui_lang = self.cfg.get("Einstellungen", "ui_sprache", fallback="de")
        if _ui_lang not in TRANSLATIONS:
            _ui_lang = "de"

        self.hotkey      = self.cfg.get("Einstellungen", "hotkey",         fallback="alt+q")
        self.target_lang = self.cfg.get("Einstellungen", "ausgabesprache", fallback="auto")

        self.voices_dir = os.path.join(APPDATA_DIR, "voices")
        os.makedirs(self.voices_dir, exist_ok=True)
        old_voices_dir = os.path.join(APP_DIR, "voices")
        if os.path.isdir(old_voices_dir):
            for f in os.listdir(old_voices_dir):
                src = os.path.join(old_voices_dir, f)
                dst = os.path.join(self.voices_dir, f)
                if f.lower().endswith(".wav") and not os.path.exists(dst):
                    shutil.move(src, dst)
        old_voice = os.path.join(APP_DIR, "stimme_vorlage.wav")
        if os.path.exists(old_voice):
            shutil.move(old_voice, os.path.join(self.voices_dir, "Standard_Stimme.wav"))

        self.spk_wav  = os.path.join(self.voices_dir, self.cfg.get("Einstellungen", "stimme_datei", fallback="Standard_Stimme.wav"))
        self.out_wav  = os.path.join(APPDATA_DIR, "quest_output.wav")
        self.replacements = (
            dict(self.cfg.items("WoW_Woerterbuch"))
            if self.cfg.has_section("WoW_Woerterbuch") else {}
        )
        self.speed             = float(self.cfg.get("Einstellungen", "geschwindigkeit", fallback="1.0"))
        self.is_active         = False
        self.is_processing     = False
        self._stop_playback    = False
        self._pause_event      = threading.Event()
        self._pause_event.set()
        self.tts               = None
        self.ocr_reader        = None
        self.gpt_cond_latent   = None
        self.speaker_embedding = None
        self.last_audio        = None
        self._is_repeating     = False
        self.cmd_queue         = queue.Queue()

        self._setup_window()
        self._build_ui()

        # Den Dialog erst prüfen, wenn der Mainloop sicher gestartet ist
        self.after(100, self._startup_check)
        self.mainloop()

    def _startup_check(self):
        if self.cfg.get("Einstellungen", "disclaimer_accepted", fallback="0") != "1":
            dlg = DisclaimerDialog(self)
            self.wait_window(dlg)
            if not dlg.accepted:
                self.destroy()
                return
            self.cfg.set("Einstellungen", "disclaimer_accepted", "1")
            self.cfg.set("Einstellungen", "ui_sprache", _ui_lang)
            with open(os.path.join(APPDATA_DIR, "config.ini"), "w", encoding="utf-8") as f:
                self.cfg.write(f)
            self._apply_language()

        self.deiconify()
        self.lift()
        self.focus_force()
        threading.Thread(target=self._load_models, daemon=True).start()
        self.after(100, self._poll_queue)

    # ----------------------------------------------------------
    #  FENSTER & UI
    # ----------------------------------------------------------
    def _setup_window(self):
        self.title(f"OmniVox Caster  v{VERSION}")
        self.geometry("400x740")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.97)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        try:
            if os.path.exists(self.out_wav):
                os.remove(self.out_wav)
        except Exception:
            pass
        self.destroy()

    def _section_frame(self, padx=14, pady=6):
        wrapper = ctk.CTkFrame(self, fg_color=COLORS["accent"], corner_radius=8)
        wrapper.pack(fill="x", padx=padx, pady=pady)
        inner = ctk.CTkFrame(wrapper, fg_color=COLORS["surface"], corner_radius=7)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        return inner

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0)
        header.pack(fill="x")

        ctk.CTkFrame(header, fg_color=COLORS["accent"], height=2, corner_radius=0).pack(fill="x")

        hdr_inner = ctk.CTkFrame(header, fg_color="transparent")
        hdr_inner.pack(fill="x", padx=18, pady=(12, 8))

        title_row = ctk.CTkFrame(hdr_inner, fg_color="transparent")
        title_row.pack(fill="x")

        ctk.CTkLabel(
            title_row,
            text="☩   O M N I V O X",
            font=("Palatino Linotype", 22, "bold"),
            text_color=COLORS["accent"],
        ).pack(side="left")

        # Language toggle button (DE / EN)
        self.w_lang_btn = ctk.CTkButton(
            title_row,
            text="DE" if _ui_lang == "de" else "EN",
            width=40, height=32,
            corner_radius=6,
            fg_color=COLORS["ornament"],
            hover_color=COLORS["border"],
            text_color=COLORS["accent"],
            font=("Palatino Linotype", 12, "bold"),
            command=self._toggle_ui_language,
        )
        self.w_lang_btn.pack(side="right", padx=(4, 0))

        ctk.CTkButton(
            title_row,
            text="?",
            width=32, height=32,
            corner_radius=6,
            fg_color=COLORS["border"],
            hover_color=COLORS["ornament"],
            text_color=COLORS["accent"],
            font=("Palatino Linotype", 14, "bold"),
            command=self._open_help,
        ).pack(side="right")

        sub_row = ctk.CTkFrame(hdr_inner, fg_color="transparent")
        sub_row.pack(fill="x", pady=(1, 0))

        ctk.CTkLabel(
            sub_row,
            text="V O X C A S T E R   I M P E R I A L I S",
            font=("Palatino Linotype", 11),
            text_color=COLORS["text_dim"],
        ).pack(side="left")

        ctk.CTkLabel(
            sub_row,
            text=f"v{VERSION}",
            font=("Palatino Linotype", 9),
            text_color=COLORS["text_dim"],
        ).pack(side="right")

        ctk.CTkFrame(header, fg_color=COLORS["ornament"], height=1, corner_radius=0).pack(fill="x")
        ctk.CTkFrame(header, fg_color=COLORS["bg"], height=2, corner_radius=0).pack(fill="x")
        ctk.CTkFrame(header, fg_color=COLORS["accent"], height=2, corner_radius=0).pack(fill="x")

        # ── Stimmvorlage ─────────────────────────────────────────
        voice_frame = self._section_frame(pady=(14, 6))
        self.w_lbl_voice = ctk.CTkLabel(
            voice_frame,
            text=f"❖  {t('section_voice')}",
            font=("Palatino Linotype", 13, "bold"),
            text_color=COLORS["accent"],
        )
        self.w_lbl_voice.pack(anchor="w", padx=14, pady=(10, 2))

        voice_controls = ctk.CTkFrame(voice_frame, fg_color="transparent")
        voice_controls.pack(fill="x", padx=14, pady=(0, 8))

        current_voice = os.path.basename(self.spk_wav) if os.path.exists(self.spk_wav) else t("no_voice_found")
        self.voice_var = tk.StringVar(value=current_voice)

        self.voice_dropdown = ctk.CTkOptionMenu(
            voice_controls,
            variable=self.voice_var,
            values=self._get_voice_list(),
            command=self._on_voice_changed,
            font=("Palatino Linotype", 13),
            fg_color=COLORS["border"],
            button_color=COLORS["ornament"],
            button_hover_color=COLORS["accent"],
            text_color=COLORS["text"],
            dropdown_fg_color=COLORS["surface"],
            dropdown_text_color=COLORS["text"],
            dropdown_hover_color=COLORS["border"],
        )
        self.voice_dropdown.pack(side="left", fill="x", expand=True, padx=(0, 4))

        ctk.CTkButton(voice_controls, text="✎", width=28, height=28,
                      fg_color=COLORS["border"], hover_color=COLORS["ornament"],
                      text_color=COLORS["accent"], font=("Palatino Linotype", 11),
                      command=self._rename_voice).pack(side="left", padx=2)
        ctk.CTkButton(voice_controls, text="✖", width=28, height=28,
                      fg_color=COLORS["border"], hover_color=COLORS["accent2"],
                      text_color=COLORS["text_dim"], font=("Palatino Linotype", 11),
                      command=self._delete_voice).pack(side="left", padx=2)

        btn_row = ctk.CTkFrame(voice_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(0, 12))

        self.w_btn_record = ctk.CTkButton(
            btn_row, text=t("btn_record"),
            width=170, height=38,
            fg_color=COLORS["border"], hover_color=COLORS["ornament"],
            text_color=COLORS["text"], font=("Palatino Linotype", 13),
            command=self._open_record_dialog,
        )
        self.w_btn_record.pack(side="left", padx=4)

        self.w_btn_add = ctk.CTkButton(
            btn_row, text=t("btn_add"),
            width=170, height=38,
            fg_color=COLORS["border"], hover_color=COLORS["ornament"],
            text_color=COLORS["text"], font=("Palatino Linotype", 13),
            command=self._load_voice_file,
        )
        self.w_btn_add.pack(side="left", padx=4)

        # ── Ausgabesprache ───────────────────────────────────────
        lang_frame = self._section_frame()
        lang_row = ctk.CTkFrame(lang_frame, fg_color="transparent")
        lang_row.pack(fill="x", padx=14, pady=10)

        self.w_lbl_outlang = ctk.CTkLabel(
            lang_row,
            text=f"❖  {t('section_outlang')}",
            font=("Palatino Linotype", 13, "bold"),
            text_color=COLORS["accent"],
        )
        self.w_lbl_outlang.pack(side="left")

        display_lang = self._target_lang_to_display(self.target_lang)
        self.target_lang_var = tk.StringVar(value=display_lang)

        self.lang_dropdown = ctk.CTkOptionMenu(
            lang_row,
            variable=self.target_lang_var,
            values=t("lang_values"),
            command=self._on_lang_changed,
            font=("Palatino Linotype", 13, "bold"),
            width=128, height=32,
            fg_color=COLORS["border"],
            button_color=COLORS["ornament"],
            button_hover_color=COLORS["accent"],
            text_color=COLORS["accent"],
            dropdown_font=("Palatino Linotype", 13),
            dropdown_fg_color=COLORS["surface"],
            dropdown_text_color=COLORS["text"],
            dropdown_hover_color=COLORS["border"],
        )
        self.lang_dropdown.pack(side="right")

        # ── Geschwindigkeit ──────────────────────────────────────
        speed_frame = self._section_frame()
        speed_header = ctk.CTkFrame(speed_frame, fg_color="transparent")
        speed_header.pack(fill="x", padx=14, pady=(10, 2))

        self.w_lbl_speed = ctk.CTkLabel(
            speed_header,
            text=f"❖  {t('section_speed')}",
            font=("Palatino Linotype", 13, "bold"),
            text_color=COLORS["accent"],
        )
        self.w_lbl_speed.pack(side="left")

        self.speed_lbl = ctk.CTkLabel(
            speed_header,
            text=f"{self.speed:.1f}×",
            font=("Palatino Linotype", 13, "bold"),
            text_color=COLORS["accent"],
        )
        self.speed_lbl.pack(side="right")

        self.speed_slider = ctk.CTkSlider(
            speed_frame,
            from_=0.5, to=2.0, number_of_steps=30,
            progress_color=COLORS["accent"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["yellow"],
            fg_color=COLORS["border"],
            command=self._on_speed_change,
        )
        self.speed_slider.set(self.speed)
        self.speed_slider.pack(fill="x", padx=14, pady=(4, 14))

        # ── Hotkey ───────────────────────────────────────────────
        hotkey_frame = self._section_frame()
        hk_row = ctk.CTkFrame(hotkey_frame, fg_color="transparent")
        hk_row.pack(fill="x", padx=14, pady=10)

        self.w_lbl_hotkey = ctk.CTkLabel(
            hk_row,
            text=f"❖  {t('section_hotkey')}",
            font=("Palatino Linotype", 13, "bold"),
            text_color=COLORS["accent"],
        )
        self.w_lbl_hotkey.pack(side="left")

        self.hotkey_btn = ctk.CTkButton(
            hk_row,
            text=self.hotkey.upper(),
            width=128, height=32,
            fg_color=COLORS["border"], hover_color=COLORS["ornament"],
            text_color=COLORS["accent"],
            font=("Palatino Linotype", 14, "bold"),
            command=self._change_hotkey,
        )
        self.hotkey_btn.pack(side="right")

        # ── Start / Stop ─────────────────────────────────────────
        self.start_btn = ctk.CTkButton(
            self,
            text=t("btn_activate"),
            height=60, corner_radius=8,
            font=("Palatino Linotype", 17, "bold"),
            fg_color=COLORS["border"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_dim"],
            state="disabled",
            command=self._toggle_active,
        )
        self.start_btn.pack(fill="x", padx=14, pady=(10, 4))

        # ── Pause / Wiederholen ──────────────────────────────────
        ctrl_row = ctk.CTkFrame(self, fg_color="transparent")
        ctrl_row.pack(fill="x", padx=14, pady=(0, 6))

        self.pause_btn = ctk.CTkButton(
            ctrl_row, text=t("btn_pause"),
            width=174, height=40, state="disabled",
            fg_color=COLORS["border"], hover_color=COLORS["ornament"],
            text_color=COLORS["text_dim"],
            font=("Palatino Linotype", 14, "bold"),
            command=self._toggle_pause,
        )
        self.pause_btn.pack(side="left", padx=(0, 4))

        self.repeat_btn = ctk.CTkButton(
            ctrl_row, text=t("btn_repeat"),
            width=174, height=40, state="disabled",
            fg_color=COLORS["border"], hover_color=COLORS["ornament"],
            text_color=COLORS["text_dim"],
            font=("Palatino Linotype", 14, "bold"),
            command=self._repeat_last,
        )
        self.repeat_btn.pack(side="left", padx=(4, 0))

        # ── Status ───────────────────────────────────────────────
        status_wrapper = ctk.CTkFrame(self, fg_color=COLORS["accent"], corner_radius=8)
        status_wrapper.pack(fill="x", padx=14, pady=6)
        status_frame = ctk.CTkFrame(status_wrapper, fg_color=COLORS["surface"], corner_radius=7)
        status_frame.pack(fill="both", expand=True, padx=1, pady=1)

        ctk.CTkLabel(
            status_frame,
            text="C O G I T A T O R   S T A T U S",
            font=("Palatino Linotype", 10, "bold"),
            text_color=COLORS["ornament"],
        ).pack(pady=(6, 0))

        self.status_lbl = ctk.CTkLabel(
            status_frame,
            text=t("status_loading"),
            font=("Palatino Linotype", 13),
            text_color=COLORS["yellow"],
        )
        self.status_lbl.pack(pady=(2, 10))

        # ── Fußzeile ─────────────────────────────────────────────
        ctk.CTkFrame(self, fg_color=COLORS["accent"], height=1, corner_radius=0).pack(fill="x", padx=14)
        self.w_lbl_footer = ctk.CTkLabel(
            self,
            text=t("footer_esc"),
            font=("Palatino Linotype", 11),
            text_color=COLORS["ornament"],
        )
        self.w_lbl_footer.pack(pady=(4, 8))

    # ----------------------------------------------------------
    #  SPRACHE UMSCHALTEN
    # ----------------------------------------------------------
    def _toggle_ui_language(self):
        global _ui_lang
        _ui_lang = "en" if _ui_lang == "de" else "de"
        self.cfg.set("Einstellungen", "ui_sprache", _ui_lang)
        with open(os.path.join(APPDATA_DIR, "config.ini"), "w", encoding="utf-8") as f:
            self.cfg.write(f)
        self._apply_language()

    def _apply_language(self):
        self.w_lang_btn.configure(text="DE" if _ui_lang == "de" else "EN")
        self.w_lbl_voice.configure(text=f"❖  {t('section_voice')}")
        self.w_btn_record.configure(text=t("btn_record"))
        self.w_btn_add.configure(text=t("btn_add"))
        self.w_lbl_outlang.configure(text=f"❖  {t('section_outlang')}")
        self.w_lbl_speed.configure(text=f"❖  {t('section_speed')}")
        self.w_lbl_hotkey.configure(text=f"❖  {t('section_hotkey')}")
        self.w_lbl_footer.configure(text=t("footer_esc"))

        # Output language dropdown: remap current value
        new_values = t("lang_values")
        self.lang_dropdown.configure(values=new_values)
        self.target_lang_var.set(self._target_lang_to_display(self.target_lang))

        # State-dependent buttons
        if not self.is_active:
            if self.start_btn.cget("state") != "disabled":
                self.start_btn.configure(text=t("btn_activate"))
        else:
            self.start_btn.configure(text=t("btn_deactivate"))

        # Only update pause/repeat if not mid-playback
        if self.pause_btn.cget("state") == "disabled":
            self.pause_btn.configure(text=t("btn_pause"))
        if not self._is_repeating and self.repeat_btn.cget("state") != "disabled":
            self.repeat_btn.configure(text=t("btn_repeat"))

        if self.is_active:
            self.status_lbl.configure(text=t("status_active").format(self.hotkey.upper()))
        elif self.tts is not None:
            self.status_lbl.configure(text=t("status_ready"))
        else:
            self.status_lbl.configure(text=t("status_loading"))

    def _target_lang_to_display(self, code):
        return {"auto": t("lang_original"), "de": t("lang_de"), "en": t("lang_en")}.get(code, t("lang_original"))

    def _display_to_target_lang(self, display):
        return {t("lang_original"): "auto", t("lang_de"): "de", t("lang_en"): "en"}.get(display, "auto")

    # ----------------------------------------------------------
    #  STIMMVORLAGE
    # ----------------------------------------------------------
    def _get_voice_list(self):
        voices = [f for f in os.listdir(self.voices_dir) if f.lower().endswith('.wav')]
        return voices if voices else [t("no_voice_found")]

    def _refresh_voice_dropdown(self):
        voices = self._get_voice_list()
        self.voice_dropdown.configure(values=voices)
        no_voice = t("no_voice_found")
        if os.path.basename(self.spk_wav) not in voices and voices and voices[0] != no_voice:
            self.voice_var.set(voices[0])
            self._on_voice_changed(voices[0])
        elif not voices or voices[0] == no_voice:
            self.voice_var.set(no_voice)
            self.spk_wav = ""

    def _on_voice_changed(self, choice):
        if choice == t("no_voice_found"):
            return
        self.spk_wav = os.path.join(self.voices_dir, choice)
        self.cfg.set("Einstellungen", "stimme_datei", choice)
        with open(os.path.join(APPDATA_DIR, "config.ini"), "w", encoding="utf-8") as f:
            self.cfg.write(f)
        if self.tts is not None:
            self._set_status(t("status_voice_changed"), COLORS["yellow"])
            threading.Thread(target=self._prepare_speaker, daemon=True).start()

    def _rename_voice(self):
        current = self.voice_var.get()
        if current == t("no_voice_found"):
            return
        dialog = ctk.CTkInputDialog(text=t("rename_dialog_text"), title=t("rename_title"))
        new_name = dialog.get_input()
        if new_name:
            new_name = new_name.strip()
            if not new_name.lower().endswith(".wav"):
                new_name += ".wav"
            old_path = os.path.join(self.voices_dir, current)
            new_path = os.path.join(self.voices_dir, new_name)
            if os.path.exists(new_path):
                messagebox.showerror(t("rename_exists_title"), t("rename_exists_msg"))
                return
            os.rename(old_path, new_path)
            if self.spk_wav == old_path:
                self.spk_wav = new_path
                self.cfg.set("Einstellungen", "stimme_datei", new_name)
                with open(os.path.join(APPDATA_DIR, "config.ini"), "w", encoding="utf-8") as f:
                    self.cfg.write(f)
            self.voice_var.set(new_name)
            self._refresh_voice_dropdown()
            self._set_status(t("status_renamed").format(new_name), COLORS["green"])

    def _delete_voice(self):
        current = self.voice_var.get()
        if current == t("no_voice_found"):
            return
        if messagebox.askyesno(t("delete_title"), t("delete_msg").format(current)):
            os.remove(os.path.join(self.voices_dir, current))
            self._refresh_voice_dropdown()
            self._set_status(t("status_voice_deleted"), COLORS["red"])

    def _open_record_dialog(self):
        RecordDialog(self, self._on_voice_saved)

    def _load_voice_file(self):
        path = filedialog.askopenfilename(
            title=t("voice_file_title"),
            filetypes=[("Audio", "*.wav *.mp3"), ("WAV", "*.wav"), ("MP3", "*.mp3")],
        )
        if not path:
            return
        base_name = os.path.basename(path)
        name, _ = os.path.splitext(base_name)
        dest_name = name + ".wav"
        dest = os.path.join(self.voices_dir, dest_name)
        counter = 1
        while os.path.exists(dest):
            dest_name = f"{name}_{counter}.wav"
            dest = os.path.join(self.voices_dir, dest_name)
            counter += 1
        if path.lower().endswith(".mp3"):
            try:
                from pydub import AudioSegment
                from pydub.utils import which
                if not which("ffmpeg"):
                    winget_ffmpeg = os.path.expandvars(
                        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages"
                        r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
                        r"\ffmpeg-8.1-full_build\bin"
                    )
                    os.environ["PATH"] = winget_ffmpeg + os.pathsep + os.environ.get("PATH", "")
                AudioSegment.from_mp3(path).export(dest, format="wav")
            except ImportError:
                messagebox.showerror(t("pydub_error_title"), t("pydub_error_msg"))
                return
            except Exception as exc:
                messagebox.showerror(t("mp3_error_title"), t("mp3_error_msg").format(exc))
                return
        else:
            shutil.copy2(path, dest)
        self._refresh_voice_dropdown()
        self.voice_var.set(dest_name)
        self._on_voice_changed(dest_name)

    def _on_voice_saved(self, temp_path):
        dialog = ctk.CTkInputDialog(text=t("save_dialog_text"), title=t("save_title"))
        name = dialog.get_input()
        if not name:
            os.remove(temp_path)
            return
        name = name.strip()
        if not name.lower().endswith(".wav"):
            name += ".wav"
        dest = os.path.join(self.voices_dir, name)
        shutil.move(temp_path, dest)
        self._refresh_voice_dropdown()
        self.voice_var.set(name)
        self._on_voice_changed(name)

    # ----------------------------------------------------------
    #  AUSGABESPRACHE
    # ----------------------------------------------------------
    def _on_lang_changed(self, choice):
        self.target_lang = self._display_to_target_lang(choice)
        self.cfg.set("Einstellungen", "ausgabesprache", self.target_lang)
        with open(os.path.join(APPDATA_DIR, "config.ini"), "w", encoding="utf-8") as f:
            self.cfg.write(f)
        if self.target_lang != "auto":
            try:
                import deep_translator  # noqa: F401
            except Exception as e:
                print(f"[FEHLER] deep_translator konnte nicht geladen werden: {e}")
                messagebox.showwarning(t("translator_missing_title"), t("translator_missing_msg").format(e))

    # ----------------------------------------------------------
    #  GESCHWINDIGKEIT
    # ----------------------------------------------------------
    def _on_speed_change(self, value):
        self.speed = value
        self.speed_lbl.configure(text=f"{value:.1f}×")

    # ----------------------------------------------------------
    #  HOTKEY ÄNDERN
    # ----------------------------------------------------------
    def _change_hotkey(self):
        if self.is_active:
            messagebox.showinfo(t("hotkey_active_title"), t("hotkey_active_msg"))
            return
        self.hotkey_btn.configure(state="disabled", text=t("hotkey_input"), text_color=COLORS["yellow"])
        self._set_status(t("status_hotkey_wait"), COLORS["yellow"])
        threading.Thread(target=self._record_hotkey, daemon=True).start()

    def _record_hotkey(self):
        new_hk = keyboard.read_hotkey(suppress=False)
        self.hotkey = new_hk
        self.cfg.set("Einstellungen", "hotkey", self.hotkey)
        with open(os.path.join(APPDATA_DIR, "config.ini"), "w", encoding="utf-8") as f:
            self.cfg.write(f)
        self.after(0, self._update_hotkey_ui)

    def _update_hotkey_ui(self):
        self.hotkey_btn.configure(state="normal", text=self.hotkey.upper(), text_color=COLORS["accent"])
        self._set_status(t("status_hotkey_saved").format(self.hotkey.upper()), COLORS["green"])

    # ----------------------------------------------------------
    #  START / STOP
    # ----------------------------------------------------------
    def _toggle_active(self):
        if not self.is_active:
            if not os.path.exists(self.spk_wav):
                messagebox.showwarning(t("no_voice_title"), t("no_voice_msg"))
                return
            if self.tts is None or self.ocr_reader is None:
                messagebox.showinfo(t("wait_models_title"), t("wait_models_msg"))
                return
            if self.gpt_cond_latent is None:
                messagebox.showinfo(t("wait_models_title"), t("wait_voice_msg"))
                return
            self._activate()
        else:
            self._deactivate()

    def _activate(self):
        self.is_active = True
        keyboard.add_hotkey(self.hotkey, self._hotkey_pressed)
        keyboard.add_hotkey("esc", self._esc_pressed)
        self.start_btn.configure(
            text=t("btn_deactivate"),
            fg_color=COLORS["accent2"], hover_color="#6b1010",
            text_color=COLORS["text"],
        )
        self._set_status(t("status_active").format(self.hotkey.upper()), COLORS["green"])

    def _deactivate(self):
        self.is_active = False
        self._stop_playback = True
        keyboard.unhook_all()
        sd.stop()
        self.start_btn.configure(
            text=t("btn_activate"),
            fg_color=COLORS["green"], hover_color="#2d5c27",
            text_color=COLORS["text"],
        )
        self._set_status(t("status_deactivated"), COLORS["text_dim"])

    # ----------------------------------------------------------
    #  KONFIGURATION
    # ----------------------------------------------------------
    def _load_config(self):
        cfg_file = os.path.join(APPDATA_DIR, "config.ini")
        old_cfg = os.path.join(APP_DIR, "config.ini")
        if not os.path.exists(cfg_file) and os.path.exists(old_cfg):
            shutil.copy2(old_cfg, cfg_file)
        if not os.path.exists(cfg_file):
            with open(cfg_file, "w", encoding="utf-8") as f:
                f.write(DEFAULT_CONFIG)
        cfg = configparser.ConfigParser()
        cfg.read(cfg_file, encoding="utf-8")
        return cfg

    # ----------------------------------------------------------
    #  MODELLE LADEN
    # ----------------------------------------------------------
    def _load_models(self):
        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            hw_name = torch.cuda.get_device_name(0) if device == "cuda" else "CPU"
            print(f"[INFO] Gerät: {hw_name}")

            print("[INFO] Lade TTS-Modell (XTTSv2) ...")
            os.environ["COQUI_TOS_AGREED"] = "1"
            self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=(device == "cuda"))
            print("[INFO] TTS geladen.")

            print("[INFO] Lade OCR-Modell (EasyOCR) ...")
            self.ocr_reader = easyocr.Reader(["de", "en"], gpu=(device == "cuda"))
            print("[INFO] OCR geladen.")

            if os.path.exists(self.spk_wav):
                self._prepare_speaker()

            self._set_status(t("status_ready"), COLORS["text"])
            print(f"\n[BEREIT] Drücke AKTIVIEREN und dann [{self.hotkey.upper()}] zum Auswählen.\n")
            self.after(0, self._enable_start_btn)

        except Exception as exc:
            print(f"[FEHLER] Beim Laden der Modelle: {exc}")
            self._set_status(t("status_load_error"), COLORS["red"])

    # ----------------------------------------------------------
    #  HOTKEY-HANDLER
    # ----------------------------------------------------------
    def _hotkey_pressed(self):
        if not self.is_processing:
            self.cmd_queue.put("select")

    def _esc_pressed(self):
        if self.is_processing:
            self._stop_playback = True
            sd.stop()
        else:
            self.cmd_queue.put("deactivate")

    # ----------------------------------------------------------
    #  QUEUE-POLLING
    # ----------------------------------------------------------
    def _poll_queue(self):
        try:
            cmd = self.cmd_queue.get_nowait()
            if cmd == "select":
                self._start_selection()
            elif cmd == "deactivate":
                self._deactivate()
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    # ----------------------------------------------------------
    #  BEREICH AUSWÄHLEN
    # ----------------------------------------------------------
    def _start_selection(self):
        self.is_processing = True
        self._set_status(t("status_selecting"), COLORS["yellow"])
        sel = RegionSelector(self)
        box = sel.select_region()
        if box:
            threading.Thread(target=self._process, args=(box,), daemon=True).start()
        else:
            self.is_processing = False
            self._set_status(t("status_active").format(self.hotkey.upper()), COLORS["green"])

    def _detect_language(self, text):
        try:
            import langdetect
            lang = langdetect.detect(text)
            if lang in ["de", "en"]:
                return lang
        except ImportError:
            pass
        except Exception:
            pass
        words = set(text.lower().split())
        de_keywords = {"der", "die", "das", "und", "ist", "in", "den", "von", "zu", "mit", "für", "auf", "sind", "ich", "euch"}
        en_keywords = {"the", "and", "is", "in", "to", "of", "with", "for", "on", "are", "you", "we", "your"}
        de_count = len(words.intersection(de_keywords))
        en_count = len(words.intersection(en_keywords))
        return "en" if en_count > de_count else "de"

    # ----------------------------------------------------------
    #  SPEAKER VORBEREITEN
    # ----------------------------------------------------------
    def _enable_start_btn(self):
        self.start_btn.configure(
            state="normal",
            fg_color=COLORS["green"], hover_color="#2d5c27",
            text_color=COLORS["text"],
        )

    def _prepare_speaker(self):
        try:
            xtts = self.tts.synthesizer.tts_model
            self.gpt_cond_latent, self.speaker_embedding = xtts.get_conditioning_latents(
                audio_path=[self.spk_wav]
            )
            print("[INFO] Stimmvorlage vorberechnet.")
            if self.is_active:
                self._set_status(t("status_active").format(self.hotkey.upper()), COLORS["green"])
            else:
                self._set_status(t("status_ready"), COLORS["text"])
        except Exception as exc:
            print(f"[FEHLER] Stimmvorlage konnte nicht vorbereitet werden: {exc}")
            self._set_status("Fehler beim Vorbereiten!", COLORS["red"])

    # ----------------------------------------------------------
    #  OCR + TTS
    # ----------------------------------------------------------
    def _process(self, box):
        try:
            self._set_status(t("status_ocr"), COLORS["yellow"])
            text = self._run_ocr(box)

            if not text:
                print("[INFO] Kein Text im Bereich erkannt.")
                return

            text = self._clean_text(text)
            detected_lang = self._detect_language(text)

            print(f"\n--- ERKANNTER TEXT ({detected_lang.upper()}) ---\n{text}\n----------------------")

            tts_lang = detected_lang
            if self.target_lang in ["de", "en"] and detected_lang != self.target_lang:
                self._set_status(t("status_translating"), COLORS["yellow"])
                try:
                    from deep_translator import GoogleTranslator
                    translator = GoogleTranslator(source=detected_lang, target=self.target_lang)
                    translated_text = translator.translate(text)
                    print(f"\n--- ÜBERSETZT ({self.target_lang.upper()}) ---\n{translated_text}\n----------------------")
                    text = translated_text
                    tts_lang = self.target_lang
                except ImportError as e:
                    print(f"[FEHLER] 'deep-translator' Import fehlgeschlagen: {e}")
                    self._set_status(t("status_no_translator"), COLORS["red"])
                    time.sleep(1.5)
                except Exception as e:
                    print(f"[FEHLER] Übersetzung fehlgeschlagen: {e}")
                    self._set_status(t("status_translate_fail"), COLORS["red"])
                    time.sleep(1.5)

            self._set_status(t("status_generating"), COLORS["accent"])
            self._stop_playback = False
            self._pause_event.set()
            xtts = self.tts.synthesizer.tts_model

            t0 = time.time()
            text_chunks = self._split_text("... " + text)

            audio_queue = queue.Queue()
            playback_finished = threading.Event()
            collected_audio = []

            def audio_player():
                try:
                    pre_buffer = []
                    pre_samples = 0
                    # Puffer-Zeit für die Audiogenerierung.
                    # 3.0 Sekunden, um die Verzögerung vor dem Sprechen kurz zu halten.
                    target_samples = int(24000 * 3.0)

                    while pre_samples < target_samples and not self._stop_playback:
                        try:
                            chunk = audio_queue.get(timeout=0.1)
                            if chunk is None:
                                break
                            pre_buffer.append(chunk)
                            pre_samples += len(chunk)
                        except queue.Empty:
                            continue

                    if self._stop_playback:
                        return

                    print(f"[INFO] Wiedergabe startet (Puffer: {pre_samples/24000:.1f}s) nach {time.time() - t0:.2f}s")
                    self._set_status(t("status_playing"), COLORS["accent"])
                    self.after(0, lambda: self.pause_btn.configure(state="normal"))

                    with sd.OutputStream(samplerate=24000, channels=1, dtype='float32', latency='high') as stream:
                        stream.write(np.zeros(int(24000 * 0.5), dtype="float32"))
                        for b in pre_buffer:
                            self._pause_event.wait()
                            if self._stop_playback:
                                break
                            stream.write(b)
                        while not self._stop_playback:
                            self._pause_event.wait()
                            if self._stop_playback:
                                break
                            try:
                                chunk = audio_queue.get(timeout=0.1)
                                if chunk is None:
                                    break
                                stream.write(chunk)
                            except queue.Empty:
                                # Verhindert Hardware-Stottern (Buffer Underrun), falls
                                # die KI kurz braucht, um den nächsten Satz zu berechnen.
                                stream.write(np.zeros(int(24000 * 0.1), dtype="float32"))
                                continue
                except Exception as e:
                    print(f"[FEHLER im Audio-Player] {e}")
                finally:
                    playback_finished.set()

            threading.Thread(target=audio_player, daemon=True).start()

            try:
                for text_chunk in text_chunks:
                    if self._stop_playback:
                        break
                    for chunk in xtts.inference_stream(
                        text_chunk, tts_lang,
                        self.gpt_cond_latent, self.speaker_embedding,
                        speed=self.speed,
                    ):
                        if self._stop_playback:
                            break
                        np_chunk = chunk.squeeze().cpu().numpy()
                        audio_queue.put(np_chunk)
                        collected_audio.append(np_chunk)
            finally:
                audio_queue.put(None)
                playback_finished.wait()

            if collected_audio and not self._stop_playback:
                self.last_audio = np.concatenate(collected_audio)
                self.after(0, lambda: self.repeat_btn.configure(
                    state="normal", fg_color=COLORS["border"],
                    hover_color=COLORS["ornament"], text_color=COLORS["text"]
                ))

            print(f"[INFO] Verarbeitung abgeschlossen in {time.time() - t0:.1f}s")

        except Exception as exc:
            if not self._stop_playback:
                print(f"[FEHLER] {exc}")
        finally:
            self.is_processing = False
            self._pause_event.set()
            self.after(0, lambda: self.pause_btn.configure(
                state="disabled", text=t("btn_pause"),
                fg_color=COLORS["border"], hover_color=COLORS["ornament"], text_color=COLORS["text_dim"]
            ))
            self._set_status(t("status_active").format(self.hotkey.upper()), COLORS["green"])

    def _run_ocr(self, box):
        with mss.mss() as sct:
            img = np.array(sct.grab(box))[:, :, :3]
        results = self.ocr_reader.readtext(img, detail=0, paragraph=True)
        return " ".join(results) if results else None

    def _clean_text(self, text):
        text = text.replace(";", ",")
        for wrong, correct in self.replacements.items():
            text = re.sub(re.escape(wrong), correct, text, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", text).strip()

    def _split_text(self, text, max_chars=240):
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current = ""
        for sentence in sentences:
            if not current:
                current = sentence
            elif len(current) + 1 + len(sentence) <= max_chars:
                current += " " + sentence
            else:
                chunks.append(current)
                current = sentence
        if current:
            chunks.append(current)
        return chunks

    # ----------------------------------------------------------
    #  PAUSE / WIEDERHOLEN
    # ----------------------------------------------------------
    def _toggle_pause(self):
        if self._pause_event.is_set():
            self._pause_event.clear()
            self.pause_btn.configure(
                text=t("btn_resume"),
                fg_color=COLORS["accent"], hover_color=COLORS["yellow"],
                text_color="#0d0a06",
            )
            self._set_status(t("status_paused"), COLORS["yellow"])
        else:
            self._pause_event.set()
            self.pause_btn.configure(
                text=t("btn_pause"),
                fg_color=COLORS["border"], hover_color=COLORS["ornament"],
                text_color=COLORS["text_dim"],
            )
            self._set_status(t("status_playing"), COLORS["accent"])

    def _repeat_last(self):
        if self._is_repeating:
            self._stop_playback = True
            sd.stop()
            return
        if self.last_audio is None or self.is_processing:
            return
        self._is_repeating = True
        self.is_processing = True
        self._pause_event.set()
        self.repeat_btn.configure(
            text=t("btn_stop_repeat"),
            fg_color=COLORS["accent2"], hover_color="#6b1010",
            text_color=COLORS["text"],
        )
        self.pause_btn.configure(state="normal")
        self._set_status(t("status_repeating"), COLORS["accent"])
        threading.Thread(target=self._play_last_audio, daemon=True).start()

    def _play_last_audio(self):
        try:
            self._stop_playback = False
            silence = np.zeros(int(24000 * 0.5), dtype="float32")
            sd.play(np.concatenate([silence, self.last_audio]), 24000)
            while sd.get_stream().active:
                self._pause_event.wait()
                if self._stop_playback:
                    sd.stop()
                    break
                time.sleep(0.05)
        except Exception as exc:
            if not self._stop_playback:
                print(f"[FEHLER] Wiederholen: {exc}")
        finally:
            self._is_repeating = False
            self.is_processing = False
            self.pause_btn.configure(
                state="disabled", text=t("btn_pause"),
                fg_color=COLORS["border"], hover_color=COLORS["ornament"],
                text_color=COLORS["text_dim"],
            )
            self.after(0, lambda: self.repeat_btn.configure(
                state="normal", text=t("btn_repeat"),
                fg_color=COLORS["border"], hover_color=COLORS["ornament"],
                text_color=COLORS["text"],
            ))
            self._set_status(t("status_active").format(self.hotkey.upper()), COLORS["green"])

    def _open_help(self):
        HelpDialog(self)

    def _set_status(self, text, color):
        self.after(0, lambda: self.status_lbl.configure(text=text, text_color=color))


# ============================================================
#  EINSTIEGSPUNKT
# ============================================================
if __name__ == "__main__":
    print("=" * 55)
    print("  OmniVox Caster — Voxcaster Imperialis")
    print("  GUI wird gestartet ...")
    print("=" * 55)
    OmniVoxCasterApp()
