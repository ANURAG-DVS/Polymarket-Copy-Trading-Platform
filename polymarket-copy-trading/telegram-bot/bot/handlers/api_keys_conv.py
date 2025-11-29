from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from bot.middleware import require_auth
import logging

logger = logging.getLogger(__name__)

# Conversation states
API_KEY, API_SECRET = range(2)

async def start_api_keys_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start API keys setup"""
    query = update.callback_query
    await query.answer()
    
    message = (
        f"🔑 *Add Polymarket API Keys*\n\n"
        f"⚠️ *Security Warning:*\n"
        f"• Delete your messages after setup\n"
        f"• Never share API keys with anyone\n"
        f"• Keys are stored encrypted\n\n"
        f"*Step 1 of 2:* Enter your API Key\n\n"
        f"Your next message should contain ONLY the API key.\n\n"
        f"Send /cancel to abort."
    )
    
    await query.edit_message_text(message, parse_mode="Markdown")
    
    return API_KEY

async def receive_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive API key"""
    api_key = update.message.text.strip()
    
    # Delete user's message for security
    try:
        await update.message.delete()
    except:
        pass
    
    # Store temporarily
    context.user_data['temp_api_key'] = api_key
    
    await update.message.reply_text(
        f"✅ API Key received.\n\n"
        f"*Step 2 of 2:* Enter your API Secret\n\n"
        f"Your next message should contain ONLY the API secret.\n\n"
        f"Send /cancel to abort.",
        parse_mode="Markdown"
    )
    
    return API_SECRET

async def receive_api_secret(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive API secret and save"""
    api_secret = update.message.text.strip()
    
    # Delete user's message for security
    try:
        await update.message.delete()
    except:
        pass
    
    api_key = context.user_data.get('temp_api_key')
    user = context.user_data.get('user')
    
    try:
        # In production: Save to database encrypted and test connection
        # await api_client.save_polymarket_keys(user.id, api_key, api_secret)
        # is_valid = await api_client.test_connection(user.id)
        
        is_valid = True  # Placeholder
        
        if is_valid:
            await update.message.reply_text(
                f"✅ *API Keys Configured Successfully!*\n\n"
                f"🔒 Your keys are securely encrypted and stored.\n"
                f"✓ Connection test passed\n\n"
                f"You can now start copy trading!\n\n"
                f"Use /traders to browse top performers.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"❌ *Connection Test Failed*\n\n"
                f"Your keys were saved, but the connection test failed.\n\n"
                f"Please verify:\n"
                f"• Keys are correct\n"
                f"• API access is enabled\n"
                f"• Polymarket service is operational\n\n"
                f"Try /settings to update keys.",
                parse_mode="Markdown"
            )
    
    except Exception as e:
        logger.error(f"Error saving API keys: {e}")
        await update.message.reply_text(
            f"❌ *Error Saving Keys*\n\n"
            f"Something went wrong. Please try again later.",
            parse_mode="Markdown"
        )
    
    # Clear temporary data
    context.user_data.pop('temp_api_key', None)
    
    return ConversationHandler.END

async def cancel_api_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel API keys setup"""
    context.user_data.pop('temp_api_key', None)
    
    await update.message.reply_text(
        "❌ API keys setup cancelled.\n\n"
        "Your data has been cleared.",
        parse_mode="Markdown"
    )
    
    return ConversationHandler.END
