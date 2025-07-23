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

    # Create and configure the Plugin Manager
    plugin_manager = PluginManager()
    plugin_manager.register_application(application)

    # Discover and initialize all plugins
    try:
        await plugin_manager.discover_plugins()
        await plugin_manager.initialize_all_plugins()

        # Register all plugin handlers
        plugin_manager.register_all_handlers()

        # Enable all plugins
        await plugin_manager.enable_all_plugins()

        # Store the plugin manager in the bot context for runtime access
        application.bot_data["plugin_manager"] = plugin_manager

        logger.info("✅ All plugins loaded and handlers registered successfully")

    except Exception as e:
        logger.error(f"❌ Failed to initialize plugin system: {e}", exc_info=True)
        # Fallback: Add basic /start handler if plugin system fails
        from telegram import Update
        from telegram.ext import CommandHandler, ContextTypes
        
        async def fallback_start_command(
            update: Update, context: ContextTypes.DEFAULT_TYPE
        ) -> None:
            """Fallback /start command when plugin system fails."""
            await update.message.reply_text(
                "🤖 Bot is running in fallback mode. Plugin system failed to load."
            )
        
        application.add_handler(CommandHandler("start", fallback_start_command))
        logger.warning("⚠️ Running in fallback mode without plugin system")

    logger.info("✅ Bot application created successfully")
    return application


async def shutdown_application(application: Application) -> None:
    """Gracefully shut down the application and its components."""
    logger.info("⏳ Shutting down application...")

    plugin_manager: PluginManager = application.bot_data.get("plugin_manager")
    if plugin_manager:
        await plugin_manager.shutdown_all_plugins()

    # You can add other shutdown logic here, e.g., closing database pools

    logger.info("👋 Application shut down complete.")
