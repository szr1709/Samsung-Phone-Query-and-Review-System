
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
    "performance": ("platform", "chipset", "cpu", "gpu", "ram", "memory", "performance",),
    "gaming": (
    "platform", "chipset", "cpu", "gpu",
    "memory", "display", "battery", "performance"
    ),
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
    """Keep comparison specifications relevant to the question."""

    specifications = phone.get("specifications", [])
    question_lower = question.lower()

    # Collect every requested comparison category.
    focus_terms = set()

    for key, terms in COMPARISON_FOCUS.items():
        if key in question_lower:
            focus_terms.update(terms)

    if focus_terms:
        relevant = [
            spec for spec in specifications
            if any(
                term in (
                    f"{spec['category']} "
                    f"{spec['specification_name']}"
                ).lower()
                for term in focus_terms
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
    battery_life_keywords = [
        "battery life",
        "battery endurance",
        "endurance",
        "active use score",
        "longest lasting battery",
        "best battery life"
    ]

    is_battery_life_question = any(
        word in question_lower
        for word in battery_life_keywords
    )

    comparative_intent = any(
        word in question_lower
        for word in [
            "better",
            "faster",
            "more powerful",
            "performance",
            "processor",
            "chipset",
            "which phone is better"
        ]
    )

    is_comparison = (
        any(
            keyword in question_lower
            for keyword in COMPARISON_KEYWORDS
        )
        or (
            len(phone_names) >= 2
            and comparative_intent
            and not is_battery_life_question
        )
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
    battery_life_keywords = [
        "battery life",
        "battery endurance",
        "endurance",
        "active use score",
        "longest lasting battery",
        "best battery life"
    ]

    if is_battery_life_question:

        # Explicit endurance questions use EU endurance measurements.
        if "endurance" in question_lower or "eu label" in question_lower:
            search_keyword = "endurance"
        else:
            # Battery-life questions use active-use scores.
            search_keyword = "Active use score"

        # If two phones are named, retrieve measurements for both.
        if len(phone_names) >= 2:

            runtime_results = []

            for model in phone_names[:2]:
                model_results = search_specifications(
                    search_keyword,
                    model_name=model
                )

                runtime_results.extend(model_results)

        else:
            runtime_results = search_specifications(search_keyword)

        # Find the highest result only for general searches.
        # Keep both phones' results when comparing named models.
        if (
            len(phone_names) < 2
            and search_keyword == "Active use score"
            and any(word in question_lower for word in [
                "best",
                "highest",
                "longest",
                "maximum",
                "most"
            ])
        ):

            scored_results = []

            for item in runtime_results:
                match = re.search(
                    r"(\d+):(\d+)\s*h",
                    item["specification_value"],
                    re.IGNORECASE
                )

                if match:
                    minutes = (
                        int(match.group(1)) * 60
                        + int(match.group(2))
                    )

                    scored_results.append((item, minutes))

            if scored_results:
                highest_score = max(
                    score for _, score in scored_results
                )

                runtime_results = [
                    item
                    for item, score in scored_results
                    if score == highest_score
                ]

        return {
            "question": question,
            "type": "battery_life_search",
            "retrieved_data": runtime_results,
            "message": (
                "Measured battery runtime information retrieved."
                if runtime_results
                else "No measured battery runtime information available."
            )
        }
    
    # 4. General specification questions
    if any(word in question_lower for word in SPECIFICATION_KEYWORDS):

        keyword = next(
            (word for word in SPECIFICATION_KEYWORDS if word in question_lower),
            None
        )

        if keyword == "processor":
            keyword = "chipset"

        value_match = re.search(
            r"\b\d+(?:\.\d+)?\s*(?:gb|tb|mah|w|hz|mp)\b",
            question,
            re.IGNORECASE
        )

        if keyword == "battery":
            highest_first = any(
                word in question_lower
                for word in ("largest", "highest", "biggest", "maximum")
            )

            results = search_specifications(
                "battery",
                model_name=phone_name,
                value_filter=value_match.group(0) if value_match else None,
                highest_first=highest_first,
                limit=100
            )
                        # Keep only phones tied for the highest battery capacity.
            if highest_first and results:
                battery_values = []

                for item in results:
                    match = re.search(
                        r"(\d+(?:\.\d+)?)\s*mAh",
                        item["specification_value"],
                        re.IGNORECASE
                    )

                    if match:
                        battery_values.append(
                            (item, float(match.group(1)))
                        )

                if battery_values:
                    max_capacity = max(
                        capacity for _, capacity in battery_values
                    )

                    results = [
                        item
                        for item, capacity in battery_values
                        if capacity == max_capacity
                    ]

        elif value_match and keyword in ("ram", "storage", "memory"):
            results = search_specifications(
                keyword,
                model_name=phone_name,
                value_filter=value_match.group(0)
            )

        else:
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
