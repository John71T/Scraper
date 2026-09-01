import csv
import re
from datetime import datetime
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


# ============================================================
# EINSTELLUNGEN
# ============================================================

SEARCH = "Elektriker Hamburg"
CATEGORY = "Elektriker"
CITY = "Hamburg"
COUNTRY = "Deutschland"

MAX_LEADS = 10

OUTPUT_FILE = "leads_clean.csv"


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
# HAUPTPROGRAMM
# ============================================================

with sync_playwright() as p:

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
    # SUCHE
    # ========================================================

    search_box = page.locator(
        'input[name="q"]'
    )

    search_box.wait_for(
        state="visible",
        timeout=20000
    )

    search_box.fill(
        SEARCH
    )

    search_box.press(
        "Enter"
    )

    print()
    print(
        f"Suche: {SEARCH}"
    )

    page.wait_for_timeout(
        7000
    )

    # ========================================================
    # FIRMEN + MAPS URLS SAMMELN
    # ========================================================

    links = page.locator(
        'a[href*="/maps/place/"]'
    )

    companies = []

    seen_urls = set()

    for i in range(
        links.count()
    ):

        try:

            link = links.nth(
                i
            )

            name = clean_text(
                link.inner_text()
            )

            href = link.get_attribute(
                "href"
            )

            if not name or not href:
                continue

            if href in seen_urls:
                continue

            seen_urls.add(
                href
            )

            companies.append({
                "name": name,
                "url": href
            })

            if len(companies) >= MAX_LEADS:
                break

        except Exception:
            continue

    print()
    print(
        f"{len(companies)} Firmen gefunden:"
    )

    for index, company in enumerate(
        companies,
        start=1
    ):

        print(
            f"{index}. {company['name']}"
        )

    # ========================================================
    # LEADS EXTRAHIEREN
    # ========================================================

    leads = []

    for index, company in enumerate(
        companies,
        start=1
    ):

        print()
        print("=" * 60)

        print(
            f"LEAD {index}/{len(companies)}"
        )

        print(
            company["name"]
        )

        print("=" * 60)

        try:

            maps_url = company[
                "url"
            ]

            if maps_url.startswith(
                "/"
            ):

                maps_url = (
                    "https://www.google.com"
                    + maps_url
                )

            page.goto(
                maps_url,
                wait_until="domcontentloaded",
                timeout=30000
            )

            page.wait_for_timeout(
                3000
            )

            lead = extract_lead(
                page,
                company["name"],
                maps_url
            )

            if lead:
                leads.append(
                    lead
                )

        except Exception as error:

            print(
                f"FEHLER: {error}"
            )

    # ========================================================
    # CSV
    # ========================================================

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
            leads
        )

    print()
    print("=" * 60)
    print(
        "SCRAPING ABGESCHLOSSEN"
    )
    print("=" * 60)

    print(
        f"{len(leads)} Leads gespeichert."
    )

    print(
        f"Datei: {OUTPUT_FILE}"
    )

    input(
        "\nENTER zum Beenden..."
    )

    browser.close()