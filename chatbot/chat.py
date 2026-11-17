
import re

from chatbot.hybrid_retriever import retrieve_hybrid_context
from chatbot.prompt import build_prompt
from chatbot.ollama_client import generate_response


def _clarify_spec_value(category, spec_name, spec_value):
    """Make compact GSMArena values unambiguous for a small language model."""
    value = str(spec_value or "").strip()
    cat_lower = (category or "").lower()
    name_lower = (spec_name or "").lower()

    if cat_lower == "memory" and name_lower == "internal":
        pairs = re.findall(
            r"\b(\d+\s*(?:GB|TB))\s+(\d+\s*GB)\s*RAM\b",
            value,
            flags=re.IGNORECASE,
        )
        if pairs:
            storages = list(dict.fromkeys(p[0].replace(" ", "") for p in pairs))
            rams = list(dict.fromkeys(p[1].replace(" ", "") for p in pairs))
            value = f"Storage: {', '.join(storages)} | RAM: {', '.join(rams)}"
    elif "camera" in cat_lower and name_lower in {"single", "dual", "triple", "quad"}:
        # Remove raw sensor fraction/pixel-size measurements and separate lenses clearly.
        value = re.sub(r',\s*1/\d+(?:\.\d+)?",\s*\d+(?:\.\d+)?µm', "", value)
        value = re.sub(r"(?<![+,/])\s+(\d+\s*MP\b)", r" + \1", value)
    elif name_lower == "nfc":
        if value.lower() == "yes":
            value = "Yes (NFC supported)"
        elif value.lower() == "no":
            value = "No (NFC not supported)"
    elif name_lower == "3.5mm jack":
        if value.lower() == "no":
            value = "No (No 3.5mm headphone jack)"
        elif value.lower() == "yes":
            value = "Yes (Has 3.5mm headphone jack)"

    return value


def _format_phone_prices(item):
    """Return formatted price strings for a phone item."""
    prices = item.get("prices", [])
    if prices:
        return [
            f"{price.get('price', 'Unknown')} {price.get('currency', '')}".strip()
            for price in prices
        ]

    for spec in item.get("specifications", []):
        if (
            spec.get("category", "").lower() == "misc"
            and spec.get("specification_name", "").lower() == "price"
        ):
            return [str(spec.get("specification_value", "")).strip()]

    return []


def format_sql_context(sql_data):
    """
    Format phone details and specification search results as readable text.
    """

    if not sql_data:
        return "No relevant information found in PostgreSQL."

    items = sql_data if isinstance(sql_data, list) else [sql_data]

    # Side-by-side category grouping when comparing two or more full phone records
    if (
        len(items) >= 2
        and all(isinstance(item, dict) and "specifications" in item for item in items)
    ):
        lines = []
        model_names = [item.get("model_name", "Unknown") for item in items]
        lines.append("Phones compared: " + " vs ".join(model_names))

        for item in items:
            model = item.get("model_name", "Unknown")
            if item.get("release_date"):
                lines.append(f"- {model} Release date: {item['release_date']}")

        preferred_order = [
            "Battery",
            "Display",
            "Platform",
            "Memory",
            "Main Camera",
            "Selfie camera",
            "Body",
            "Comms",
            "Sound",
            "Network",
            "Features",
            "Launch",
            "Misc",
        ]
        all_cats = []
        spec_lookup = {}
        for item in items:
            model = item.get("model_name", "Unknown")
            for spec in item.get("specifications", []):
                cat = spec.get("category", "Other")
                name = spec.get("specification_name", "")
                val = _clarify_spec_value(cat, name, spec.get("specification_value", ""))
                if cat not in all_cats:
                    all_cats.append(cat)
                spec_lookup.setdefault(cat, {}).setdefault(name, {})[model] = val

        ordered_cats = [c for c in preferred_order if c in all_cats] + [
            c for c in all_cats if c not in preferred_order
        ]

        for cat in ordered_cats:
            lines.append(f"\n[{cat}]")
            for spec_name, per_model in spec_lookup[cat].items():
                parts = [
                    f"{model} = {per_model[model]}"
                    for model in model_names
                    if model in per_model
                ]
                lines.append(f"- {spec_name}: {' | '.join(parts)}")

        lines.append("\n[Prices]")
        for item in items:
            model = item.get("model_name", "Unknown")
            price_list = _format_phone_prices(item)
            if price_list:
                lines.append(f"- {model}: {', '.join(price_list)}")
            else:
                lines.append(f"- {model}: Price not available")

        lines.append(
            "Note: Do not convert currencies or estimate exchange rates when "
            "prices are in different currencies (e.g., EUR vs INR). "
            "Scraped prices may not reflect current retail prices."
        )
        return "\n".join(lines)

    lines = []

    for item in items:
        if not isinstance(item, dict):
            lines.append(str(item))
            continue

        if "specification_name" in item:
            cat = item.get("category", "")
            name = item.get("specification_name", "")
            val = _clarify_spec_value(cat, name, item.get("specification_value", ""))
            lines.append(
                f"{item.get('model_name', 'Unknown')} | "
                f"{cat} | "
                f"{name}: "
                f"{val}"
            )
            continue

        lines.append(f"Phone: {item.get('model_name', 'Unknown')}")
        if item.get("brand"):
            lines.append(f"Brand: {item['brand']}")
        if item.get("release_date"):
            lines.append(f"Release date: {item['release_date']}")

        for spec in item.get("specifications", []):
            cat = spec.get("category", "")
            name = spec.get("specification_name", "")
            val = _clarify_spec_value(cat, name, spec.get("specification_value", ""))
            lines.append(f"- {cat} - {name}: {val}")

        prices = item.get("prices", [])
        for price in prices:
            lines.append(
                f"- Price: {price.get('price', 'Unknown')} "
                f"{price.get('currency', '')}"
            )
        if prices:
            lines.append("Scraped prices may not reflect current retail prices.")

    return "\n".join(lines)




def format_semantic_context(semantic_data):
    """
    Convert ChromaDB retrieval results into readable text.
    """

    if not semantic_data:
        return "No relevant semantic information found."

    formatted_results = []

    for item in semantic_data:
        metadata = item.get("metadata", {})

        document = item.get("document", "")

        formatted_results.append(
            f"""
Phone: {metadata.get('model_name', 'Unknown')}
Category: {metadata.get('category', 'Unknown')}
Specification: {document}
"""
        )

    return "\n".join(formatted_results)


def chat(question, on_token=None):
    """
    Main chatbot function.

    Flow:
    User question
        -> Hybrid retrieval
        -> Context formatting
        -> Prompt generation
        -> Ollama response
    """

    question = question.strip()

    if not question:
        return "Please enter a question."

    # Step 1: Retrieve information
    retrieval_result = retrieve_hybrid_context(question)

    sql_data = retrieval_result.get("sql_data", [])
    semantic_data = retrieval_result.get("semantic_data", [])

    # Don't ask the LLM to fill in facts when retrieval found no evidence.
    if not sql_data and not semantic_data:
        return retrieval_result.get("message", "No relevant information found.")

    # Step 2: Format retrieved information
    sql_context = format_sql_context(sql_data)

    semantic_context = format_semantic_context(semantic_data)

    # Step 3: Build prompt
    prompt = build_prompt(
        question=question,
        sql_context=sql_context,
        semantic_context=semantic_context
    )

    # Step 4: Select output length based on question type
    question_lower = question.lower()

    if retrieval_result.get("type") == "phone_comparison" or any(
    word in question_lower
    for word in [
        "compare", "comparison", "difference", "vs", "versus"
    ]):
        max_tokens = 1600

    elif any(word in question_lower for word in [
        "review", "detailed review", "pros and cons"
    ]):
        max_tokens = 1200

    else:
        max_tokens = 600

    # Step 5: Generate answer using Qwen
    answer = generate_response(
        prompt,
        on_token=on_token,
        num_predict=max_tokens
    )

    return answer