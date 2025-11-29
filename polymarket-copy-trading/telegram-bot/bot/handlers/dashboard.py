from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.middleware import require_auth
from bot.api_client import api_client
import logging

logger = logging.getLogger(__name__)

@require_auth
async def dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user dashboard with stats"""
    user = context.user_data.get('user')
    
    try:
        # In production, fetch real data from API
        # data = await api_client.get_dashboard(user_token)
        
        message = (
            f"📊 *Your Portfolio*\n\n"
            f"💰 Total P&L: +$0.00\n"
            f"📈 7-day Change: +0%\n"
            f"📉 Sparkline: ▁▂▃▅▇ (7d)\n\n"
            f"👥 Active Copies: 0\n"
            f"📂 Open Positions: 0\n"
            f"💵 Available Balance: $0.00\n"
            f"🔒 Locked Balance: $0.00\n\n"
            f"_Connect your Polymarket API keys to start trading_"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("👥 View Copies", callback_data="view_copies"),
                InlineKeyboardButton("📂 View Positions", callback_data="view_positions")
            ],
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="refresh_dashboard"),
                InlineKeyboardButton("◀️ Menu", callback_data="back_to_menu")
            ]
        ]
        
        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    except Exception as e:
        logger.error(f"Error in dashboard_command: {e}")
        await update.message.reply_text(
            "❌ Failed to load dashboard.\n\nPlease try again later."
        )

async def refresh_dashboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Refresh dashboard"""
    query = update.callback_query
    await query.answer("Refreshing...")
    
    message = (
        f"📊 *Your Portfolio* (Updated)\n\n"
        f"💰 Total P&L: +$0.00\n"
        f"📈 7-day Change: +0%\n"
        f"📉 Sparkline: ▁▂▃▅▇ (7d)\n\n"
        f"👥 Active Copies: 0\n"
        f"📂 Open Positions: 0\n"
        f"💵 Available Balance: $0.00\n"
        f"🔒 Locked Balance: $0.00\n\n"
        f"_Connect your Polymarket API keys to start trading_"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("👥 View Copies", callback_data="view_copies"),
            InlineKeyboardButton("📂 View Positions", callback_data="view_positions")
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_dashboard"),
            InlineKeyboardButton("◀️ Menu", callback_data="back_to_menu")
        ]
    ]
    
    await query.edit_message_text(
        message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
