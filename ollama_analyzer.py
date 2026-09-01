import csv
import json
import requests
import os


INPUT_FILE = "leads.csv"
OUTPUT_FILE = "leads.csv"

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1:8b"


def analyze_lead(lead):

    prompt = f"""
Du bist ein professionelles Lead-Scoring-System für eine Webdesign-Agentur.

Deine Aufgabe ist NICHT, allgemein zu erklären, warum eine Branche interessant ist.

Du musst entscheiden, wie attraktiv dieser konkrete Lead für einen Vertriebler ist.

Bewerte besonders:

1. Website vorhanden oder nicht
2. Website-Qualität
3. Google-Bewertung
4. Anzahl der Bewertungen
5. Professioneller Eindruck
6. Wahrscheinlichkeit eines konkreten Website-Bedarfs
7. Wie leicht sich ein Verkaufsargument formulieren lässt

WICHTIG:

- Sei kritisch.
- Vergib keine hohen Scores nur wegen einer guten Google-Bewertung.
- Eine gute Bewertung bedeutet nicht automatisch, dass die Website gut ist.
- Eine schlechte oder fehlende Website ist ein starkes Signal.
- Wenn kaum Daten vorhanden sind, darf der Score nicht künstlich hoch sein.
- Bewerte den konkreten Lead und nicht nur die Branche.

LEAD:

Firma: {lead.get("company_name", "")}
Branche: {lead.get("category", "")}
Adresse: {lead.get("address", "")}
Stadt: {lead.get("city", "")}
Telefon: {lead.get("phone", "")}
Website: {lead.get("website", "")}
Google Bewertung: {lead.get("google_rating", "")}
Anzahl Bewertungen: {lead.get("review_count", "")}
Website vorhanden: {lead.get("has_website", "")}
Website Qualität: {lead.get("website_quality", "")}

Bewertung:

1-3 = schlechter Lead
4-5 = eher uninteressant
6 = interessant, aber nicht dringend
7 = guter Lead
8 = sehr guter Lead
9 = extrem guter Lead
10 = außergewöhnlich guter Lead

PRIORITÄT:

NIEDRIG = aktuell wenig interessant
MITTEL = interessant, aber kein dringender Kontakt
HOCH = sollte zeitnah kontaktiert werden

POTENZIAL:

NIEDRIG
MITTEL
HOCH

Antworte ausschließlich als gültiges JSON.

Format:

{{
  "score": 0,
  "prioritaet": "NIEDRIG",
  "potenzial": "NIEDRIG",
  "begruendung": "Kurze konkrete Begründung.",
  "verkaufsargumente": [
    "Argument 1",
    "Argument 2",
    "Argument 3"
  ]
}}
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        },
        timeout=120
    )

    response.raise_for_status()

    data = response.json()

    result = json.loads(data["response"])

    return result


def main():

    if not os.path.exists(INPUT_FILE):
        print(f"FEHLER: {INPUT_FILE} wurde nicht gefunden.")
        return

    with open(
        INPUT_FILE,
        newline="",
        encoding="utf-8"
    ) as file:

        reader = csv.DictReader(file)
        leads = list(reader)

    if not leads:
        print("Keine Leads gefunden.")
        return

    print(f"{len(leads)} Leads gefunden.")
    print("=" * 60)

    fieldnames = list(leads[0].keys())

    new_fields = [
        "lead_score",
        "priority",
        "potential",
        "ai_reason",
        "sales_argument_1",
        "sales_argument_2",
        "sales_argument_3"
    ]

    for field in new_fields:
        if field not in fieldnames:
            fieldnames.append(field)

    for index, lead in enumerate(leads, start=1):

        print()
        print(f"LEAD {index}/{len(leads)}")
        print(lead.get("company_name", "Unbekannte Firma"))
        print("-" * 60)

        try:

            result = analyze_lead(lead)

            lead["lead_score"] = result.get("score", "")
            lead["priority"] = result.get("prioritaet", "")
            lead["potential"] = result.get("potenzial", "")
            lead["ai_reason"] = result.get("begruendung", "")

            arguments = result.get("verkaufsargumente", [])

            lead["sales_argument_1"] = arguments[0] if len(arguments) > 0 else ""
            lead["sales_argument_2"] = arguments[1] if len(arguments) > 1 else ""
            lead["sales_argument_3"] = arguments[2] if len(arguments) > 2 else ""

            print(f"SCORE: {lead['lead_score']}")
            print(f"PRIORITAET: {lead['priority']}")
            print(f"POTENZIAL: {lead['potential']}")
            print(f"BEGRUENDUNG: {lead['ai_reason']}")

            print("\nVERKAUFSARGUMENTE:")

            for argument in arguments:
                print(f"- {argument}")

        except Exception as error:

            print(f"FEHLER: {error}")

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(leads)

    print()
    print("=" * 60)
    print("ANALYSE ABGESCHLOSSEN")
    print(f"{len(leads)} Leads analysiert.")
    print(f"Ergebnisse gespeichert in: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
