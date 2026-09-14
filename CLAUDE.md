# CLAUDE.md

Diese Datei gibt Claude Code den Kontext, um an diesem Projekt weiterzuarbeiten.

## Projektüberblick

Interner Lead-Generierungs-Pipeline für **Prozesspiloten** (ehem. Nova Core), eine
3-Personen-Digitalagentur für deutsche KMU (John, Maurice, Mxi). Ziel: potenzielle
Kunden (aktuell Fokus: Handwerksbetriebe) automatisiert über Google Maps finden,
anreichern und nach Vertriebspotenzial bewerten — als Grundlage für Cold-Calling /
Outreach.

Geplante Gesamt-Pipeline (siehe Roadmap unten): Scraper → Website-Analyse →
Lead-Scoring → Dedup → FastAPI → Frontend → CRM-Automatisierung. Aktuell ist nur
der erste Teil (Scraper, Website-Analyzer, Lead-Analyzer) als eigenständige
Python-Skripte umgesetzt, die nacheinander manuell ausgeführt werden und CSV-Dateien
als Zwischenspeicher nutzen.

## Pipeline / Ausführungsreihenfolge

Seit 2026-09-14 gibt es `main.py`, das die drei Schritte automatisch nacheinander
als eigene Prozesse ausfuehrt (inkl. Ollama-Erreichbarkeitscheck vor Schritt 3) und
bei einem Fehler abbricht, statt fehlerhaft weiterzulaufen: `python main.py`. Die
Skripte funktionieren weiterhin auch einzeln, genau wie unten beschrieben.

1. `scraper.py` — öffnet Google Maps im echten Chromium-Fenster (Playwright,
   `headless=False`, damit man das Google-Consent-Banner manuell bestätigen kann),
   sucht nach `SEARCH` (aktuell hart kodiert: `"Elektriker Hamburg"`), sammelt bis zu
   `MAX_LEADS` Firmenprofile und extrahiert je Firma Name, Adresse, Telefon, Bewertung,
   Website + Social-Media-Links, sowie (per `requests`/`BeautifulSoup`) eine E-Mail von
   der Firmenwebsite (Startseite oder Kontakt-/Impressum-Unterseite). Schreibt
   `leads_clean.csv`.
2. `website_analyzer.py` — liest `leads_clean.csv`, ruft jede Website ab und bewertet
   sie über 15 Kriterien (HTTPS, gültiges SSL-Zertifikat, Title, Meta-Description, H1,
   Viewport/Mobile-Meta, Ladezeit, Telefon/E-Mail im Text, Kontaktformular, Impressum,
   Datenschutz, Social-Links, robots.txt/sitemap.xml) zu einem `website_score` (0–100)
   und `website_quality` (NIEDRIG/MITTEL/HOCH). Schreibt zurück in `leads_clean.csv`.
3. `analyze_leads.py` — liest `leads_clean.csv`, berechnet einen **deterministischen**
   `lead_score` (reine Python-Logik, keine KI) auf Basis von: fehlende/schwache
   Website, Google-Bewertung, Anzahl Bewertungen, Telefon/E-Mail vorhanden, Social
   Media ohne eigene Website. Ruft danach **Ollama** (`llama3.1:8b`, lokal unter
   `localhost:11434`) auf — aber nur, um auf Basis des bereits berechneten Scores
   `priority`, `potential`, eine kurze Begründung und 3 Verkaufsargumente zu
   formulieren. Ollama darf laut Prompt keine Fakten erfinden und den
   Python-Score nicht überschreiben. Schreibt `leads_analyzed.csv`.

Zusätzliche Skripte, die **nicht** Teil der eigentlichen Pipeline sind, sondern
Wegwerf-/Debug-Experimente für die Playwright-Selektoren bzw. Ollama-Prompts:
`browser_test.py`, `website_debug.py`, `test_ollama.py`.

## Tech-Stack

- Python 3.14, venv unter `.venv/`
- **Playwright** (`sync_api`, Chromium) fürs Scraping von Google Maps — **wichtig:**
  Playwright ist aktuell **nicht** im `.venv` installiert (nur `beautifulsoup4`,
  `requests`, `certifi`, `urllib3`, `idna`, `soupsieve`, `charset_normalizer`,
  `typing_extensions`, `pip`). Es gibt außerdem noch kein `requirements.txt`. Vor dem
  Weiterarbeiten: `pip install playwright beautifulsoup4 requests` und
  `playwright install chromium`, danach `pip freeze > requirements.txt` anlegen.
- `requests` + `BeautifulSoup4` fürs Abrufen/Parsen von Firmenwebsites
- Ollama (lokal, Modell `llama3.1:8b`) nur für qualitative Texte, nicht fürs Scoring
- Kein Web-Framework bisher (FastAPI ist laut Roadmap geplant, aber noch nicht
  angefangen)
- Datenhaltung aktuell: CSV (`leads_clean.csv`, `leads_analyzed.csv`). Eine Migration
  auf ein sauberes JSON-Datenmodell mit UUIDs ist geplant, aber im Code noch nicht
  begonnen.

## Datenmodell (aktuelle CSV-Spalten)

Von `scraper.py`: `company_name, category, address, city, postal_code, country,
phone, email, website, instagram, facebook, tiktok, youtube, linkedin,
google_rating, review_count, has_website, website_quality, lead_score, priority,
source, scraped_at, maps_url`

Von `website_analyzer.py` ergänzt: `website_status, website_final_url,
website_http_status, website_https, website_title, website_meta_description,
website_h1, website_mobile_meta, website_has_phone, website_has_email,
website_impressum, website_datenschutz, website_instagram/_facebook/_linkedin/
_youtube/_tiktok, website_ssl_valid, website_load_time_ms, website_contact_form,
website_robots_txt, website_sitemap, website_score, website_quality`

Von `analyze_leads.py` ergänzt: `lead_score` (überschrieben mit deterministischem
Score), `priority, potential, score_reasons, ai_reason, sales_argument_1/_2/_3`

## Akuter Arbeitsauftrag (aktueller Fokus)

Der Scraper muss umgebaut werden, konkret zwei Probleme:

1. **[BEHOBEN, 2026-09-14] Kein Dedup über mehrere Läufe hinweg.** `scraper.py`
   scrollt jetzt aktiv das Ergebnis-Panel (`div[role="feed"]`, bis zu
   `MAX_SCROLL_ATTEMPTS` mal, Abbruch nach `STAGNANT_ROUNDS_LIMIT` Runden ohne neue
   Treffer) und gleicht jeden gefundenen Link sowie jeden fertig extrahierten Lead
   (über `maps_url` bzw. normalisierte Firma+Adresse, siehe `load_known_leads()` /
   `normalize_key()`) gegen die bereits in `leads_clean.csv` vorhandenen Zeilen ab.
   Neue Leads werden an `leads_clean.csv` angehängt statt die Datei zu überschreiben.
   `SEARCH`/`CATEGORY`/`CITY` sind weiterhin hart kodiert — das ist Punkt 2 unten und
   noch offen. Lokal noch nicht mit echtem Playwright-Lauf getestet (nur
   `py_compile`-Syntaxcheck), da Playwright in `.venv` fehlt (siehe Tech-Stack).
2. **Keine Geo-/Branchen-Steuerung.** `CATEGORY`/`CITY`/`SEARCH` sind aktuell fix auf
   `"Elektriker"` / `"Hamburg"` gesetzt. Gewünscht: Handwerksbetriebe im Umkreis von
   ca. 25 km um **Alfeld (Leine), Hildesheim und Hannover**. Google Maps' Textsuche
   kennt keinen echten Radius-Parameter — mögliche Ansätze, die es abzuwägen gilt:
   mehrere Suchbegriffe pro Ort/Branche durchlaufen (z.B. Liste von Handwerker-Branchen
   × Liste von Städten/Orten im 25-km-Radius), oder über Koordinaten/Zoom-Level in der
   Maps-URL (`@lat,lng,zoom`) eine Umkreissuche annähern. Das ist eine offene
   Design-Entscheidung — bitte mit John klären, bevor viel Code dafür geschrieben wird.

## Code-Stil (aktuell im Repo)

- Kommentare, Prints und Variablennamen für Geschäftsdaten sind auf Deutsch, Code
  (Funktionsnamen etc.) auf Englisch.
- Sehr kleinteilige, defensive Funktionen mit breiten `try/except`, die im Fehlerfall
  leere Strings/Defaults zurückgeben statt zu crashen — Scraping-Robustheit hat
  Vorrang vor Eleganz.
- Fortschritt wird über `print()`-Ausgaben mit `"=" * 60`-Trennlinien kommuniziert,
  kein `logging`-Modul.
- Auffällig: viele Funktionsaufrufe sind mit einem Argument pro Zeile formatiert
  (sehr vertikal). Beim Editieren nicht zwingend in diesem Stil weiterschreiben,
  außer John wünscht es explizit — Lesbarkeit geht vor.
- Bisher kein Test-Setup, kein Linting/Formatting-Tool konfiguriert.

## Roadmap (aus Projektplanung)

JSON-Datenmodell → Scraper → Website-Analyzer → Lead-Analyzer → Dedup → FastAPI →
Frontend → CRM-Browser-Automatisierung. Scraper/Website-Analyzer/Lead-Analyzer
existieren bereits (s.o.); Dedup, JSON-Migration, FastAPI, Frontend und
CRM-Automatisierung stehen noch aus.

## Hinweise für Claude Code

- Vor jeder Änderung am Scraping-Teil kurz prüfen, ob Playwright + Browser-Binaries
  lokal installiert sind (`pip show playwright`, `playwright install --dry-run`
  o.ä.) — siehe Dependency-Hinweis oben.
- `leads.csv` ist laut `.gitignore` bewusst nicht versioniert (enthält vermutlich
  Rohdaten/Testläufe); `leads_clean.csv` und `leads_analyzed.csv` sind aktuell nicht
  in `.gitignore` — beim Committen beachten, ob diese Dateien (mit echten
  Kundendaten von Handwerksbetrieben) wirklich ins Repo sollen.
- Ollama läuft lokal und muss vor `analyze_leads.py` gestartet sein
  (`ollama serve` bzw. die Ollama-App), sonst schlägt der Request auf
  `localhost:11434` fehl.
- Der Scraper öffnet bewusst ein sichtbares Browserfenster (`headless=False`), weil
  das Google-Consent-Banner manuell bestätigt werden muss — das sollte beim Umbau
  erhalten bleiben, sonst hängt das Skript beim ersten Consent-Prompt.
