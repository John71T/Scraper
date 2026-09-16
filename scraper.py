import csv
import json
import os
import re
from datetime import datetime
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


# ============================================================
# EINSTELLUNGEN
# ============================================================

# Mehrere Suchbegriffe (Branche x Ort) statt einer einzelnen Stadt/Branche.
# Wird in HAUPTPROGRAMM unten der Reihe nach durchlaufen; SEARCH/CATEGORY/CITY
# werden pro Kombination neu gesetzt (siehe run_one_search()).
SEARCH_TRADES = [
    "Elektriker",
    "Sanitaer Heizung Klima",
    "Dachdecker",
    "Maler Lackierer",
    "Tischler Schreiner",
    "Zimmerer",
    "Fliesenleger",
    "Garten- und Landschaftsbau",
    "Maurer Betonbauer",
    "Trockenbauer",
    "Metallbauer Schlosser",
    "Glaser",
]

# 25-km-Radius um Alfeld (Leine), Hildesheim und Hannover, angenaehert ueber
# Landkreis Hildesheim + Region Hannover (siehe scraper-crm-integration-plan.md
# im Projekt bzw. CLAUDE.md). Grobe Naeherung aus offiziellen Gemeindelisten,
# nicht einzeln geodaetisch nachgemessen - bei Bedarf Orte ergaenzen/entfernen.
SEARCH_LOCATIONS = [
    # Landkreis Hildesheim
    "Alfeld (Leine)", "Algermissen", "Bad Salzdetfurth", "Bockenem",
    "Diekholzen", "Elze", "Freden (Leine)", "Giesen", "Harsum", "Hildesheim",
    "Holle", "Lamspringe", "Nordstemmen", "Sarstedt", "Schellerten",
    "Sibbesse", "Soehlde", "Duingen", "Eime", "Gronau (Leine)",
    # Region Hannover
    "Barsinghausen", "Burgdorf", "Burgwedel", "Garbsen", "Gehrden",
    "Hannover", "Hemmingen", "Isernhagen", "Laatzen", "Langenhagen",
    "Lehrte", "Neustadt am Ruebenberge", "Pattensen", "Ronnenberg", "Seelze",
    "Sehnde", "Springe", "Uetze", "Wedemark", "Wennigsen (Deister)",
    "Wunstorf",
]

CATEGORY = ""   # wird pro Suchlauf neu gesetzt, siehe HAUPTPROGRAMM
CITY = ""       # wird pro Suchlauf neu gesetzt
SEARCH = ""     # wird pro Suchlauf neu gesetzt
COUNTRY = "Deutschland"

# Ziel: so viele NEUE Leads insgesamt pro Pipeline-Durchlauf (ueber alle
# Branche x Ort Kombinationen hinweg), nicht pro einzelner Suche.
TARGET_NEW_LEADS = 100

# Obergrenze neuer Leads PRO Suchkombination, damit keine einzelne Kombination
# den ganzen Lauf dominiert und jede Kombination ungefaehr gleich viel Zeit kostet.
MAX_LEADS_PER_SEARCH = 10

# Nach wie vielen komplett erfolglosen Kombinationen (0 neue Leads) in Folge
# wird der Lauf abgebrochen, statt die ganze Liste erfolglos durchzuscrollen.
MAX_CONSECUTIVE_EMPTY = 15

OUTPUT_FILE = "leads_clean.csv"
STATE_FILE = "scraper_state.json"

# Dedup / Scroll-Einstellungen
MAX_SCROLL_ATTEMPTS = 40      # Sicherheitslimit, damit die Suche nicht endlos scrollt
SCROLL_WAIT_MS = 2000         # Wartezeit nach jedem Scroll, bis neue Ergebnisse nachladen
STAGNANT_ROUNDS_LIMIT = 3     # Nach so vielen Scrolls ohne neue Treffer gilt die Liste als am Ende


# ============================================================
# HILFSFUNKTIONEN
# ============================================================

def clean_text(value):
    if not value:
        return ""

    value = value.replace("", "")
    value = value.replace("", "")
    value = value.replace("", "")
    value = value.replace("", "")

    return " ".join(value.split()).strip()


def safe_text(locator):
    try:
        if locator.count() > 0:
            return clean_text(locator.first.inner_text())
    except Exception:
        pass

    return ""


def safe_attribute(locator, attribute):
    try:
        if locator.count() > 0:
            return locator.first.get_attribute(attribute) or ""
    except Exception:
        pass

    return ""


# ============================================================
# DEDUP GEGEN FRUEHERE LAEUFE
# ============================================================

def normalize_key(name, address):
    combined = f"{name}{address}".lower()
    combined = re.sub(r"\W+", "", combined)
    return combined


def absolutize_maps_url(href):
    if not href:
        return ""

    if href.startswith("/"):
        return "https://www.google.com" + href

    return href


def load_known_leads(filepath):
    known_urls = set()
    known_keys = set()

    if not os.path.exists(filepath):
        return known_urls, known_keys

    try:
        with open(filepath, "r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for row in reader:
                url = (row.get("maps_url") or "").strip()

                if url:
                    known_urls.add(url)

                key = normalize_key(
                    row.get("company_name") or "",
                    row.get("address") or ""
                )

                if key:
                    known_keys.add(key)

    except Exception as error:
        print(f"WARNUNG: Konnte {filepath} nicht fuer Dedup-Abgleich lesen: {error}")

    return known_urls, known_keys


# ============================================================
# URL-VALIDIERUNG
# ============================================================

SOCIAL_DOMAINS = {
    "instagram.com": "instagram",
    "facebook.com": "facebook",
    "fb.com": "facebook",
    "tiktok.com": "tiktok",
    "youtube.com": "youtube",
    "linkedin.com": "linkedin",
    "twitter.com": "twitter",
    "x.com": "twitter",
}


BLOCKED_DOMAINS = [
    "google.com",
    "google.de",
    "googleusercontent.com",
    "gstatic.com",
    "googleadservices.com",
]


def normalize_url(url):
    if not url:
        return ""

    url = url.strip()

    if url.startswith("//"):
        return "https:" + url

    return url


def get_domain(url):
    try:
        parsed = urlparse(url)

        domain = parsed.netloc.lower()

        if domain.startswith("www."):
            domain = domain[4:]

        return domain

    except Exception:
        return ""


def is_google_url(url):
    lower = url.lower()

    if url.startswith("/aclk"):
        return True

    return any(domain in lower for domain in BLOCKED_DOMAINS)


def detect_social_type(url):
    domain = get_domain(url)

    for social_domain, social_type in SOCIAL_DOMAINS.items():

        if (
            domain == social_domain
            or domain.endswith("." + social_domain)
        ):
            return social_type

    return ""


# Branchenverzeichnisse, die Google Maps manchmal statt einer echten
# Firmen-Website als "Website" verlinkt. Solche Links zaehlen NICHT als
# eigene Website (has_website bleibt false) und werden nicht fuer die
# E-Mail-Suche verwendet - sonst landet dort oft eine generische
# Verzeichnis-Kontakt-E-Mail, die sich mehrere Firmen teilen und die als
# CRM-Dedupe-Key (E-Mail) faelschlich Leads zusammenfuehren wuerde.
DIRECTORY_DOMAINS = {
    "elektrikerportal.com",
    "11880.com",
    "gelbeseiten.de",
    "dasoertliche.de",
    "meinestadt.de",
    "firmenwissen.de",
    "cylex.de",
    "cylex-deutschland.de",
    "branchenbuch24.de",
    "wlw.de",
    "kompass.com",
    "yelp.de",
    "goyellow.de",
    "stadtbranchenbuch.com",
    "firmenverzeichnis.org",
    "unternehmensregister.de",
}


def is_directory_domain(url):
    domain = get_domain(url)

    return any(
        domain == directory_domain or domain.endswith("." + directory_domain)
        for directory_domain in DIRECTORY_DOMAINS
    )


# ============================================================
# WEBSITE AUS GOOGLE MAPS
# ============================================================

def extract_urls(page, company_name):

    result = {
        "website": "",
        "instagram": "",
        "facebook": "",
        "tiktok": "",
        "youtube": "",
        "linkedin": "",
    }

    candidates = []

    selectors = [
        'a[data-item-id="authority"]',
        'a[data-value="Website"]',
        f'a[aria-label="Zur Website von {company_name}"]',
        f'a[aria-label*="Website von {company_name}"]',
    ]

    for selector in selectors:

        elements = page.locator(selector)

        for i in range(elements.count()):

            try:

                href = elements.nth(i).get_attribute("href")

                if href:
                    candidates.append(href)

            except Exception:
                continue

    unique_candidates = []

    for url in candidates:

        url = normalize_url(url)

        if url and url not in unique_candidates:
            unique_candidates.append(url)

    for url in unique_candidates:

        if not url:
            continue

        if is_google_url(url):
            continue

        if not (
            url.startswith("http://")
            or url.startswith("https://")
        ):
            continue

        social_type = detect_social_type(url)

        if social_type:

            if social_type in result and not result[social_type]:
                result[social_type] = url

            continue

        if is_directory_domain(url):
            continue

        if not result["website"]:
            result["website"] = url

    return result


# ============================================================
# E-MAIL ERKENNUNG
# ============================================================

EMAIL_PATTERN = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)


def clean_email(email):

    if not email:
        return ""

    email = email.strip()

    email = email.replace("mailto:", "")

    email = email.split("?")[0]

    return email.strip()


def valid_email(email):

    if not email:
        return False

    lower = email.lower()

    blocked = [
        "example.com",
        "example.org",
        "example.net",
        "sentry.io",
        "wixpress.com",
        "wordpress.com",
        "cloudflare.com",
    ]

    if any(domain in lower for domain in blocked):
        return False

    image_endings = [
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".svg",
    ]

    if any(lower.endswith(x) for x in image_endings):
        return False

    return bool(EMAIL_PATTERN.fullmatch(email))


def extract_emails_from_html(html):

    emails = []

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    # --------------------------------------------------------
    # MAILTO-LINKS
    # --------------------------------------------------------

    for link in soup.select('a[href^="mailto:"]'):

        href = link.get(
            "href",
            ""
        )

        email = clean_email(href)

        if valid_email(email):

            if email not in emails:
                emails.append(email)

    # --------------------------------------------------------
    # SICHTBARER TEXT
    # --------------------------------------------------------

    text = soup.get_text(
        " ",
        strip=True
    )

    matches = EMAIL_PATTERN.findall(
        text
    )

    for email in matches:

        email = clean_email(email)

        if valid_email(email):

            if email not in emails:
                emails.append(email)

    return emails


def find_internal_pages(html, base_url):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    pages = []

    keywords = [
        "kontakt",
        "contact",
        "impressum",
        "imprint",
        "ueber-uns",
        "über-uns",
    ]

    base_domain = get_domain(
        base_url
    )

    for link in soup.find_all(
        "a",
        href=True
    ):

        href = link.get(
            "href",
            ""
        )

        text = link.get_text(
            " ",
            strip=True
        ).lower()

        href_lower = href.lower()

        if not any(
            keyword in href_lower
            or keyword in text
            for keyword in keywords
        ):
            continue

        full_url = urljoin(
            base_url,
            href
        )

        if get_domain(full_url) != base_domain:
            continue

        if full_url not in pages:
            pages.append(full_url)

    return pages


def extract_email_from_website(website):

    if not website:
        return ""

    print(
        f"Suche E-Mail auf: {website}"
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/139.0 Safari/537.36"
        )
    }

    try:

        response = requests.get(
            website,
            headers=headers,
            timeout=10,
            allow_redirects=True
        )

        if response.status_code >= 400:
            return ""

    except requests.RequestException:

        return ""

    # --------------------------------------------------------
    # STARTSEITE
    # --------------------------------------------------------

    emails = extract_emails_from_html(
        response.text
    )

    if emails:
        return emails[0]

    # --------------------------------------------------------
    # KONTAKT / IMPRESSUM SUCHEN
    # --------------------------------------------------------

    pages = find_internal_pages(
        response.text,
        response.url
    )

    # Maximal 5 Unterseiten prüfen
    for page_url in pages[:5]:

        print(
            f"Prüfe: {page_url}"
        )

        try:

            sub_response = requests.get(
                page_url,
                headers=headers,
                timeout=10,
                allow_redirects=True
            )

            if sub_response.status_code >= 400:
                continue

            emails = extract_emails_from_html(
                sub_response.text
            )

            if emails:
                return emails[0]

        except requests.RequestException:
            continue

    return ""


# ============================================================
# ADRESSE
# ============================================================

def extract_address(page):

    selectors = [
        '[data-item-id="address"]',
        '[data-item-id^="address"]',
        'button[aria-label^="Adresse:"]',
    ]

    for selector in selectors:

        element = page.locator(
            selector
        )

        if element.count() == 0:
            continue

        text = safe_text(
            element
        )

        if text:
            return text

        aria = safe_attribute(
            element,
            "aria-label"
        )

        if aria:

            aria = re.sub(
                r"^Adresse:\s*",
                "",
                aria,
                flags=re.IGNORECASE
            )

            return clean_text(
                aria
            )

    return ""


# ============================================================
# TELEFON
# ============================================================

def extract_phone(page):

    selectors = [
        '[data-item-id^="phone:tel:"]',
        'button[data-item-id^="phone"]',
        'button[aria-label^="Telefon:"]',
    ]

    for selector in selectors:

        element = page.locator(
            selector
        )

        if element.count() == 0:
            continue

        aria = safe_attribute(
            element,
            "aria-label"
        )

        if aria:

            aria = re.sub(
                r"^Telefon:\s*",
                "",
                aria,
                flags=re.IGNORECASE
            )

            phone = clean_text(
                aria
            )

            if phone:
                return phone

        text = safe_text(
            element
        )

        if text:
            return text

    return ""


# ============================================================
# RATING
# ============================================================

def extract_rating(page):

    rating = ""
    review_count = ""

    candidates = page.locator(
        '[aria-label*="Sterne"]'
    )

    for i in range(
        candidates.count()
    ):

        try:

            aria = candidates.nth(
                i
            ).get_attribute(
                "aria-label"
            )

            if not aria:
                continue

            rating_match = re.search(
                r"([0-5][,.][0-9])",
                aria
            )

            review_match = re.search(
                r"([\d.]+)\s+(?:Rezension|Rezensionen|Bewertung|Bewertungen)",
                aria,
                re.IGNORECASE
            )

            if rating_match:

                rating = rating_match.group(
                    1
                ).replace(
                    ",",
                    "."
                )

            if review_match:

                review_count = review_match.group(
                    1
                ).replace(
                    ".",
                    ""
                )

            if rating:
                return rating, review_count

        except Exception:
            continue

    try:

        main = page.locator(
            "main"
        )

        if main.count() > 0:

            text = main.first.inner_text()

        else:
            text = ""

        match = re.search(
            r"([0-5],[0-9])\s*\(([\d.]+)\)",
            text
        )

        if match:

            rating = match.group(
                1
            ).replace(
                ",",
                "."
            )

            review_count = match.group(
                2
            ).replace(
                ".",
                ""
            )

    except Exception:
        pass

    return rating, review_count


# ============================================================
# FIRMENNAME
# ============================================================

def extract_opened_company_name(page):

    headings = page.locator(
        "h1"
    )

    for i in range(
        headings.count()
    ):

        try:

            text = clean_text(
                headings.nth(
                    i
                ).inner_text()
            )

            if text:
                return text

        except Exception:
            continue

    return ""


# ============================================================
# EINEN LEAD EXTRAHIEREN
# ============================================================

def extract_lead(
    page,
    expected_name,
    maps_url
):

    page.wait_for_timeout(
        3000
    )

    opened_name = extract_opened_company_name(
        page
    )

    print(
        f"Erwartete Firma: {expected_name}"
    )

    print(
        f"Geöffnetes Profil: {opened_name}"
    )

    if opened_name:

        expected_simple = re.sub(
            r"\W+",
            "",
            expected_name.lower()
        )

        opened_simple = re.sub(
            r"\W+",
            "",
            opened_name.lower()
        )

        if (
            expected_simple
            and opened_simple
            and expected_simple not in opened_simple
            and opened_simple not in expected_simple
        ):

            print(
                "Profilname stimmt nicht mit Suchergebnis überein."
            )

            return None

    company_name = (
        opened_name
        or expected_name
    )

    address = extract_address(
        page
    )

    phone = extract_phone(
        page
    )

    rating, review_count = extract_rating(
        page
    )

    urls = extract_urls(
        page,
        company_name
    )

    website = urls[
        "website"
    ]

    # ========================================================
    # E-MAIL SUCHEN
    # ========================================================

    email = ""

    if website:

        email = extract_email_from_website(
            website
        )

    # ========================================================
    # AUSGABE
    # ========================================================

    print()
    print(
        "EXTRAHIERTER LEAD"
    )

    print("=" * 60)

    print(
        f"Firma:       {company_name}"
    )

    print(
        f"Bewertung:   {rating}"
    )

    print(
        f"Bewertungen: {review_count}"
    )

    print(
        f"Adresse:     {address}"
    )

    print(
        f"Telefon:     {phone}"
    )

    print(
        f"Website:     {website}"
    )

    print(
        f"E-Mail:      {email}"
    )

    print(
        f"Instagram:   {urls['instagram']}"
    )

    print("=" * 60)

    return {
        "company_name": company_name,
        "category": CATEGORY,
        "address": address,
        "city": CITY,
        "postal_code": "",
        "country": COUNTRY,
        "phone": phone,

        "email": email,

        "website": website,

        "instagram": urls["instagram"],
        "facebook": urls["facebook"],
        "tiktok": urls["tiktok"],
        "youtube": urls["youtube"],
        "linkedin": urls["linkedin"],

        "google_rating": rating,
        "review_count": review_count,

        "has_website": (
            "true"
            if website
            else "false"
        ),

        "website_quality": "",
        "lead_score": "",
        "priority": "",

        "source": "Google Maps",

        "scraped_at": datetime.now().isoformat(),

        "maps_url": maps_url,
    }


# ============================================================
# EINZELNE SUCHE (EINE BRANCHE x ORT KOMBINATION) AUSFUEHREN
# ============================================================

def run_one_search(page, search_term, category, city, known_urls, known_keys, max_new, fieldnames):
    """
    Fuehrt eine einzelne Google-Maps-Suche aus (Suchfeld fuellen, scrollen,
    Firmen oeffnen und extrahieren) und haengt neu gefundene, noch unbekannte
    Leads sofort an OUTPUT_FILE an.

    known_urls / known_keys werden in-place erweitert, damit spaetere
    Kombinationen im selben Lauf dieselben Firmen nicht erneut sammeln.

    Erwartet, dass 'page' bereits auf https://www.google.com/maps steht und
    der Google-Consent bereits bestaetigt wurde (siehe HAUPTPROGRAMM unten).

    Gibt die Anzahl neu geschriebener Leads zurueck.
    """

    global CATEGORY, CITY, SEARCH
    CATEGORY = category
    CITY = city
    SEARCH = search_term

    search_box = page.locator('input[name="q"]')

    search_box.wait_for(state="visible", timeout=20000)

    search_box.fill("")
    search_box.fill(search_term)
    search_box.press("Enter")

    print()
    print(f"Suche: {search_term}")

    page.wait_for_timeout(7000)

    print()
    print("Suche nach Firmen (scrollt bei Bedarf, ueberspringt bereits bekannte Leads)...")

    companies = []
    seen_urls = set()

    scroll_attempts = 0
    stagnant_rounds = 0
    last_link_count = 0

    while len(companies) < max_new and scroll_attempts <= MAX_SCROLL_ATTEMPTS:

        links = page.locator('a[href*="/maps/place/"]')
        link_count = links.count()

        for i in range(link_count):
            try:
                link = links.nth(i)
                name = clean_text(link.inner_text())
                href = link.get_attribute("href")

                if not name or not href:
                    continue

                href = absolutize_maps_url(href)

                if href in seen_urls:
                    continue

                seen_urls.add(href)

                if href in known_urls:
                    continue

                companies.append({"name": name, "url": href})

                if len(companies) >= max_new:
                    break

            except Exception:
                continue

        if len(companies) >= max_new:
            break

        if link_count == last_link_count:
            stagnant_rounds += 1

            if stagnant_rounds >= STAGNANT_ROUNDS_LIMIT:
                print("Keine neuen Ergebnisse mehr beim Scrollen - Ende der Liste erreicht.")
                break
        else:
            stagnant_rounds = 0

        last_link_count = link_count

        feed = page.locator('div[role="feed"]')

        try:
            if feed.count() > 0:
                feed.first.evaluate("el => el.scrollBy(0, el.scrollHeight)")
            else:
                page.mouse.wheel(0, 2000)
        except Exception:
            page.mouse.wheel(0, 2000)

        page.wait_for_timeout(SCROLL_WAIT_MS)

        scroll_attempts += 1

    print()
    print(f"{len(companies)} neue Firmen gefunden (bereits bekannte uebersprungen):")

    for index, company in enumerate(companies, start=1):
        print(f"{index}. {company['name']}")

    leads = []

    for index, company in enumerate(companies, start=1):
        print()
        print("=" * 60)
        print(f"LEAD {index}/{len(companies)}")
        print(company["name"])
        print("=" * 60)

        try:
            maps_url = company["url"]

            if maps_url.startswith("/"):
                maps_url = "https://www.google.com" + maps_url

            page.goto(maps_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            lead = extract_lead(page, company["name"], maps_url)

            if lead:
                leads.append(lead)

        except Exception as error:
            print(f"FEHLER: {error}")

    unique_leads = []

    for lead in leads:
        key = normalize_key(lead["company_name"], lead["address"])

        if key and key in known_keys:
            print(f"Ueberspringe Duplikat (Name+Adresse bereits bekannt): {lead['company_name']}")
            continue

        if key:
            known_keys.add(key)

        if lead["maps_url"]:
            known_urls.add(lead["maps_url"])

        unique_leads.append(lead)

    file_exists = (
        os.path.exists(OUTPUT_FILE)
        and os.path.getsize(OUTPUT_FILE) > 0
    )

    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerows(unique_leads)

    print()
    print(f"{len(unique_leads)} neue Leads fuer '{search_term}' angehaengt.")

    return len(unique_leads)


# ============================================================
# ZUSTAND (WELCHE KOMBINATION ZULETZT DRAN WAR)
# ============================================================

def load_state(filepath):
    if not os.path.exists(filepath):
        return {"combo_index": 0}

    try:
        with open(filepath, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {"combo_index": 0}


def save_state(filepath, state):
    try:
        with open(filepath, "w", encoding="utf-8") as file:
            json.dump(state, file)
    except Exception as error:
        print(f"WARNUNG: Konnte {filepath} nicht schreiben: {error}")


# ============================================================
# HAUPTPROGRAMM
# ============================================================

with sync_playwright() as p:

    print("Lade bereits bekannte Leads fuer Dedup-Abgleich...")

    known_urls, known_keys = load_known_leads(OUTPUT_FILE)

    print(f"{len(known_urls)} bereits bekannte Leads gefunden (werden uebersprungen).")

    combos = [
        (trade, ort)
        for trade in SEARCH_TRADES
        for ort in SEARCH_LOCATIONS
    ]

    state = load_state(STATE_FILE)
    start_index = state.get("combo_index", 0) % len(combos)

    fieldnames = [
        "company_name",
        "category",
        "address",
        "city",
        "postal_code",
        "country",
        "phone",

        "email",

        "website",

        "instagram",
        "facebook",
        "tiktok",
        "youtube",
        "linkedin",

        "google_rating",
        "review_count",

        "has_website",
        "website_quality",
        "lead_score",
        "priority",

        "source",
        "scraped_at",

        "maps_url",
    ]

    browser = p.chromium.launch(
        headless=False
    )

    page = browser.new_page(
        viewport={
            "width": 1440,
            "height": 1000
        }
    )

    print(
        "Google Maps wird geöffnet..."
    )

    page.goto(
        "https://www.google.com/maps",
        wait_until="domcontentloaded"
    )

    page.wait_for_timeout(
        3000
    )

    # ========================================================
    # CONSENT
    # ========================================================

    if "consent.google.com" in page.url:

        print()
        print(
            "Google-Consent erkannt."
        )

        input(
            "Consent bestätigen und danach ENTER drücken..."
        )

        page.wait_for_timeout(
            3000
        )

    # ========================================================
    # KOMBINATIONEN DURCHLAUFEN, BIS TARGET_NEW_LEADS ERREICHT
    # ========================================================

    total_new = 0
    consecutive_empty = 0
    combos_tried = 0

    print()
    print(f"Ziel: {TARGET_NEW_LEADS} neue Leads ueber bis zu {len(combos)} Branche x Ort Kombinationen.")
    print(f"Start bei Kombination #{start_index + 1} (gemerkt aus vorherigem Lauf, {STATE_FILE}).")

    for offset in range(len(combos)):

        if total_new >= TARGET_NEW_LEADS:
            print()
            print(f"Ziel von {TARGET_NEW_LEADS} neuen Leads erreicht.")
            break

        if consecutive_empty >= MAX_CONSECUTIVE_EMPTY:
            print()
            print(f"{MAX_CONSECUTIVE_EMPTY} Kombinationen in Folge ohne neue Leads - Lauf wird beendet.")
            break

        combo_index = (start_index + offset) % len(combos)
        trade, ort = combos[combo_index]
        search_term = f"{trade} {ort}"

        print()
        print("#" * 60)
        print(f"KOMBINATION {offset + 1}/{len(combos)} (Index {combo_index}): {search_term}")
        print("#" * 60)

        remaining = TARGET_NEW_LEADS - total_new
        max_new_this_search = min(MAX_LEADS_PER_SEARCH, remaining)

        try:
            new_count = run_one_search(
                page,
                search_term,
                trade,
                ort,
                known_urls,
                known_keys,
                max_new_this_search,
                fieldnames,
            )
        except Exception as error:
            print(f"FEHLER bei Kombination '{search_term}': {error}")
            new_count = 0

        total_new += new_count
        combos_tried += 1

        if new_count == 0:
            consecutive_empty += 1
        else:
            consecutive_empty = 0

        # Fortschritt sofort merken, damit der naechste Lauf hier weitermacht,
        # statt immer wieder von vorne (bereits ausgeschoepfte Kombinationen).
        next_index = (combo_index + 1) % len(combos)
        save_state(STATE_FILE, {"combo_index": next_index})

    print()
    print("=" * 60)
    print("SCRAPING ABGESCHLOSSEN")
    print("=" * 60)

    print(
        f"{total_new} neue Leads insgesamt angehaengt (aus {combos_tried} Kombination(en))."
    )

    print(
        f"Datei: {OUTPUT_FILE}"
    )

    input(
        "\nENTER zum Beenden..."
    )

    browser.close()
