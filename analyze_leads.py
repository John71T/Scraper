import csv
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1:8b"


def analyze_lead(lead):
    prompt = f"""
Du bist ein B2B-Lead-Analyst für eine Webdesign-Agentur.

Analysiere diesen Lead:

Firma: {lead["Firma"]}
Branche: {lead["branche"]}
Stadt: {lead["stadt"]}
Website: {lead["website"]}

Bewerte ausschließlich anhand der vorhandenen Informationen.

Gib exakt dieses Format zurück:

Score: X/10
Potenzial: HOCH/MITTEL/NIEDRIG
Begründung: [kurze Begründung]

Wichtig:
- Erfinde keine Informationen.
- Behaupte nicht, dass eine Website schlecht oder veraltet ist, wenn du sie nicht analysiert hast.
- Wenn Informationen fehlen, sage das ausdrücklich.
"""

    data = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False
    }

    response = requests.post(OLLAMA_URL, json=data)
    response.raise_for_status()

    return response.json()["response"]


with open("leads.csv", newline="", encoding="utf-8") as file:
    reader = csv.DictReader(file)

    for lead in reader:
        print("\n" + "=" * 50)
        print(f"lead:{lead['Firma']}")
        print("=" * 50)

        result = analyze_lead(lead)

        print(result)



