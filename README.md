# Lead Scraper

Automatisierter Lead Scraper für das Lead-Management-System.

## Ziel

Der Lead Scraper soll Unternehmen über Google Maps finden, relevante Unternehmensdaten extrahieren und diese anschließend für die weitere Lead-Bearbeitung und das CRM bereitstellen.

## Aktueller Stand

- Google Maps wird über Playwright geöffnet
- Google-Consent kann manuell bestätigt werden
- Suchbegriffe können vorgegeben werden
- Unternehmen können gefunden und geöffnet werden
- Unternehmensname wird extrahiert
- Bewertung wird extrahiert
- Anzahl der Bewertungen wird extrahiert
- Adresse wird extrahiert
- Telefonnummer wird extrahiert
- Website wird erkannt
- Ollama kann lokal über Python angesprochen werden
- Leads können mit Ollama analysiert und bewertet werden
- CSV-Struktur für den späteren CRM-Import ist vorhanden

## Technologie

- Python
- Playwright
- Ollama
- Llama 3.1 8B
- CSV
- Git / GitHub

## Projektstruktur

```text
scraper/
├── analyze_leads.py
├── browser_test.py
├── scraper.py
├── test_ollama.py
├── .gitignore
└── README.md
