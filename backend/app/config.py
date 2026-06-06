"""WC2026 Betting Predictor - Configuration"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/wc2026.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # CORS - comma-separated list of allowed origins
    cors_origins: str = "http://localhost:5173,http://localhost:3000,https://wc2026-044.pages.dev"

    # The Odds API
    odds_api_key: str = ""

    # NewsAPI
    news_api_key: str = ""

    # API-Football
    football_api_key: str = ""

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Scheduler intervals (minutes)
    odds_update_interval: int = 360      # 6h: 500 req/month free → ~120/month
    news_update_interval: int = 60       # RSS: no quota limit
    injury_update_interval: int = 480    # 8h: 100 req/day free → ~75/day
    prediction_recalc_interval: int = 360

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
