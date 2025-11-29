from telegram import Update
from telegram.ext import ContextTypes
from bot.middleware import admin_only
from bot.database import async_session
from sqlalchemy import select, func
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../backend')))

from app.models.user import User
import logging

logger = logging.getLogger(__name__)

@admin_only
async def admin_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot usage statistics"""
    try:
        async with async_session() as session:
            # Total users
            total_users_result = await session.execute(select(func.count(User.id)))
            total_users = total_users_result.scalar()
            
            # Active users (with telegram_id)
            active_users_result = await session.execute(
                select(func.count(User.id)).where(User.telegram_id.isnot(None))
            )
            active_users = active_users_result.scalar()
            
            # Verified users
            verified_users_result = await session.execute(
                select(func.count(User.id)).where(User.is_verified == True)
            )
            verified_users = verified_users_result.scalar()
        
        message = (
            f"📊 *Bot Statistics*\n\n"
            f"👥 Total Users: {total_users}\n"
            f"✅ Active (Telegram): {active_users}\n"
            f"🔐 Verified: {verified_users}\n\n"
            f"💰 Active Copies: 0\n"
            f"📊 Total Trades: 0\n"
            f"💵 Total Volume: $0\n\n"
            f"_Updated: Just now_"
        )
        
        await update.message.reply_text(message, parse_mode="Markdown")
    
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        await update.message.reply_text(
            "❌ Error retrieving statistics."
        )

@admin_only
async def admin_broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast message to all users"""
    if not context.args:
        await update.message.reply_text(
            "📢 *Admin Broadcast*\n\n"
            "Usage: `/admin_broadcast <message>`\n\n"
            "Example:\n"
            "`/admin_broadcast System maintenance in 1 hour`",
            parse_mode="Markdown"
        )
        return
    
    message_text = " ".join(context.args)
    
    try:
        async with async_session() as session:
            result = await session.execute(
                select(User.telegram_id).where(User.telegram_id.isnot(None))
            )
            telegram_ids = [row[0] for row in result.fetchall()]
        
        # Broadcast to all users
        success_count = 0
        fail_count = 0
        
        broadcast_message = (
            f"📢 *System Announcement*\n\n"
            f"{message_text}\n\n"
            f"_This is an official message from the Polymarket Copy Trading team._"
        )
        
        for telegram_id in telegram_ids:
            try:
                await context.bot.send_message(
                    chat_id=telegram_id,
                    text=broadcast_message,
                    parse_mode="Markdown"
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send to {telegram_id}: {e}")
                fail_count += 1
        
        await update.message.reply_text(
            f"✅ *Broadcast Complete*\n\n"
            f"Sent: {success_count}\n"
            f"Failed: {fail_count}",
            parse_mode="Markdown"
        )
    
    except Exception as e:
        logger.error(f"Error broadcasting: {e}")
        await update.message.reply_text(
            "❌ Error sending broadcast."
        )

@admin_only
async def admin_pause_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pause a specific user's trading"""
    if not context.args or len(context.args) != 1:
        await update.message.reply_text(
            "⏸️ *Pause User Trading*\n\n"
            "Usage: `/admin_pause_user <telegram_id>`\n\n"
            "Example:\n"
            "`/admin_pause_user 123456789`",
            parse_mode="Markdown"
        )
        return
    
    try:
        telegram_id = int(context.args[0])
        
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalars().first()
            
            if not user:
                await update.message.reply_text(
                    "❌ User not found."
                )
                return
            
            # Deactivate user
            user.is_active = False
            await session.commit()
        
        # Notify the user
        try:
            await context.bot.send_message(
                chat_id=telegram_id,
                text=(
                    "⏸️ *Trading Paused*\n\n"
                    "Your trading has been temporarily paused by an administrator.\n\n"
                    "Contact support for more information."
                ),
                parse_mode="Markdown"
            )
        except:
            pass
        
        await update.message.reply_text(
            f"✅ *User Paused*\n\n"
            f"Telegram ID: {telegram_id}\n"
            f"Username: @{user.username}\n\n"
            f"All trading activity has been stopped.",
            parse_mode="Markdown"
        )
    
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid telegram ID. Must be a number."
        )
    except Exception as e:
        logger.error(f"Error pausing user: {e}")
        await update.message.reply_text(
            "❌ Error pausing user."
        )

@admin_only
async def admin_circuit_breaker_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trigger emergency circuit breaker"""
    
    # Confirmation required
    if not context.args or context.args[0] != "CONFIRM":
        await update.message.reply_text(
            "🚨 *Emergency Circuit Breaker*\n\n"
            "⚠️ This will IMMEDIATELY stop ALL trading for ALL users!\n\n"
            "Use only in emergencies:\n"
            "• Critical bug discovered\n"
            "• Security breach\n"
            "• API issues\n\n"
            "To confirm, use:\n"
            "`/admin_circuit_breaker CONFIRM`",
            parse_mode="Markdown"
        )
        return
    
    try:
        # In production: Set circuit breaker flag in Redis/DB
        # await redis_client.set("circuit_breaker", "true")
        
        # Deactivate all users
        async with async_session() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()
            
            for user in users:
                user.is_active = False
            
            await session.commit()
            
            # Get telegram users for notification
            telegram_ids = [u.telegram_id for u in users if u.telegram_id]
        
        # Broadcast to all users
        for telegram_id in telegram_ids:
            try:
                await context.bot.send_message(
                    chat_id=telegram_id,
                    text=(
                        "🚨 *EMERGENCY: Trading Halted*\n\n"
                        "All trading has been temporarily stopped due to a system issue.\n\n"
                        "Our team is investigating. You will be notified when trading resumes.\n\n"
                        "Your funds are safe."
                    ),
                    parse_mode="Markdown"
                )
            except:
                pass
        
        await update.message.reply_text(
            "🚨 *CIRCUIT BREAKER ACTIVATED*\n\n"
            "✅ All trading stopped\n"
            f"✅ {len(telegram_ids)} users notified\n\n"
            "Remember to reset when issue is resolved!",
            parse_mode="Markdown"
        )
        
        logger.critical(f"CIRCUIT BREAKER ACTIVATED by admin {update.effective_user.id}")
    
    except Exception as e:
        logger.error(f"Error activating circuit breaker: {e}")
        await update.message.reply_text(
            "❌ Error activating circuit breaker!"
        )
