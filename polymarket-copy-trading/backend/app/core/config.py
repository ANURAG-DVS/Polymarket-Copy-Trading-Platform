import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    NODE_ENV: str = "development"
    ENVIRONMENT: str = "development"  # development, production, worker
    PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:8500"
    API_URL: str = "http://localhost:8000"
    
    # Database
    DATABASE_URL: str
    
    # JWT
    JWT_SECRET: str
    JWT_REFRESH_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: str = "noreply@polymarket-copy.com"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    
    # Polymarket
    POLYMARKET_API_BASE_URL: str = "https://clob.polymarket.com"
    POLYGON_RPC_URL: str
    
    # Encryption
    MASTER_ENCRYPTION_KEY: str
    
    # Stripe
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    
    # The Graph Protocol
    GRAPH_API_URL: str = "https://api.thegraph.com/subgraphs/name/polymarket/matic-markets-5"
    GRAPH_API_KEY: Optional[str] = None
    
    # Trader Data Configuration
    TRADER_FETCH_INTERVAL: int = 300  # 5 minutes in seconds
    LEADERBOARD_CACHE_TTL: int = 60  # 1 minute
    TRADER_CACHE_TTL: int = 300  # 5 minutes
    MIN_TRADER_TRADES: int = 10
    MIN_TRADER_VOLUME: float = 1000.0
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
