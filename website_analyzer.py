import csv
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse


INPUT_FILE = "leads.csv"


# ============================================================
# WEBSITE ABRUFEN
# ============================================================

def fetch_website(url):

    if not url:
        return None

    if not url.startswith("http"):
        url = "https://" + url

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/139.0 Safari/537.36"
        )
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=10,
            allow_redirects=True
        )

        return response

    except requests.RequestException as e:

        print(f"Website konnte nicht geladen werden: {e}")

        return None


# ============================================================
# SSL
# ============================================================

def check_https(url):

    return url.lower().startswith("https://")


# ============================================================
# TITLE
# ============================================================

def get_title(soup):

    if soup.title:

        return soup.title.get_text(
            " ",
            strip=True
        )

    return ""


# ============================================================
# META DESCRIPTION
# ============================================================

def get_meta_description(soup):

    meta = soup.find(
        "meta",
        attrs={"name": re.compile(
            "^description$",
            re.I
        )}
    )

    if meta:

        return meta.get("content", "").strip()

    return ""


# ============================================================
# H1
# ============================================================

def get_h1(soup):

    h1 = soup.find("h1")

    if h1:

        return h1.get_text(
            " ",
            strip=True
        )

    return ""


# ============================================================
# MOBILE META
# ============================================================

def has_viewport(soup):

    viewport = soup.find(
        "meta",
        attrs={
            "name": re.compile(
                "^viewport$",
                re.I
            )
        }
    )

    return viewport is not None


# ============================================================
# CONTACT INFORMATION
# ============================================================

def has_phone(text):

    pattern = r"(?:\+49|0)\s*[\d\s()/.-]{6,}"

    return bool(
        re.search(
            pattern,
            text
        )
    )


def has_email(text):

    pattern = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"

    return bool(
        re.search(
            pattern,
            text
        )
    )


# ============================================================
# SOCIAL MEDIA
# ============================================================

def detect_social_media(soup):

    platforms = {
        "instagram": False,
        "facebook": False,
        "linkedin": False,
        "youtube": False,
        "tiktok": False
    }

    links = soup.find_all("a")

    for link in links:

        href = link.get("href", "")

        href = href.lower()

        if "instagram.com" in href:
            platforms["instagram"] = True

        if "facebook.com" in href:
            platforms["facebook"] = True

        if "linkedin.com" in href:
            platforms["linkedin"] = True

        if "youtube.com" in href:
            platforms["youtube"] = True

        if "tiktok.com" in href:
            platforms["tiktok"] = True

    return platforms


# ============================================================
# LEGAL PAGES
# ============================================================

def detect_legal_pages(soup):

    text = soup.get_text(
        " ",
        strip=True
    ).lower()

    return {
        "impressum": (
            "impressum" in text
        ),

        "datenschutz": (
            "datenschutz" in text
        )
    }


# ============================================================
# WEBSITE ANALYSIEREN
# ============================================================

def analyze_website(url):

    print(f"\nAnalysiere: {url}")

    response = fetch_website(url)

    if not response:

        return {
            "website_status": "NICHT ERREICHBAR"
        }

    final_url = response.url

    status_code = response.status_code

    html = response.text

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    # Gesamter sichtbarer Text
    text = soup.get_text(
        " ",
        strip=True
    )

    title = get_title(soup)

    description = get_meta_description(
        soup
    )

    h1 = get_h1(soup)

    viewport = has_viewport(
        soup
    )

    phone = has_phone(
        text
    )

    email = has_email(
        text
    )

    social = detect_social_media(
        soup
    )

    legal = detect_legal_pages(
        soup
    )

    # ========================================================
    # SCORE
    # ========================================================

    score = 0

    if status_code == 200:
        score += 10

    if check_https(final_url):
        score += 10

    if title:
        score += 10

    if description:
        score += 10

    if h1:
        score += 10

    if viewport:
        score += 15

    if phone:
        score += 10

    if email:
        score += 5

    if legal["impressum"]:
        score += 5

    if legal["datenschutz"]:
        score += 5

    # Maximal 100
    score = min(score, 100)

    # ========================================================
    # QUALITÄT
    # ========================================================

    if score >= 80:

        quality = "HOCH"

    elif score >= 55:

        quality = "MITTEL"

    else:

        quality = "NIEDRIG"

    return {

        "website_status": "ERREICHBAR",

        "website_final_url": final_url,

        "website_http_status": status_code,

        "website_https": (
            "true"
            if check_https(final_url)
            else "false"
        ),

        "website_title": title,

        "website_meta_description": description,

        "website_h1": h1,

        "website_mobile_meta": (
            "true"
            if viewport
            else "false"
        ),

        "website_has_phone": (
            "true"
            if phone
            else "false"
        ),

        "website_has_email": (
            "true"
            if email
            else "false"
        ),

        "website_impressum": (
            "true"
            if legal["impressum"]
            else "false"
        ),

        "website_datenschutz": (
            "true"
            if legal["datenschutz"]
            else "false"
        ),

        "website_instagram": (
            "true"
            if social["instagram"]
            else "false"
        ),

        "website_facebook": (
            "true"
            if social["facebook"]
            else "false"
        ),

        "website_linkedin": (
            "true"
            if social["linkedin"]
            else "false"
        ),

        "website_youtube": (
            "true"
            if social["youtube"]
            else "false"
        ),

        "website_tiktok": (
            "true"
            if social["tiktok"]
            else "false"
        ),

        "website_score": score,

        "website_quality": quality
    }


# ============================================================
# CSV VERARBEITEN
# ============================================================

with open(
    INPUT_FILE,
    newline="",
    encoding="utf-8"
) as file:

    reader = csv.DictReader(file)

    leads = list(reader)


print(
    f"\n{len(leads)} Leads gefunden."
)

print("=" * 60)


# ============================================================
# LEADS ANALYSIEREN
# ============================================================

for index, lead in enumerate(
    leads,
    start=1
):

    company = lead.get(
        "company_name",
        ""
    )

    website = lead.get(
        "website",
        ""
    )

    print("\n")
    print("=" * 60)

    print(
        f"WEBSITE ANALYSE {index}/{len(leads)}"
    )

    print(
        f"Firma: {company}"
    )

    print("=" * 60)

    # Keine Website
    if not website:

        print(
            "Keine Website vorhanden."
        )

        lead["website_status"] = (
            "KEINE WEBSITE"
        )

        lead["website_quality"] = (
            "KEINE WEBSITE"
        )

        lead["website_score"] = "100"

        continue

    result = analyze_website(
        website
    )

    lead.update(result)

    print(
        f"\nStatus: "
        f"{result.get('website_status', '')}"
    )

    print(
        f"HTTPS: "
        f"{result.get('website_https', '')}"
    )

    print(
        f"Title: "
        f"{result.get('website_title', '')}"
    )

    print(
        f"H1: "
        f"{result.get('website_h1', '')}"
    )

    print(
        f"Mobile Meta: "
        f"{result.get('website_mobile_meta', '')}"
    )

    print(
        f"Telefon gefunden: "
        f"{result.get('website_has_phone', '')}"
    )

    print(
        f"E-Mail gefunden: "
        f"{result.get('website_has_email', '')}"
    )

    print(
        f"Impressum: "
        f"{result.get('website_impressum', '')}"
    )

    print(
        f"Datenschutz: "
        f"{result.get('website_datenschutz', '')}"
    )

    print(
        f"\nWEBSITE SCORE: "
        f"{result.get('website_score', '')}/100"
    )

    print(
        f"QUALITÄT: "
        f"{result.get('website_quality', '')}"
    )


# ============================================================
# CSV SPEICHERN
# ============================================================

fieldnames = list(leads[0].keys())


with open(
    INPUT_FILE,
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


print("\n")
print("=" * 60)
print("WEBSITE-ANALYSE ABGESCHLOSSEN")
print("=" * 60)

print(
    f"{len(leads)} Leads analysiert."
)

print(
    f"Ergebnisse gespeichert in: {INPUT_FILE}"
)