
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

    # Step 2: Decide whether semantic search can supplement SQL
    semantic_types = [
        "specification_search",
        "phone_search"
    ]

    semantic_data = []

    if (
        sql_result["type"] in semantic_types
        and len(sql_data) < limit
        and len(phone_names) <= 1
    ):

        # Restrict semantic results to the requested phone
        where_filter = (
            {"model_name": phone_names[0]}
            if len(phone_names) == 1
            else None
        )

        chroma_results = search_documents(
            question,
            limit=limit,
            where=where_filter
        )

        candidates = format_semantic_results(
            chroma_results,
            limit=limit * 3
        )

        # Avoid adding records already retrieved from SQL
        existing_keys = {
            (
                item.get("model_name", "").lower(),
                item.get("category", "").lower(),
                item.get("specification_name", "").lower()
            )
            for item in sql_data
        }

        # When SQL has results, keep semantic results
        # within the same specification category
        sql_categories = {
            item.get("category", "").lower()
            for item in sql_data
        }

        for item in candidates:
            metadata = item["metadata"]

            model_name = metadata.get("model_name", "")
            category = metadata.get("category", "")
            specification_name = metadata.get(
                "specification_name", ""
            )

            if sql_data and category.lower() not in sql_categories:
                continue

            key = (
                model_name.lower(),
                category.lower(),
                specification_name.lower()
            )

            if key in existing_keys:
                continue

            semantic_data.append(item)
            existing_keys.add(key)

            if len(sql_data) + len(semantic_data) >= limit:
                break

    # Step 3: Return retrieval results
    return {
        "question": question,
        "type": sql_result["type"],
        "message": sql_result["message"],
        "sql_data": sql_data,
        "semantic_data": semantic_data,
        "retrieved_data": sql_data
    }
