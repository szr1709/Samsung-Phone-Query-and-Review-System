"""Create the configured PostgreSQL database if it does not already exist."""

import os

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text


def main() -> None:
    load_dotenv()
    database_name = os.getenv("DB_NAME")
    if not database_name:
        raise RuntimeError("DB_NAME is missing from the environment/.env file.")

    admin_url = URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "5432")),
        database="postgres",
    )
    engine = create_engine(admin_url, pool_pre_ping=True)
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": database_name},
            ).scalar_one_or_none()
            if exists:
                print(f"Database '{database_name}' already exists.")
                return

            quoted_name = '"' + database_name.replace('"', '""') + '"'
            connection.exec_driver_sql(f"CREATE DATABASE {quoted_name}")
            print(f"Created database '{database_name}'.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
