from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import get_supabase
import logging

logger = logging.getLogger(__name__)

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer)
):
    """
    Validates the Supabase JWT and returns the user.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authorization token provided",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        supabase = get_supabase()
        response = supabase.auth.get_user(credentials.credentials)

        if response is None or response.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"}
            )

        return response.user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate token",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def require_admin(user = Depends(get_current_user)):
    """
    Extends get_current_user — also checks for admin role.
    """
    app_metadata = getattr(user, "app_metadata", {}) or {}
    role = app_metadata.get("role", "user")

    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return user


async def optional_auth(
    credentials: HTTPAuthorizationCredentials = Depends(bearer)
):
    """
    Returns user if token is present and valid.
    Returns None if no token provided.
    """
    if credentials is None:
        return None

    try:
        supabase = get_supabase()
        response = supabase.auth.get_user(credentials.credentials)
        return response.user if response and response.user else None
    except Exception:
        return None


def get_user_id(user) -> str:
    """
    Helper that safely extracts the user ID string.
    """
    return str(user.id)