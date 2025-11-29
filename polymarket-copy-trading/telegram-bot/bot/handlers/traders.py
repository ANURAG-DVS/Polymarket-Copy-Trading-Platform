from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.middleware import require_auth
from bot.api_client import api_client
import logging

logger = logging.getLogger(__name__)

@require_auth
async def traders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top traders with inline keyboard"""
    try:
        # Fetch top traders from API
        data = await api_client.get_traders_leaderboard(limit=10)
        
        if not data or not data.get('traders'):
            await update.message.reply_text(
                "❌ No traders found.\n\nPlease try again later.",
                parse_mode="Markdown"
            )
            return
        
        traders = data['traders']
        
        # Build message
        message = "🏆 *Top Traders* (Last 7 Days)\n\n"
        keyboard = []
        
        medals = ["🥇", "🥈", "🥉"]
        
        for i, trader in enumerate(traders):
            rank = i + 1
            medal = medals[i] if i < 3 else f"#{rank}"
            
            # Truncate address
            address = trader['wallet_address']
            short_address = f"{address[:6]}...{address[-4:]}"
            
            # Format P&L
            pnl = trader['pnl_7d']
            pnl_symbol = "+" if pnl >= 0 else ""
            
            message += f"{medal} `{short_address}` | {pnl_symbol}${pnl:,.2f}\n"
            
            # Create buttons for this trader
            keyboard.append([
                InlineKeyboardButton(
                    f"📊 View #{rank}",
                    callback_data=f"view_trader_{trader['id']}"
                ),
                InlineKeyboardButton(
                    f"📋 Copy #{rank}",
                    callback_data=f"copy_trader_{trader['id']}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("◀️ Back to Menu", callback_data="back_to_menu")
        ])
        
        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    except Exception as e:
        logger.error(f"Error in traders_command: {e}")
        await update.message.reply_text(
            "❌ Failed to load traders.\n\nPlease try again later."
        )

async def view_trader_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show trader details"""
    query = update.callback_query
    await query.answer()
    
    # Extract trader ID from callback data
    trader_id = int(query.data.split("_")[-1])
    
    try:
        # Fetch trader details from API (placeholder)
        # In production, call: await api_client.get_trader_details(trader_id)
        
        message = (
            f"📊 *Trader Details*\n\n"
            f"Address: `0x1234...5678`\n\n"
            f"*Performance (7 Days):*\n"
            f"💰 Total P&L: +$1,234.56\n"
            f"📈 Win Rate: 68.5%\n"
            f"📊 Total Trades: 24\n"
            f"💵 Avg Trade Size: $125\n\n"
            f"*Recent Trades:*\n"
            f"• Market A: +$45.20 ✅\n"
            f"• Market B: -$12.50 ❌\n"
            f"• Market C: +$89.30 ✅\n"
        )
        
        keyboard = [
            [InlineKeyboardButton("📋 Copy This Trader", callback_data=f"copy_trader_{trader_id}")],
            [InlineKeyboardButton("◀️ Back to List", callback_data="back_to_traders")]
        ]
        
        await query.edit_message_text(
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    except Exception as e:
        logger.error(f"Error viewing trader: {e}")
        await query.edit_message_text(
            "❌ Failed to load trader details.\n\nPlease try again."
        )

async def back_to_traders_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to traders list"""
    query = update.callback_query
    await query.answer()
    
    # Re-trigger traders command
    try:
        data = await api_client.get_traders_leaderboard(limit=10)
        traders = data['traders']
        
        message = "🏆 *Top Traders* (Last 7 Days)\n\n"
        keyboard = []
        medals = ["🥇", "🥈", "🥉"]
        
        for i, trader in enumerate(traders):
            rank = i + 1
            medal = medals[i] if i < 3 else f"#{rank}"
            address = trader['wallet_address']
            short_address = f"{address[:6]}...{address[-4:]}"
            pnl = trader['pnl_7d']
            pnl_symbol = "+" if pnl >= 0 else ""
            
            message += f"{medal} `{short_address}` | {pnl_symbol}${pnl:,.2f}\n"
            
            keyboard.append([
                InlineKeyboardButton(f"📊 View #{rank}", callback_data=f"view_trader_{trader['id']}"),
                InlineKeyboardButton(f"📋 Copy #{rank}", callback_data=f"copy_trader_{trader['id']}")
            ])
        
        keyboard.append([InlineKeyboardButton("◀️ Back to Menu", callback_data="back_to_menu")])
        
        await query.edit_message_text(
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Error going back to traders: {e}")
