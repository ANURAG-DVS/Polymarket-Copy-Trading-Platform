from telegram import Update
from telegram.ext import ContextTypes
from bot.middleware import require_auth
import logging

logger = logging.getLogger(__name__)

@require_auth
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick trade status"""
    user = context.user_data.get('user')
    
    # In production: Fetch real data from API
    
    message = (
        "⚡ *Quick Status*\n\n"
        f"📂 Open Positions: 0\n"
        f"💰 Today's P&L: $0.00\n"
        f"📊 Last 24h Trades: 0\n\n"
        f"_Use /dashboard for detailed view_"
    )
    
    await update.message.reply_text(message, parse_mode="Markdown")
