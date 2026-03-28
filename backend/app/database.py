from supabase import create_client, Client
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# --- Singletons ---
_anon_client: Client | None = None
_service_client: Client | None = None


def get_supabase() -> Client:
    """
    Returns the anon client.
    Use this in routers — respects RLS, user context only.
    """
    global _anon_client
    if _anon_client is None:
        _anon_client = create_client(
            settings.supabase_url,
            settings.supabase_anon_key
        )
    return _anon_client


def get_service_supabase() -> Client:
    """
    Returns the service client.
    Use this in services + scheduler only — bypasses RLS entirely.
    Never expose this to routers.
    """
    global _service_client
    if _service_client is None:
        _service_client = create_client(
            settings.supabase_url,
            settings.supabase_service_key
        )
    return _service_client


async def check_connection() -> bool:
    """
    Lightweight health check — called on startup.
    Confirms both clients can reach Supabase before
    the app starts accepting requests.
    """
    try:
        client = get_service_supabase()
        client.table("asset_registry").select("ticker").limit(1).execute()
        logger.info("Supabase connection OK")
        return True
    except Exception as e:
        logger.error(f"Supabase connection failed: {e}")
        return False