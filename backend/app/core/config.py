"""Configuration Predator Brain."""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Predator Brain"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "predator-brain-secret-change-in-production"

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/predator_db"

    # APIs
    FOOTBALL_DATA_API_KEY: str = ""
    THE_ODDS_API_KEY: str = ""
    API_FOOTBALL_KEY: str = ""

    # CORS
    CORS_ORIGINS: list = ["http://localhost:3001", "http://localhost:3000"]

    # Modèle
    CSV_DATA_DIR: str = "data/raw"
    MODEL_RETRAIN_INTERVAL_HOURS: int = 24
    MIN_MATCHES_TO_TRAIN: int = 200

    # Bankroll defaults
    DEFAULT_INITIAL_BANKROLL: float = 10_000.0
    DEFAULT_KELLY_FRACTION: float = 0.25
    DEFAULT_MAX_STAKE_PCT: float = 0.05

    class Config:
        env_file = ".env"
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
