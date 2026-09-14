"""
main.py - Startet die komplette Lead-Pipeline automatisch, in der Reihenfolge:

  1. scraper.py           Google Maps -> leads_clean.csv (neue Leads anhaengen)
  2. website_analyzer.py  bewertet die Websites in leads_clean.csv
  3. analyze_leads.py     Scoring (deterministisch) + Ollama-Verkaufsargumente
                           -> leads_analyzed.csv

Jeder Schritt laeuft als eigener Python-Prozess (genau wie bisher beim
manuellen Ausfuehren), nicht als Import. Das ist bewusst so, weil
scraper.py oeffnet ein Browserfenster und wartet per input() auf die
manuelle Google-Consent-Bestaetigung - das funktioniert nur, wenn das
Skript als eigener Prozess mit eigenem Terminal-Zugriff laeuft, nicht
wenn man es importiert.

Bricht bei einem Fehler in einem Schritt sofort ab, damit die
nachfolgenden Schritte nicht mit kaputten oder leeren Daten weiterlaufen.

Aufruf:
    python main.py
"""

import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

PIPELINE = [
    ("Scraper (Google Maps)", "scraper.py"),
    ("Website-Analyse", "website_analyzer.py"),
    ("Lead-Analyse (Scoring + Ollama)", "analyze_leads.py"),
]

OLLAMA_CHECK_URL = "http://localhost:11434"


def check_ollama_running():
    try:
        urllib.request.urlopen(OLLAMA_CHECK_URL, timeout=2)
        return True

    except urllib.error.URLError:
        return False

    except Exception:
        return False


def run_step(title, script_name):
    script_path = BASE_DIR / script_name

    print()
    print("=" * 60)
    print(f"SCHRITT: {title}")
    print("=" * 60)

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=BASE_DIR,
    )

    if result.returncode != 0:
        print()
        print(f"FEHLER: '{script_name}' wurde mit Code {result.returncode} beendet.")
        print("Pipeline gestoppt - nachfolgende Schritte werden nicht ausgefuehrt.")
        sys.exit(result.returncode)


def main():
    print("=" * 60)
    print("LEAD-PIPELINE START")
    print("=" * 60)
    print(f"Arbeitsverzeichnis: {BASE_DIR}")

    if not check_ollama_running():
        print()
        print(f"WARNUNG: Ollama scheint unter {OLLAMA_CHECK_URL} nicht erreichbar zu sein.")
        print("Der letzte Schritt (analyze_leads.py) braucht Ollama fuer die Verkaufsargumente.")

        answer = input("Trotzdem mit der Pipeline fortfahren? (j/n): ").strip().lower()

        if answer not in ("j", "ja", "y", "yes"):
            print("Abgebrochen. Bitte zuerst Ollama starten ('ollama serve') und main.py erneut ausfuehren.")
            sys.exit(1)

    for title, script_name in PIPELINE:
        run_step(title, script_name)

    print()
    print("=" * 60)
    print("PIPELINE ABGESCHLOSSEN")
    print("=" * 60)
    print("Ergebnis: leads_analyzed.csv")


if __name__ == "__main__":
    main()
