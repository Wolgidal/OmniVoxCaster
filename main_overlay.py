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

_orig_torch_load = torch.load
def _patched_torch_load(f, *args, **kwargs):
    kwargs.setdefault("weights_only", False)
    return _orig_torch_load(f, *args, **kwargs)
torch.load = _patched_torch_load

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

COLORS = {
    "bg":       "#09070a",    # Void black
    "surface":  "#120e0f",    # Dark Gothic surface
    "border":   "#3a2810",    # Dark brass
    "accent":   "#c8a44a",    # Brass / Gold
    "accent2":  "#9b1a1a",    # Blood red
    "green":    "#3d7a35",    # Bionics green
    "red":      "#cc2200",    # Imperial red
    "yellow":   "#c8960a",    # Warning amber
    "text":     "#e0d4b8",    # Parchment
    "text_dim": "#6e5e42",    # Faded parchment
    "ornament": "#5a3c15",    # Secondary brass
}

DEFAULT_CONFIG = """\
[Einstellungen]
hotkey = alt+q
sprache = de
stimme_datei = stimme_vorlage.wav
ausgabe_datei = quest_output.wav
ausgabesprache = auto
geschwindigkeit = 1.0

[WoW_Woerterbuch]
# Korrekturen für OCR-Fehler oder WoW-Begriffe
# Beispiel:
# Hollschrei = Höllschrei
"""


# ============================================================
#  AUFNAHME-DIALOG
# ============================================================
class RecordDialog(ctk.CTkToplevel):
    """Mikrofon-Aufnahme-Dialog für die Stimmvorlage."""

    def __init__(self, parent, on_save_callback):
        super().__init__(parent)
        self.on_save = on_save_callback
        self.recording = False
        self.audio_chunks = []
        self.stream = None
        self.recorded_data = None

        self.title("OmniVox Caster —Stimmvorlage aufnehmen")
        self.geometry("380x300")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["surface"])
        self.attributes("-topmost", True)
        self.grab_set()
        self._build()

    def _build(self):
        # Top accent line
        ctk.CTkFrame(self, fg_color=COLORS["accent"], height=2, corner_radius=0).pack(fill="x")

        ctk.CTkLabel(
            self,
            text="☩   S T I M M V O R L A G E",
            font=("Palatino Linotype", 14, "bold"),
            text_color=COLORS["accent"],
        ).pack(pady=(14, 2))

        ctk.CTkLabel(
            self,
            text="Sprich 5–15 Sekunden in dein Mikrofon.\nDie Aufnahme wird als Stimmvorlage gespeichert.",
            font=("Palatino Linotype", 10),
            text_color=COLORS["text_dim"],
            justify="center",
        ).pack(pady=(0, 14))

        self.indicator = ctk.CTkLabel(
            self,
            text="◈  Bereit",
            font=("Palatino Linotype", 12, "bold"),
            text_color=COLORS["text_dim"],
        )
        self.indicator.pack(pady=4)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=14)

        self.rec_btn = ctk.CTkButton(
            btn_row,
            text="🎤  Aufnahme starten",
            width=172,
            height=36,
            fg_color=COLORS["border"],
            hover_color=COLORS["ornament"],
            text_color=COLORS["accent"],
            font=("Palatino Linotype", 11, "bold"),
            command=self._toggle_recording,
        )
        self.rec_btn.grid(row=0, column=0, padx=6)

        self.save_btn = ctk.CTkButton(
            btn_row,
            text="💾  Speichern",
            width=138,
            height=36,
            state="disabled",
            fg_color=COLORS["green"],
            hover_color="#2d5c27",
            text_color=COLORS["text"],
            font=("Palatino Linotype", 11, "bold"),
            command=self._save,
        )
        self.save_btn.grid(row=0, column=1, padx=6)

        ctk.CTkButton(
            self,
            text="Abbrechen",
            width=110,
            height=30,
            fg_color=COLORS["border"],
            hover_color=COLORS["ornament"],
            text_color=COLORS["text_dim"],
            font=("Palatino Linotype", 10),
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
        self.rec_btn.configure(
            text="⏹  Aufnahme stoppen",
            fg_color=COLORS["accent2"],
            hover_color="#6b1010",
        )
        self.indicator.configure(text="◈  Aufnahme läuft ...", text_color=COLORS["red"])
        self.save_btn.configure(state="disabled")

        def callback(indata, frames, time_info, status):
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
                text=f"◈  Aufnahme bereit  ({duration:.1f} s)",
                text_color=COLORS["green"],
            )
            self.rec_btn.configure(
                text="🔄  Neu aufnehmen",
                fg_color=COLORS["border"],
                hover_color=COLORS["ornament"],
                text_color=COLORS["accent"],
            )
            self.save_btn.configure(state="normal")
        else:
            self.indicator.configure(text="◈  Keine Daten erfasst", text_color=COLORS["yellow"])
            self.rec_btn.configure(
                text="🎤  Aufnahme starten",
                fg_color=COLORS["border"],
                hover_color=COLORS["ornament"],
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
    """Nutzungsvereinbarung — muss beim ersten Start bestätigt werden."""

    def __init__(self, parent):
        super().__init__(parent)
        self.accepted = False
        self.title("OmniVox Caster —Nutzungsvereinbarung")
        self.geometry("520x560")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["surface"])
        self.attributes("-topmost", True)
        self.grab_set()
        self._build()

    def _build(self):
        ctk.CTkFrame(self, fg_color=COLORS["accent"], height=2, corner_radius=0).pack(fill="x")

        ctk.CTkLabel(self, text="☩   N U T Z U N G S V E R E I N B A R U N G",
                     font=("Palatino Linotype", 14, "bold"),
                     text_color=COLORS["accent"]).pack(pady=(14, 2))
        ctk.CTkLabel(self, text="OmniVox Caster —Voxcaster Imperialis",
                     font=("Palatino Linotype", 9), text_color=COLORS["text_dim"]).pack(pady=(0, 8))

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["border"], corner_radius=8, height=380)
        scroll.pack(fill="x", padx=16, pady=(0, 12))

        text = (
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
        )

        ctk.CTkLabel(scroll, text=text, font=("Palatino Linotype", 10),
                     text_color=COLORS["text"], justify="left",
                     wraplength=458, anchor="w").pack(anchor="w", padx=10, pady=8)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=(0, 12))

        ctk.CTkButton(btn_row, text="✔   Ich stimme zu und akzeptiere die Bedingungen",
                      height=40, fg_color=COLORS["green"], hover_color="#2d5c27",
                      text_color=COLORS["text"], font=("Palatino Linotype", 12, "bold"),
                      command=self._accept).pack(padx=8, pady=(0, 6))

        ctk.CTkButton(btn_row, text="✖   Ablehnen & Beenden",
                      height=36, fg_color=COLORS["border"], hover_color=COLORS["accent2"],
                      text_color=COLORS["text_dim"], font=("Palatino Linotype", 11),
                      command=self.destroy).pack(padx=8)

        ctk.CTkFrame(self, fg_color=COLORS["accent"], height=2, corner_radius=0).pack(fill="x", side="bottom")

    def _accept(self):
        self.accepted = True
        self.destroy()


# ============================================================
#  HILFE-DIALOG  (Tutorial)
# ============================================================
class HelpDialog(ctk.CTkToplevel):
    """Tutorial und Hilfeinformationen."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("OmniVox Caster —Hilfe & Tutorial")
        self.geometry("500x600")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["surface"])
        self.attributes("-topmost", True)
        self._build()

    def _build(self):
        ctk.CTkFrame(self, fg_color=COLORS["accent"], height=2, corner_radius=0).pack(fill="x")

        ctk.CTkLabel(self, text="☩   H I L F E  &  T U T O R I A L",
                     font=("Palatino Linotype", 14, "bold"),
                     text_color=COLORS["accent"]).pack(pady=(14, 2))
        ctk.CTkLabel(self, text="OmniVox Caster —Voxcaster Imperialis",
                     font=("Palatino Linotype", 9), text_color=COLORS["text_dim"]).pack(pady=(0, 8))

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["border"], corner_radius=8, height=460)
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        sections = [
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
        ]

        for title, body in sections:
            ctk.CTkLabel(scroll, text=title, font=("Palatino Linotype", 12, "bold"),
                         text_color=COLORS["accent"], anchor="w",
                         justify="left").pack(anchor="w", padx=10, pady=(14, 2))
            ctk.CTkLabel(scroll, text=body, font=("Palatino Linotype", 11),
                         text_color=COLORS["text"], justify="left",
                         wraplength=440, anchor="w").pack(anchor="w", padx=16, pady=(0, 2))
            ctk.CTkFrame(scroll, fg_color=COLORS["ornament"], height=1,
                         corner_radius=0).pack(fill="x", padx=10, pady=(8, 0))

        ctk.CTkButton(self, text="✔   Schließen", height=36, width=150,
                      fg_color=COLORS["border"], hover_color=COLORS["ornament"],
                      text_color=COLORS["accent"], font=("Palatino Linotype", 12, "bold"),
                      command=self.destroy).pack(pady=8)

        ctk.CTkFrame(self, fg_color=COLORS["accent"], height=2, corner_radius=0).pack(fill="x", side="bottom")


# ============================================================
#  REGION-SELECTOR  (Screenshot-Auswahl)
# ============================================================
class RegionSelector:
    """Transparentes Vollbild-Overlay zur Mausauswahl eines Bereichs."""

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
    """OmniVox Caster —Voxcaster Imperialis."""

    def __init__(self):
        ctk.set_appearance_mode("dark")
        super().__init__()
        self.withdraw()
        self.update_idletasks()

        self.cfg = self._load_config()

        # Disclaimer beim ersten Start
        if self.cfg.get("Einstellungen", "disclaimer_accepted", fallback="0") != "1":
            dlg = DisclaimerDialog(self)
            self.wait_window(dlg)
            if not dlg.accepted:
                self.destroy()
                return
            self.cfg.set("Einstellungen", "disclaimer_accepted", "1")
            with open(os.path.join(APPDATA_DIR, "config.ini"), "w", encoding="utf-8") as f:
                self.cfg.write(f)

        self.deiconify()
        self.hotkey     = self.cfg.get("Einstellungen", "hotkey",        fallback="alt+q")
        self.target_lang = self.cfg.get("Einstellungen", "ausgabesprache", fallback="auto")

        self.voices_dir = os.path.join(APPDATA_DIR, "voices")
        os.makedirs(self.voices_dir, exist_ok=True)
        # Migration: alte Stimmen aus dem App-Ordner nach AppData verschieben
        old_voices_dir = os.path.join(APP_DIR, "voices")
        if os.path.isdir(old_voices_dir):
            for f in os.listdir(old_voices_dir):
                src = os.path.join(old_voices_dir, f)
                dst = os.path.join(self.voices_dir, f)
                if f.lower().endswith(".wav") and not os.path.exists(dst):
                    shutil.move(src, dst)
        # Legacy: einzelne Stimmdatei im App-Root
        old_voice = os.path.join(APP_DIR, "stimme_vorlage.wav")
        if os.path.exists(old_voice):
            shutil.move(old_voice, os.path.join(self.voices_dir, "Standard_Stimme.wav"))

        self.spk_wav    = os.path.join(self.voices_dir, self.cfg.get("Einstellungen", "stimme_datei", fallback="Standard_Stimme.wav"))
        self.out_wav    = os.path.join(APPDATA_DIR, "quest_output.wav")
        self.replacements = (
            dict(self.cfg.items("WoW_Woerterbuch"))
            if self.cfg.has_section("WoW_Woerterbuch") else {}
        )
        self.speed              = float(self.cfg.get("Einstellungen", "geschwindigkeit", fallback="1.0"))
        self.is_active          = False
        self.is_processing      = False
        self._stop_playback     = False
        self._pause_event       = threading.Event()
        self._pause_event.set()
        self.tts                = None
        self.ocr_reader         = None
        self.gpt_cond_latent    = None
        self.speaker_embedding  = None
        self.last_audio         = None
        self._is_repeating      = False
        self.cmd_queue          = queue.Queue()

        self._setup_window()
        self._build_ui()

        threading.Thread(target=self._load_models, daemon=True).start()
        self.after(100, self._poll_queue)
        self.mainloop()

    # ----------------------------------------------------------
    #  FENSTER & UI
    # ----------------------------------------------------------
    def _setup_window(self):
        self.title("OmniVox Caster")
        self.geometry("370x690")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.97)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        """Aufräumen beim Beenden: temporäre Audiodatei löschen."""
        try:
            if os.path.exists(self.out_wav):
                os.remove(self.out_wav)
        except Exception:
            pass
        self.destroy()

    def _section_frame(self, padx=14, pady=6):
        """Erstellt einen WH40K-gestylten Abschnitt mit Messing-Rahmen."""
        wrapper = ctk.CTkFrame(self, fg_color=COLORS["accent"], corner_radius=8)
        wrapper.pack(fill="x", padx=padx, pady=pady)
        inner = ctk.CTkFrame(wrapper, fg_color=COLORS["surface"], corner_radius=7)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        return inner

    def _section_label(self, parent, text):
        """Abschnitts-Titel im Imperialis-Stil."""
        ctk.CTkLabel(
            parent,
            text=f"❖  {text}",
            font=("Palatino Linotype", 11, "bold"),
            text_color=COLORS["accent"],
        ).pack(anchor="w", padx=14, pady=(10, 2))

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
            font=("Palatino Linotype", 19, "bold"),
            text_color=COLORS["accent"],
        ).pack(side="left")

        ctk.CTkButton(
            title_row,
            text="?",
            width=30,
            height=30,
            corner_radius=6,
            fg_color=COLORS["border"],
            hover_color=COLORS["ornament"],
            text_color=COLORS["accent"],
            font=("Palatino Linotype", 13, "bold"),
            command=self._open_help,
        ).pack(side="right")

        ctk.CTkLabel(
            hdr_inner,
            text="V O X C A S T E R   I M P E R I A L I S",
            font=("Palatino Linotype", 10),
            text_color=COLORS["text_dim"],
        ).pack(anchor="w", pady=(1, 0))

        ctk.CTkFrame(header, fg_color=COLORS["ornament"], height=1, corner_radius=0).pack(fill="x")
        ctk.CTkFrame(header, fg_color=COLORS["bg"], height=2, corner_radius=0).pack(fill="x")
        ctk.CTkFrame(header, fg_color=COLORS["accent"], height=2, corner_radius=0).pack(fill="x")

        # ── Stimmvorlage ────────────────────────────────────────
        voice_frame = self._section_frame(pady=(14, 6))
        self._section_label(voice_frame, "STIMMVORLAGE")

        voice_controls = ctk.CTkFrame(voice_frame, fg_color="transparent")
        voice_controls.pack(fill="x", padx=14, pady=(0, 8))

        current_voice = os.path.basename(self.spk_wav) if os.path.exists(self.spk_wav) else "Keine Stimme gefunden"
        self.voice_var = tk.StringVar(value=current_voice)

        self.voice_dropdown = ctk.CTkOptionMenu(
            voice_controls,
            variable=self.voice_var,
            values=self._get_voice_list(),
            command=self._on_voice_changed,
            font=("Palatino Linotype", 12),
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

        ctk.CTkButton(
            btn_row,
            text="🎤  Aufnehmen",
            width=158,
            height=34,
            fg_color=COLORS["border"],
            hover_color=COLORS["ornament"],
            text_color=COLORS["text"],
            font=("Palatino Linotype", 12),
            command=self._open_record_dialog,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_row,
            text="📁  Hinzufügen",
            width=158,
            height=34,
            fg_color=COLORS["border"],
            hover_color=COLORS["ornament"],
            text_color=COLORS["text"],
            font=("Palatino Linotype", 12),
            command=self._load_voice_file,
        ).pack(side="left", padx=4)

        # ── Ausgabesprache ──────────────────────────────────────
        lang_frame = self._section_frame()

        lang_row = ctk.CTkFrame(lang_frame, fg_color="transparent")
        lang_row.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(
            lang_row,
            text="❖  AUSGABESPRACHE",
            font=("Palatino Linotype", 11, "bold"),
            text_color=COLORS["accent"],
        ).pack(side="left")

        display_lang = {"auto": "Original", "de": "Deutsch", "en": "Englisch"}.get(self.target_lang, "Original")
        self.target_lang_var = tk.StringVar(value=display_lang)

        self.lang_dropdown = ctk.CTkOptionMenu(
            lang_row,
            variable=self.target_lang_var,
            values=["Original", "Deutsch", "Englisch"],
            command=self._on_lang_changed,
            font=("Palatino Linotype", 11),
            width=118,
            height=28,
            fg_color=COLORS["border"],
            button_color=COLORS["ornament"],
            button_hover_color=COLORS["accent"],
            text_color=COLORS["text"],
            dropdown_fg_color=COLORS["surface"],
            dropdown_text_color=COLORS["text"],
            dropdown_hover_color=COLORS["border"],
        )
        self.lang_dropdown.pack(side="right")

        # ── Geschwindigkeit ─────────────────────────────────────
        speed_frame = self._section_frame()

        speed_header = ctk.CTkFrame(speed_frame, fg_color="transparent")
        speed_header.pack(fill="x", padx=14, pady=(10, 2))

        ctk.CTkLabel(
            speed_header,
            text="❖  ÜBERTRAGUNGSRATE",
            font=("Palatino Linotype", 11, "bold"),
            text_color=COLORS["accent"],
        ).pack(side="left")

        self.speed_lbl = ctk.CTkLabel(
            speed_header,
            text=f"{self.speed:.1f}×",
            font=("Palatino Linotype", 11, "bold"),
            text_color=COLORS["accent"],
        )
        self.speed_lbl.pack(side="right")

        self.speed_slider = ctk.CTkSlider(
            speed_frame,
            from_=0.5,
            to=2.0,
            number_of_steps=30,
            progress_color=COLORS["accent"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["yellow"],
            fg_color=COLORS["border"],
            command=self._on_speed_change,
        )
        self.speed_slider.set(self.speed)
        self.speed_slider.pack(fill="x", padx=14, pady=(4, 14))

        # ── Hotkey ──────────────────────────────────────────────
        hotkey_frame = self._section_frame()

        hk_row = ctk.CTkFrame(hotkey_frame, fg_color="transparent")
        hk_row.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(
            hk_row,
            text="❖  AKTIVIERUNGS-RUNE",
            font=("Palatino Linotype", 11, "bold"),
            text_color=COLORS["accent"],
        ).pack(side="left")

        self.hotkey_btn = ctk.CTkButton(
            hk_row,
            text=self.hotkey.upper(),
            width=118,
            height=28,
            fg_color=COLORS["border"],
            hover_color=COLORS["ornament"],
            text_color=COLORS["accent"],
            font=("Palatino Linotype", 12, "bold"),
            command=self._change_hotkey,
        )
        self.hotkey_btn.pack(side="right")

        # ── Start / Stop ─────────────────────────────────────────
        self.start_btn = ctk.CTkButton(
            self,
            text="▶   A K T I V I E R E N",
            height=54,
            corner_radius=8,
            font=("Palatino Linotype", 15, "bold"),
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
            ctrl_row,
            text="⏸   Pause",
            width=162,
            height=36,
            state="disabled",
            fg_color=COLORS["border"],
            hover_color=COLORS["ornament"],
            text_color=COLORS["text_dim"],
            font=("Palatino Linotype", 13, "bold"),
            command=self._toggle_pause,
        )
        self.pause_btn.pack(side="left", padx=(0, 4))

        self.repeat_btn = ctk.CTkButton(
            ctrl_row,
            text="🔁   Wiederholen",
            width=162,
            height=36,
            state="disabled",
            fg_color=COLORS["border"],
            hover_color=COLORS["ornament"],
            text_color=COLORS["text_dim"],
            font=("Palatino Linotype", 13, "bold"),
            command=self._repeat_last,
        )
        self.repeat_btn.pack(side="left", padx=(4, 0))

        # ── Status (Cogitator-Terminal) ──────────────────────────
        status_wrapper = ctk.CTkFrame(self, fg_color=COLORS["accent"], corner_radius=8)
        status_wrapper.pack(fill="x", padx=14, pady=6)
        status_frame = ctk.CTkFrame(status_wrapper, fg_color=COLORS["surface"], corner_radius=7)
        status_frame.pack(fill="both", expand=True, padx=1, pady=1)

        ctk.CTkLabel(
            status_frame,
            text="C O G I T A T O R   S T A T U S",
            font=("Palatino Linotype", 9, "bold"),
            text_color=COLORS["ornament"],
        ).pack(pady=(6, 0))

        self.status_lbl = ctk.CTkLabel(
            status_frame,
            text="◈  Lade Modelle ...",
            font=("Palatino Linotype", 12),
            text_color=COLORS["yellow"],
        )
        self.status_lbl.pack(pady=(2, 10))

        # ── Fußzeile ─────────────────────────────────────────────
        ctk.CTkFrame(self, fg_color=COLORS["accent"], height=1, corner_radius=0).pack(fill="x", padx=14)
        ctk.CTkLabel(
            self,
            text="✠   ESC — Übertragung abbrechen   ✠",
            font=("Palatino Linotype", 10),
            text_color=COLORS["ornament"],
        ).pack(pady=(4, 8))

    # ----------------------------------------------------------
    #  STIMMVORLAGE
    # ----------------------------------------------------------
    def _get_voice_list(self):
        voices = [f for f in os.listdir(self.voices_dir) if f.lower().endswith('.wav')]
        return voices if voices else ["Keine Stimme gefunden"]

    def _refresh_voice_dropdown(self):
        voices = self._get_voice_list()
        self.voice_dropdown.configure(values=voices)
        if os.path.basename(self.spk_wav) not in voices and voices and voices[0] != "Keine Stimme gefunden":
            self.voice_var.set(voices[0])
            self._on_voice_changed(voices[0])
        elif not voices or voices[0] == "Keine Stimme gefunden":
            self.voice_var.set("Keine Stimme gefunden")
            self.spk_wav = ""

    def _on_voice_changed(self, choice):
        if choice == "Keine Stimme gefunden": return
        self.spk_wav = os.path.join(self.voices_dir, choice)
        self.cfg.set("Einstellungen", "stimme_datei", choice)
        with open(os.path.join(APPDATA_DIR, "config.ini"), "w", encoding="utf-8") as f:
            self.cfg.write(f)

        if self.tts is not None:
            self._set_status("◈  Stimme gewechselt ... bereite vor", COLORS["yellow"])
            threading.Thread(target=self._prepare_speaker, daemon=True).start()

    def _rename_voice(self):
        current = self.voice_var.get()
        if current == "Keine Stimme gefunden": return

        dialog = ctk.CTkInputDialog(text="Neuer Name für die Stimme (ohne .wav):", title="Umbenennen")
        new_name = dialog.get_input()
        if new_name:
            new_name = new_name.strip()
            if not new_name.lower().endswith(".wav"):
                new_name += ".wav"

            old_path = os.path.join(self.voices_dir, current)
            new_path = os.path.join(self.voices_dir, new_name)

            if os.path.exists(new_path):
                messagebox.showerror("Fehler", "Eine Stimme mit diesem Namen existiert bereits.")
                return

            os.rename(old_path, new_path)

            if self.spk_wav == old_path:
                self.spk_wav = new_path
                self.cfg.set("Einstellungen", "stimme_datei", new_name)
                with open(os.path.join(APPDATA_DIR, "config.ini"), "w", encoding="utf-8") as f:
                    self.cfg.write(f)

            self.voice_var.set(new_name)
            self._refresh_voice_dropdown()
            self._set_status(f"◈  Umbenannt zu '{new_name}'", COLORS["green"])

    def _delete_voice(self):
        current = self.voice_var.get()
        if current == "Keine Stimme gefunden": return

        if messagebox.askyesno("Löschen", f"Soll die Stimme '{current}' wirklich gelöscht werden?"):
            os.remove(os.path.join(self.voices_dir, current))
            self._refresh_voice_dropdown()
            self._set_status("◈  Stimme gelöscht", COLORS["red"])

    def _open_record_dialog(self):
        RecordDialog(self, self._on_voice_saved)

    def _load_voice_file(self):
        path = filedialog.askopenfilename(
            title="Stimmvorlage wählen",
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
                import pydub.utils as pydub_utils
                if not which("ffmpeg"):
                    winget_ffmpeg = os.path.expandvars(
                        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages"
                        r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
                        r"\ffmpeg-8.1-full_build\bin"
                    )
                    os.environ["PATH"] = winget_ffmpeg + os.pathsep + os.environ.get("PATH", "")
                AudioSegment.from_mp3(path).export(dest, format="wav")
            except ImportError:
                messagebox.showerror(
                    "Fehler",
                    "pydub ist nicht installiert.\nInstalliere es mit:\n  pip install pydub\n\nFür MP3-Support wird außerdem ffmpeg benötigt.",
                )
                return
            except Exception as exc:
                messagebox.showerror("Fehler", f"MP3-Konvertierung fehlgeschlagen:\n{exc}")
                return
        else:
            shutil.copy2(path, dest)

        self._refresh_voice_dropdown()
        self.voice_var.set(dest_name)
        self._on_voice_changed(dest_name)

    def _on_voice_saved(self, temp_path):
        dialog = ctk.CTkInputDialog(text="Name für die neue Aufnahme:", title="Aufnahme speichern")
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
        lang_map = {"Original": "auto", "Deutsch": "de", "Englisch": "en"}
        self.target_lang = lang_map.get(choice, "auto")
        self.cfg.set("Einstellungen", "ausgabesprache", self.target_lang)
        with open(os.path.join(APPDATA_DIR, "config.ini"), "w", encoding="utf-8") as f:
            self.cfg.write(f)

        if self.target_lang != "auto":
            try:
                import deep_translator
            except Exception as e:
                print(f"[FEHLER] deep_translator konnte nicht geladen werden: {e}")
                messagebox.showwarning("Fehlendes Modul", f"Das Modul 'deep-translator' wurde nicht gefunden.\nFehler: {e}\n\nBitte starte das Programm neu. Achte darauf, es innerhalb deiner '(venv)' Umgebung zu starten!")

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
            messagebox.showinfo("Hinweis", "Bitte stoppe zuerst die Anwendung (auf 'STOP' klicken), um den Hotkey zu ändern.")
            return

        self.hotkey_btn.configure(state="disabled", text="Eingabe...", text_color=COLORS["yellow"])
        self._set_status("◈  Warte auf neue Aktivierungs-Rune ...", COLORS["yellow"])
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
        self._set_status(f"◈  Rune gespeichert: {self.hotkey.upper()}", COLORS["green"])

    # ----------------------------------------------------------
    #  START / STOP
    # ----------------------------------------------------------
    def _toggle_active(self):
        if not self.is_active:
            if not os.path.exists(self.spk_wav):
                messagebox.showwarning(
                    "Keine Stimmvorlage",
                    "Bitte erst eine Stimmvorlage aufnehmen oder eine Datei laden.",
                )
                return
            if self.tts is None or self.ocr_reader is None:
                messagebox.showinfo("Bitte warten", "Die KI-Modelle werden noch geladen ...")
                return
            if self.gpt_cond_latent is None:
                messagebox.showinfo("Bitte warten", "Stimmvorlage wird noch vorbereitet ...")
                return
            self._activate()
        else:
            self._deactivate()

    def _activate(self):
        self.is_active = True
        keyboard.add_hotkey(self.hotkey, self._hotkey_pressed)
        keyboard.add_hotkey("esc", self._esc_pressed)
        self.start_btn.configure(
            text="■   D E A K T I V I E R E N",
            fg_color=COLORS["accent2"],
            hover_color="#6b1010",
            text_color=COLORS["text"],
        )
        self._set_status(f"◈  Aktiv  —  [{self.hotkey.upper()}] zum Auswählen", COLORS["green"])

    def _deactivate(self):
        self.is_active = False
        self._stop_playback = True
        keyboard.unhook_all()
        sd.stop()
        self.start_btn.configure(
            text="▶   A K T I V I E R E N",
            fg_color=COLORS["green"],
            hover_color="#2d5c27",
            text_color=COLORS["text"],
        )
        self._set_status("◈  Deaktiviert", COLORS["text_dim"])

    # ----------------------------------------------------------
    #  KONFIGURATION
    # ----------------------------------------------------------
    def _load_config(self):
        cfg_file = os.path.join(APPDATA_DIR, "config.ini")
        # Migration: alte config.ini aus dem App-Ordner übernehmen
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
    #  MODELLE LADEN  (Hintergrund-Thread)
    # ----------------------------------------------------------
    def _load_models(self):
        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            hw_name = torch.cuda.get_device_name(0) if device == "cuda" else "CPU"
            print(f"[INFO] Gerät: {hw_name}")

            print("[INFO] Lade TTS-Modell (XTTSv2) ...")
            os.environ["COQUI_TOS_AGREED"] = "1"
            self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
            print("[INFO] TTS geladen.")

            print("[INFO] Lade OCR-Modell (EasyOCR) ...")
            self.ocr_reader = easyocr.Reader(["de", "en"], gpu=(device == "cuda"))
            print("[INFO] OCR geladen.")

            if os.path.exists(self.spk_wav):
                self._prepare_speaker()

            self._set_status("◈  Systeme bereit — Voxcaster online", COLORS["text"])
            print(f"\n[BEREIT] Drücke AKTIVIEREN und dann [{self.hotkey.upper()}] zum Auswählen.\n")
            self.after(0, self._enable_start_btn)

        except Exception as exc:
            print(f"[FEHLER] Beim Laden der Modelle: {exc}")
            self._set_status("◈  Ladefehler! Konsole prüfen.", COLORS["red"])

    # ----------------------------------------------------------
    #  HOTKEY-HANDLER  (keyboard-Thread)
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
    #  QUEUE-POLLING  (Tkinter-Haupt-Thread)
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
    #  BEREICH AUSWÄHLEN  (Haupt-Thread)
    # ----------------------------------------------------------
    def _start_selection(self):
        self.is_processing = True
        self._set_status("◈  Bereich auswählen ...", COLORS["yellow"])

        sel = RegionSelector(self)
        box = sel.select_region()

        if box:
            threading.Thread(target=self._process, args=(box,), daemon=True).start()
        else:
            self.is_processing = False
            self._set_status(f"◈  Aktiv  —  [{self.hotkey.upper()}] zum Auswählen", COLORS["green"])

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

        if en_count > de_count:
            return "en"
        return "de"

    # ----------------------------------------------------------
    #  SPEAKER VORBEREITEN
    # ----------------------------------------------------------
    def _enable_start_btn(self):
        self.start_btn.configure(
            state="normal",
            fg_color=COLORS["green"],
            hover_color="#2d5c27",
            text_color=COLORS["text"],
        )

    def _prepare_speaker(self):
        try:
            xtts = self.tts.synthesizer.tts_model
            self.gpt_cond_latent, self.speaker_embedding = xtts.get_conditioning_latents(
                audio_path=[self.spk_wav]
            )
            print("[INFO] Stimmvorlage vorberechnet.")
        except Exception as exc:
            print(f"[FEHLER] Stimmvorlage konnte nicht vorbereitet werden: {exc}")

    # ----------------------------------------------------------
    #  OCR + TTS  (Hintergrund-Thread)
    # ----------------------------------------------------------
    def _process(self, box):
        try:
            self._set_status("◈  Erkenne Text ...", COLORS["yellow"])
            text = self._run_ocr(box)

            if not text:
                print("[INFO] Kein Text im Bereich erkannt.")
                return

            text = self._clean_text(text)
            detected_lang = self._detect_language(text)

            print(f"\n--- ERKANNTER TEXT ({detected_lang.upper()}) ---\n{text}\n----------------------")

            tts_lang = detected_lang
            if self.target_lang in ["de", "en"] and detected_lang != self.target_lang:
                self._set_status("◈  Übersetze Text ...", COLORS["yellow"])
                try:
                    from deep_translator import GoogleTranslator
                    translator = GoogleTranslator(source=detected_lang, target=self.target_lang)
                    translated_text = translator.translate(text)
                    print(f"\n--- ÜBERSETZT ({self.target_lang.upper()}) ---\n{translated_text}\n----------------------")

                    text = translated_text
                    tts_lang = self.target_lang
                except ImportError as e:
                    print(f"[FEHLER] 'deep-translator' Import fehlgeschlagen: {e}")
                    self._set_status("◈  Übersetzungs-Modul fehlt", COLORS["red"])
                    time.sleep(1.5)
                except Exception as e:
                    print(f"[FEHLER] Übersetzung fehlgeschlagen: {e}")
                    self._set_status("◈  Übersetzung fehlgeschlagen", COLORS["red"])
                    time.sleep(1.5)

            self._set_status("◈  Generiere Vox-Signal ...", COLORS["accent"])
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
                    target_samples = int(24000 * 1.5)

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
                    self._set_status("◈  Übertragung läuft ...", COLORS["accent"])
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
                        text_chunk,
                        tts_lang,
                        self.gpt_cond_latent,
                        self.speaker_embedding,
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
                state="disabled", text="⏸   Pause",
                fg_color=COLORS["border"], hover_color=COLORS["ornament"], text_color=COLORS["text_dim"]
            ))
            self._set_status(f"◈  Aktiv  —  [{self.hotkey.upper()}] zum Auswählen", COLORS["green"])

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
            self.pause_btn.configure(text="▶   Weiter", fg_color=COLORS["accent"], hover_color=COLORS["yellow"], text_color="#0d0a06")
            self._set_status("◈  Übertragung pausiert", COLORS["yellow"])
        else:
            self._pause_event.set()
            self.pause_btn.configure(text="⏸   Pause", fg_color=COLORS["border"], hover_color=COLORS["ornament"], text_color=COLORS["text_dim"])
            self._set_status("◈  Übertragung läuft ...", COLORS["accent"])

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
            text="⏹   Stoppen",
            fg_color=COLORS["accent2"],
            hover_color="#6b1010",
            text_color=COLORS["text"],
        )
        self.pause_btn.configure(state="normal")
        self._set_status("◈  Wiederhole Übertragung ...", COLORS["accent"])
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
            self.pause_btn.configure(state="disabled", text="⏸   Pause", fg_color=COLORS["border"], hover_color=COLORS["ornament"], text_color=COLORS["text_dim"])
            self.after(0, lambda: self.repeat_btn.configure(
                state="normal", text="🔁   Wiederholen",
                fg_color=COLORS["border"], hover_color=COLORS["ornament"], text_color=COLORS["text"]
            ))
            self._set_status(f"◈  Aktiv  —  [{self.hotkey.upper()}] zum Auswählen", COLORS["green"])

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
