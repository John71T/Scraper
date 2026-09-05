import csv
import json
import requests
from pathlib import Path


# ============================================================
# EINSTELLUNGEN
# ============================================================

INPUT_FILE = "leads_clean.csv"
OUTPUT_FILE = "leads_analyzed.csv"

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1:8b"


# ============================================================
# HILFSFUNKTIONEN
# ============================================================

def to_bool(value):
    return str(value).lower() == "true"


def to_float(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


# ============================================================
# OBJEKTIVER BASIS-SCORE
# ============================================================

def calculate_base_score(lead):
    """
    0-100 Punkte.

    Hoher Score = interessanter Lead für Webdesign-Vertrieb.
    """

    score = 0
    reasons = []

    has_website = to_bool(
        lead.get("has_website", "")
    )

    website_quality = (
        lead.get("website_quality", "")
        .strip()
        .upper()
    )

    rating = to_float(
        lead.get("google_rating")
    )

    reviews = to_int(
        lead.get("review_count")
    )

    phone = lead.get(
        "phone",
        ""
    ).strip()

    email = lead.get(
        "email",
        ""
    ).strip()

    instagram = lead.get(
        "instagram",
        ""
    ).strip()

    facebook = lead.get(
        "facebook",
        ""
    ).strip()

    # --------------------------------------------------------
    # WEBSITE
    # --------------------------------------------------------

    if not has_website:

        score += 40

        reasons.append(
            "Keine eigene Website vorhanden."
        )

    else:

        if website_quality in [
            "NIEDRIG",
            "LOW"
        ]:

            score += 30

            reasons.append(
                "Vorhandene Website wurde als schwach bewertet."
            )

        elif website_quality in [
            "MITTEL",
            "MEDIUM"
        ]:

            score += 18

            reasons.append(
                "Website besitzt Verbesserungspotenzial."
            )

        elif website_quality in [
            "HOCH",
            "HIGH"
        ]:

            score += 5

            reasons.append(
                "Website ist bereits relativ gut."
            )

        else:

            score += 10

            reasons.append(
                "Website vorhanden, Qualität noch nicht eindeutig bewertet."
            )

    # --------------------------------------------------------
    # GOOGLE REPUTATION
    # --------------------------------------------------------

    if rating >= 4.5:

        score += 10

        reasons.append(
            "Sehr gute Google-Bewertung."
        )

    elif rating >= 4.0:

        score += 7

    elif rating > 0:

        score += 3

    # --------------------------------------------------------
    # ANZAHL BEWERTUNGEN
    # --------------------------------------------------------

    if reviews >= 100:

        score += 12

        reasons.append(
            "Starke bestehende Kundenbasis."
        )

    elif reviews >= 50:

        score += 10

    elif reviews >= 20:

        score += 7

    elif reviews >= 5:

        score += 4

    # --------------------------------------------------------
    # KONTAKTIERBARKEIT
    # --------------------------------------------------------

    if phone:

        score += 8

    if email:

        score += 8

        reasons.append(
            "Direkte E-Mail-Adresse vorhanden."
        )

    # --------------------------------------------------------
    # SOCIAL MEDIA ABER KEINE WEBSITE
    # --------------------------------------------------------

    if not has_website and (
        instagram
        or facebook
    ):

        score += 7

        reasons.append(
            "Social-Media-Präsenz vorhanden, aber keine eigene Website."
        )

    score = min(
        score,
        100
    )

    return score, reasons


# ============================================================
# OLLAMA
# ============================================================

def analyze_with_ollama(
    lead,
    base_score,
    score_reasons
):

    prompt = f"""
Du bist ein Lead-Qualifizierungs-System für eine deutsche
Webdesign- und Digitalagentur.

Du erhältst ausschließlich bereits geprüfte Lead-Daten.

WICHTIGE REGELN:

- Erfinde keine Informationen.
- Behaupte niemals, eine Website sei schlecht, alt oder unmodern,
  wenn diese Information nicht in den gelieferten Daten steht.
- Bewerte ausschließlich diesen konkreten Lead.
- Eine gute Google-Bewertung bedeutet NICHT automatisch hohen
  Webdesign-Bedarf.
- Eine fehlende Website ist ein starkes Vertriebssignal.
- Social Media ohne eigene Website kann ebenfalls ein starkes Signal sein.
- Verwende den von Python berechneten Basisscore als wichtigste Grundlage.

LEAD-DATEN:

Firma:
{lead.get("company_name", "")}

Branche:
{lead.get("category", "")}

Ort:
{lead.get("city", "")}

Telefon:
{lead.get("phone", "")}

E-Mail:
{lead.get("email", "")}

Website:
{lead.get("website", "")}

Website vorhanden:
{lead.get("has_website", "")}

Website Qualität:
{lead.get("website_quality", "")}

Google Bewertung:
{lead.get("google_rating", "")}

Google Bewertungen:
{lead.get("review_count", "")}

Instagram:
{lead.get("instagram", "")}

Facebook:
{lead.get("facebook", "")}

PYTHON BASIS-SCORE:
{base_score}/100

FAKTISCHE SCORE-GRÜNDE:
{json.dumps(score_reasons, ensure_ascii=False)}

Ordne den Lead ein.

Priorität:

NIEDRIG:
Keine besondere Verkaufschance.

MITTEL:
Interessanter Lead, aber nicht höchste Priorität.

HOCH:
Sollte zeitnah vom Vertrieb kontaktiert werden.

Potenzial:

NIEDRIG
MITTEL
HOCH

Gib ausschließlich gültiges JSON zurück:

{{
    "priority": "HOCH",
    "potential": "HOCH",
    "reason": "Kurze konkrete Begründung mit maximal drei Sätzen.",
    "sales_arguments": [
        "Konkretes Argument 1",
        "Konkretes Argument 2",
        "Konkretes Argument 3"
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

    ollama_response = response.json()

    return json.loads(
        ollama_response["response"]
    )


# ============================================================
# EINEN LEAD ANALYSIEREN
# ============================================================

def analyze_lead(lead):

    base_score, score_reasons = calculate_base_score(
        lead
    )

    ai_result = analyze_with_ollama(
        lead,
        base_score,
        score_reasons
    )

    arguments = ai_result.get(
        "sales_arguments",
        []
    )

    lead["lead_score"] = base_score

    lead["priority"] = ai_result.get(
        "priority",
        ""
    )

    lead["potential"] = ai_result.get(
        "potential",
        ""
    )

    lead["ai_reason"] = ai_result.get(
        "reason",
        ""
    )

    lead["score_reasons"] = " | ".join(
        score_reasons
    )

    lead["sales_argument_1"] = (
        arguments[0]
        if len(arguments) > 0
        else ""
    )

    lead["sales_argument_2"] = (
        arguments[1]
        if len(arguments) > 1
        else ""
    )

    lead["sales_argument_3"] = (
        arguments[2]
        if len(arguments) > 2
        else ""
    )

    return lead


# ============================================================
# HAUPTPROGRAMM
# ============================================================

def main():

    input_path = Path(
        INPUT_FILE
    )

    if not input_path.exists():

        print(
            f"FEHLER: {INPUT_FILE} wurde nicht gefunden."
        )

        return

    with open(
        INPUT_FILE,
        newline="",
        encoding="utf-8"
    ) as file:

        reader = csv.DictReader(
            file
        )

        leads = list(
            reader
        )

    if not leads:

        print(
            "Keine Leads gefunden."
        )

        return

    print()
    print("=" * 60)
    print("LEAD ANALYZER")
    print("=" * 60)

    print(
        f"{len(leads)} Leads gefunden."
    )

    analyzed_leads = []

    for index, lead in enumerate(
        leads,
        start=1
    ):

        company_name = lead.get(
            "company_name",
            "Unbekannt"
        )

        print()
        print("=" * 60)

        print(
            f"LEAD {index}/{len(leads)}"
        )

        print(
            company_name
        )

        print("=" * 60)

        try:

            analyzed = analyze_lead(
                lead
            )

            analyzed_leads.append(
                analyzed
            )

            print(
                f"Score:       {analyzed['lead_score']}/100"
            )

            print(
                f"Priorität:   {analyzed['priority']}"
            )

            print(
                f"Potenzial:   {analyzed['potential']}"
            )

            print(
                f"E-Mail:      {analyzed.get('email', '')}"
            )

            print(
                f"Website:     {analyzed.get('website', '')}"
            )

            print()
            print(
                f"Begründung: {analyzed['ai_reason']}"
            )

            print()
            print(
                "Verkaufsargumente:"
            )

            print(
                f"1. {analyzed['sales_argument_1']}"
            )

            print(
                f"2. {analyzed['sales_argument_2']}"
            )

            print(
                f"3. {analyzed['sales_argument_3']}"
            )

        except Exception as error:

            print(
                f"FEHLER bei {company_name}: {error}"
            )

            analyzed_leads.append(
                lead
            )

    # ========================================================
    # CSV SPALTEN
    # ========================================================

    fieldnames = list(
        analyzed_leads[0].keys()
    )

    additional_fields = [
        "lead_score",
        "priority",
        "potential",
        "score_reasons",
        "ai_reason",
        "sales_argument_1",
        "sales_argument_2",
        "sales_argument_3",
    ]

    for field in additional_fields:

        if field not in fieldnames:
            fieldnames.append(
                field
            )

    # ========================================================
    # SPEICHERN
    # ========================================================

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

        writer.writerows(
            analyzed_leads
        )

    print()
    print("=" * 60)
    print(
        "ANALYSE ABGESCHLOSSEN"
    )
    print("=" * 60)

    print(
        f"{len(analyzed_leads)} Leads verarbeitet."
    )

    print(
        f"Ausgabe: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()


