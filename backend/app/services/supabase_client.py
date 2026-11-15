from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_supabase_client: Any = None


def get_supabase_key() -> Optional[str]:
    """Prefers SUPABASE_SERVICE_ROLE_KEY to bypass RLS restrictions on backend."""
    return (
        settings.supabase_service_role_key
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or settings.supabase_key
        or os.getenv("SUPABASE_KEY")
        or settings.supabase_anon_key
        or os.getenv("SUPABASE_ANON_KEY")
    )


def get_supabase_url() -> Optional[str]:
    return settings.supabase_url or os.getenv("SUPABASE_URL")


def get_supabase_client() -> Any:
    """Returns initialized supabase Client or custom REST client with service_role privileges."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    url = get_supabase_url()
    key = get_supabase_key()

    if not url or not key:
        logger.debug("Supabase URL or Key not set, skipping REST client init")
        return None

    try:
        from supabase import Client, create_client
        _supabase_client = create_client(url, key)
        logger.info("Supabase client initialized with service_role/api key")
        return _supabase_client
    except ImportError:
        logger.debug("supabase-py is not installed; direct asyncpg pooler connection is used.")
        return None
