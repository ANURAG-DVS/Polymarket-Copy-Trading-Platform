"""Telegram bot main entry point"""

import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


async def start_command(update: Update, context):
    """Handle /start command"""
    await update.message.reply_text(
        "Welcome to Polymarket Copy Trading Bot! 🚀\n\n"
        "Available commands:\n"
        "/wallet - Connect your wallet\n"
        "/follow <address> - Follow a trader\n"
        "/leaderboard - View top traders\n"
        "/portfolio - View your positions\n"
        "/settings - Configure settings"
    )


async def help_command(update: Update, context):
    """Handle /help command"""
    await update.message.reply_text(
        "Need help? Visit our documentation or contact support."
    )


async def main():
    """Main bot function"""
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Start bot
    print("Starting Polymarket Copy Trading Bot...")
    await application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    asyncio.run(main())
