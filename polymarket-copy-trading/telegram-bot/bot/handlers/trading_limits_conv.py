from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from bot.middleware import require_auth
import logging

logger = logging.getLogger(__name__)

# Conversation states for different settings
EDIT_VALUE = 0

async def start_edit_copy_percentage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start editing copy percentage"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['editing'] = 'copy_percentage'
    
    message = (
        f"✏️ *Edit Default Copy Percentage*\n\n"
        f"Current: 5.0%\n\n"
        f"Enter new percentage (0.1 - 100):\n\n"
        f"Example: `10` for 10%\n\n"
        f"Send /cancel to abort."
    )
    
    await query.edit_message_text(message, parse_mode="Markdown")
    
    return EDIT_VALUE

async def start_edit_daily_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start editing daily limit"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['editing'] = 'daily_limit'
    
    message = (
        f"✏️ *Edit Daily Spending Limit*\n\n"
        f"Current: $100\n\n"
        f"Enter new limit in USD:\n\n"
        f"Example: `200` for $200\n\n"
        f"Send /cancel to abort."
    )
    
    await query.edit_message_text(message, parse_mode="Markdown")
    
    return EDIT_VALUE

async def start_edit_weekly_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start editing weekly limit"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['editing'] = 'weekly_limit'
    
    message = (
        f"✏️ *Edit Weekly Spending Limit*\n\n"
        f"Current: $500\n\n"
        f"Enter new limit in USD:\n\n"
        f"Example: `1000` for $1,000\n\n"
        f"Send /cancel to abort."
    )
    
    await query.edit_message_text(message, parse_mode="Markdown")
    
    return EDIT_VALUE

async def start_edit_slippage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start editing slippage tolerance"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['editing'] = 'slippage'
    
    message = (
        f"✏️ *Edit Slippage Tolerance*\n\n"
        f"Current: 1.0%\n\n"
        f"Enter new tolerance (0 - 10):\n\n"
        f"Example: `2` for 2%\n\n"
        f"Send /cancel to abort."
    )
    
    await query.edit_message_text(message, parse_mode="Markdown")
    
    return EDIT_VALUE

async def receive_limit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and validate limit value"""
    editing = context.user_data.get('editing')
    
    try:
        value = float(update.message.text.replace("$", "").replace(",", ""))
        
        # Validate based on what's being edited
        if editing == 'copy_percentage':
            if value < 0.1 or value > 100:
                await update.message.reply_text(
                    "❌ Invalid percentage! Must be between 0.1 and 100.\n\n"
                    "Please try again or send /cancel."
                )
                return EDIT_VALUE
            field_name = "Default Copy Percentage"
            formatted_value = f"{value}%"
        
        elif editing == 'daily_limit':
            if value <= 0:
                await update.message.reply_text(
                    "❌ Invalid amount! Must be greater than 0.\n\n"
                    "Please try again or send /cancel."
                )
                return EDIT_VALUE
            field_name = "Daily Limit"
            formatted_value = f"${value:,.0f}"
        
        elif editing == 'weekly_limit':
            if value <= 0:
                await update.message.reply_text(
                    "❌ Invalid amount! Must be greater than 0.\n\n"
                    "Please try again or send /cancel."
                )
                return EDIT_VALUE
            field_name = "Weekly Limit"
            formatted_value = f"${value:,.0f}"
        
        elif editing == 'slippage':
            if value < 0 or value > 10:
                await update.message.reply_text(
                    "❌ Invalid tolerance! Must be between 0 and 10.\n\n"
                    "Please try again or send /cancel."
                )
                return EDIT_VALUE
            field_name = "Slippage Tolerance"
            formatted_value = f"{value}%"
        
        # Save to database (placeholder)
        # await api_client.update_preference(user.id, editing, value)
        
        await update.message.reply_text(
            f"✅ *{field_name} Updated!*\n\n"
            f"New value: {formatted_value}\n\n"
            f"Use /settings to view all settings.",
            parse_mode="Markdown"
        )
        
        # Clear editing state
        context.user_data.pop('editing', None)
        
        return ConversationHandler.END
    
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid input! Please enter a number.\n\n"
            "Example: `100` or `2.5`\n\n"
            "Send /cancel to abort."
        )
        return EDIT_VALUE

async def cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel editing"""
    context.user_data.pop('editing', None)
    
    await update.message.reply_text(
        "❌ Edit cancelled.\n\n"
        "Use /settings to access settings menu."
    )
    
    return ConversationHandler.END
