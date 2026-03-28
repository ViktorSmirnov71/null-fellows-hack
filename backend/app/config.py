from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Required
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str

    # Redis
    redis_url: str = "redis://localhost:6379"

    # AI engine endpoints
    ai_model_url: str = "http://localhost:8001"
    ai_sentiment_url: str = "http://localhost:8001/sentiment"
    ai_allocator_url: str = "http://localhost:8001/allocate"
    ai_backtest_url: str = "http://localhost:8001/backtest"
    ai_model_api_key: Optional[str] = None

    # External data APIs
    fred_api_key: Optional[str] = None
    kurthapy_api_key: Optional[str] = None
    alpha_vantage_api_key: Optional[str] = None
    market_data_api_key: Optional[str] = None

    # App config
    run_scheduler: bool = False
    environment: str = "development"

    model_config = {
        "env_file": ".env",
        "extra": "ignore"    # ignore any .env keys not listed here
    }


settings = Settings()