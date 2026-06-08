from app.scorer import score_product


def test_exact_name_match():
    product = {
        "name": "Nike Air Max",
        "brand": "Nike",
        "category": "footwear",
        "tags": ["running"],
        "description": "Popular running shoe",
        "rating": 4.8,
        "review_count": 500,
        "in_stock": True,
    }

    score, breakdown = score_product(
        product,
        "nike air max",
    )

    assert score >= 100
    assert "exact_name_match" in breakdown


def test_no_matching_signals():
    product = {
        "name": "Laptop",
        "brand": "Dell",
        "category": "electronics",
        "tags": ["computer"],
        "description": "Business laptop",
        "rating": None,
        "review_count": 0,
        "in_stock": False,
    }

    score, breakdown = score_product(
        product,
        "banana",
    )

    assert score == -10
    assert breakdown == {
        "penalty_out_of_stock": -10
    }