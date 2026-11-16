
import subprocess
import sys


def main() -> None:
    commands = (
        ("database.create_database", "PostgreSQL database setup"),
        ("database.create_tables", "PostgreSQL table setup"),
        ("scraper.gsmarena_scraper", "Samsung phone listings"),
        (
            "scraper.gsmarena_specification_scraper",
            "phone specifications and prices",
        ),
    )

    for module, label in commands:
        print(f"\n=== Scraping {label} ===", flush=True)

        subprocess.run(
            [sys.executable, "-m", module],
            check=True,
        )

    print("\nAll tasks completed successfully!")


if __name__ == "__main__":
    main()
