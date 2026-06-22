"""Elastic client helpers for the future v2.2 search backend.

The client is created lazily so the rest of the application can continue to run
without Elastic-specific dependencies or credentials being present.
"""

from __future__ import annotations

from typing import Any

from app.database import settings


def is_elastic_configured() -> bool:
    return bool(settings.ELASTIC_CLOUD_ID or settings.ELASTIC_URL)


def get_elastic_target() -> str:
    if settings.ELASTIC_CLOUD_ID:
        return settings.ELASTIC_CLOUD_ID
    if settings.ELASTIC_URL:
        return settings.ELASTIC_URL
    raise RuntimeError(
        "Elastic is not configured. Set ELASTIC_CLOUD_ID or ELASTIC_URL."
    )


def _build_auth_kwargs() -> dict[str, Any]:
    if settings.ELASTIC_API_KEY:
        return {"api_key": settings.ELASTIC_API_KEY}

    if settings.ELASTIC_USERNAME and settings.ELASTIC_PASSWORD:
        return {
            "basic_auth": (
                settings.ELASTIC_USERNAME,
                settings.ELASTIC_PASSWORD,
            )
        }

    raise RuntimeError(
        "Elastic credentials are not configured. Set ELASTIC_API_KEY or both "
        "ELASTIC_USERNAME and ELASTIC_PASSWORD."
    )


def create_async_elasticsearch_client():
    """Create an AsyncElasticsearch client using either Cloud ID or URL."""
    try:
        from elasticsearch import AsyncElasticsearch
    except ImportError as exc:
        raise RuntimeError(
            "The Elasticsearch Python client is not installed. "
            "Install project dependencies to enable Elastic features."
        ) from exc

    auth_kwargs = _build_auth_kwargs()
    common_kwargs = {
        "request_timeout": settings.ELASTIC_V2_TIMEOUT_SECONDS,
        **auth_kwargs,
    }

    if settings.ELASTIC_CLOUD_ID:
        return AsyncElasticsearch(
            cloud_id=settings.ELASTIC_CLOUD_ID,
            **common_kwargs,
        )

    if settings.ELASTIC_URL:
        return AsyncElasticsearch(
            settings.ELASTIC_URL,
            **common_kwargs,
        )

    raise RuntimeError(
        "Elastic is not configured. Set ELASTIC_CLOUD_ID or ELASTIC_URL."
    )


async def get_elastic_info() -> dict[str, Any]:
    """Return cluster info for a configured Elastic deployment."""
    client = create_async_elasticsearch_client()
    try:
        return await client.info()
    finally:
        await client.close()
