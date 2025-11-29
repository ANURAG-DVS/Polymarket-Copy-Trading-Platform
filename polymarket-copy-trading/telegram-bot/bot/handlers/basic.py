from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../backend')))

from app.models.user import User
from bot.database import async_session
from bot.middleware import get_user_by_telegram_id
import logging

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - User registration"""
    telegram_id = update.effective_user.id
    username = update.effective_user.username or f"user_{telegram_id}"
    first_name = update.effective_user.first_name or "User"
    
    # Check if user already exists
    user = await get_user_by_telegram_id(telegram_id)
    
    if user:
        # Existing user - show main menu
        await update.message.reply_text(
            f"👋 Welcome back, {first_name}!\n\n"
            f"What would you like to do?",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        # New user - create account
        try:
            async with async_session() as session:
                # Create new user
                new_user = User(
                    email=f"telegram_{telegram_id}@temp.com",
                    username=username,
                    hashed_password="telegram_auto",  # Telegram users don't need password
                    telegram_id=telegram_id,
                    full_name=first_name,
                    is_verified=True  # Auto-verify Telegram users
                )
                
                session.add(new_user)
                await session.commit()
                
                logger.info(f"Created new Telegram user: {telegram_id}")
                
                await update.message.reply_text(
                    f"🎉 Welcome to Polymarket Copy Trading, {first_name}!\n\n"
                    f"Your account has been created successfully.\n\n"
                    f"You can now:\n"
                    f"• Browse top traders\n"
                    f"• Set up copy trading\n"
                    f"• Monitor your portfolio\n\n"
                    f"Use /menu to see all available commands.",
                    reply_markup=get_main_menu_keyboard()
                )
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            await update.message.reply_text(
                "❌ Sorry, there was an error creating your account.\n\n"
                "Please try again later or contact support."
            )

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main menu"""
    await update.message.reply_text(
        "📱 *Main Menu*\n\n"
        "Choose an option:",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help information"""
    help_text = """
🤖 *Available Commands*

*Main Commands:*
/start - Register or login
/menu - Show main menu
/help - Show this help message

*Trading Commands:*
/traders - View top traders
/dashboard - View your portfolio
/copies - Manage copy relationships
/settings - Account settings

*Examples:*
• `/traders` - See the top 10 performing traders
• `/dashboard` - Check your P&L and positions
• `/copies` - View and manage who you're copying

*Need Help?*
Contact support or visit our documentation.
    """
    
    await update.message.reply_text(
        help_text,
        parse_mode="Markdown"
    )

def get_main_menu_keyboard():
    """Get main menu inline keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("🏆 Top Traders", callback_data="top_traders"),
            InlineKeyboardButton("📊 My Dashboard", callback_data="my_dashboard")
        ],
        [
            InlineKeyboardButton("👥 My Copies", callback_data="my_copies"),
            InlineKeyboardButton("⚙️ Settings", callback_data="settings")
        ],
        [
            InlineKeyboardButton("❓ Help", callback_data="help")
        ]
    ]
    
    return InlineKeyboardMarkup(keyboard)

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle main menu button callbacks"""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    if callback_data == "top_traders":
        await show_top_traders(update, context)
    elif callback_data == "my_dashboard":
        await show_dashboard(update, context)
    elif callback_data == "my_copies":
        await show_copies(update, context)
    elif callback_data == "settings":
        await show_settings(update, context)
    elif callback_data == "help":
        await help_command(update, context)

async def show_top_traders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top traders (placeholder)"""
    query = update.callback_query
    
    await query.edit_message_text(
        "🏆 *Top Traders*\n\n"
        "Loading top performing traders...\n\n"
        "_This feature will show the leaderboard_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Back to Menu", callback_data="back_to_menu")
        ]])
    )

async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user dashboard (placeholder)"""
    query = update.callback_query
    
    await query.edit_message_text(
        "📊 *My Dashboard*\n\n"
        "Total P&L: $0.00\n"
        "Active Copies: 0\n"
        "Open Positions: 0\n\n"
        "_Connect your Polymarket API keys to start trading_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Back to Menu", callback_data="back_to_menu")
        ]])
    )

async def show_copies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show copy relationships (placeholder)"""
    query = update.callback_query
    
    await query.edit_message_text(
        "👥 *My Copy Relationships*\n\n"
        "You're not copying any traders yet.\n\n"
        "_Browse top traders to start copying!_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Back to Menu", callback_data="back_to_menu")
        ]])
    )

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show settings (placeholder)"""
    query = update.callback_query
    
    await query.edit_message_text(
        "⚙️ *Settings*\n\n"
        "• Polymarket API Keys: ❌ Not configured\n"
        "• Email Notifications: ✅ Enabled\n"
        "• Telegram Notifications: ✅ Enabled\n\n"
        "_Use the web app for full settings_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Back to Menu", callback_data="back_to_menu")
        ]])
    )

async def back_to_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle back to menu button"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📱 *Main Menu*\n\n"
        "Choose an option:",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )
