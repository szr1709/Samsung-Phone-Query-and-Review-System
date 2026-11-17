import re
from sqlalchemy import text

from database.connection import engine


def search_phones(query, limit=10):
    """
    Search phones by model name or brand.
    Returns a list of matching phones.
    """

    query = query.strip()

    if not query:
        return []

    limit = max(1, min(limit, 50))

    sql = text("""
        SELECT
            id,
            model_name,
            brand,
            release_date
        FROM phones
        WHERE (model_name ILIKE :query OR brand ILIKE :query)
          AND model_name NOT ILIKE 'Galaxy Tab %'
          AND model_name NOT ILIKE 'Galaxy Watch%'
        ORDER BY model_name
        LIMIT :limit
    """)

    with engine.connect() as connection:
        results = connection.execute(
            sql,
            {
                "query": f"%{query}%",
                "limit": limit
            }
        ).mappings().all()

    return [dict(row) for row in results]


def get_phone_details(model_name):
    """
    Retrieve a phone's basic information,
    specifications, and available prices.

    Exact model name is preferred.
    Returns None if the phone is not found.
    """

    sql_phone = text("""
        SELECT
            id,
            model_name,
            brand,
            release_date,
            source_url,
            image_url
        FROM phones
        WHERE LOWER(model_name) = LOWER(:model_name)
          AND model_name NOT ILIKE 'Galaxy Tab %'
          AND model_name NOT ILIKE 'Galaxy Watch%'
        LIMIT 1
    """)

    sql_specifications = text("""
        SELECT
            category,
            specification_name,
            specification_value
        FROM phone_specifications
        WHERE phone_id = :phone_id
        ORDER BY category, specification_name
    """)

    sql_prices = text("""
        SELECT
            price,
            currency,
            source,
            checked_at
        FROM phone_prices
        WHERE phone_id = :phone_id
        ORDER BY checked_at DESC
    """)

    with engine.connect() as connection:

        phone = connection.execute(
            sql_phone,
            {"model_name": model_name.strip()}
        ).mappings().first()

        if not phone:
            return None

        phone = dict(phone)

        specifications = connection.execute(
            sql_specifications,
            {"phone_id": phone["id"]}
        ).mappings().all()

        prices = connection.execute(
            sql_prices,
            {"phone_id": phone["id"]}
        ).mappings().all()

    phone["specifications"] = [
        dict(spec) for spec in specifications
    ]

    phone["prices"] = [
        dict(price) for price in prices
    ]

    return phone


def get_phone_price(model_name):
    """
    Retrieve structured price records first.
    If unavailable, fall back to the scraped Misc -> Price specification.
    """

    phone = get_phone_details(model_name)

    if not phone:
        return None

    # First priority: structured price records
    if phone["prices"]:
        return {
            "model_name": phone["model_name"],
            "prices": phone["prices"],
            "source_type": "phone_prices"
        }

    # Second priority: scraped price specification
    for spec in phone["specifications"]:
        if (
            spec["category"].lower() == "misc"
            and spec["specification_name"].lower() == "price"
        ):
            return {
                "model_name": phone["model_name"],
                "prices": [
                    {
                        "price": spec["specification_value"],
                        "currency": "As listed",
                        "source": "Scraped phone specification"
                    }
                ],
                "source_type": "phone_specifications"
            }

    return {
        "model_name": phone["model_name"],
        "prices": [],
        "source_type": None
    }






def search_specifications(
    keyword,
    model_name=None,
    limit=20,
    value_filter=None,
    highest_first=False
):
    """
    Search phone specifications.

    RAM/storage use exact configuration matching.
    Battery searches return only battery capacity (mAh).
    """

    keyword = keyword.strip().lower()

    if not keyword:
        return []

    limit = max(1, min(limit, 100))

    value_pattern = None

    # Validate and normalize numeric filters.
    if value_filter:
        normalized_value = re.sub(
            r"\s+", "", value_filter
        ).upper()

        if not re.fullmatch(
            r"\d+(?:\.\d+)?(?:GB|TB|MAH)",
            normalized_value
        ):
            return []

        if keyword == "ram":
            value_pattern = (
                rf"(^|[[:space:]]){normalized_value}"
                rf"[[:space:]]+RAM([,[:space:]]|$)"
            )

        elif keyword in ("storage", "internal"):
            value_pattern = (
                rf"(^|[,[:space:]]){normalized_value}"
                rf"([0-9]|[,[:space:]]|$)"
            )

        elif keyword == "battery":
            number = normalized_value[:-3]
            value_pattern = (
                rf"(^|[^0-9]){number}"
                rf"[[:space:]]*mAh([^[:alnum:]]|$)"
            )

    # Select the correct specification fields.
    if keyword in ("ram", "storage", "internal"):
        field_condition = """
            s.category ILIKE 'Memory'
            AND s.specification_name ILIKE 'Internal'
            AND (
                CAST(:value_pattern AS VARCHAR) IS NULL
                OR s.specification_value ~* :value_pattern
            )
        """

    elif keyword == "battery":
        field_condition = """
            s.category ILIKE 'Battery'
            AND s.specification_name ILIKE 'Type'
            AND (
                CAST(:value_pattern AS VARCHAR) IS NULL
                OR s.specification_value ~* :value_pattern
            )
        """

    elif keyword in ("screen size", "screen", "display size", "size"):
        field_condition = """
            s.category ILIKE 'Display'
            AND s.specification_name ILIKE 'Size'
        """

    else:
        field_condition = """
            (
                s.specification_name ILIKE :keyword
                OR s.specification_value ILIKE :keyword
                OR s.category ILIKE :keyword
            )
        """

    sql = text(f"""
        SELECT
            p.model_name,
            s.category,
            s.specification_name,
            s.specification_value
        FROM phone_specifications s
        JOIN phones p ON p.id = s.phone_id
        WHERE {field_condition}
          AND p.model_name NOT ILIKE 'Galaxy Tab%'
          AND p.model_name NOT ILIKE 'Galaxy Watch%'
          AND (
              CAST(:model_name AS VARCHAR) IS NULL
              OR LOWER(p.model_name) = LOWER(:model_name)
          )
        ORDER BY
            CASE
                WHEN :highest_first AND :sort_battery
                THEN CAST(
                    NULLIF(
                        substring(
                            s.specification_value
                            FROM '([0-9]+(?:\\.[0-9]+)?)\\s*mAh'
                        ),
                        ''
                    ) AS NUMERIC
                )
            END DESC NULLS LAST,
            p.model_name
        LIMIT :limit
    """)

    with engine.connect() as connection:
        results = connection.execute(
            sql,
            {
                "keyword": f"%{keyword}%",
                "sort_battery": keyword == "battery",
                "value_pattern": value_pattern,
                "model_name": (
                    model_name.strip() if model_name else None
                ),
                "highest_first": highest_first,
                "limit": limit
            }
        ).mappings().all()

    return [dict(row) for row in results]






def get_all_phone_names():
    sql = text("""
        SELECT model_name
        FROM phones
        WHERE model_name NOT ILIKE 'Galaxy Tab %'
          AND model_name NOT ILIKE 'Galaxy Watch%'
        ORDER BY model_name
    """)

    with engine.connect() as connection:
        results = connection.execute(sql).scalars().all()

    return results
