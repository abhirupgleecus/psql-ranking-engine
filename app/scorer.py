import re


SIGNAL_WEIGHTS = {
    "exact_name_match": 100,
    "name_starts_with_query": 80,
    "name_whole_word_match": 60,
    "name_contains_query": 40,
    "exact_brand_match": 50,
    "brand_contains_query": 25,
    "exact_category_match": 30,
    "category_contains_query": 15,
    "tag_exact_match": 20,
    "tag_contains_query": 10,
    "description_contains_query": 5,
    "boost_high_rating": 8,
    "boost_high_review_count": 5,
    "boost_in_stock": 3,
    "penalty_out_of_stock": -10,
}


def score_product(product: dict, query: str) -> tuple[int, dict]:
    query = query.strip().lower()

    score = 0
    breakdown: dict[str, int] = {}

    name = str(product.get("name", "")).lower()
    brand = str(product.get("brand", "")).lower()
    category = str(product.get("category", "")).lower()
    description = str(product.get("description", "")).lower()

    tags = [
        str(tag).lower()
        for tag in product.get("tags", [])
    ]

    rating = product.get("rating")
    review_count = product.get("review_count", 0)
    in_stock = product.get("in_stock", False)

    def add_signal(signal_name: str):
        nonlocal score

        points = SIGNAL_WEIGHTS[signal_name]
        score += points
        breakdown[signal_name] = points

    # Name signals

    if query == name:
        add_signal("exact_name_match")

    if name.startswith(query):
        add_signal("name_starts_with_query")

    if re.search(rf"\b{re.escape(query)}\b", name):
        add_signal("name_whole_word_match")

    if query in name:
        add_signal("name_contains_query")

    # Brand signals

    if query == brand:
        add_signal("exact_brand_match")

    if query in brand:
        add_signal("brand_contains_query")

    # Category signals

    if query == category:
        add_signal("exact_category_match")

    if query in category:
        add_signal("category_contains_query")

    # Tag signals

    if any(query == tag for tag in tags):
        add_signal("tag_exact_match")

    if any(query in tag for tag in tags):
        add_signal("tag_contains_query")

    # Description

    if query in description:
        add_signal("description_contains_query")

    # Boosts

    if rating is not None and float(rating) >= 4.5:
        add_signal("boost_high_rating")

    if review_count >= 100:
        add_signal("boost_high_review_count")

    if in_stock:
        add_signal("boost_in_stock")
    else:
        add_signal("penalty_out_of_stock")

    return score, breakdown