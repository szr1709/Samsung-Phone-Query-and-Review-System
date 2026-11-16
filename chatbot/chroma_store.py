
import chromadb
import ollama


# Embedding model
EMBEDDING_MODEL = "nomic-embed-text"

# Persistent ChromaDB storage
CHROMA_PATH = "database/chroma_db"


# Initialize ChromaDB client
client = chromadb.PersistentClient(
    path=CHROMA_PATH
)


# Create or retrieve collection
collection = client.get_or_create_collection(
    name="samsung_phones",
    metadata={
        "description": "Samsung phone specifications and information",
        "hnsw:space": "cosine"
    }
)


def generate_embedding(text):
    """
    Generate an embedding using Ollama.
    """

    response = ollama.embed(
        model=EMBEDDING_MODEL,
        input=text
    )

    return response.embeddings[0]


def search_documents(query, limit=5):
    """
    Search ChromaDB using semantic similarity.
    """

    document_count = collection.count()
    if document_count == 0:
        return []

    query_embedding = generate_embedding(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(limit * 3, document_count)
    )

    return results
