from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.middleware import require_auth
import logging

logger = logging.getLogger(__name__)

@require_auth
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show settings menu"""
    user = context.user_data.get('user')
    
    message = (
        f"⚙️ *Settings*\n\n"
        f"Manage your account and trading preferences."
    )
    
    keyboard = [
        [InlineKeyboardButton("📧 Email Notifications", callback_data="settings_email")],
        [InlineKeyboardButton("💰 Trading Limits", callback_data="settings_limits")],
        [InlineKeyboardButton("🔑 Polymarket API Keys", callback_data="settings_keys")],
        [InlineKeyboardButton("📱 Account Info", callback_data="settings_account")],
        [InlineKeyboardButton("◀️ Back to Menu", callback_data="back_to_menu")]
    ]
    
    await update.message.reply_text(
        message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle settings menu callbacks"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "settings_email":
        await show_email_settings(update, context)
    elif query.data == "settings_limits":
        await show_trading_limits(update, context)
    elif query.data == "settings_keys":
        await show_polymarket_keys(update, context)
    elif query.data == "settings_account":
        await show_account_info(update, context)

async def show_email_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show email notification settings"""
    query = update.callback_query
    user = context.user_data.get('user')
    
    # Get user preferences (placeholder)
    email_trade = True
    email_daily = False
    email_security = True
    
    message = (
        f"📧 *Email Notifications*\n\n"
        f"Trade Executions: {'✅' if email_trade else '❌'}\n"
        f"Daily Summary: {'✅' if email_daily else '❌'}\n"
        f"Security Alerts: {'✅' if email_security else '❌'}\n\n"
        f"_Toggle notifications by clicking the buttons below._"
    )
    
    keyboard = [
        [InlineKeyboardButton(
            f"{'✅' if email_trade else '☐'} Trade Executions",
            callback_data="toggle_email_trade"
        )],
        [InlineKeyboardButton(
            f"{'✅' if email_daily else '☐'} Daily Summary",
            callback_data="toggle_email_daily"
        )],
        [InlineKeyboardButton(
            f"{'✅' if email_security else '☐'} Security Alerts",
            callback_data="toggle_email_security"
        )],
        [InlineKeyboardButton("◀️ Back to Settings", callback_data="back_to_settings")]
    ]
    
    await query.edit_message_text(
        message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_trading_limits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show trading limits settings"""
    query = update.callback_query
    
    # Get user preferences (placeholder)
    default_copy = 5.0
    daily_limit = 100.0
    weekly_limit = 500.0
    slippage = 1.0
    
    message = (
        f"💰 *Trading Limits*\n\n"
        f"Default Copy %: {default_copy}%\n"
        f"Daily Limit: ${daily_limit:,.0f}\n"
        f"Weekly Limit: ${weekly_limit:,.0f}\n"
        f"Slippage Tolerance: {slippage}%\n\n"
        f"_Click a setting to edit._"
    )
    
    keyboard = [
        [InlineKeyboardButton("✏️ Edit Copy %", callback_data="edit_copy_percentage")],
        [InlineKeyboardButton("✏️ Edit Daily Limit", callback_data="edit_daily_limit")],
        [InlineKeyboardButton("✏️ Edit Weekly Limit", callback_data="edit_weekly_limit")],
        [InlineKeyboardButton("✏️ Edit Slippage", callback_data="edit_slippage")],
        [InlineKeyboardButton("◀️ Back to Settings", callback_data="back_to_settings")]
    ]
    
    await query.edit_message_text(
        message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_polymarket_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show Polymarket API keys status"""
    query = update.callback_query
    user = context.user_data.get('user')
    
    is_configured = bool(user.polymarket_api_key)
    
    message = (
        f"🔑 *Polymarket API Keys*\n\n"
        f"Status: {'✅ Connected' if is_configured else '❌ Not configured'}\n\n"
    )
    
    if is_configured:
        message += (
            f"Your API keys are securely stored.\n\n"
            f"_Keys are encrypted in our database._"
        )
        keyboard = [
            [InlineKeyboardButton("🔄 Test Connection", callback_data="test_api_keys")],
            [InlineKeyboardButton("🗑️ Revoke Keys", callback_data="revoke_api_keys")],
            [InlineKeyboardButton("◀️ Back to Settings", callback_data="back_to_settings")]
        ]
    else:
        message += (
            f"Add your Polymarket API keys to start trading.\n\n"
            f"⚠️ *Security Note:*\n"
            f"This conversation is encrypted, but always be cautious with API keys.\n\n"
            f"📚 [How to get API keys](https://docs.polymarket.com)"
        )
        keyboard = [
            [InlineKeyboardButton("➕ Add API Keys", callback_data="add_api_keys")],
            [InlineKeyboardButton("◀️ Back to Settings", callback_data="back_to_settings")]
        ]
    
    await query.edit_message_text(
        message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )

async def show_account_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show account information"""
    query = update.callback_query
    user = context.user_data.get('user')
    
    message = (
        f"📱 *Account Information*\n\n"
        f"*Profile:*\n"
        f"Email: {user.email}\n"
        f"Username: @{user.username}\n"
        f"Subscription: {user.subscription_tier.value.title()}\n\n"
        f"*Usage Stats:*\n"
        f"Active Copies: 0/{'5' if user.subscription_tier.value == 'free' else '25'}\n"
        f"Total Trades: 0\n"
        f"Member Since: {user.created_at.strftime('%B %Y')}\n\n"
        f"🌐 [Open Web Dashboard](https://yourapp.com/dashboard)"
    )
    
    keyboard = [
        [InlineKeyboardButton("🚪 Logout", callback_data="logout_confirm")],
        [InlineKeyboardButton("◀️ Back to Settings", callback_data="back_to_settings")]
    ]
    
    await query.edit_message_text(
        message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )

async def back_to_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to settings menu"""
    query = update.callback_query
    await query.answer()
    
    message = (
        f"⚙️ *Settings*\n\n"
        f"Manage your account and trading preferences."
    )
    
    keyboard = [
        [InlineKeyboardButton("📧 Email Notifications", callback_data="settings_email")],
        [InlineKeyboardButton("💰 Trading Limits", callback_data="settings_limits")],
        [InlineKeyboardButton("🔑 Polymarket API Keys", callback_data="settings_keys")],
        [InlineKeyboardButton("📱 Account Info", callback_data="settings_account")],
        [InlineKeyboardButton("◀️ Back to Menu", callback_data="back_to_menu")]
    ]
    
    await query.edit_message_text(
        message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
