
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from database.connection import engine
from database.models import Base, Phone

LISTING_URL = "https://www.gsmarena.com/samsung-phones-9.php"
MAX_PHONES = 15
EXCLUDED_PREFIXES = (
    "galaxy tab",
    "galaxy watch"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}


def fetch_listing(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def parse_phones(html):
    soup = BeautifulSoup(html, "html.parser")
    listing = soup.select_one(".makers")

    if listing is None:
        print("Could not find phone list on GSMArena.")
        return []

    phones = []
    links = listing.select("ul li a")

    for link in links:
        name_tag = link.find("strong")
        if name_tag is None:
            continue

        model_name = name_tag.get_text(" ", strip=True)

        if model_name.lower().startswith(EXCLUDED_PREFIXES):
            continue
        phone_url = urljoin(LISTING_URL, link.get("href"))

        image_tag = link.find("img")
        image_url = None
        if image_tag is not None:
            src = image_tag.get("src") or image_tag.get("data-src")
            if src:
                image_url = urljoin(LISTING_URL, src)

        phones.append({
            "model_name": model_name,
            "source_url": phone_url,
            "image_url": image_url,
        })

        # Stop once we have 15 phones
        if len(phones) == MAX_PHONES:
            break

    return phones





def save_phones(phones):
    Base.metadata.create_all(bind=engine)
    session = Session(engine)

    for item in phones:
        existing_phone = session.query(Phone).filter_by(
            model_name=item["model_name"]
        ).first()

        if existing_phone is None:
            new_phone = Phone(
                model_name=item["model_name"],
                brand="Samsung",
                source_url=item["source_url"],
                image_url=item["image_url"],
            )
            session.add(new_phone)
        else:
            existing_phone.source_url = item["source_url"]
            existing_phone.image_url = item["image_url"]

    session.commit()
    session.close()


def run_listing_scraper():
    Base.metadata.create_all(bind=engine)
    session = Session(engine)

    count = session.query(Phone).filter(
        ~Phone.model_name.ilike("Galaxy Tab%"),
        ~Phone.model_name.ilike("Galaxy Watch%")
    ).count()

    session.close()

    if count >= MAX_PHONES:
        print(f"Database already has {count} smartphones. Skipping listing scrape.")
        return

    html = fetch_listing(LISTING_URL)
    phones = parse_phones(html)
    save_phones(phones)

    print(f"Processed {len(phones)} Samsung smartphones.")