from telegram import Update
from telegram.ext import ContextTypes
import logging
import traceback

logger = logging.getLogger(__name__)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    logger.error(traceback.format_exc())
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ *Oops! Something went wrong.*\n\n"
                "Our team has been notified. Please try again later.\n\n"
                "If the problem persists, use /help for support.",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Failed to send error message: {e}")
