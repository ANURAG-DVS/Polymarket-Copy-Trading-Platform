from telegram import Bot
from bot.config import config
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for sending notifications to users"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
    
    async def send_trade_executed(self, telegram_id: int, trade_data: dict):
        """Send trade execution notification"""
        try:
            message = (
                f"✅ *Trade Executed*\n\n"
                f"Copied trader `{trade_data['trader_address']}`\n\n"
                f"Market: {trade_data['market_title']}\n"
                f"Side: {trade_data['side'].upper()}\n"
                f"Amount: ${trade_data['amount_usd']:.2f}\n"
                f"Price: ${trade_data['entry_price']:.3f}\n\n"
                f"Trade ID: #{trade_data['trade_id']}"
            )
            
            await self.bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode="Markdown"
            )
            
            logger.info(f"Sent trade notification to {telegram_id}")
        
        except Exception as e:
            logger.error(f"Failed to send trade notification: {e}")
    
    async def send_position_closed(self, telegram_id: int, position_data: dict):
        """Send position closed notification"""
        try:
            pnl = position_data['realized_pnl']
            pnl_emoji = "📈" if pnl >= 0 else "📉"
            status_emoji = "💰" if pnl >= 0 else "📊"
            
            message = (
                f"{status_emoji} *Position Closed*\n\n"
                f"Market: {position_data['market_title']}\n"
                f"Side: {position_data['side'].upper()}\n\n"
                f"Entry: ${position_data['entry_price']:.3f}\n"
                f"Exit: ${position_data['exit_price']:.3f}\n\n"
                f"{pnl_emoji} P&L: {pnl:+.2f} USD\n\n"
                f"Position ID: #{position_data['position_id']}"
            )
            
            await self.bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode="Markdown"
            )
            
            logger.info(f"Sent position closed notification to {telegram_id}")
        
        except Exception as e:
            logger.error(f"Failed to send position notification: {e}")
    
    async def send_warning(self, telegram_id: int, warning_type: str, message_text: str):
        """Send warning notification"""
        try:
            warnings = {
                "daily_limit": "⚠️ *Daily Limit Warning*\n\n",
                "low_balance": "⚠️ *Low Balance Warning*\n\n",
                "api_error": "⚠️ *API Error*\n\n",
            }
            
            prefix = warnings.get(warning_type, "⚠️ *Warning*\n\n")
            message = prefix + message_text
            
            await self.bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode="Markdown"
            )
            
            logger.info(f"Sent warning notification to {telegram_id}")
        
        except Exception as e:
            logger.error(f"Failed to send warning notification: {e}")
    
    async def send_daily_summary(self, telegram_id: int, summary_data: dict):
        """Send daily trading summary"""
        try:
            message = (
                f"📊 *Daily Summary*\n\n"
                f"Date: {summary_data['date']}\n\n"
                f"💰 Total P&L: {summary_data['total_pnl']:+.2f} USD\n"
                f"📊 Trades: {summary_data['total_trades']}\n"
                f"✅ Wins: {summary_data['winning_trades']}\n"
                f"❌ Losses: {summary_data['losing_trades']}\n\n"
                f"Top Market: {summary_data['top_market']}\n"
                f"Best Trade: +${summary_data['best_trade']:.2f}\n\n"
                f"Use /dashboard for more details."
            )
            
            await self.bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode="Markdown"
            )
            
            logger.info(f"Sent daily summary to {telegram_id}")
        
        except Exception as e:
            logger.error(f"Failed to send daily summary: {e}")

# Usage example (called from backend worker):
# notification_service = NotificationService(bot)
# await notification_service.send_trade_executed(user.telegram_id, trade_data)
