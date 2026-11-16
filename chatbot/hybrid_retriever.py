
from chatbot.retriever import extract_phone_names, retrieve_context
from chatbot.chroma_store import search_documents


def format_semantic_results(results, limit=5):
    """
    Convert ChromaDB results into a readable list.
    """

    if not results or not isinstance(results, dict):
        return []

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    semantic_data = []

    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances
    ):
        model_name = metadata.get("model_name", "")
        if model_name.startswith(("Galaxy Tab", "Galaxy Watch")):
            continue

        semantic_data.append({
            "document": document,
            "metadata": metadata,
            "distance": distance
        })
        if len(semantic_data) == limit:
            break

    return semantic_data


def retrieve_hybrid_context(question, limit=5):
    """
    Retrieve information using both PostgreSQL
    and ChromaDB.
    """

    question = question.strip()

    # Step 1: Retrieve structured SQL data
    phone_names = extract_phone_names(question)
    sql_result = retrieve_context(question, phone_names=phone_names)

    sql_data = sql_result.get("retrieved_data", [])

    # Step 2: Decide whether semantic search is useful
    semantic_types = [
        "specification_search",
        "phone_search"
    ]

    semantic_data = []

    if (
        sql_result["type"] in semantic_types
        and not sql_data
        and not phone_names
    ):

        chroma_results = search_documents(
            question,
            limit=limit
        )

        semantic_data = format_semantic_results(
            chroma_results,
            limit=limit,
        )

    # Step 3: Return combined retrieval results
    return {
        "question": question,
        "type": sql_result["type"],
        "message": sql_result["message"],

        "sql_data": sql_data,

        "semantic_data": semantic_data,

        # Preserve the original SQL result structure
        "retrieved_data": sql_data
    }
