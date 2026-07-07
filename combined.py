from flask import Flask, request, render_template_string
import asyncio
from urllib.parse import quote, urlparse, parse_qs, urlencode, urlunparse
import re
from playwright.async_api import async_playwright

app = Flask(__name__)

async def scrape_booking(location, checkin, checkout):

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

        browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64)"
                "AppleWebKit/537.36"
                "(KHTML, like Gecko)"
                "Chrome/137.0.0.0 Safari/537.36"
            )
        )

        page = await context.new_page()

        try:

            await page.goto(
                search_url,
                wait_until="domcontentloaded",
                timeout=120000
            )

            body = (await page.locator("body").inner_text())[:2000]
            print(body)

            await page.wait_for_timeout(5000)

            print(page.url)
            print(await page.title())
            
            html = await page.content()
            print(len(html))

            try:
                cards = await page.locator(
                    '[data-testid="property-card-container"]'
                ).count()
                
                print("no. of cards : ",cards)
            except:
                await page.wait_for_selector(
                    '[data-testid="property-card"]',
                    timeout=30000
                )

            hotels = await page.query_selector_all(
                '[data-testid="property-card-container"]'
            )

            if not hotels:
                hotels = await page.query_selector_all(
                    '[data-testid="property-card"]'
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
'''
async def scrape_agoda(location, checkin, checkout, hotel_name=""):

    results = []
    user_hotel_name = hotel_name.strip()

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox"]
        )

        context = await browser.new_context(
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            viewport={"width": 1366, "height": 768}
        )

        page = await context.new_page()

        try:

            print("Opening Agoda...")

            await page.goto(
                "https://www.agoda.com",
                timeout=90000
            )

            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(10000)

            # Destination input
            destination = page.locator(
                'input[placeholder*="destination"]'
            ).first

            await destination.click()

            await destination.fill(location)

            await page.wait_for_timeout(3000)

            suggestion = page.locator("li").filter(
                has_text=location
            ).first

            await suggestion.click()

            print("Suggestion selected")

            await page.wait_for_timeout(2000)

            # Search
            search_btn = page.locator(
                '[data-element-name="search-button"]'
            )

            await search_btn.click()

            await page.wait_for_timeout(10000)
            html = await page.content()

            print("HTML Length:", len(html))

            print("After click URL:", page.url)

            print("Search clicked")

            await page.wait_for_url(
                "**/search?*",
                timeout=60000
            )

            print("TITLE:", await page.title())

            body = (await page.locator("body").inner_text()).lower()

            if "problem completing your search" in body:
                print("BOT BLOCKED")

            if "captcha" in body:
                print("CAPTCHA FOUND")

            if "robot" in body:
                print("ROBOT DETECTED")

            print("Results page loaded")
            print(page.url)

            url = page.url

            parts = urlparse(url)
            query = parse_qs(parts.query)

            query["checkIn"] = [checkin]
            query["checkOut"] = [checkout]

            new_url = urlunparse(
                (
                    parts.scheme,
                    parts.netloc,
                    parts.path,
                    parts.params,
                    urlencode(query, doseq=True),
                    parts.fragment
                )
            )
            new_url = new_url.replace("currency=USD", "currency=INR")
            new_url = new_url.replace("currencyCode=USD", "currencyCode=INR")
            new_url = new_url.replace("priceCur=USD", "priceCur=INR")

            print("Modified URL:")
            print(new_url)

            await page.goto(
                new_url,
                wait_until="networkidle",
                timeout=90000
            )

            await page.wait_for_timeout(10000)

            # Load more hotels by scrolling

            hotel_cards = await page.query_selector_all(
                '[data-element-name="property-card-content"]'
            )
            print("HOTEL CARDS FOUND:", len(hotel_cards))

            results = []

            for hotel in hotel_cards[:20]:

                try:
                    hotel_el = await hotel.query_selector(
                        'a[data-testid="property-name-link"] span'
                    )

                    if not hotel_el:
                        continue

                    hotel_name = (await hotel_el.inner_text()).strip()

                    hotel_location = "N/A"
                    price = "N/A"
                    rating = "N/A"
                    link = ""

                    location_el = await hotel.query_selector(
                        'button[data-selenium="area-city-text"]'
                    )

                    if location_el:
                        hotel_location = (await location_el.inner_text()).strip()

                    price_el = await hotel.query_selector(
                        '[data-selenium="display-price"]'
                    )

                    if price_el:
                        price = (await price_el.inner_text()).strip()

                    rating_el = await hotel.query_selector(
                        '[data-element-name="property-card-review"]'
                    )

                    if rating_el:
                        rating_text = await rating_el.inner_text()

                        match = re.search(r'(\d+\.\d+)', rating_text)

                        if match:
                            rating = match.group(1)

                    link_el = await hotel.query_selector(
                        'a[data-testid="property-name-link"]'
                    )

                    if link_el:
                        link = await link_el.get_attribute("href")

                        if link and link.startswith("/"):
                            link = "https://www.agoda.com" + link

                    results.append({
                        "hotel_name": hotel_name,
                        "location": hotel_location,
                        "price": price,
                        "rating": rating,
                        "link": link
                    })

                except Exception as e:
                    print("Parse Error:", e)

        except Exception as e:
            print("Agoda Error:", e)

        finally:

            await browser.close()

    return results

async def search_all(location, checkin, checkout):

    booking_task = scrape_booking(
        location,
        checkin,
        checkout
    )

    agoda_task = scrape_agoda(
        location,
        checkin,
        checkout
    )

    booking_results, agoda_results = await asyncio.gather(
        booking_task,
        agoda_task,
        return_exceptions=True
    )
    print("BOOKING COUNT:", len(booking_results))
    print("AGODA COUNT:", len(agoda_results))

    if isinstance(booking_results, Exception):
        print("Booking Error:", booking_results)
        booking_results = []

    if isinstance(agoda_results, Exception):
        print("Agoda Error:", agoda_results)
        agoda_results = []

    combined = booking_results + agoda_results

    def rating_value(h):
        try:
            return float(h["rating"])
        except:
            return 0

    combined.sort(
        key=rating_value,
        reverse=True
    )

    return combined
'''

@app.route("/")
def home():

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Booking Hotel Search</title>

        <style>

            body{
                font-family:Arial;
                background:#f4f6f9;
                padding:40px;
            }

            .container{
                max-width:700px;
                margin:auto;
                background:white;
                padding:30px;
                border-radius:12px;
                box-shadow:0 2px 15px rgba(0,0,0,.1);
            }

            h2{
                text-align:center;
                color:#0071c2;
            }

            input{
                width:100%;
                padding:12px;
                margin-top:8px;
                margin-bottom:20px;
                border:1px solid #ccc;
                border-radius:6px;
                box-sizing:border-box;
            }

            button{
                width:100%;
                padding:12px;
                background:#0071c2;
                color:white;
                border:none;
                border-radius:6px;
                cursor:pointer;
                font-size:16px;
            }

            button:hover{
                background:#005ea6;
            }

        </style>

    </head>

    <body>

        <div class="container">

            <h2>Hotel Search</h2>

            <form action="/search" method="GET">

                <label>Location</label>
                <input
                    type="text"
                    name="location"
                    placeholder="Enter city"
                    required
                >

                <label>Check-in Date</label>
                <input
                    type="date"
                    name="checkin"
                    required
                >

                <label>Check-out Date</label>
                <input
                    type="date"
                    name="checkout"
                    required
                >

                <button type="submit">
                    Search Hotels
                </button>

            </form>

        </div>

    </body>
    </html>
    """)

@app.route("/search")
def search_hotels():

    location = request.args.get("location")
    checkin = request.args.get("checkin")
    checkout = request.args.get("checkout")

    if not location or not checkin or not checkout:
        return "location, checkin and checkout are required"

    hotels = asyncio.run(
        scrape_booking(
            location,
            checkin,
            checkout
        )
    )

    html = f"""
    <!DOCTYPE html>
    <html>

    <head>

        <title>Hotel Results</title>

        <style>

            body{{
                font-family:Arial;
                background:#f4f6f9;
                padding:30px;
            }}

            h2{{
                color:#0071c2;
            }}

            .hotel{{
                background:white;
                padding:20px;
                margin-bottom:20px;
                border-radius:10px;
                box-shadow:0 2px 10px rgba(0,0,0,.1);
            }}

            .btn{{
                display:inline-block;
                background:#0071c2;
                color:white;
                padding:10px 15px;
                border-radius:6px;
                text-decoration:none;
            }}

        </style>

    </head>

    <body>

        <h2>Hotels Found: {len(hotels)}</h2>

        <p>
            <a href="/" class="btn">
                New Search
            </a>
        </p>
    """

    if len(hotels) == 0:

        html += """
        <div class="hotel">
            <h3>No hotels found.</h3>
        </div>
        """

    for hotel in hotels:

        html += f"""

        <div class="hotel">

            <h3>{hotel['hotel_name']}</h3>

            <p>
                <b>Location:</b>
                {hotel['location']}
            </p>

            <p>
                <b>Price:</b>
                {hotel['price']}
            </p>

            <p>
                <b>Rating:</b>
                {hotel['rating']}
            </p>

            <p>
                <a
                    class="btn"
                    href="{hotel['link']}"
                    target="_blank"
                >
                    View Hotel
                </a>
            </p>

        </div>

        """

    html += """
    </body>
    </html>
    """

    return html


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=1000,
        debug=True,
        use_reloader=False
    )
