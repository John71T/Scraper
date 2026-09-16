"""
crm_export.py - Mappt die angereicherten Scraper-Leads (leads_analyzed.csv) auf
das CSV-Importschema von Maurices Lead-Management-System
(POST /api/v1/leads/import, siehe scraper-crm-integration-plan.md im Projekt).

Zielspalten laut CRM-README:
  Pflicht:   title, firstName, lastName, email
  Optional:  phone, company, estimatedValue, assignedTo

Mit Maurice geklaert (2026-09-15): leere firstName/lastName werden vom Import
nicht akzeptiert, ein Platzhalter reicht (siehe FIRSTNAME_PLACEHOLDER unten).
Mit Maurice geklaert (2026-09-16): "title" soll Leistung (Branche/Gewerk)
und Firmenname enthalten, Format "<Branche> - <Firmenname>".

Verfolgt bereits erfolgreich hochgeladene Leads (siehe crm_upload.py) ueber
--state-file und nimmt sie bei einem erneuten Export NICHT wieder mit rein -
so bringt jeder Export/Upload-Zyklus nur echte neue Leads zu Maurices CRM,
auch wenn leads_analyzed.csv ueber mehrere Scraper-Laeufe hinweg waechst.

Nutzung:
    python crm_export.py [--input leads_analyzed.csv] [--output crm_import.csv]
    python crm_export.py --ignore-state   # alle exportieren, auch bereits hochgeladene
"""
import argparse
import csv
import json
import sys
from pathlib import Path

CRM_FIELDS = ["title", "firstName", "lastName", "email", "phone", "company", "estimatedValue", "assignedTo"]

# Mit Maurice geklaert (2026-09-15): Import verlangt immer einen Wert,
# leere firstName/lastName werden nicht akzeptiert. Deshalb Platzhalter,
# klar als solcher erkennbar statt einer erfundenen echten Person.
FIRSTNAME_PLACEHOLDER = "Ansprechpartner"
LASTNAME_PLACEHOLDER = "unbekannt"

STATE_FILE_DEFAULT = "crm_exported_state.json"


def load_exported_emails(state_path):
    if not state_path.exists():
        return set()

    try:
        with state_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("exported_emails", {}).keys())
    except Exception as error:
        print(f"WARNUNG: Konnte {state_path} nicht lesen ({error}) - behandle als leer.", file=sys.stderr)
        return set()


def map_row(row):
    category = row.get("category", "").strip()
    company_name = row.get("company_name", "").strip()

    # Mit Maurice geklaert (2026-09-16): title = Leistung (Branche/Gewerk) + Firmenname.
    if category and company_name:
        title = f"{category} - {company_name}"
    else:
        title = company_name or category

    return {
        "title": title,
        "firstName": FIRSTNAME_PLACEHOLDER,
        "lastName": LASTNAME_PLACEHOLDER,
        "email": row.get("email", "").strip(),
        "phone": row.get("phone", "").strip(),
        "company": company_name,
        # Platzhalter bis das CRM ein eigenes Scoring-Feld hat (siehe Integrationsplan)
        "estimatedValue": row.get("lead_score", "").strip(),
        "assignedTo": "",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", default="leads_analyzed.csv")
    parser.add_argument("--output", default="crm_import.csv")
    parser.add_argument(
        "--state-file",
        default=STATE_FILE_DEFAULT,
        help="Datei mit bereits hochgeladenen E-Mails (wird von crm_upload.py nach erfolgreichem Upload gepflegt)",
    )
    parser.add_argument(
        "--keep-no-email",
        action="store_true",
        help="Leads ohne E-Mail NICHT ueberspringen (Default: werden uebersprungen, da E-Mail Pflichtfeld + Dedupe-Key im CRM ist)",
    )
    parser.add_argument(
        "--ignore-state",
        action="store_true",
        help="Bereits hochgeladene Leads TROTZDEM wieder mit exportieren (z.B. fuer einen bewussten Re-Upload)",
    )
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)
    state_path = Path(args.state_file)

    if not in_path.exists():
        print(f"FEHLER: {in_path} nicht gefunden.", file=sys.stderr)
        sys.exit(1)

    already_exported = set() if args.ignore_state else load_exported_emails(state_path)

    skipped_no_email = 0
    skipped_already_exported = 0
    written = 0

    with in_path.open(newline="", encoding="utf-8") as f_in, \
         out_path.open("w", newline="", encoding="utf-8") as f_out:
        reader = csv.DictReader(f_in)
        writer = csv.DictWriter(f_out, fieldnames=CRM_FIELDS)
        writer.writeheader()

        for row in reader:
            mapped = map_row(row)

            if not args.keep_no_email and not mapped["email"]:
                skipped_no_email += 1
                continue

            if mapped["email"].lower() in already_exported:
                skipped_already_exported += 1
                continue

            writer.writerow(mapped)
            written += 1

    print(f"{written} Leads nach {out_path} exportiert.")

    if skipped_no_email:
        print(f"{skipped_no_email} Lead(s) ohne E-Mail uebersprungen (--keep-no-email zum Behalten).")

    if skipped_already_exported:
        print(f"{skipped_already_exported} Lead(s) bereits frueher erfolgreich hochgeladen, uebersprungen (--ignore-state fuer erneuten Export).")

    print()
    print(f"Hinweis: firstName/lastName sind Platzhalter ('{FIRSTNAME_PLACEHOLDER} {LASTNAME_PLACEHOLDER}'),")
    print("da der Scraper keine Kontaktperson erfasst (mit Maurice abgeklaert, 2026-09-15:")
    print("Import verlangt immer einen Wert, leere Felder werden nicht akzeptiert).")
    print()
    print(f"Nach einem ERFOLGREICHEN Upload (crm_upload.py) werden Leads automatisch in")
    print(f"{state_path} vermerkt, damit der naechste Export sie nicht nochmal mitschickt.")


if __name__ == "__main__":
    main()
