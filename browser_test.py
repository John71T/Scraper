import re

from playwright.sync_api import sync_playwright


SEARCH = "Elektriker Hamburg"

COMPANY_NAME = "BEA Bergmann Elektro- u. Antennentechnik GmbH"


with sync_playwright() as p:

    browser = p.chromium.launch(headless=False)

    page = browser.new_page()

    # --------------------------------------------------
    # GOOGLE MAPS ÖFFNEN
    # --------------------------------------------------

    page.goto(
        "https://www.google.com/maps",
        wait_until="domcontentloaded"
    )

    page.wait_for_timeout(3000)

    # --------------------------------------------------
    # CONSENT
    # --------------------------------------------------

    if "consent.google.com" in page.url:

        print("Bitte Google-Consent einmal bestätigen.")

        input(
            "Wenn Google Maps sichtbar ist, ENTER drücken..."
        )

    page.wait_for_timeout(3000)

    # --------------------------------------------------
    # SUCHE
    # --------------------------------------------------

    search_box = page.locator(
        'input[name="q"]'
    )

    search_box.wait_for(
        state="visible",
        timeout=15000
    )

    search_box.fill(SEARCH)
    search_box.press("Enter")

    page.wait_for_timeout(7000)

    print("\nSuche abgeschlossen.")

    # --------------------------------------------------
    # FIRMA ÖFFNEN
    # --------------------------------------------------

    company = page.locator("a").filter(
        has_text=COMPANY_NAME
    ).first

    company.wait_for(
        state="visible",
        timeout=15000
    )

    print("Firma gefunden.")

    company.click()

    page.wait_for_timeout(4000)

    print("Firma geöffnet.")

    # --------------------------------------------------
    # SEITENTEXT
    # --------------------------------------------------

    text = page.locator("body").inner_text()

    # --------------------------------------------------
    # BEWERTUNG
    # --------------------------------------------------

    rating = ""

    review_count = ""

    rating_match = re.search(
        r"(\d,\d)\s*\((\d+)\)",
        text
    )

    if rating_match:

        rating = rating_match.group(1).replace(",", ".")
        review_count = rating_match.group(2)

    # --------------------------------------------------
    # TELEFON
    # --------------------------------------------------

    phone = ""

    phone_match = re.search(
        r"(?:\+49|0)\s*\d[\d\s\/-]{6,}",
        text
    )

    if phone_match:

        phone = phone_match.group(0).strip()

    # --------------------------------------------------
    # ADRESSE
    # --------------------------------------------------

    address = ""

    address_match = re.search(
        r"([A-ZÄÖÜ][^,\n]+ \d+[A-Za-z]?, \d{5} [A-ZÄÖÜa-zäöüß -]+)",
        text
    )

    if address_match:

        address = address_match.group(1).strip()

    # --------------------------------------------------
    # WEBSITE DIAGNOSE
    # --------------------------------------------------

    print("\n")
    print("=" * 60)
    print("WEBSITE-DIAGNOSE")
    print("=" * 60)

    # Alle Elemente untersuchen, deren Text "Website" enthält
    website_elements = page.locator(
        "text=Website"
    )

    print(
        f"Elemente mit 'Website' gefunden: "
        f"{website_elements.count()}"
    )

    for i in range(website_elements.count()):

        element = website_elements.nth(i)

        print("\nElement", i)

        print(
            "Tag:",
            element.evaluate(
                "(el) => el.tagName"
            )
        )

        print(
            "Text:",
            repr(element.inner_text())
        )

        print(
            "HTML:",
            element.evaluate(
                "(el) => el.outerHTML"
            )[:1000]
        )

        # Prüfen, ob das Element selbst oder ein Elternteil
        # einen Link enthält
        try:

            parent = element.locator("xpath=..")

            print(
                "Parent:",
                parent.evaluate(
                    "(el) => el.outerHTML"
                )[:1000]
            )

        except Exception:
            pass

    print("=" * 60)

    # --------------------------------------------------
    # LEAD AUSGABE
    # --------------------------------------------------

    print("\n")
    print("=" * 60)
    print("EXTRAHIERTER LEAD")
    print("=" * 60)

    print(f"Firma:             {COMPANY_NAME}")
    print(f"Bewertung:         {rating}")
    print(f"Bewertungen:       {review_count}")
    print(f"Adresse:           {address}")
    print(f"Telefon:           {phone}")

    print("=" * 60)

    input("\nENTER zum Beenden...")

    browser.close()
    