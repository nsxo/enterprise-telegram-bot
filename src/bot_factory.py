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


async def create_application() -> Application:
    """
    Create and configure the Telegram bot application instance.

    This function sets up the bot, loads all plugins, registers their
    handlers, and initializes the application.

    Returns:
        The configured Application instance.
    """
    logger.info("🚀 Creating bot application...")

    # Set default settings for the bot
    defaults = Defaults(
        parse_mode=ParseMode.MARKDOWN,
        quote=True,
    )

    # Create the application instance
    application = Application.builder().token(BOT_TOKEN).defaults(defaults).build()

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
        # You might want to handle this more gracefully in production
        # e.g., run with core plugins only or exit

    # --- Register Core Handlers (that are not part of plugins) ---

    # Example: A master error handler
    # from src.handlers import error_handlers
    # application.add_error_handler(error_handlers.master_error_handler)

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
