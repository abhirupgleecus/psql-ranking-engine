import asyncio
from collections import Counter
from decimal import Decimal
from pathlib import Path
import sys

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from app.database import AsyncSessionLocal
from app.models import Product


EXPECTED_CATEGORIES = {
    "electronics",
    "footwear",
    "clothing",
    "kitchen",
    "fitness",
}


def build_product(
    product_id: str,
    name: str,
    brand: str,
    category: str,
    tags: list[str],
    description: str,
    price: str,
    rating: str,
    review_count: int,
    in_stock: bool,
) -> dict:
    return {
        "id": product_id,
        "name": name,
        "brand": brand,
        "category": category,
        "tags": tags,
        "description": description,
        "price": Decimal(price),
        "rating": Decimal(rating),
        "review_count": review_count,
        "in_stock": in_stock,
    }


PRODUCTS = [
    build_product(
        "00000000-0000-0000-0000-000000000001",
        "Sony WH-1000XM5 Wireless Headphones",
        "Sony",
        "electronics",
        ["wireless", "noise-cancelling", "headphones", "bluetooth"],
        "Flagship over-ear headphones with adaptive noise cancelling and long battery life.",
        "349.99",
        "4.80",
        420,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000002",
        "Bose QuietComfort Ultra Headphones",
        "Bose",
        "electronics",
        ["wireless", "noise-cancelling", "headphones", "travel"],
        "Premium wireless headphones tuned for comfort on long flights and daily commutes.",
        "429.99",
        "4.70",
        210,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000003",
        "Apple AirPods Pro 2",
        "Apple",
        "electronics",
        ["wireless", "earbuds", "bluetooth", "noise-cancelling"],
        "Compact earbuds with strong transparency mode and seamless pairing across Apple devices.",
        "249.99",
        "4.60",
        980,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000004",
        "Samsung Galaxy Buds 3 Pro",
        "Samsung",
        "electronics",
        ["wireless", "earbuds", "bluetooth", "android"],
        "Wireless earbuds designed for Samsung phones with punchy sound and secure fit.",
        "199.99",
        "4.40",
        160,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000005",
        "JBL Flip 6 Portable Speaker",
        "JBL",
        "electronics",
        ["wireless", "speaker", "bluetooth", "portable"],
        "Portable speaker built for pool days, road trips, and easy wireless playback.",
        "129.99",
        "4.50",
        310,
        False,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000006",
        "Anker Soundcore Motion Plus Speaker",
        "Anker",
        "electronics",
        ["wireless", "speaker", "bluetooth", "value"],
        "Value-focused speaker with clear mids and enough volume for a small room.",
        "99.99",
        "4.30",
        95,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000007",
        "Logitech MX Master 3S Mouse",
        "Logitech",
        "electronics",
        ["wireless", "mouse", "productivity", "office"],
        "Ergonomic wireless mouse with quiet clicks and excellent battery endurance.",
        "109.99",
        "4.80",
        650,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000008",
        "Dell XPS 13 Laptop",
        "Dell",
        "electronics",
        ["laptop", "ultrabook", "productivity", "portable"],
        "Compact premium laptop with a bright display and dependable all-day performance.",
        "1199.99",
        "4.70",
        140,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000009",
        "Amazon Kindle Paperwhite",
        "Amazon",
        "electronics",
        ["ereader", "portable", "reading", "travel"],
        "Water-resistant e-reader with a crisp screen that feels great for bedtime reading.",
        "149.99",
        "4.60",
        500,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000010",
        "Sony Bravia 55 OLED TV",
        "Sony",
        "electronics",
        ["television", "oled", "streaming", "home theater"],
        "OLED television with deep contrast, smooth motion, and a polished streaming experience.",
        "1499.99",
        "4.70",
        180,
        False,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000011",
        "Nike Air Max 270",
        "Nike",
        "footwear",
        ["running", "cushioned", "air max", "lifestyle"],
        "Popular Nike sneaker that blends visible Air cushioning with easy everyday comfort.",
        "159.99",
        "4.70",
        430,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000012",
        "Nike Revolution 7 Running Shoes",
        "Nike",
        "footwear",
        ["running", "lightweight", "training", "budget"],
        "Entry-level running shoes with a soft foam ride for short daily miles.",
        "74.99",
        "4.50",
        150,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000013",
        "Adidas Ultraboost Light",
        "Adidas",
        "footwear",
        ["running", "boost", "cushioning", "road"],
        "Responsive Adidas running shoes with plush underfoot feel for longer efforts.",
        "189.99",
        "4.80",
        320,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000014",
        "Adidas Samba OG Sneakers",
        "Adidas",
        "footwear",
        ["casual", "classic", "indoor", "streetwear"],
        "Classic low-profile sneakers that work equally well with denim and track pants.",
        "109.99",
        "4.60",
        210,
        False,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000015",
        "Puma Velocity Nitro 3",
        "Puma",
        "footwear",
        ["running", "nitro", "training", "road"],
        "Fast-feeling daily trainer with energetic foam and a smooth forefoot transition.",
        "139.99",
        "4.40",
        85,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000016",
        "New Balance 574 Core",
        "New Balance",
        "footwear",
        ["casual", "heritage", "suede", "everyday"],
        "Heritage New Balance favorite with versatile styling and reliable step-in comfort.",
        "89.99",
        "4.60",
        260,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000017",
        "Asics Gel-Kayano 31",
        "Asics",
        "footwear",
        ["running", "stability", "marathon", "support"],
        "Stability running shoe built to keep longer training runs feeling controlled and smooth.",
        "164.99",
        "4.70",
        130,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000018",
        "Nike Metcon 9 Training Shoes",
        "Nike",
        "footwear",
        ["training", "gym", "crossfit", "lifting"],
        "Stable training shoes with a broad base for lifting, rope climbs, and circuits.",
        "149.99",
        "4.50",
        110,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000019",
        "Under Armour Charged Assert 10",
        "Under Armour",
        "footwear",
        ["running", "budget", "everyday", "mesh"],
        "Affordable everyday running option with breathable mesh and a forgiving ride.",
        "79.99",
        "4.30",
        70,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000020",
        "Hoka Clifton 9 Running Shoes",
        "Hoka",
        "footwear",
        ["running", "cushioning", "road", "daily trainer"],
        "Highly cushioned running shoes that stay surprisingly light for daily mileage.",
        "144.99",
        "4.80",
        290,
        False,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000021",
        "Nike Dri-FIT Legend Tee",
        "Nike",
        "clothing",
        ["training", "dri-fit", "t-shirt", "gym"],
        "Moisture-wicking training tee that works well for lifting sessions and hot runs.",
        "29.99",
        "4.60",
        240,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000022",
        "Nike Club Fleece Hoodie",
        "Nike",
        "clothing",
        ["hoodie", "fleece", "casual", "sportswear"],
        "Soft fleece hoodie with a relaxed cut that layers easily over training gear.",
        "59.99",
        "4.70",
        190,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000023",
        "Adidas Essentials Track Jacket",
        "Adidas",
        "clothing",
        ["track", "jacket", "casual", "warmup"],
        "Lightweight track jacket for warmups, travel days, and easy street styling.",
        "64.99",
        "4.50",
        125,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000024",
        "Lululemon ABC Jogger",
        "Lululemon",
        "clothing",
        ["jogger", "athleisure", "stretch", "travel"],
        "Polished jogger with stretch fabric that works for flights, errands, and casual office days.",
        "128.00",
        "4.80",
        150,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000025",
        "Under Armour HeatGear Compression Shirt",
        "Under Armour",
        "clothing",
        ["compression", "training", "baselayer", "gym"],
        "Close-fitting base layer that stays cool during fast intervals and hard circuits.",
        "34.99",
        "4.40",
        90,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000026",
        "Levi's 501 Original Jeans",
        "Levi's",
        "clothing",
        ["denim", "classic", "everyday", "straight fit"],
        "Classic straight-leg jeans with the lived-in feel people expect from Levi's.",
        "69.99",
        "4.70",
        510,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000027",
        "Patagonia Better Sweater Fleece",
        "Patagonia",
        "clothing",
        ["fleece", "sweater", "outdoor", "layering"],
        "Cozy fleece layer that fits right into cool-weather commutes and weekend hikes.",
        "139.00",
        "4.60",
        170,
        False,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000028",
        "Uniqlo Airism Polo Shirt",
        "Uniqlo",
        "clothing",
        ["polo", "breathable", "airism", "workwear"],
        "Breathable polo with a clean drape that works well in warm offices and travel.",
        "39.90",
        "4.50",
        140,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000029",
        "Nike Sportswear Club Joggers",
        "Nike",
        "clothing",
        ["joggers", "casual", "sportswear", "fleece"],
        "Everyday joggers with tapered legs and brushed fabric for casual comfort.",
        "54.99",
        "4.60",
        220,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000030",
        "Adidas Adicolor Classics Trefoil Tee",
        "Adidas",
        "clothing",
        ["t-shirt", "casual", "trefoil", "streetwear"],
        "Soft cotton tee that leans into retro Adidas styling without feeling costume-like.",
        "34.99",
        "4.50",
        118,
        False,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000031",
        "Ninja Professional Plus Blender",
        "Ninja",
        "kitchen",
        ["blender", "smoothie", "countertop", "ice crushing"],
        "Powerful blender that handles frozen fruit, soups, and quick weekday smoothies.",
        "119.99",
        "4.70",
        410,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000032",
        "Vitamix Explorian E310 Blender",
        "Vitamix",
        "kitchen",
        ["blender", "smoothie", "premium", "countertop"],
        "Premium blender with excellent texture control for soups, sauces, and nut butters.",
        "349.95",
        "4.80",
        220,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000033",
        "Instant Pot Duo 7-in-1 Cooker",
        "Instant Pot",
        "kitchen",
        ["pressure cooker", "multicooker", "meal prep", "weeknight"],
        "Dependable multicooker that cuts down weeknight cleanup and speeds up batch cooking.",
        "99.95",
        "4.70",
        860,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000034",
        "Cuisinart 14-Cup Food Processor",
        "Cuisinart",
        "kitchen",
        ["food processor", "prep", "slicing", "countertop"],
        "Large-capacity food processor that makes slicing, shredding, and dough work easier.",
        "199.95",
        "4.60",
        170,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000035",
        "KitchenAid Artisan Stand Mixer",
        "KitchenAid",
        "kitchen",
        ["mixer", "baking", "countertop", "dough"],
        "Iconic stand mixer with enough torque for cookies, bread dough, and weekend baking.",
        "449.99",
        "4.80",
        540,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000036",
        "Ninja Air Fryer Pro",
        "Ninja",
        "kitchen",
        ["air fryer", "crispy", "countertop", "weeknight"],
        "Compact air fryer that turns out crisp fries and quick proteins with minimal fuss.",
        "129.99",
        "4.60",
        300,
        False,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000037",
        "Breville Barista Express Espresso Machine",
        "Breville",
        "kitchen",
        ["espresso", "coffee", "barista", "countertop"],
        "Home espresso machine that balances approachable controls with cafe-style results.",
        "749.95",
        "4.70",
        260,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000038",
        "OXO Good Grips Chef Knife",
        "OXO",
        "kitchen",
        ["knife", "prep", "cutlery", "essentials"],
        "Comfortable chef knife for everyday prep with a secure grip and easy control.",
        "39.99",
        "4.40",
        80,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000039",
        "Cuisinart Stainless Steel Toaster",
        "Cuisinart",
        "kitchen",
        ["toaster", "breakfast", "countertop", "small appliance"],
        "Two-slice toaster with straightforward controls and a clean stainless finish.",
        "49.95",
        "4.30",
        95,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000040",
        "NutriBullet Pro 900 Blender",
        "NutriBullet",
        "kitchen",
        ["blender", "smoothie", "compact", "personal"],
        "Compact blender aimed at fast smoothies and easy cleanup in smaller kitchens.",
        "89.99",
        "4.50",
        205,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000041",
        "Fitbit Charge 6 Fitness Tracker",
        "Fitbit",
        "fitness",
        ["fitness tracker", "wearable", "heart rate", "recovery"],
        "Slim fitness tracker that keeps daily activity, heart rate, and sleep trends visible.",
        "159.95",
        "4.50",
        230,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000042",
        "Garmin Forerunner 265",
        "Garmin",
        "fitness",
        ["running watch", "gps", "wearable", "training"],
        "Training-focused GPS watch with strong battery life and useful pace guidance.",
        "449.99",
        "4.80",
        180,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000043",
        "Bowflex SelectTech 552 Dumbbells",
        "Bowflex",
        "fitness",
        ["strength", "dumbbells", "home gym", "adjustable"],
        "Adjustable dumbbells that replace a rack of weights for compact home gyms.",
        "429.00",
        "4.80",
        640,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000044",
        "TRX All-in-One Suspension Trainer",
        "TRX",
        "fitness",
        ["suspension", "training", "bodyweight", "portable"],
        "Portable suspension trainer that makes hotel rooms and park workouts more useful.",
        "189.95",
        "4.60",
        120,
        False,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000045",
        "Theragun Prime Massage Gun",
        "Therabody",
        "fitness",
        ["massage gun", "recovery", "therapy", "muscle"],
        "Recovery tool that targets sore legs, tight shoulders, and post-lift stiffness.",
        "299.00",
        "4.70",
        200,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000046",
        "Nike Training Mat 2.0",
        "Nike",
        "fitness",
        ["yoga mat", "training", "floor", "studio"],
        "Durable floor mat for stretching, core circuits, and bodyweight training sessions.",
        "44.99",
        "4.40",
        75,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000047",
        "Adidas Resistance Bands Set",
        "Adidas",
        "fitness",
        ["resistance bands", "training", "home gym", "mobility"],
        "Versatile band set for warmups, glute work, and travel-friendly resistance sessions.",
        "24.99",
        "4.50",
        160,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000048",
        "Peloton Cycling Shoes",
        "Peloton",
        "fitness",
        ["cycling", "spin", "indoor", "cardio"],
        "Indoor cycling shoes with a snug fit that clip in quickly for spin sessions.",
        "125.00",
        "4.30",
        88,
        False,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000049",
        "Manduka Pro Yoga Mat",
        "Manduka",
        "fitness",
        ["yoga mat", "premium", "studio", "grip"],
        "Dense yoga mat with excellent grip and long-wearing support for daily practice.",
        "138.00",
        "4.80",
        340,
        True,
    ),
    build_product(
        "00000000-0000-0000-0000-000000000050",
        "Hyperice Hypervolt Go 2",
        "Hyperice",
        "fitness",
        ["massage gun", "recovery", "portable", "muscle"],
        "Portable percussion massager that is easy to toss in a gym bag after tough sessions.",
        "199.00",
        "4.60",
        130,
        True,
    ),
]


def validate_seed_data(products: list[dict]) -> None:
    if len(products) < 50:
        raise ValueError("Seed data must include at least 50 products.")

    ids = [product["id"] for product in products]
    if len(ids) != len(set(ids)):
        raise ValueError("Product IDs must be unique.")

    name_brand_pairs = [
        (product["name"], product["brand"])
        for product in products
    ]
    if len(name_brand_pairs) != len(set(name_brand_pairs)):
        raise ValueError("Product (name, brand) pairs must be unique.")

    category_counts = Counter(product["category"] for product in products)

    if set(category_counts) != EXPECTED_CATEGORIES:
        raise ValueError(
            "Seed data must use exactly these categories: "
            f"{sorted(EXPECTED_CATEGORIES)}."
        )

    too_small_categories = [
        category
        for category, count in category_counts.items()
        if count < 8
    ]
    if too_small_categories:
        raise ValueError(
            "Every category must contain at least 8 products. "
            f"Too small: {too_small_categories}"
        )

    boosted_products = [
        product
        for product in products
        if product["rating"] >= Decimal("4.50")
        and product["review_count"] >= 100
    ]
    if len(boosted_products) < 10:
        raise ValueError(
            "Seed data must include at least 10 products with "
            "rating >= 4.5 and review_count >= 100."
        )

    out_of_stock_products = [
        product
        for product in products
        if not product["in_stock"]
    ]
    if len(out_of_stock_products) < 5:
        raise ValueError(
            "Seed data must include at least 5 out-of-stock products."
        )


async def seed_products() -> None:
    validate_seed_data(PRODUCTS)

    async with AsyncSessionLocal() as session:
        before_count = await session.scalar(
            select(func.count()).select_from(Product)
        )

        insert_stmt = (
            pg_insert(Product)
            .values(PRODUCTS)
            .on_conflict_do_nothing(
                index_elements=["name", "brand"],
            )
        )

        await session.execute(insert_stmt)
        await session.commit()

        after_count = await session.scalar(
            select(func.count()).select_from(Product)
        )

    inserted_count = int(after_count or 0) - int(before_count or 0)

    print(f"Seed validation passed for {len(PRODUCTS)} products.")
    print(f"Products before seed: {before_count}")
    print(f"Products after seed: {after_count}")
    print(f"Inserted this run: {inserted_count}")


if __name__ == "__main__":
    asyncio.run(seed_products())
