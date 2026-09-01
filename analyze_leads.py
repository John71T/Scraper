import csv
import requests


CSV_FILE = "leads.csv"

OLLAMA_URL = "http://localhost:11434/api/generate"

MODEL = "llama3.1:8b"


def analyze_lead(lead):

    prompt = f"""
Du bist ein B2B-Vertriebsexperte für eine Webdesign-Agentur.

Bewerte diesen Lead danach, wie interessant er für eine Webdesign-Agentur
ist.

Firma: {lead.get('company_name', '')}
Branche: {lead.get('category', '')}
Adresse: {lead.get('address', '')}
Stadt: {lead.get('city', '')}
Telefon: {lead.get('phone', '')}
Website: {lead.get('website', '')}
Google Bewertung: {lead.get('google_rating', '')}
Anzahl Bewertungen: {lead.get('review_count', '')}

Bewerte:

1. Lead Score von 1 bis 10
2. Priorität: HOCH, MITTEL oder NIEDRIG
3. Website-Qualität
4. Kurze Begründung

Antworte exakt in diesem Format:

SCORE: 8
PRIORITAET: HOCH
WEBSITE_QUALITAET: MITTEL
BEGRUENDUNG: Die Firma hat Potenzial für eine moderne Website, da ...

Keine zusätzlichen Informationen.
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        },
        timeout=120
    )

    response.raise_for_status()

    return response.json()["response"]


def parse_analysis(text):

    score = ""
    priority = ""
    website_quality = ""
    reason = ""

    for line in text.splitlines():

        line = line.strip()

        if line.startswith("SCORE:"):
            score = line.replace(
                "SCORE:",
                ""
            ).strip()

        elif line.startswith("PRIORITAET:"):
            priority = line.replace(
                "PRIORITAET:",
                ""
            ).strip()

        elif line.startswith("WEBSITE_QUALITAET:"):
            website_quality = line.replace(
                "WEBSITE_QUALITAET:",
                ""
            ).strip()

        elif line.startswith("BEGRUENDUNG:"):
            reason = line.replace(
                "BEGRUENDUNG:",
                ""
            ).strip()

    return score, priority, website_quality, reason


# --------------------------------------------------
# CSV LADEN
# --------------------------------------------------

with open(
    CSV_FILE,
    "r",
    newline="",
    encoding="utf-8"
) as file:

    reader = csv.DictReader(file)

    leads = list(reader)


print(
    f"{len(leads)} Leads gefunden."
)


# --------------------------------------------------
# LEADS ANALYSIEREN
# --------------------------------------------------

for lead in leads:

    company = lead.get(
        "company_name",
        ""
    )

    print()
    print("=" * 50)
    print(f"Lead: {company}")
    print("=" * 50)

    try:

        result = analyze_lead(lead)

        print(result)

        score, priority, website_quality, reason = parse_analysis(
            result
        )

        lead["lead_score"] = score
        lead["priority"] = priority
        lead["website_quality"] = website_quality

        print(
            f"\nScore: {score}"
        )

        print(
            f"Priorität: {priority}"
        )

        print(
            f"Website: {website_quality}"
        )

        print(
            f"Begründung: {reason}"
        )

    except Exception as error:

        print(
            f"Fehler bei {company}: {error}"
        )


# --------------------------------------------------
# CSV SPEICHERN
# --------------------------------------------------

fieldnames = list(leads[0].keys())

with open(
    CSV_FILE,
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
print("=" * 50)
print("ANALYSE ABGESCHLOSSEN")
print("=" * 50)

print(
    f"{len(leads)} Leads wurden analysiert."
)

print(
    f"Ergebnisse gespeichert in: {CSV_FILE}"
)



