
from database.connection import engine
from database.models import Base

def create_tables():
    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables checked successfully!")

    except Exception as e:
        print("Error creating database tables:")
        print(e)


if __name__ == "__main__":
    create_tables()
