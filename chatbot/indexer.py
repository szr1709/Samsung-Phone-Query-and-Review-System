
from sqlalchemy import text
import ollama

from database.connection import engine
from chatbot.chroma_store import collection


EMBEDDING_MODEL = "nomic-embed-text"
BATCH_SIZE = 50


def fetch_phone_specifications():
    """
    Fetch phone specifications from PostgreSQL.
    """

    sql = text("""
        SELECT
            p.id AS phone_id,
            p.model_name,
            p.brand,
            s.id AS specification_id,
            s.category,
            s.specification_name,
            s.specification_value
        FROM phone_specifications s
        JOIN phones p ON p.id = s.phone_id
        WHERE s.specification_value IS NOT NULL
          AND TRIM(s.specification_value) != ''
        ORDER BY p.model_name, s.category
    """)

    with engine.connect() as connection:
        results = connection.execute(sql).mappings().all()

    return [dict(row) for row in results]


def create_document(spec):
    """
    Convert a phone specification into readable text.
    """

    return (
        f"{spec['brand']} {spec['model_name']}. "
        f"Category: {spec['category']}. "
        f"Specification: {spec['specification_name']}. "
        f"Value: {spec['specification_value']}."
    )


def index_phone_specifications():
    """
    Generate embeddings and store specifications in ChromaDB.
    """

    specifications = fetch_phone_specifications()

    if not specifications:
        print("No phone specifications found in PostgreSQL.")
        return

    total_indexed = 0

    for start in range(0, len(specifications), BATCH_SIZE):

        batch = specifications[start:start + BATCH_SIZE]

        documents = [
            create_document(spec)
            for spec in batch
        ]

        ids = [
            f"phone-{spec['phone_id']}-spec-{spec['specification_id']}"
            for spec in batch
        ]

        metadatas = [
            {
                "phone_id": int(spec["phone_id"]),
                "model_name": spec["model_name"],
                "brand": spec["brand"],
                "category": spec["category"],
                "specification_name": spec["specification_name"]
            }
            for spec in batch
        ]

        # Generate embeddings for the entire batch
        response = ollama.embed(
            model=EMBEDDING_MODEL,
            input=documents
        )

        embeddings = response.embeddings

        # Store documents and embeddings in ChromaDB
        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )

        total_indexed += len(batch)

        print(
            f"Indexed {total_indexed}/{len(specifications)} specifications"
        )

    print("\nIndexing completed successfully!")
    print("Total specifications indexed:", total_indexed)
    print("ChromaDB document count:", collection.count())


if __name__ == "__main__":
    index_phone_specifications()
