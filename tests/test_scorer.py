from decimal import Decimal

from app.scorer import score_product


def test_exact_name_match_on_product_master():
    product = {
        "name": "HP ProBook 450 G10 Notebook PC",
        "brand": "HP",
        "category": "Electronics",
        "type": "Laptop",
        "sub_category": "Laptops & Notebooks",
        "model_number": "675S7A",
        "required_certifications": ["Energy Star 8.0", "EPEAT Gold"],
        "hazardous_materials": ["Lithium-ion Battery"],
        "repairability_score": Decimal("8.20"),
        "status": "ACTIVE",
    }

    score, breakdown = score_product(
        product,
        "hp probook 450 g10 notebook pc",
    )

    assert score >= 100
    assert breakdown["exact_name_match"] == 100
    assert breakdown["boost_high_repairability"] == 8



def test_model_number_and_certification_signals():
    product = {
        "name": "HP Color LaserJet Pro MFP M283fdw",
        "brand": "HP",
        "category": "Electronics",
        "type": "Multi-function Laser Printer",
        "sub_category": "Printers & Imaging Equipment",
        "model_number": "5QK13A",
        "required_certifications": ["Energy Star", "EPEAT Silver"],
        "hazardous_materials": ["Toner Powder"],
        "repairability_score": Decimal("6.50"),
        "status": "ACTIVE",
    }

    score, breakdown = score_product(product, "Energy Star")

    assert score == 28
    assert breakdown == {
        "certification_exact_match": 20,
        "boost_high_repairability": 8,
    }


def test_no_matching_signals():
    product = {
        "name": "Laptop",
        "brand": "Dell",
        "category": "Electronics",
        "type": "Laptop",
        "sub_category": "Laptops & Notebooks",
        "model_number": "XPS13",
        "required_certifications": [],
        "hazardous_materials": [],
        "repairability_score": None,
        "status": "ARCHIVED",
    }

    score, breakdown = score_product(
        product,
        "banana",
    )

    assert score == 0
    assert breakdown == {}
