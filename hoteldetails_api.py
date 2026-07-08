from flask import Flask, request, render_template_string, jsonify
import asyncio
from urllib.parse import quote
import re
from playwright.async_api import async_playwright

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Booking Hotel Search</title>

    <style>
        body{
            font-family: Arial;
            max-width:1200px;
            margin:auto;
            padding:20px;
        }

        h2{
            color:#333;
        }

        input{
            width:300px;
            padding:10px;
            margin:5px;
        }

        button{
            padding:10px 20px;
            cursor:pointer;
        }

        .hotel{
            border:1px solid #ddd;
            border-radius:8px;
            padding:15px;
            margin-top:15px;
        }

        .loading{
            color:blue;
            font-weight:bold;
        }
    </style>
</head>

<body>

<h2>Booking Hotel Search</h2>

<form id="hotelForm">

    <input
        type="text"
        name="location"
        placeholder="Location"
        required>

    <br>

    <input
        type="text"
        name="hotel_name"
        placeholder="Hotel Name"
        required>

    <br>

    <input
        type="date"
        name="checkin"
        required>

    <br>

    <input
        type="date"
        name="checkout"
        required>

    <br><br>

    <button type="submit">
        Search Hotels
    </button>

</form>

<hr>

<div id="results"></div>

<script>

document.getElementById("hotelForm")
.addEventListener("submit", async function(e){

    e.preventDefault();

    const formData = new FormData(this);

    const params = new URLSearchParams({
        location: formData.get("location"),
        hotel_name: formData.get("hotel_name"),
        checkin: formData.get("checkin"),
        checkout: formData.get("checkout")
    });

    document.getElementById("results").innerHTML =
        "<p class='loading'>Loading hotels...</p>";

    let response = await fetch("/detail?" + params.toString());

    let data = await response.json();

    let html = "";

    if(data.length === 0){
        html = "<h3>No hotels found</h3>";
    }

    data.forEach(hotel=>{

    let roomsHtml = "";

    if(hotel.rooms && hotel.rooms.length > 0){

        roomsHtml += "<h4>Room Details</h4><ul>";

        hotel.rooms.forEach(room=>{

            roomsHtml += `
            <li>
                <b>${room.room_type}</b>
                - ${room.price}
            </li>
            `;
        });

        roomsHtml += "</ul>";

    } else {

        roomsHtml = "<p>No room details found</p>";
    }

    html += `
    <div class="hotel">

        <h3>${hotel.hotel_name}</h3>

        <p><b>Location:</b>
        ${hotel.location}</p>

        <p><b>Rating:</b>
        ${hotel.rating}</p>

        <p><b>Price:</b>
        ${hotel.price}</p>

        ${roomsHtml}

        <p>
            <a href="${hotel.link}"
               target="_blank">
               Open Hotel
            </a>
        </p>

    </div>
    `;
});

    document.getElementById("results").innerHTML = html;

});

</script>

</body>
</html>
"""

async def scrape_booking(location, hotel_name, checkin, checkout):

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
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
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

            await page.wait_for_timeout(5000)

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

            for hotel in hotels[:30]:

                try:
                    name = "N/A"
                    rating = "N/A"
                    price = "N/A"
                    location_text = "N/A"
                    link = ""
                    room_details = []
                    seen_rooms = set()

                    name_el = await hotel.query_selector(
                        '[data-testid="title"]'
                    )

                    if name_el:
                        name = (await name_el.inner_text()).strip()

                    search_words = hotel_name.lower().split()

                    if hotel_name:
                        if not all(
                            word in name.lower()
                            for word in search_words
                        ):
                            continue

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

                    if hotel_name and link:

                        try:

                            detail_page = await context.new_page()

                            await detail_page.goto(
                                link,
                                timeout=90000,
                                wait_until="domcontentloaded"
                            )

                            try:

                                address_selectors = [
                                    '[data-node_tt_id="location_score_tooltip"]',
                                    '.hp_address_subtitle',
                                    '[data-testid="PropertyHeaderAddressDesktop-wrapper"]'
                                ]

                                for sel in address_selectors:

                                    el = await detail_page.query_selector(sel)

                                    if el:

                                        address = (
                                            await el.inner_text()
                                        ).strip()

                                        # Keep address only up to "India"
                                        match = re.search(
                                            r"^(.*?India)",
                                            address,
                                            flags=re.IGNORECASE | re.DOTALL
                                        )

                                        if match:
                                            hotel_location = match.group(1).strip()
                                        else:
                                            hotel_location = address

                                        print("Location:", hotel_location)

                                        break

                            except Exception as e:

                                print("Address error:", e)

                            await detail_page.wait_for_timeout(
                                6000
                            )

                            room_rows = await detail_page.query_selector_all(
                                "tr"
                            )

                            print(
                                "Rows found:",
                                len(room_rows)
                            )

                            for row in room_rows:

                                try:

                                    txt = (
                                        await row.inner_text()
                                    ).strip()

                                    if not txt:
                                        continue

                                    lines = [
                                        x.strip()
                                        for x in txt.split("\n")
                                        if x.strip()
                                    ]

                                    if len(lines) >= 2:

                                        room_type = ""

                                        for line in lines:

                                            if "Rs." in line:
                                                continue

                                            if re.fullmatch(r"\d+", line):
                                                continue

                                            if "Max. people" in line:
                                                continue

                                            room_type = line
                                            break

                                        price_match = re.search(
                                            r'[₹₹]\s*[\d,]+',
                                            txt
                                        )

                                        if not price_match:
                                            price_match = re.search(
                                                r'[\d,]+\s*₹',
                                                txt
                                            )

                                        if price_match:
                                            room_price = price_match.group().strip()
                                        else:
                                            room_price = "N/A"

                                        key = f"{room_type}_{room_price}"

                                        if key not in seen_rooms:

                                            seen_rooms.add(key)

                                            room_details.append({
                                                "room_type": room_type,
                                                "price": room_price
                                            })

                                except:
                                    pass

                            await detail_page.close()

                        except Exception as e:

                            print("Room scrape error:",e)

                    results.append({
                        "hotel_name": name,
                        "location": hotel_location,
                        "price": price,
                        "rating": rating,
                        "link": link,
                        "rooms": room_details
                    })

                except Exception as e:
                    print("Hotel parse error:", e)

        except Exception as e:

            print("Main scraper error:", e)

        finally:
            await browser.close()

    return results


@app.route("/")
def home():
    return render_template_string(HTML)


@app.route("/detail", methods=["GET"])
def detail():

    location = request.args.get("location")
    hotel_name = request.args.get("hotel_name", "")
    checkin = request.args.get("checkin")
    checkout = request.args.get("checkout")

    results = asyncio.run(
        scrape_booking(
            location,
            hotel_name,
            checkin,
            checkout
        )
    )

    return jsonify(results)


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=8000,
        debug=True,
        use_reloader=False
    )
