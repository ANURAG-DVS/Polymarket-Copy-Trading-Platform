import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters
)
from bot.config import config

# Import all handlers
from bot.handlers.basic import (
    start_command,
    menu_command,
    help_command,
    handle_menu_callback,
    back_to_menu_callback
)
from bot.handlers.traders import (
    traders_command,
    view_trader_callback,
    back_to_traders_callback
)
from bot.handlers.conversations import (
    start_copy_flow,
    receive_copy_percentage,
    receive_max_investment,
    confirm_copy,
    cancel_copy,
    COPY_PERCENTAGE,
    MAX_INVESTMENT,
    CONFIRM
)
from bot.handlers.dashboard import (
    dashboard_command,
    refresh_dashboard_callback
)
from bot.handlers.copies import (
    copies_command,
    toggle_copy_callback,
    stop_copy_callback,
    confirm_stop_callback,
    view_copies_callback
)
from bot.handlers.status import status_command
from bot.handlers.settings import (
    settings_command,
    settings_callback,
    back_to_settings_callback
)
from bot.handlers.api_keys_conv import (
    start_api_keys_flow,
    receive_api_key,
    receive_api_secret,
    cancel_api_keys,
    API_KEY,
    API_SECRET
)
from bot.handlers.trading_limits_conv import (
    start_edit_copy_percentage,
    start_edit_daily_limit,
    start_edit_weekly_limit,
    start_edit_slippage,
    receive_limit_value,
    cancel_edit,
    EDIT_VALUE
)
from bot.handlers.admin import (
    admin_stats_command,
    admin_broadcast_command,
    admin_pause_user_command,
    admin_circuit_breaker_command
)
from bot.handlers.errors import error_handler

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def post_init(application: Application):
    """Initialize bot after startup"""
    logger.info("Bot initialized successfully")
    
    # Set bot commands
    await application.bot.set_my_commands([
        ("start", "Register or login"),
        ("menu", "Show main menu"),
        ("traders", "View top traders"),
        ("dashboard", "View your portfolio"),
        ("copies", "Manage copy relationships"),
        ("status", "Quick trade status"),
        ("settings", "Account settings"),
        ("help", "Show help")
    ])

async def main():
    """Start the bot"""
    
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set in environment variables")
        return
    
    # Create application
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    
    # ===== BASIC COMMANDS =====
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("traders", traders_command))
    application.add_handler(CommandHandler("dashboard", dashboard_command))
    application.add_handler(CommandHandler("copies", copies_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("settings", settings_command))
    
    # ===== ADMIN COMMANDS =====
    application.add_handler(CommandHandler("admin_stats", admin_stats_command))
    application.add_handler(CommandHandler("admin_broadcast", admin_broadcast_command))
    application.add_handler(CommandHandler("admin_pause_user", admin_pause_user_command))
    application.add_handler(CommandHandler("admin_circuit_breaker", admin_circuit_breaker_command))
    
    # ===== CONVERSATION HANDLERS =====
    
    # Copy trader conversation
    copy_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_copy_flow, pattern="^copy_trader_")],
        states={
            COPY_PERCENTAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_copy_percentage)],
            MAX_INVESTMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_max_investment)],
            CONFIRM: [CallbackQueryHandler(confirm_copy, pattern="^confirm_copy_")]
        },
        fallbacks=[CommandHandler("cancel", cancel_copy)],
        conversation_timeout=300
    )
    application.add_handler(copy_conversation)
    
    # API keys conversation
    api_keys_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_api_keys_flow, pattern="^add_api_keys$")],
        states={
            API_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_api_key)],
            API_SECRET: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_api_secret)]
        },
        fallbacks=[CommandHandler("cancel", cancel_api_keys)],
        conversation_timeout=300
    )
    application.add_handler(api_keys_conversation)
    
    # Trading limits conversations
    edit_copy_percentage_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_edit_copy_percentage, pattern="^edit_copy_percentage$")],
        states={
            EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_limit_value)]
        },
        fallbacks=[CommandHandler("cancel", cancel_edit)],
        conversation_timeout=300
    )
    application.add_handler(edit_copy_percentage_conv)
    
    edit_daily_limit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_edit_daily_limit, pattern="^edit_daily_limit$")],
        states={
            EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_limit_value)]
        },
        fallbacks=[CommandHandler("cancel", cancel_edit)],
        conversation_timeout=300
    )
    application.add_handler(edit_daily_limit_conv)
    
    edit_weekly_limit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_edit_weekly_limit, pattern="^edit_weekly_limit$")],
        states={
            EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_limit_value)]
        },
        fallbacks=[CommandHandler("cancel", cancel_edit)],
        conversation_timeout=300
    )
    application.add_handler(edit_weekly_limit_conv)
    
    edit_slippage_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_edit_slippage, pattern="^edit_slippage$")],
        states={
            EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_limit_value)]
        },
        fallbacks=[CommandHandler("cancel", cancel_edit)],
        conversation_timeout=300
    )
    application.add_handler(edit_slippage_conv)
    
    # ===== CALLBACK QUERY HANDLERS =====
    application.add_handler(CallbackQueryHandler(handle_menu_callback, pattern="^(top_traders|my_dashboard|my_copies|settings|help)$"))
    application.add_handler(CallbackQueryHandler(back_to_menu_callback, pattern="^back_to_menu$"))
    application.add_handler(CallbackQueryHandler(view_trader_callback, pattern="^view_trader_"))
    application.add_handler(CallbackQueryHandler(back_to_traders_callback, pattern="^back_to_traders$"))
    application.add_handler(CallbackQueryHandler(refresh_dashboard_callback, pattern="^refresh_dashboard$"))
    application.add_handler(CallbackQueryHandler(view_copies_callback, pattern="^view_copies$"))
    application.add_handler(CallbackQueryHandler(toggle_copy_callback, pattern="^toggle_copy_"))
    application.add_handler(CallbackQueryHandler(stop_copy_callback, pattern="^stop_copy_"))
    application.add_handler(CallbackQueryHandler(confirm_stop_callback, pattern="^confirm_stop_"))
    application.add_handler(CallbackQueryHandler(settings_callback, pattern="^settings_"))
    application.add_handler(CallbackQueryHandler(back_to_settings_callback, pattern="^back_to_settings$"))
    
    # ===== ERROR HANDLER =====
    application.add_error_handler(error_handler)
    
    # Start bot
    if config.USE_WEBHOOK:
        logger.info(f"Starting bot in webhook mode: {config.WEBHOOK_URL}")
        await application.run_webhook(
            listen="0.0.0.0",
            port=8443,
            url_path=config.TELEGRAM_BOT_TOKEN,
            webhook_url=f"{config.WEBHOOK_URL}/{config.TELEGRAM_BOT_TOKEN}"
        )
    else:
        logger.info("Starting bot in polling mode")
        await application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
