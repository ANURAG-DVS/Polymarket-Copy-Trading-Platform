"""Core configuration settings"""

from pydantic_settings import BaseSettings
from pydantic import PostgresDsn, RedisDsn, validator
from typing import Optional, List
import secrets


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Polymarket Copy Trading Platform"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    RELOAD: bool = True
    
    # Database
    DATABASE_URL: PostgresDsn
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    
    # Redis
    REDIS_URL: RedisDsn
    REDIS_CACHE_TTL: int = 3600
    
    # Celery
    CELERY_BROKER_URL: RedisDsn
    CELERY_RESULT_BACKEND: RedisDsn
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_TIME_LIMIT: int = 300
    
    # Security
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    MASTER_ENCRYPTION_KEY: str
    BCRYPT_ROUNDS: int = 12
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "PATCH"]
    CORS_HEADERS: List[str] = ["*"]
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    # --------------------------------------------------
    # Polygon Blockchain
    # --------------------------------------------------
    POLYGON_RPC_URL: Optional[str] = None
    POLYGON_RPC_WSS: Optional[str] = None
    POLYGON_RPC_FALLBACKS: Optional[List[str]] = None
    
    BLOCKCHAIN_POLLING_INTERVAL: int = 12
    BLOCKCHAIN_ENABLE_WEBSOCKET: bool = True
    BLOCKCHAIN_RECOVERY_LOOKBACK: int = 100
    
    @validator('POLYGON_RPC_FALLBACKS', pre=True)
    def parse_fallback_urls(cls, v):
        if isinstance(v, str):
            return [url.strip() for url in v.split(',') if url.strip()]
        return v or []
    
    # --------------------------------------------------
    # API Keys Encryption
    # --------------------------------------------------
    
    # Polymarket Contracts
    POLYMARKET_CTF_EXCHANGE: str = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
    POLYMARKET_CONDITIONAL_TOKENS: str = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
    USDC_CONTRACT: str = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    
    # Polymarket API
    POLYMARKET_API_URL: str = "https://clob.polymarket.com"
    POLYMARKET_API_KEY: Optional[str] = None
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # Trade Execution
    MAX_SLIPPAGE_PERCENT: float = 1.0
    MAX_GAS_PRICE_GWEI: int = 500
    DEFAULT_GAS_LIMIT: int = 300000
    TRADE_CONFIRMATION_BLOCKS: int = 2
    
    # Risk Management
    MAX_TRADE_SIZE_USD: int = 10000
    MAX_DAILY_TRADES_PER_USER: int = 100
    MAX_POSITION_SIZE_PERCENT: int = 20
    MIN_BALANCE_THRESHOLD_USD: int = 10
    
    # Monitoring
    SENTRY_DSN: Optional[str] = None
    SENTRY_TRACES_SAMPLE_RATE: float = 1.0
    SENTRY_ENVIRONMENT: str = "development"
    
    # Telegram
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_WEBHOOK_URL: Optional[str] = None
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = None
    
    # Email
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: str = "noreply@polymarketcopy.com"
    
    # Feature Flags
    ENABLE_2FA: bool = True
    ENABLE_EMAIL_NOTIFICATIONS: bool = False
    ENABLE_TELEGRAM_NOTIFICATIONS: bool = True
    ENABLE_TRADE_EXECUTION: bool = True
    ENABLE_LEADERBOARD: bool = True
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
