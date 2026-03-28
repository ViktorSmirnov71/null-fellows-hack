from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import check_connection
from app.config import settings
from app.auth import get_current_user, require_admin, optional_auth, get_user_id
from fastapi import Depends
from app.routers import portfolios
from app.routers import portfolios, signals
from app.database import check_connection
from app.cache import check_cache_connection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Portfolio Backend",
    version="0.1.0",
    description="AI-powered portfolio management backend"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolios.router, prefix="/portfolios", tags=["portfolios"])

@app.on_event("startup")
async def startup():
    logger.info("Starting up...")
    db_ok = await check_connection()
    if not db_ok:
        logger.warning(
            "Supabase unreachable on startup — "
            "check your .env values"
        )


@app.get("/health")
async def health_check():
    db_ok = await check_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "environment": settings.environment
    }

@app.get("/auth/me")
async def get_me(user = Depends(get_current_user)):
    """Test route — confirms token is valid and returns user info."""
    return {
        "id": get_user_id(user),
        "email": user.email,
        "role": (user.app_metadata or {}).get("role", "user")
    }

@app.get("/auth/admin-test")
async def admin_test(user = Depends(require_admin)):
    """Test route — confirms admin role check works."""
    return {
        "message": "you are an admin",
        "email": user.email
    }

@app.get("/auth/optional-test")
async def optional_test(user = Depends(optional_auth)):
    """Test route — works with or without a token."""
    if user:
        return {"message": f"hello {user.email}"}
    return {"message": "hello anonymous"}


@app.on_event("startup")
async def startup():
    logger.info("Starting up...")
    db_ok = await check_connection()
    cache_ok = await check_cache_connection()
    if not db_ok:
        logger.warning("Supabase unreachable on startup — check your .env values")
    if not cache_ok:
        logger.warning("Redis unreachable — caching disabled, app will still run")