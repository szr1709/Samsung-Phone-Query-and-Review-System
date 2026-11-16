
from datetime import datetime
from decimal import Decimal
import re
import time

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from database.connection import engine
from database.models import Phone, PhonePrice, PhoneSpecification
from scraper.gsmarena_scraper import HEADERS, MAX_PHONES

CURRENCY_SYMBOLS = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "₹": "INR",
    "৳": "BDT",
}


def fetch_phone_page(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def parse_specifications(html):
    soup = BeautifulSoup(html, "html.parser")
    specs_table = soup.select_one("#specs-list")

    if specs_table is None:
        print("Could not find specifications table.")
        return []

    specifications = []
    current_category = None

    for row in specs_table.select("tr"):
        category_tag = row.find("th")
        if category_tag is not None:
            current_category = category_tag.get_text(" ", strip=True)

        name_tag = row.select_one("td.ttl")
        value_tag = row.select_one("td.nfo")

        if current_category is None or name_tag is None or value_tag is None:
            continue

        spec_name = name_tag.get_text(" ", strip=True)
        spec_value = value_tag.get_text(" ", strip=True)

        if spec_name and spec_value:
            specifications.append({
                "category": current_category,
                "specification_name": spec_name,
                "specification_value": spec_value,
            })

    return specifications


def parse_prices(specifications):
    price_text = ""
    for spec in specifications:
        if spec["specification_name"].lower() == "price":
            price_text = spec["specification_value"]
            break

    prices = []
    pattern = r"([$€£₹৳]|USD|EUR|GBP|BDT|INR)\s*([\d,]+(?:\.\d{1,2})?)"
    matches = re.findall(pattern, price_text, re.IGNORECASE)

    for raw_currency, raw_amount in matches:
        currency = CURRENCY_SYMBOLS.get(raw_currency, raw_currency.upper())
        clean_amount = raw_amount.replace(",", "")
        prices.append({
            "currency": currency,
            "price": Decimal(clean_amount),
        })

    return prices


def parse_release_date(specifications):
    status_text = ""
    for spec in specifications:
        if spec["category"] == "Launch" and spec["specification_name"] == "Status":
            status_text = spec["specification_value"]
            break

    match = re.search(r"Released\s+(\d{4}),\s*([A-Za-z]+)\s+(\d{1,2})", status_text)
    if match:
        year, month, day = match.groups()
        date_string = f"{year} {month} {day}"
        return datetime.strptime(date_string, "%Y %B %d").date()

    return None


def save_phone_details(phone_id, source_url, specifications, prices):
    session = Session(engine)

    phone = session.get(Phone, phone_id)
    if phone is None:
        session.close()
        return

    release_date = parse_release_date(specifications)
    if release_date is not None:
        phone.release_date = release_date

    # Save or update specifications
    for spec in specifications:
        existing_spec = session.query(PhoneSpecification).filter_by(
            phone_id=phone_id,
            category=spec["category"],
            specification_name=spec["specification_name"],
        ).first()

        if existing_spec:
            existing_spec.specification_value = spec["specification_value"]
        else:
            new_spec = PhoneSpecification(
                phone_id=phone_id,
                category=spec["category"],
                specification_name=spec["specification_name"],
                specification_value=spec["specification_value"],
            )
            session.add(new_spec)

    # Save or update prices
    for item in prices:
        existing_price = session.query(PhonePrice).filter_by(
            phone_id=phone_id,
            currency=item["currency"],
            source=source_url,
        ).first()

        if existing_price:
            existing_price.price = item["price"]
        else:
            new_price = PhonePrice(
                phone_id=phone_id,
                price=item["price"],
                currency=item["currency"],
                source=source_url,
            )
            session.add(new_price)

    session.commit()
    session.close()


def run_specification_scraper():
    session = Session(engine)
    phones = (
        session.query(Phone)
        .filter(Phone.source_url.isnot(None))
        .order_by(Phone.id)
        .limit(MAX_PHONES)
        .all()
    )
    session.close()

    print(f"Found {len(phones)} phones to scrape.")

    for phone in phones:
        try:
            print(f"\nScraping: {phone.model_name} (ID: {phone.id})")
            html = fetch_phone_page(phone.source_url)
            specifications = parse_specifications(html)
            prices = parse_prices(specifications)

            save_phone_details(phone.id, phone.source_url, specifications, prices)
            print(f"Saved {len(specifications)} specs and {len(prices)} prices.")
        except Exception as error:
            print(f"Failed to scrape {phone.model_name}: {error}")

        time.sleep(3)

    print("\nScraping completed!")


if __name__ == "__main__":
    run_specification_scraper()
