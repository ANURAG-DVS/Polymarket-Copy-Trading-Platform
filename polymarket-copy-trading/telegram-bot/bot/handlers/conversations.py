from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from bot.middleware import require_auth
import logging

logger = logging.getLogger(__name__)

# Conversation states
COPY_PERCENTAGE, MAX_INVESTMENT, CONFIRM = range(3)

async def start_copy_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start copy trader conversation flow"""
    query = update.callback_query
    await query.answer()
    
    # Extract trader ID
    trader_id = int(query.data.split("_")[-1])
    context.user_data['copy_trader_id'] = trader_id
    
    await query.edit_message_text(
        f"📋 *Copy Trader Setup*\n\n"
        f"Trader: `0x{trader_id:04d}...`\n\n"
        f"*Step 1 of 3: Copy Percentage*\n\n"
        f"Enter the percentage of this trader's positions you want to copy.\n\n"
        f"Example: `5` (for 5%)\n"
        f"Range: 0.1% - 100%\n\n"
        f"Send /cancel to abort.",
        parse_mode="Markdown"
    )
    
    return COPY_PERCENTAGE

async def receive_copy_percentage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive copy percentage input"""
    try:
        percentage = float(update.message.text)
        
        if percentage < 0.1 or percentage > 100:
            await update.message.reply_text(
                "❌ *Invalid percentage!*\n\n"
                "Please enter a value between 0.1 and 100.",
                parse_mode="Markdown"
            )
            return COPY_PERCENTAGE
        
        context.user_data['copy_percentage'] = percentage
        
        await update.message.reply_text(
            f"✅ Copy percentage set to {percentage}%\n\n"
            f"*Step 2 of 3: Maximum Investment*\n\n"
            f"Enter the maximum amount (in USD) you want to invest per trade.\n\n"
            f"Example: `100` (for $100)\n\n"
            f"Send /cancel to abort.",
            parse_mode="Markdown"
        )
        
        return MAX_INVESTMENT
    
    except ValueError:
        await update.message.reply_text(
            "❌ *Invalid input!*\n\n"
            "Please enter a number (e.g., 5 for 5%).",
            parse_mode="Markdown"
        )
        return COPY_PERCENTAGE

async def receive_max_investment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive max investment input"""
    try:
        max_investment = float(update.message.text.replace("$", "").replace(",", ""))
        
        if max_investment <= 0:
            await update.message.reply_text(
                "❌ *Invalid amount!*\n\n"
                "Please enter a positive number.",
                parse_mode="Markdown"
            )
            return MAX_INVESTMENT
        
        context.user_data['max_investment'] = max_investment
        
        # Show confirmation
        trader_id = context.user_data['copy_trader_id']
        percentage = context.user_data['copy_percentage']
        
        message = (
            f"📋 *Confirm Copy Settings*\n\n"
            f"Trader: `0x{trader_id:04d}...`\n"
            f"Copy %: {percentage}%\n"
            f"Max Investment: ${max_investment:,.2f}\n\n"
            f"*Example:*\n"
            f"If this trader buys $1,000, you'll copy ${percentage * 10:,.2f}\n"
            f"(capped at your max of ${max_investment:,.2f})\n\n"
            f"Confirm?"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, Start Copying", callback_data=f"confirm_copy_yes"),
                InlineKeyboardButton("❌ Cancel", callback_data=f"confirm_copy_no")
            ]
        ]
        
        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return CONFIRM
    
    except ValueError:
        await update.message.reply_text(
            "❌ *Invalid input!*\n\n"
            "Please enter a number (e.g., 100 for $100).",
            parse_mode="Markdown"
        )
        return MAX_INVESTMENT

async def confirm_copy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle copy confirmation"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "confirm_copy_yes":
        # Execute copy relationship creation
        trader_id = context.user_data['copy_trader_id']
        percentage = context.user_data['copy_percentage']
        max_investment = context.user_data['max_investment']
        
        try:
            # Call API to create copy relationship
            # In production: await api_client.create_copy_relationship(...)
            
            await query.edit_message_text(
                f"✅ *Copy Relationship Created!*\n\n"
                f"You're now copying trader `0x{trader_id:04d}...`\n\n"
                f"📊 Settings:\n"
                f"• Copy %: {percentage}%\n"
                f"• Max Investment: ${max_investment:,.2f}\n\n"
                f"You'll receive notifications when trades are executed.\n\n"
                f"Use /copies to manage your copy relationships.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error creating copy relationship: {e}")
            await query.edit_message_text(
                "❌ *Failed to create copy relationship.*\n\n"
                "Please try again later or contact support.",
                parse_mode="Markdown"
            )
    else:
        await query.edit_message_text(
            "❌ Copy setup cancelled.\n\n"
            "Use /traders to browse traders again.",
            parse_mode="Markdown"
        )
    
    # Clear user data
    context.user_data.clear()
    
    return ConversationHandler.END

async def cancel_copy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel copy flow"""
    context.user_data.clear()
    
    await update.message.reply_text(
        "❌ Copy setup cancelled.\n\n"
        "Use /traders to browse traders again."
    )
    
    return ConversationHandler.END
