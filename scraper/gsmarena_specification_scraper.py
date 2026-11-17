
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
    "US$": "USD",
    "€": "EUR",
    "£": "GBP",
    "₹": "INR",
    "৳": "BDT",
    "RS": "INR",
    "RS.": "INR",
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

    if not price_text:
        return []

    prices = []

    currency_pattern = r"US\$|[$€£₹৳]|USD|EUR|GBP|BDT|INR|Rs\.?"

    amount_pattern = r"\d[\d,]*(?:\.\d{1,2})?"

    pattern = (
        rf"(?:"
        rf"({currency_pattern})\s*({amount_pattern})"
        rf"(?:\s*[-–]\s*({amount_pattern}))?"
        rf"|"
        rf"({amount_pattern})"
        rf"(?:\s*[-–]\s*({amount_pattern}))?"
        rf"\s*({currency_pattern})"
        rf")"
    )

    matches = re.finditer(pattern, price_text, re.IGNORECASE)

    for match in matches:
        (
            currency_before,
            amount_before,
            range_before,
            amount_after,
            range_after,
            currency_after,
        ) = match.groups()

        raw_currency = currency_before or currency_after

        raw_amounts = [
            amount_before or amount_after,
            range_before or range_after,
        ]

        currency_key = raw_currency.upper()

        currency = CURRENCY_SYMBOLS.get(
            raw_currency,
            CURRENCY_SYMBOLS.get(
                currency_key,
                currency_key
            )
        )

        valid_amounts = [
            Decimal(amount.replace(",", ""))
            for amount in raw_amounts
            if amount is not None
        ]

        if not valid_amounts:
            continue

        prices.append({
            "currency": currency,
            "price": min(valid_amounts),
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

    try:
        phone = session.get(Phone, phone_id)

        if not phone:
            raise ValueError(f"Phone ID {phone_id} not found.")

        # Update the phone's source URL and release date.
        phone.source_url = source_url
        phone.release_date = parse_release_date(specifications)

        # Remove old specifications and prices for this phone.
        session.query(PhoneSpecification).filter_by(
            phone_id=phone_id
        ).delete()

        session.query(PhonePrice).filter_by(
            phone_id=phone_id
        ).delete()

        # Save specifications.
        for spec in specifications:
            new_spec = PhoneSpecification(
                phone_id=phone_id,
                category=spec["category"],
                specification_name=spec["specification_name"],
                specification_value=spec["specification_value"],
            )
            session.add(new_spec)

        # Save prices.
        for price in prices:
            new_price = PhonePrice(
                phone_id=phone_id,
                price=price["price"],
                currency=price["currency"],
                source=source_url,
            )
            session.add(new_price)

        session.commit()

        print(
            f"Saved {len(specifications)} specifications "
            f"and {len(prices)} prices for phone ID {phone_id}."
        )

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


def run_specification_scraper():
    session = Session(engine)
    phones = (
        session.query(Phone)
        .filter(
            Phone.source_url.isnot(None),
            ~Phone.model_name.ilike("%Tab%"),
            ~Phone.model_name.ilike("%Watch%")
        )
        .order_by(Phone.id)
        .limit(15)
        .all()
    )

    session.close()

    print(f"Found {len(phones)} Samsung smartphones needing specifications.")

    for phone in phones:
        try:
            print(f"\nScraping: {phone.model_name} (ID: {phone.id})")

            html = fetch_phone_page(phone.source_url)
            specifications = parse_specifications(html)
            prices = parse_prices(specifications)

            save_phone_details(
                phone.id,
                phone.source_url,
                specifications,
                prices
            )

            print(
                f"Saved {len(specifications)} specs "
                f"and {len(prices)} prices."
            )

        except Exception as error:
            print(f"Failed to scrape {phone.model_name}: {error}")

        time.sleep(3)

    print("\nScraping completed!")