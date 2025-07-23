"""
Enterprise Telegram Bot - Bot Factory

This module is responsible for creating and configuring the main
Telegram bot application instance, including all handlers and middleware.
"""

import logging
from telegram.ext import Application, Defaults
from telegram.constants import ParseMode

from src.config import BOT_TOKEN
from src.plugins import PluginManager

logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    """Post-initialization callback for the application."""
    logger.info("🔧 Post-initialization complete")


async def post_shutdown(application: Application) -> None:
    """Post-shutdown callback for the application."""
    logger.info("🔧 Post-shutdown complete")


async def create_application() -> Application:
    """Create and configure the Telegram application with plugin system.

    Returns:
        The configured Application instance.
    """
    logger.info("🚀 Creating bot application...")

    # Set default settings for the bot
    defaults = Defaults(
        parse_mode=ParseMode.MARKDOWN,
    )

    # Create the Application instance
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .defaults(defaults)
        .concurrent_updates(True)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # TEMPORARY: Skip plugin system for debugging
    logger.info("⚠️ DEBUGGING MODE: Skipping plugin system initialization")
    
    # Add a simple /start handler for testing
    from telegram import Update
    from telegram.ext import CommandHandler, ContextTypes
    
    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /start command."""
        await update.message.reply_text("🤖 Bot is working! Plugin system disabled for debugging.")
    
    application.add_handler(CommandHandler("start", start_command))
    
    logger.info("✅ Basic bot application created (plugin system disabled)")
    return application


async def shutdown_application(application: Application) -> None:
    """Gracefully shut down the application and its components."""
    logger.info("⏳ Shutting down application...")

    plugin_manager: PluginManager = application.bot_data.get("plugin_manager")
    if plugin_manager:
        await plugin_manager.shutdown_all_plugins()

    # You can add other shutdown logic here, e.g., closing database pools

    logger.info("👋 Application shut down complete.")
