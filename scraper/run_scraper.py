
from database.create_database import create_database
from database.create_tables import create_tables
from scraper.gsmarena_scraper import run_listing_scraper
from scraper.gsmarena_specification_scraper import run_specification_scraper


def main():
    print("\n--- Step 1: Setting up PostgreSQL database ---")
    create_database()

    print("\n--- Step 2: Creating database tables ---")
    create_tables()

    print("\n--- Step 3: Scraping Samsung phone listings ---")
    run_listing_scraper()

    print("\n--- Step 4: Scraping phone specifications and prices ---")
    run_specification_scraper()

    print("\nAll tasks completed successfully!")


if __name__ == "__main__":
    main()
