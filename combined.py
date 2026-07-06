import brotli
import os
import tarfile
import subprocess
import json
import asyncio
import re
from urllib.parse import quote, urlparse, parse_qs, urlencode, urlunparse
from playwright.async_api import async_playwright
import platform
from flask import Flask, request, render_template_string

app = Flask(__name__)
def extract_tar_br(source, destination):

    if os.path.exists(destination):
        return

    tar_file = destination + ".tar"

    with open(source, "rb") as f:
        data = brotli.decompress(f.read())

    with open(tar_file, "wb") as f:
        f.write(data)

    with tarfile.open(tar_file) as tar:
        tar.extractall(destination)

async def scrape_booking(location, checkin, checkout):

    from urllib.request import urlopen

    print(
        "Public IP:",
        urlopen("https://api.ipify.org", timeout=10)
            .read()
            .decode()
    )

    results = []

    search_url = (
        "https://www.booking.com/searchresults.en-gb.html"
        f"?ss={quote(location)}"
        f"&checkin={checkin}"
        f"&checkout={checkout}"
        "&group_adults=2"
        "&group_children=0"
        "&no_rooms=1"
        "&selected_currency=INR"
    )

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        proc = browser._impl_obj._connection._transport._proc

        #print("returncode =", proc.returncode)

        browser_process = browser._impl_obj._connection._transport._proc

        #print("PID:",browser_process.pid)

        #print("Browser connected:", browser.is_connected())

        await asyncio.sleep(2)

        if os.path.exists("/tmp/chrome.log"):
            print(open("/tmp/chrome.log").read())

        print(
            "Return code after 2 sec:",
            browser_process.returncode
        )

        print(
            "Browser connected after 2 sec:",
            browser.is_connected()
        )

        context = await browser.new_context(
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            viewport={"width": 1366, "height": 768},
            java_script_enabled=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/149.0.0.0 Safari/537.36"
            )
        )

        print(
            "Connected before new_context:",
            browser.is_connected()
        )

        print(
            "Return code before new_context:",
            browser_process.returncode
        )

        page = await context.new_page()

        await page.goto("https://api.ipify.org")
        #print("Public IP:", await page.text_content("body"))

        await page.goto("https://ifconfig.me/ip")
        #print("Public IP:", await page.text_content("body"))

        await page.goto("data:text/html,<script>document.body.innerHTML='JS Works';</script>")

        #print(await page.text_content("body"))

        await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => false
        });

        window.chrome = {
            runtime: {}
        };

        """)

        await page.set_extra_http_headers({
            "Accept-Language": "en-IN,en;q=0.9",
            "Upgrade-Insecure-Requests": "1"
        })

        try:
            '''

            response = await page.goto(
                search_url,
                wait_until="load",
                timeout=120000
            )
            '''
            page.on(
                "response",
                lambda r: (
                    print("WAF:", r.status, r.url)
                    if "awswaf" in r.url
                    else None
                )
            )

            response = await page.goto(search_url)

            #print(response.status)
            #print(response.headers.get("x-amzn-waf-action"))

            await page.wait_for_timeout(20000)
            #print(page.url)
            #print(await page.evaluate("typeof AwsWafIntegration"))
            print(await page.evaluate("""
            () => Object.keys(window.AwsWafIntegration || {})
            """))

            body = await page.content()

            #print(body[:5000])      # first 5000 chars
            #print("BODY LENGTH:", len(body))

            #print("TITLE:", await page.title())

            #print("READY:", await page.evaluate("document.readyState"))

            '''
            print(
                "BODY LENGTH:",
                await page.evaluate("document.body.innerHTML.length")
            )
            '''

            html = await page.content()
            #print(html[:3000])

            if "AwsWafIntegration" in body:
                print("AWS WAF CHALLENGE")

            if "challenge.js" in body:
                print("BOT BLOCKED")

            if "verify that you're not a robot" in body.lower():
                print("CAPTCHA PAGE")

            await page.wait_for_timeout(15000)

            print("URL:", page.url)
            print("TITLE:", await page.title())

            print(await page.locator("body").inner_text())

            await page.wait_for_timeout(30000)

            print("FINAL URL:", page.url)

            # Check what cookies were set
            # Existing cookies
            print("===== BEFORE getToken =====")
            cookies = await context.cookies()
            for c in cookies:
                print(c)

            # Call getToken()
            token = await page.evaluate("""
            async () => {
                try {
                    if (!window.AwsWafIntegration)
                        return "No AwsWafIntegration";

                    const result = await AwsWafIntegration.getToken();

                    return {
                        result: result,
                        cookie: document.cookie
                    };
                } catch(e) {
                    return {
                        error: e.toString()
                    };
                }
            }
            """)

            print(token)

            print("getToken() result:")
            print(token)
            print("getToken returned:", repr(token))

            # Give JS time to write cookies
            await page.wait_for_timeout(5000)

            # Fetch cookies AGAIN
            print("===== AFTER getToken =====")
            cookies = await context.cookies()

            for c in cookies:
                print(c)

            waf_cookie = next(
                (c for c in cookies if "waf" in c["name"].lower()),
                None
            )

            print("AWS WAF COOKIE:", waf_cookie)

            # Wait longer if needed
            await page.wait_for_timeout(60000)

            print("===== AFTER 60 SECONDS =====")
            for c in await context.cookies():
                print(c)

            cards = await page.locator(
                '[data-testid="property-card"]'
            ).count()

            print("booking CARDS:", cards)
            print(await page.locator("article").count())
            print(await page.locator("div").count())
            print(await page.locator("a").count())
            
            await page.wait_for_timeout(5000)

            try:
                await page.wait_for_selector(
                    '[data-testid="property-card"]',
                    timeout=50000
                )
            except:
                await page.wait_for_selector(
                    '[data-testid="property-card-container"]',
                    timeout=50000
                )

            hotels = await page.query_selector_all(
                '[data-testid="property-card"]'
            )
            
            if not hotels:
                hotels = await page.query_selector_all(
                    '[data-testid="property-card-container"]'
                )
            
            for hotel in hotels[:20]:

                try:
                    name = "N/A"
                    rating = "N/A"
                    price = "N/A"
                    location_text = "N/A"
                    link = ""

                    name_el = await hotel.query_selector(
                        '[data-testid="title"]'
                    )

                    if name_el:
                        name = (await name_el.inner_text()).strip()

                    rating_selectors = [
                        '[data-testid="review-score"]',
                        '[data-testid="review-score-right-component"]',
                        '[data-testid="review-score-component"]'
                    ]

                    for sel in rating_selectors:

                        rating_el = await hotel.query_selector(sel)

                        if rating_el:

                            txt = await rating_el.inner_text()

                            print("RATING TEXT:", txt)

                            match = re.search(r'\d+(\.\d+)?', txt)

                            if match:
                                rating = match.group()
                                break

                    price_el = await hotel.query_selector(
                        '[data-testid="price-and-discounted-price"]'
                    )

                    if price_el:
                        price = (await price_el.inner_text()).strip()

                    address_el = await hotel.query_selector(
                        '[data-testid="address"]'
                    )

                    if not address_el:
                        address_el = await hotel.query_selector(
                            '[data-testid="address-link"]'
                        )

                    if address_el:
                        location_text = (
                            await address_el.inner_text()
                        ).strip()

                    link_el = await hotel.query_selector("a")

                    if link_el:
                        href = await link_el.get_attribute("href")

                        if href:
                            if href.startswith("/"):
                                link = (
                                    "https://www.booking.com"
                                    + href
                                )
                            else:
                                link = href

                    results.append({
                        "hotel_name": name,
                        "location": location_text,
                        "price": price,
                        "rating": rating,
                        "link": link
                    })

                except Exception as e:
                    print("Hotel parse error:", e)

        except Exception as e:
            print("Scraper error:", e)

        finally:
            await browser.close()

    def rating_value(h):
        try:
            return float(h["rating"])
        except:
            return 0.0

    results.sort(key=rating_value, reverse=True)

    return results

@app.route("/")
def home():
    return """
    <h2>Hotel Search</h2>

    <form action="/search" method="get">
        <p>
            <input
                type="text"
                name="location"
                placeholder="Location"
                required>
        </p>

        <p>
            <input
                type="date"
                name="checkin"
                required>
        </p>

        <p>
            <input
                type="date"
                name="checkout"
                required>
        </p>

        <button type="submit">
            Search
        </button>
    </form>
    """


@app.route("/search")
def search():

    location = request.args.get("location")
    checkin = request.args.get("checkin")
    checkout = request.args.get("checkout")

    if not location or not checkin or not checkout:
        return "Missing parameters"

    hotels = asyncio.run(
        scrape_booking(
            location,
            checkin,
            checkout
        )
    )

    html = f"<h2>Hotels Found: {len(hotels)}</h2>"

    for hotel in hotels:

        html += f"""
        <hr>

        <h3>{hotel['hotel_name']}</h3>

        <p><b>Location:</b> {hotel['location']}</p>

        <p><b>Price:</b> {hotel['price']}</p>

        <p><b>Rating:</b> {hotel['rating']}</p>

        <a href="{hotel['link']}" target="_blank">
            View Hotel
        </a>
        """

    return html


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=1000,
        debug=True,
        use_reloader=False
    )
