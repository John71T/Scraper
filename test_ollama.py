import requests

url = "http://localhost:11434/api/generate"

lead = {
    "firma": "Muster Elektrotechnik GmbH",
    "branche": "Elektrotechnik",
    "stadt": "Hamburg",
    "website": "https://beispiel.de"
}

prompt = f"""
Du bist ein B2B-Lead-Analyst für eine Webdesign-Agentur.

Bewerte den folgenden Lead:

Firma: {lead["firma"]}
Branche: {lead["branche"]}
Stadt: {lead["stadt"]}
Website: {lead["website"]}

Bewerte den Lead auf einer Skala von 1 bis 10.

Berücksichtige:
- Wie interessant ist die Branche für eine Webdesign-Agentur?
- Wie wahrscheinlich ist ein Bedarf an einer modernen Website?
- Wie attraktiv könnte der Lead als Kunde sein?

Gib ausschließlich dieses Format zurück:

Score: X/10
Potenzial: HOCH/MITTEL/NIEDRIG
Begründung: [kurze Begründung]
"""

data = {
    "model": "llama3.1:8b",
    "prompt": prompt,
    "stream": False
}

response = requests.post(url, json=data)

print(response.json()["response"])
