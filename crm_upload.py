"""
crm_upload.py - Schickt eine gemappte CSV (siehe crm_export.py) per Bulk-Import
an Maurices Lead-Management-System: POST /api/v1/leads/import

Credentials stehen NICHT im Code, sondern kommen aus Umgebungsvariablen:
    CRM_BASE_URL   z.B. http://localhost:8080  (Default: http://localhost:8080)
    CRM_USER       z.B. admin
    CRM_PASSWORD   z.B. admin

Nutzung:
    CRM_USER=admin CRM_PASSWORD=admin python crm_upload.py crm_import.csv \
        --conflict-strategy SKIP

Bei erfolgreichem Upload (HTTP 2xx) werden die enthaltenen E-Mails in
--state-file (Default: crm_exported_state.json, siehe crm_export.py) vermerkt -
so exportiert crm_export.py sie beim naechsten Lauf nicht nochmal. Das ist der
Mechanismus, der dafuer sorgt, dass der Scraper/Export-Kreislauf ueber mehrere
Tage hinweg nur wirklich neue Leads zu Maurices CRM schickt.

Empfehlung: Erst manuell ein paar Test-Leads ueber die CRM-UI (Import/Export)
hochladen und Dedupe-/Conflict-Verhalten pruefen, bevor das hier automatisiert
per Cron o.ae. laeuft (siehe scraper-crm-integration-plan.md im Projekt).
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests

STATE_FILE_DEFAULT = "crm_exported_state.json"


def load_state(state_path):
    if not state_path.exists():
        return {"exported_emails": {}}

    try:
        with state_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("exported_emails", {})
        return data
    except Exception as error:
        print(f"WARNUNG: Konnte {state_path} nicht lesen ({error}) - starte mit leerem Stand.", file=sys.stderr)
        return {"exported_emails": {}}


def mark_as_exported(state_path, csv_path, conflict_strategy):
    state = load_state(state_path)

    now = datetime.now().isoformat()
    count = 0

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            email = (row.get("email") or "").strip().lower()

            if not email:
                continue

            state["exported_emails"][email] = {
                "company": row.get("company", ""),
                "uploaded_at": now,
                "conflict_strategy": conflict_strategy,
            }
            count += 1

    with state_path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_file")
    parser.add_argument(
        "--conflict-strategy",
        choices=["SKIP", "UPDATE", "FAIL"],
        default="SKIP",
        help="Default SKIP (sicherste Wahl, solange nicht mit Maurice abgestimmt)",
    )
    parser.add_argument("--base-url", default=os.environ.get("CRM_BASE_URL", "http://localhost:8080"))
    parser.add_argument(
        "--state-file",
        default=STATE_FILE_DEFAULT,
        help="Wohin erfolgreich hochgeladene E-Mails vermerkt werden (siehe crm_export.py)",
    )
    parser.add_argument(
        "--no-state-update",
        action="store_true",
        help="State-Datei NICHT aktualisieren (z.B. fuer einen Testlauf gegen eine Test-Instanz)",
    )
    args = parser.parse_args()

    user = os.environ.get("CRM_USER")
    password = os.environ.get("CRM_PASSWORD")

    if not user or not password:
        print("FEHLER: CRM_USER und CRM_PASSWORD als Umgebungsvariablen setzen.", file=sys.stderr)
        sys.exit(1)

    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        print(f"FEHLER: {csv_path} nicht gefunden.", file=sys.stderr)
        sys.exit(1)

    url = f"{args.base_url}/api/v1/leads/import"
    params = {"conflictStrategy": args.conflict_strategy}

    print(f"Importiere {csv_path} nach {url} (conflictStrategy={args.conflict_strategy}) ...")

    with csv_path.open("rb") as f:
        response = requests.post(
            url,
            params=params,
            auth=(user, password),
            files={"file": (csv_path.name, f, "text/csv")},
            timeout=30,
        )

    print(f"Status: {response.status_code}")
    print(response.text)

    if not response.ok:
        sys.exit(1)

    if not args.no_state_update:
        state_path = Path(args.state_file)
        count = mark_as_exported(state_path, csv_path, args.conflict_strategy)
        print()
        print(f"{count} E-Mail(s) in {state_path} als hochgeladen vermerkt.")


if __name__ == "__main__":
    main()
