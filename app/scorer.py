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
    "type_contains_query": 5,
    "sub_category_contains_query": 10,
    "model_number_contains_query": 10,
    "exact_model_number_match": 90,
    "exact_upc_match": 100,
    "upc_contains_query": 20,
    "certification_exact_match": 20,
    "hazardous_material_contains_query": 10,
    "boost_high_repairability": 8,
}


def normalize_text(value: object) -> str:
    return str(value or "").strip().lower()


def contains_whole_word(query: str, haystack: str) -> bool:
    if not haystack:
        return False

    return bool(re.search(rf"\b{re.escape(query)}\b", haystack))


def score_product(product: dict, query: str) -> tuple[int, dict[str, int]]:
    query = normalize_text(query)
    score = 0
    breakdown: dict[str, int] = {}

    if not query:
        return score, breakdown

    name = normalize_text(product.get("name"))
    brand = normalize_text(product.get("brand"))
    category = normalize_text(product.get("category"))
    product_type = normalize_text(product.get("type"))
    sub_category = normalize_text(product.get("sub_category"))
    model_number = normalize_text(product.get("model_number"))
    upc = normalize_text(product.get("upc"))

    required_certifications = [
        normalize_text(certification)
        for certification in product.get("required_certifications", [])
        if certification is not None
    ]
    hazardous_materials = [
        normalize_text(material)
        for material in product.get("hazardous_materials", [])
        if material is not None
    ]

    repairability_score = product.get("repairability_score")


    def add_signal(signal_name: str):
        nonlocal score

        points = SIGNAL_WEIGHTS[signal_name]
        score += points
        breakdown[signal_name] = points

    if query == name:
        add_signal("exact_name_match")

    if name.startswith(query):
        add_signal("name_starts_with_query")

    if contains_whole_word(query, name):
        add_signal("name_whole_word_match")

    if query in name:
        add_signal("name_contains_query")

    if query == brand:
        add_signal("exact_brand_match")

    if query in brand:
        add_signal("brand_contains_query")

    if query == category:
        add_signal("exact_category_match")

    if query in category:
        add_signal("category_contains_query")

    if query in product_type:
        add_signal("type_contains_query")

    if query in sub_category:
        add_signal("sub_category_contains_query")

    if query == model_number:
        add_signal("exact_model_number_match")

    if query in model_number:
        add_signal("model_number_contains_query")

    if query == upc:
        add_signal("exact_upc_match")

    if upc and query in upc:
        add_signal("upc_contains_query")

    if any(query == certification for certification in required_certifications):
        add_signal("certification_exact_match")

    if any(query in material for material in hazardous_materials):
        add_signal("hazardous_material_contains_query")

    if repairability_score is not None and float(repairability_score) >= 0.75:
        add_signal("boost_high_repairability")

    return score, breakdown
