from telegram import Update
from telegram.ext import ContextTypes
from bot.middleware import require_auth
import logging

logger = logging.getLogger(__name__)

@require_auth
async def traders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top traders"""
    await update.message.reply_text(
        "🏆 *Top Traders* (Last 7 Days)\n\n"
        "Loading top performing traders...\n\n"
        "_Feature coming soon_",
        parse_mode="Markdown"
    )

@require_auth
async def dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user dashboard"""
    user = context.user_data.get('user')
    
    await update.message.reply_text(
        f"📊 *Dashboard - {user.username}*\n\n"
        f"💰 Total P&L: $0.00\n"
        f"📈 7-day Change: +0%\n"
        f"👥 Active Copies: 0\n"
        f"📂 Open Positions: 0\n"
        f"💵 Available Balance: $0.00\n\n"
        f"_Connect your Polymarket API keys in settings to start trading_",
        parse_mode="Markdown"
    )

@require_auth
async def copies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show copy relationships"""
    await update.message.reply_text(
        "👥 *My Copy Relationships*\n\n"
        "You're not copying any traders yet.\n\n"
        "Use /traders to browse top performers and start copying!",
        parse_mode="Markdown"
    )

@require_auth
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show settings"""
    user = context.user_data.get('user')
    
    polymarket_status = "✅ Connected" if user.polymarket_api_key else "❌ Not configured"
    
    await update.message.reply_text(
        f"⚙️ *Account Settings*\n\n"
        f"*Profile:*\n"
        f"Username: {user.username}\n"
        f"Email: {user.email}\n"
        f"Subscription: {user.subscription_tier.value}\n\n"
        f"*Polymarket API:*\n"
        f"Status: {polymarket_status}\n\n"
        f"*Notifications:*\n"
        f"Email: ✅ Enabled\n"
        f"Telegram: ✅ Enabled\n\n"
        f"_For full settings, visit the web app_",
        parse_mode="Markdown"
    )
