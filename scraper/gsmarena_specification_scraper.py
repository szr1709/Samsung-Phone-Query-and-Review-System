
from datetime import date, datetime
from decimal import Decimal
import re
import time

import requests
from bs4 import BeautifulSoup
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from database.connection import engine
from database.models import Phone, PhonePrice, PhoneSpecification


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_PHONES_PER_RUN = 15
RELEASE_PATTERN = re.compile(
    r"Released\s+(\d{4}),\s*([A-Za-z]+)\s+(\d{1,2})",
    re.IGNORECASE,
)
PRICE_PATTERN = re.compile(
    r"(?:(?P<currency>USD|EUR|GBP|BDT|INR|CAD|AUD|JPY|CNY|[$€£₹৳])"
    r"[\s\u00a0\u2009\u202f]*"
    r"(?P<amount>\d[\d,]*(?:\.\d{1,2})?)"
    r"|(?P<amount_suffix>\d[\d,]*(?:\.\d{1,2})?)"
    r"[\s\u00a0\u2009\u202f]*"
    r"(?P<currency_suffix>USD|EUR|GBP|BDT|INR|CAD|AUD|JPY|CNY))",
    re.IGNORECASE,
)

CURRENCY_CODES = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "₹": "INR",
    "৳": "BDT",
}


def fetch_phone_page(url: str) -> str:
    """Download an individual phone's GSMArena detail page."""

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

    except requests.RequestException as exc:
        raise RuntimeError(
            f"Could not retrieve phone page: {exc}"
        ) from exc

    return response.text


def parse_specifications(html: str) -> list[dict[str, str]]:
    """Extract specification categories, names and values."""

    soup = BeautifulSoup(html, "html.parser")

    specs_table = soup.select_one("#specs-list")

    if specs_table is None:
        raise ValueError(
            "Could not find specifications section. "
            "GSMArena page structure may have changed."
        )

    specifications = []
    current_category = None

    for row in specs_table.select("tr"):

        # Identify specification category
        category_node = row.select_one("th")

        if category_node:
            current_category = category_node.get_text(
                " ", strip=True
            )
            continue

        # Identify specification name
        name_node = row.select_one("td.ttl")

        # Identify specification value
        value_node = row.select_one("td.nfo")

        if not name_node or not value_node:
            continue

        if not current_category:
            continue

        specification_name = name_node.get_text(
            " ", strip=True
        )

        specification_value = value_node.get_text(
            " ", strip=True
        )

        if not specification_name or not specification_value:
            continue

        specifications.append({
            "category": current_category,
            "specification_name": specification_name,
            "specification_value": specification_value,
        })

    if not specifications:
        raise ValueError("No specifications were extracted.")

    return specifications


def parse_prices(html: str) -> list[dict[str, str | Decimal]]:
    """Extract explicit currency/amount pairs from the GSMArena Price row."""
    soup = BeautifulSoup(html, "html.parser")
    for row in soup.select("#specs-list tr"):
        name = row.select_one("td.ttl")
        value = row.select_one("td.nfo")
        if not name or not value or name.get_text(" ", strip=True).lower() != "price":
            continue

        prices = []
        for match in PRICE_PATTERN.finditer(value.get_text(" ", strip=True)):
            currency = (match.group("currency") or match.group("currency_suffix")).upper()
            currency = CURRENCY_CODES.get(currency, currency)
            raw_amount = match.group("amount") or match.group("amount_suffix")
            amount = Decimal(raw_amount.replace(",", ""))
            prices.append({"currency": currency, "price": amount})
        return prices
    return []


def save_prices(
    phone_id: int,
    source_url: str,
    prices: list[dict[str, str | Decimal]],
) -> int:
    """Save or refresh the price observation for each currency and source."""
    with Session(engine) as session, session.begin():
        for item in prices:
            existing = session.execute(
                select(PhonePrice).where(
                    PhonePrice.phone_id == phone_id,
                    PhonePrice.currency == item["currency"],
                    PhonePrice.source == source_url,
                )
            ).scalar_one_or_none()
            if existing:
                existing.price = item["price"]
                existing.checked_at = func.now()
            else:
                session.add(
                    PhonePrice(
                        phone_id=phone_id,
                        price=item["price"],
                        currency=item["currency"],
                        source=source_url,
                    )
                )
    return len(prices)


def parse_release_date(specifications: list[dict[str, str]]) -> date | None:
    """Extract the release date from the Launch -> Status specification if present."""
    status = next(
        (
            spec["specification_value"]
            for spec in specifications
            if spec["category"] == "Launch" and spec["specification_name"] == "Status"
        ),
        None,
    )
    match = RELEASE_PATTERN.search(status or "")
    if not match:
        return None
    year, month, day = match.groups()
    return datetime.strptime(f"{year} {month} {day}", "%Y %B %d").date()


def save_specifications(
    phone_id: int,
    specifications: list[dict[str, str]]
) -> tuple[int, int]:
    """Insert new specifications, update existing ones, and sync release_date."""

    inserted = 0
    updated = 0
    release_date = parse_release_date(specifications)

    with Session(engine) as session, session.begin():

        phone = session.get(Phone, phone_id)

        if phone is None:
            raise ValueError(f"Phone ID {phone_id} not found.")

        if release_date is not None:
            phone.release_date = release_date
        phone.updated_at = func.now()

        for spec in specifications:

            existing = session.execute(
                select(PhoneSpecification).where(
                    PhoneSpecification.phone_id == phone_id,
                    PhoneSpecification.category == spec["category"],
                    PhoneSpecification.specification_name
                    == spec["specification_name"]
                )
            ).scalar_one_or_none()

            if existing:
                existing.specification_value = (
                    spec["specification_value"]
                )
                updated += 1

            else:
                new_spec = PhoneSpecification(
                    phone_id=phone_id,
                    category=spec["category"],
                    specification_name=spec["specification_name"],
                    specification_value=spec["specification_value"]
                )

                session.add(new_spec)
                inserted += 1

    return inserted, updated


def main() -> None:
    with Session(engine) as session:
        phones = session.execute(
            select(
                Phone.id,
                Phone.model_name,
                Phone.source_url,
            )
            .where(Phone.source_url.isnot(None))
            .order_by(Phone.id)
            .limit(MAX_PHONES_PER_RUN)
        ).all()

    print(f"Found {len(phones)} phones to scrape.")

    for phone_id, model_name, phone_url in phones:

        try:
            print(f"\nScraping: {model_name} (ID: {phone_id})")

            html = fetch_phone_page(phone_url)

            specifications = parse_specifications(html)
            prices = parse_prices(html)

            inserted, updated = save_specifications(
                phone_id,
                specifications
            )
            saved_prices = save_prices(phone_id, phone_url, prices)

            print(f"Extracted: {len(specifications)}")
            print(f"Inserted: {inserted}")
            print(f"Updated: {updated}")
            print(f"Prices saved: {saved_prices}")
            print("Completed successfully!")

        except Exception as exc:
            print(f"Failed: {model_name}")
            print(f"Reason: {exc}")

        time.sleep(3)

    print("\nScraping batch completed!")


if __name__ == "__main__":
    main()
