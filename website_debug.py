from playwright.sync_api import sync_playwright


COMPANY_URL = "https://www.google.com/maps/search/Elektro+Rodin+Hamburg"


with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=False
    )

    page = browser.new_page()

    page.goto(
        COMPANY_URL,
        wait_until="domcontentloaded"
    )

    page.wait_for_timeout(5000)

    # Falls Consent erscheint
    if "consent.google.com" in page.url:

        print("Consent erkannt.")

        input(
            "Consent bestätigen und ENTER drücken..."
        )

    # ==================================================
    # ERSTES ERGEBNIS ÖFFNEN
    # ==================================================

    links = page.locator(
        'a[href*="/maps/place/"]'
    )

    print(
        "Firmen gefunden:",
        links.count()
    )

    if links.count() == 0:

        print(
            "Keine Firma gefunden."
        )

        input("ENTER zum Beenden...")

        browser.close()

        exit()

    links.first.click()

    page.wait_for_timeout(4000)

    print()
    print("Firma geöffnet.")
    print("URL:")
    print(page.url)

    # ==================================================
    # ALLE WEBSITE-ELEMENTE
    # ==================================================

    website_elements = page.locator(
        '[aria-label*="Website"], '
        '[data-value="Website"]'
    )

    count = website_elements.count()

    print()
    print(
        "Website-Elemente gefunden:",
        count
    )

    print()
    print("=" * 70)

    for i in range(count):

        element = website_elements.nth(i)

        try:

            print()
            print(
                f"ELEMENT {i}"
            )

            print(
                "TAG:",
                element.evaluate(
                    "(el) => el.tagName"
                )
            )

            print(
                "TEXT:",
                repr(element.inner_text())
            )

            print(
                "ARIA:",
                element.get_attribute(
                    "aria-label"
                )
            )

            print(
                "HREF:",
                element.get_attribute(
                    "href"
                )
            )

            print(
                "DATA-VALUE:",
                element.get_attribute(
                    "data-value"
                )
            )

            print(
                "HTML:"
            )

            print(
                element.evaluate(
                    "(el) => el.outerHTML"
                )
            )

        except Exception as error:

            print(
                "FEHLER:",
                error
            )

    print()
    print("=" * 70)

    input(
        "\nENTER zum Beenden..."
    )

    browser.close()