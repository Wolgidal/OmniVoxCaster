import torch
from TTS.api import TTS
import os
import time

# Hardware-Check
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"--- INITIALISIERUNG ---")
print(f"Hardware: {torch.cuda.get_device_name(0) if device == 'cuda' else 'CPU'}")

# Der Pfad zu deiner manuell bereitgestellten Datei
speaker_path = "stimme_vorlage.wav"

if not os.path.exists(speaker_path):
    print(f"!!! FEHLER: Die Datei '{speaker_path}' wurde nicht im Ordner gefunden.")
    print("Bitte lege eine kurze .wav Datei in den Ordner C:\\Projekte und nenne sie 'stimme_vorlage.wav'.")
else:
    # Modell laden
    print("Lade KI-Modell (XTTSv2)...")
    os.environ["COQUI_TOS_AGREED"] = "1"
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

    # Dein Quest-Text
    quest_text = (
        "Seid gegrüßt, edler Recke! Deine RTX 4090 hat soeben die Macht der künstlichen Intelligenz entfesselt. "
        "Jetzt, wo ich eine echte Stimme als Vorlage habe, kann ich endlich sprechen. "
        "Wie findest du das Ergebnis?"
    )

    print("\n--- GENERIERUNG STARTET ---")
    start_time = time.time()

    try:
        tts.tts_to_file(
            text=quest_text,
            speaker_wav=speaker_path, 
            language="de",
            file_path="quest_test.wav"
        )
        end_time = time.time()
        print(f"\nERFOLG! Dauer: {end_time - start_time:.2f} Sekunden.")
        print(f"Die fertige Datei liegt hier: {os.path.abspath('quest_test.wav')}")
    except Exception as e:
        print(f"Fehler bei der Generierung: {e}")