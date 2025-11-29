from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../backend')))

from app.models.user import User
from bot.database import async_session
import logging

logger = logging.getLogger(__name__)

async def get_user_by_telegram_id(telegram_id: int) -> User:
    """Get user from database by telegram ID"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalars().first()

def require_auth(func):
    """Decorator to require authentication"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        telegram_id = update.effective_user.id
        
        # Check if user exists
        user = await get_user_by_telegram_id(telegram_id)
        
        if not user:
            await update.message.reply_text(
                "⚠️ You need to register first!\n\n"
                "Use /start to create your account."
            )
            return
        
        if not user.is_active:
            await update.message.reply_text(
                "⚠️ Your account is inactive.\n\n"
                "Please contact support."
            )
            return
        
        # Store user in context for use in handler
        context.user_data['user'] = user
        
        return await func(update, context)
    
    return wrapper

def admin_only(func):
    """Decorator to restrict access to admins"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        from bot.config import config
        
        telegram_id = update.effective_user.id
        
        if telegram_id not in config.ADMIN_TELEGRAM_IDS:
            await update.message.reply_text(
                "⚠️ This command is only available to administrators."
            )
            return
        
        return await func(update, context)
    
    return wrapper
