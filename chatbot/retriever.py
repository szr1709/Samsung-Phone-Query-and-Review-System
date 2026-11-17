
import re

from chatbot.sql_retriever import (
    search_phones,
    get_phone_details,
    get_phone_price,
    search_specifications,
    get_all_phone_names
)

SPECIFICATION_KEYWORDS = [
    "battery", "mah", "charging",
    "camera", "display", "screen",
    "processor", "chipset", "ram",
    "storage", "memory", "resolution",
    "bluetooth", "nfc", "weight",
    "dimensions", "network", "5g"
]

PRICE_KEYWORDS = [
    "price", "cost", "pricing"
]

COMPARISON_KEYWORDS = [
    "compare", "comparison", "difference between",
    "vs", "versus"
]

COMPARISON_FOCUS = {
    "performance": ("platform", "chipset", "cpu", "gpu", "ram", "memory"),
    "camera": ("camera", "photo", "video"),
    "battery": ("battery", "charging"),
    "display": ("display", "screen"),
    "screen": ("display", "screen"),
    "price": ("price",),
    "storage": ("storage", "memory"),
}


IGNORED_COMPARISON_SPECS = {
    ("network", "2g bands"),
    ("network", "3g bands"),
    ("network", "4g bands"),
    ("network", "5g bands"),
    ("network", "speed"),
    ("misc", "sar"),
    ("misc", "sar eu"),
    ("misc", "models"),
    ("misc", "colors"),
    ("launch", "announced"),
    ("launch", "status"),
    ("comms", "positioning"),
    ("comms", "radio"),
    ("body", "dimensions"),
    ("main camera", "features"),
    ("selfie camera", "features"),
}


def _trim_comparison_details(phone, question):
    """Keep comparison prompts focused and small enough for quick answers."""
    specifications = phone.get("specifications", [])
    question_lower = question.lower()
    focus = next(
        (terms for key, terms in COMPARISON_FOCUS.items() if key in question_lower),
        None,
    )

    if focus:
        relevant = [
            spec for spec in specifications
            if any(
                term in f"{spec['category']} {spec['specification_name']}".lower()
                for term in focus
            )
        ]
        phone["specifications"] = relevant
    else:
        phone["specifications"] = [
            spec for spec in specifications
            if (
                spec.get("category", "").lower(),
                spec.get("specification_name", "").lower(),
            ) not in IGNORED_COMPARISON_SPECS
        ]

    return phone


def extract_phone_names(question):
    """
    Find phone models in the database and common Galaxy names
    not indexed yet. Avoid matching shorter names inside longer ones.
    """

    phone_names = sorted(
        get_all_phone_names(),
        key=len,
        reverse=True
    )

    found_phones = []
    matched_spans = []

        
    for model in phone_names:
        pattern = re.compile(
            r"(?<!\w)" + re.escape(model) + r"(?!\w)",
            re.IGNORECASE
        )

        for match in pattern.finditer(question):
            overlaps = any(
                match.start() < end and match.end() > start
                for start, end in matched_spans
            )

            if not overlaps:
                found_phones.append(model)
                matched_spans.append(match.span())
                break


    # Recognize common Galaxy models not present in the database.
    model_pattern = re.compile(
        r"\bGalaxy\s+((?:Z\s+(?:Fold|Flip)\s+\d{1,2}|"
        r"Tab\s+[A-Z]\s+\d{1,2}|[A-Z]\s+\d{1,2})"
        r"(?:\s+(?:Ultra|Plus|FE|Pro|Edge))?)\b",
        re.IGNORECASE
    )

    for match in model_pattern.finditer(question):
        model = "Galaxy " + re.sub(
            r"\s+", " ", match.group(1)
        ).strip()

        overlaps = any(
            match.start() < end and match.end() > start
            for start, end in matched_spans
        )

        if not overlaps:
            found_phones.append(model)
            matched_spans.append(match.span())

    # Recognize shorthand comparisons, e.g. Galaxy S23 vs S22.
    if found_phones:
        shorthand_pattern = re.compile(
            r"\b(?:to\s+(?:the\s+)?|and\s+|vs\.?\s*|versus\s+)"
            r"([SMA]\s*\d{1,2}(?:\s+(?:Ultra|Plus|FE|Pro))?)\b",
            re.IGNORECASE
        )

        for match in shorthand_pattern.finditer(question):
            model = "Galaxy " + re.sub(
                r"\s+", " ", match.group(1)
            ).strip()

            if model.casefold() not in {
                name.casefold() for name in found_phones
            }:
                found_phones.append(model)

    return found_phones



def retrieve_context(question, phone_names=None):
    """
    Route the question to the appropriate SQL retriever.
    """

    question = question.strip()
    question_lower = question.lower()

    if not question:
        return {
            "question": question,
            "type": "empty",
            "retrieved_data": [],
            "message": "Please enter a question."
        }

    if phone_names is None:
        phone_names = extract_phone_names(question)

    phone_name = phone_names[0] if phone_names else None

    # 1. Phone comparison questions
    is_comparison = any(
        keyword in question_lower
        for keyword in COMPARISON_KEYWORDS
    )

    if is_comparison:

        if len(phone_names) < 2:
            return {
                "question": question,
                "type": "phone_comparison",
                "retrieved_data": [],
                "message": (
                    "Please mention at least two phone "
                    "models to compare."
                )
            }

        comparison_data = []

        for model in phone_names[:2]:

            details = get_phone_details(model)

            if details:
                comparison_data.append(_trim_comparison_details(details, question))

        if len(comparison_data) < 2:
            return {
                "question": question,
                "type": "phone_comparison",
                "retrieved_data": comparison_data,
                "message": (
                    "Could not retrieve complete details "
                    "for both phones."
                )
            }

        return {
            "question": question,
            "type": "phone_comparison",
            "retrieved_data": comparison_data,
            "message": (
                "Phone comparison data retrieved successfully."
            )
        }

    
    # 2. Price questions
    is_price_question = (
        any(word in question_lower for word in PRICE_KEYWORDS)
        or (
            "how much" in question_lower
            and any(
                word in question_lower
                for word in ["phone", "mobile", "samsung", "galaxy"]
            )
            and not any(
                word in question_lower
                for word in ["ram", "storage", "memory", "battery", "charging"]
            )
        )
    )

    if is_price_question:

        if not phone_name:
            return {
                "question": question,
                "type": "price_search",
                "retrieved_data": [],
                "message": "Please specify a phone model."
            }

        price_data = get_phone_price(phone_name)

        if not price_data:
            return {
                "question": question,
                "type": "price_search",
                "retrieved_data": [],
                "message": f"{phone_name} was not found in the database."
            }

        return {
            "question": question,
            "type": "price_search",
            "retrieved_data": price_data,
            "message": (
                "Price information retrieved."
                if price_data["prices"]
                else f"No price information available for {phone_name}."
            )
        }


    # 3. Exact battery capacity search
        # 3. Battery life and endurance questions
    battery_life_keywords = [
        "battery life",
        "battery endurance",
        "endurance",
        "active use score",
        "longest lasting battery",
        "best battery life"
    ]

    if any(word in question_lower for word in battery_life_keywords):
        results = search_specifications(
            "Active use score"
        )

        # Also retrieve EU endurance measurements.
        eu_results = search_specifications("endurance")

        runtime_results = [
            item for item in results + eu_results
            if (
                item["category"].lower() == "our tests"
                or item["category"].lower() == "eu label"
            )
        ]

        return {
            "question": question,
            "type": "battery_life_search",
            "retrieved_data": runtime_results,
            "message": (
                "Measured battery runtime information retrieved."
                if runtime_results
                else "No measured battery runtime information available. "
                     "Battery capacity alone cannot establish battery life."
            )
        }
    
    # 4. General specification questions
    if any(word in question_lower for word in SPECIFICATION_KEYWORDS):

        keyword = next(
            (
                word for word in SPECIFICATION_KEYWORDS
                if word in question_lower
            ),
            None
        )

        # Map user-friendly terms to database specification names.
        if keyword == "processor":
            keyword = "chipset"

        # Search for a numerical specification first.
        value_match = re.search(
            r"\b\d+(?:\.\d+)?\s*(?:gb|tb|w|hz|mp)\b",
            question,
            re.IGNORECASE
        )

        if value_match:
            keyword = value_match.group(0)

        results = search_specifications(
            keyword,
            model_name=phone_name
        )

        return {
            "question": question,
            "type": "specification_search",
            "retrieved_data": results,
            "message": (
                "Specification results found."
                if results
                else "No matching specifications found."
            )
        }

    # 5. General phone details
    if phone_name:
        details = get_phone_details(phone_name)

        if details:
            return {
                "question": question,
                "type": "phone_details",
                "retrieved_data": details,
                "message": "Phone details retrieved."
            }

        return {
            "question": question,
            "type": "phone_details",
            "retrieved_data": [],
            "message": f"{phone_name} was not found in the database."
        }

    # 6. General phone search
    results = search_phones(question)

    return {
        "question": question,
        "type": "phone_search",
        "retrieved_data": results,
        "message": (
            "Matching phones found."
            if results
            else "No matching information found."
        )
    }
