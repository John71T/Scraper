import csv
from datetime import datetime


OUTPUT_FILE = "leads.csv"

FIELDS = [
    "company_name",
    "category",
    "address",
    "city",
    "postal_code",
    "country",
    "phone",
    "email",
    "website",
    "google_rating",
    "review_count",
    "has_website",
    "website_quality",
    "lead_score",
    "priority",
    "source",
    "scraped_at",
]


def save_leads(leads):
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()

        for lead in leads:
            writer.writerow(lead)


def main():
    leads = [
        {
            "company_name": "Test Elektrotechnik",
            "category": "Elektriker",
            "address": "Teststraße 1",
            "city": "Hamburg",
            "postal_code": "20095",
            "country": "Deutschland",
            "phone": "+49 40 123456",
            "email": "",
            "website": "https://example.com",
            "google_rating": "4.7",
            "review_count": "86",
            "has_website": "true",
            "website_quality": "",
            "lead_score": "",
            "priority": "",
            "source": "test",
            "scraped_at": datetime.now().isoformat(),
        }
    ]

    save_leads(leads)

    print(f"{len(leads)} Lead(s) gespeichert in {OUTPUT_FILE}")


if __name__ == "__main__":
    main()