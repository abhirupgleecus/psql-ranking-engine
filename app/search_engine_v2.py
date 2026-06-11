import re
from typing import Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def normalize_to_tsquery(q: str) -> str:
    """Normalize user input query into a valid prefix-matching tsquery.

    Extracts alphanumeric tokens and joins them with '&' and suffix :*.
    If no alphanumeric tokens exist, returns empty string.
    """
    words = re.findall(r"[a-zA-Z0-9]+", q)
    if not words:
        return ""
    # Join words with '&' and suffix with ':*' for prefix matching
    return " & ".join(f"{word}:*" for word in words)


def enum_value(value: Any) -> str | None:
    """Helper to safely get string value from an enum."""
    if value is None:
        return None
    if hasattr(value, "value"):
        return value.value
    return str(value)


async def search_products_v2(
    db: AsyncSession,
    q: str,
    top_n: int = 10,
    category: str | None = None,
    fallback_enabled: bool = True,
) -> tuple[list[dict[str, Any]], str]:
    """Execute Phase 2 search against PostgreSQL.

    1. Attempts full-text search (FTS) using ts_rank_cd.
    2. If FTS yields 0 results and fallback_enabled is True, falls back to ILIKE.
    3. Returns (list of products, search_mode).
    """
    query_str = q.strip()
    tsquery_val = normalize_to_tsquery(query_str)

    results = []
    search_mode = "fulltext"

    # 1. Primary path: Full-text search
    if tsquery_val:
        fts_sql = text("""
            SELECT
                uuid, status, type, name, category, sub_category, brand, manufacturer,
                upc, variant, model_number, serial_number, model_year, weight_lb, weight_kg,
                dimensions_inches, repairability_score, disassembly_complexity, average_life_span_years,
                energy_efficiency_rating, authorized_needed, special_handling_required, contains_user_data,
                mandatory_data_wipe_needed, required_certifications, market_value, market_value_avgs,
                hazardous_materials, additional_data, created_at, updated_at, goods_type,
                master_uuid, gtin, ean,
                ts_rank_cd(search_vector, to_tsquery('english', :tsquery)) AS rank
            FROM product_master
            WHERE status = 'ACTIVE'
              AND (cast(:category as varchar) IS NULL OR category = :category)
              AND search_vector @@ to_tsquery('english', :tsquery)
            ORDER BY rank DESC, name ASC
            LIMIT :top_n;
        """)

        res = await db.execute(fts_sql, {
            "tsquery": tsquery_val,
            "category": category,
            "top_n": top_n
        })
        rows = res.mappings().all()

        if rows:
            for row in rows:
                p_dict = dict(row)
                p_dict["search_score"] = float(p_dict.pop("rank"))
                p_dict["search_mode"] = "fulltext"
                p_dict["status"] = enum_value(p_dict["status"])
                p_dict["disassembly_complexity"] = enum_value(p_dict["disassembly_complexity"])
                p_dict["goods_type"] = enum_value(p_dict["goods_type"])
                p_dict["required_certifications"] = p_dict["required_certifications"] or []
                p_dict["hazardous_materials"] = p_dict["hazardous_materials"] or []
                results.append(p_dict)
            return results, "fulltext"

    # 2. Fallback path: Wildcard ILIKE search (if enabled and FTS yielded nothing)
    if fallback_enabled:
        search_mode = "wildcard"
        wildcard_pattern = f"%{query_str}%"

        wildcard_sql = text("""
            SELECT
                uuid, status, type, name, category, sub_category, brand, manufacturer,
                upc, variant, model_number, serial_number, model_year, weight_lb, weight_kg,
                dimensions_inches, repairability_score, disassembly_complexity, average_life_span_years,
                energy_efficiency_rating, authorized_needed, special_handling_required, contains_user_data,
                mandatory_data_wipe_needed, required_certifications, market_value, market_value_avgs,
                hazardous_materials, additional_data, created_at, updated_at, goods_type,
                master_uuid, gtin, ean
            FROM product_master
            WHERE status = 'ACTIVE'
              AND (cast(:category as varchar) IS NULL OR category = :category)
              AND (
                  name ILIKE :wildcard OR
                  brand ILIKE :wildcard OR
                  category ILIKE :wildcard OR
                  sub_category ILIKE :wildcard OR
                  type ILIKE :wildcard OR
                  model_number ILIKE :wildcard OR
                  immutable_array_to_string(required_certifications, ' ') ILIKE :wildcard OR
                  immutable_array_to_string(hazardous_materials, ' ') ILIKE :wildcard
              )
            ORDER BY name ASC
            LIMIT :top_n;
        """)


        res = await db.execute(wildcard_sql, {
            "wildcard": wildcard_pattern,
            "category": category,
            "top_n": top_n
        })
        rows = res.mappings().all()

        for row in rows:
            p_dict = dict(row)
            p_dict["search_score"] = 0.0
            p_dict["search_mode"] = "wildcard"
            p_dict["status"] = enum_value(p_dict["status"])
            p_dict["disassembly_complexity"] = enum_value(p_dict["disassembly_complexity"])
            p_dict["goods_type"] = enum_value(p_dict["goods_type"])
            p_dict["required_certifications"] = p_dict["required_certifications"] or []
            p_dict["hazardous_materials"] = p_dict["hazardous_materials"] or []
            results.append(p_dict)

    return results, search_mode
