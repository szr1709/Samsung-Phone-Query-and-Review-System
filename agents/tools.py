
from chatbot.hybrid_retriever import retrieve_hybrid_context
from chatbot.chat import format_sql_context, format_semantic_context


def retrieve_phone_information(question):
    """
    Tool used by Agent 1 to retrieve phone information.
    """

    result = retrieve_hybrid_context(question)

    sql_data = result.get("sql_data", [])
    semantic_data = result.get("semantic_data", [])

    if not sql_data and not semantic_data:
        return {
            "success": False,
            "message": result.get(
                "message",
                "No relevant phone information found."
            ),
            "context": ""
        }

    sql_context = format_sql_context(sql_data)
    semantic_context = format_semantic_context(semantic_data)

    context = f"""
POSTGRESQL INFORMATION:
{sql_context}

CHROMADB SEMANTIC INFORMATION:
{semantic_context}
"""

    return {
        "success": True,
        "message": "Phone information retrieved successfully.",
        "context": context
    }
