import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Telegram bot configuration"""
    
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    USE_WEBHOOK = os.getenv("USE_TELEGRAM_WEBHOOK", "false").lower() == "true"
    WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL")
    
    # Backend API
    BACKEND_API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # JWT
    JWT_SECRET = os.getenv("JWT_SECRET")
    JWT_ALGORITHM = "HS256"
    
    # Admin users (telegram IDs)
    ADMIN_TELEGRAM_IDS = [
        int(id.strip())
        for id in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",")
        if id.strip()
    ]

config = Config()
