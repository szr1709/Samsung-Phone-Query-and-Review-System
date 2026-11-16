
from urllib.parse import urljoin
import re

import requests
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.connection import engine
from database.models import Base, Phone


LISTING_URL = "https://www.gsmarena.com/samsung-phones-9.php"
# Keep this project run focused on the requested 10–15 devices.
MAX_PHONES = 15
# Samsung models in GSMArena's 2025 most-searched list, in rank order.
POPULAR_MODEL_NAMES = (
    "Galaxy S25 Ultra",
    "Galaxy A56",
    "Galaxy S25",
    "Galaxy A36",
    "Galaxy A16",
    "Galaxy S25 Edge",
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_listing(url: str = LISTING_URL) -> str:
    """Return page HTML, with a useful error for blocked or failed requests."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (402, 403, 429):
            raise RuntimeError(
                f"GSMArena refused the request (HTTP {status}). "
                "The site may require browser verification or may be rate-limiting requests."
            ) from exc
        raise RuntimeError(f"Could not retrieve GSMArena page: {exc}") from exc
    return response.text


def parse_phones(html: str, page_url: str = LISTING_URL) -> list[dict[str, str | None]]:
    """Extract model names and listing URLs/images from a GSMArena listing page."""
    soup = BeautifulSoup(html, "html.parser")
    listing = soup.select_one(".makers")
    if listing is None:
        raise ValueError(
            "Could not find the GSMArena phone list (.makers). "
            "The page markup may have changed or a block page was returned."
        )

    phones: list[dict[str, str | None]] = []
    for anchor in listing.select("ul li a[href]"):
        name_node = anchor.select_one("strong span") or anchor.select_one("strong")
        if name_node is None:
            continue
        model_name = name_node.get_text(" ", strip=True)
        if not model_name:
            continue

        image = anchor.select_one("img")
        image_url = None
        if image is not None:
            image_url = image.get("src") or image.get("data-src")
            if image_url:
                image_url = urljoin(page_url, image_url)

        phones.append(
            {
                "model_name": model_name,
                "source_url": urljoin(page_url, anchor["href"]),
                "image_url": image_url,
            }
        )

    if not phones:
        raise ValueError("GSMArena page loaded, but no Samsung phone entries were found.")
    return phones


def save_phones(phones: list[dict[str, str | None]]) -> int:
    """Insert new models and refresh listing URLs/images for existing models."""
    Base.metadata.create_all(bind=engine)
    saved = 0
    with Session(engine) as session, session.begin():
        for item in phones:
            phone = session.execute(
                select(Phone).where(Phone.model_name == item["model_name"])
            ).scalar_one_or_none()
            if phone is None:
                phone = Phone(
                    model_name=item["model_name"],
                    brand="Samsung",
                    source_url=item["source_url"],
                    image_url=item["image_url"],
                )
                session.add(phone)
            else:
                phone.source_url = item["source_url"]
                phone.image_url = item["image_url"]
            saved += 1
    return saved


def select_focus_phones(phones: list[dict[str, str | None]]) -> list[dict[str, str | None]]:
    """Prioritize popular models found on the page, then fill to 15 listings."""
    normalize = lambda name: re.sub(r"[^a-z0-9]+", "", name.lower().replace("samsung", ""))
    by_name = {normalize(phone["model_name"] or ""): phone for phone in phones}
    selected: list[dict[str, str | None]] = []
    selected_urls: set[str | None] = set()

    for popular_name in POPULAR_MODEL_NAMES:
        key = normalize(popular_name)
        match = by_name.get(key)
        if match and match["source_url"] not in selected_urls:
            selected.append(match)
            selected_urls.add(match["source_url"])

    for phone in phones:
        if phone["source_url"] not in selected_urls:
            selected.append(phone)
            selected_urls.add(phone["source_url"])
        if len(selected) >= MAX_PHONES:
            break
    return selected[:MAX_PHONES]


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        existing_count = session.query(Phone).count()
    if existing_count >= 10:
        print(
            f"Database already contains {existing_count} Samsung models (target: 10–15); "
            "skipping listing scrape."
        )
        return

    phones = select_focus_phones(parse_phones(fetch_listing()))
    if len(phones) < 10:
        raise RuntimeError(
            f"Only {len(phones)} phone listings were found; expected at least 10."
        )
    saved = save_phones(phones)
    print(f"Saved {saved} Samsung phone listings to the database.")


if __name__ == "__main__":
    main()
