from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.middleware import require_auth
from bot.api_client import api_client
import logging

logger = logging.getLogger(__name__)

@require_auth
async def copies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's copy relationships"""
    user = context.user_data.get('user')
    
    try:
        # In production: data = await api_client.get_copy_relationships(user_token)
        
        # Placeholder data
        copies = []
        
        if not copies:
            message = (
                "👥 *My Copy Relationships*\n\n"
                "You're not copying any traders yet.\n\n"
                "_Use /traders to browse top performers and start copying!_"
            )
            
            keyboard = [
                [InlineKeyboardButton("🏆 Browse Traders", callback_data="top_traders")],
                [InlineKeyboardButton("◀️ Back to Menu", callback_data="back_to_menu")]
            ]
        else:
            message = "👥 *My Copy Relationships*\n\n"
            keyboard = []
            
            for i, copy in enumerate(copies, 1):
                trader_address = copy['trader_address']
                short_address = f"{trader_address[:6]}...{trader_address[-4:]}"
                percentage = copy['copy_percentage']
                pnl = copy['total_pnl']
                status = copy['status']
                
                status_emoji = "🟢" if status == "active" else "⏸️"
                pnl_emoji = "📈" if pnl >= 0 else "📉"
                
                message += (
                    f"{i}. {status_emoji} `{short_address}`\n"
                    f"   Copy: {percentage}% | P&L: {pnl_emoji} ${pnl:+.2f}\n\n"
                )
                
                keyboard.append([
                    InlineKeyboardButton(
                        "⏸️ Pause" if status == "active" else "▶️ Resume",
                        callback_data=f"toggle_copy_{copy['id']}"
                    ),
                    InlineKeyboardButton("✏️ Edit", callback_data=f"edit_copy_{copy['id']}"),
                    InlineKeyboardButton("🛑 Stop", callback_data=f"stop_copy_{copy['id']}")
                ])
            
            keyboard.append([InlineKeyboardButton("◀️ Back to Menu", callback_data="back_to_menu")])
        
        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    except Exception as e:
        logger.error(f"Error in copies_command: {e}")
        await update.message.reply_text(
            "❌ Failed to load copy relationships.\n\nPlease try again later."
        )

async def toggle_copy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle copy relationship status"""
    query = update.callback_query
    await query.answer()
    
    copy_id = int(query.data.split("_")[-1])
    
    # In production: Call API to toggle status
    
    await query.answer("✅ Status updated!", show_alert=True)
    
    # Refresh the list
    message = "👥 *My Copy Relationships*\n\n_Status updated_"
    
    await query.edit_message_text(message, parse_mode="Markdown")

async def stop_copy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop copying a trader"""
    query = update.callback_query
    
    copy_id = int(query.data.split("_")[-1])
    
    # Show confirmation
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, Stop", callback_data=f"confirm_stop_{copy_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data="view_copies")
        ]
    ]
    
    await query.edit_message_text(
        "⚠️ *Stop Copying?*\n\n"
        "Are you sure you want to stop copying this trader?\n\n"
        "_Your existing positions will remain open._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def confirm_stop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm stopping copy relationship"""
    query = update.callback_query
    await query.answer()
    
    copy_id = int(query.data.split("_")[-1])
    
    # In production: Call API to stop relationship
    
    await query.edit_message_text(
        "✅ *Copy Relationship Stopped*\n\n"
        "You're no longer copying this trader.\n\n"
        "_Your existing open positions remain unchanged._",
        parse_mode="Markdown"
    )

async def view_copies_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View copies from callback"""
    query = update.callback_query
    await query.answer()
    
    message = (
        "👥 *My Copy Relationships*\n\n"
        "You're not copying any traders yet.\n\n"
        "_Use /traders to browse top performers!_"
    )
    
    keyboard = [
        [InlineKeyboardButton("🏆 Browse Traders", callback_data="top_traders")],
        [InlineKeyboardButton("◀️ Back to Menu", callback_data="back_to_menu")]
    ]
    
    await query.edit_message_text(
        message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
