from sqlalchemy import create_engine, text
from database.connection import database_url


def create_database():
    database_name = database_url.database

    # Connect to the default 'postgres' database first
    admin_url = database_url.set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    with admin_engine.connect() as connection:
        query = text("SELECT 1 FROM pg_database WHERE datname = :name")
        result = connection.execute(query, {"name": database_name}).fetchone()

        if result:
            print(f"Database '{database_name}' already exists.")
        else:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
            print(f"Created database '{database_name}'.")

    admin_engine.dispose()


if __name__ == "__main__":
    create_database()
