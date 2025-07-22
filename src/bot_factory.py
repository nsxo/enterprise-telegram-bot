"""
Enterprise Telegram Bot - Application Factory

This module contains the application factory function that creates and configures
the Telegram bot application with all handlers, middleware, and settings.
"""

import logging
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    InvalidCallbackData,
)

from src.config import BOT_TOKEN
from src.handlers import error_handlers, commands, admin, user_interactions, purchases, message_router

logger = logging.getLogger(__name__)


def create_application() -> Application:
    """
    Create and configure the Telegram bot application.
    
    This factory function sets up the complete bot application with all handlers,
    middleware, and configuration needed for production deployment.
    
    Returns:
        Configured Application instance with all handlers registered
    """
    logger.info("🤖 Creating Telegram bot application...")
    
    # Create application with arbitrary callback data support
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .arbitrary_callback_data(True)
        .build()
    )
    
    # ==========================================================================
    # COMMAND HANDLERS
    # ==========================================================================
    
    logger.info("📝 Registering command handlers...")
    
    # User commands
    application.add_handler(CommandHandler("start", commands.enhanced_start_command))
    application.add_handler(CommandHandler("balance", commands.balance_command))
    application.add_handler(CommandHandler("billing", purchases.billing_command))
    
    # Command handlers from commands module
    application.add_handler(CommandHandler("reset", commands.reset_command))
    application.add_handler(CommandHandler("help", commands.help_command))
    application.add_handler(CommandHandler("buy", commands.buy_command))
    application.add_handler(CommandHandler("status", commands.status_command))
    application.add_handler(CommandHandler("time", commands.time_command))
    application.add_handler(CommandHandler("history", commands.purchase_history_command))
    
    # Quick buy command handlers
    application.add_handler(CommandHandler("buy10", commands.buy10_command))
    application.add_handler(CommandHandler("buy25", commands.buy25_command))
    application.add_handler(CommandHandler("buy50", commands.buy50_command))
    
    # Admin commands (all moved to handlers/admin.py)
    application.add_handler(CommandHandler("admin", admin.admin_command))
    application.add_handler(CommandHandler("dashboard", admin.dashboard_command))
    application.add_handler(CommandHandler("settings", admin.settings_command))
    application.add_handler(CommandHandler("products", admin.products_command))
    application.add_handler(CommandHandler("analytics", admin.analytics_command))
    application.add_handler(CommandHandler("users", admin.users_command))
    application.add_handler(CommandHandler("conversations", admin.conversations_command))
    application.add_handler(CommandHandler("broadcast", admin.broadcast_command))
    application.add_handler(CommandHandler("webhook", admin.webhook_command))
    application.add_handler(CommandHandler("system", admin.system_command))
    
    # ==========================================================================
    # CALLBACK QUERY HANDLERS
    # ==========================================================================
    
    logger.info("🔘 Registering callback query handlers...")
    
    # Product and purchase handlers
    application.add_handler(CallbackQueryHandler(purchases.show_products_callback, pattern="^show_products$"))
    application.add_handler(CallbackQueryHandler(purchases.product_type_callback, pattern="^product_type_"))
    application.add_handler(CallbackQueryHandler(purchases.purchase_product_callback, pattern="^purchase_product_"))
    application.add_handler(CallbackQueryHandler(purchases.billing_portal_callback, pattern="^billing_portal$"))
    application.add_handler(CallbackQueryHandler(purchases.quick_buy_callback, pattern="^quick_buy_"))
    application.add_handler(CallbackQueryHandler(purchases.refresh_history_callback, pattern="^refresh_history$"))
    application.add_handler(CallbackQueryHandler(purchases.detailed_history_callback, pattern="^detailed_history$"))
    application.add_handler(CallbackQueryHandler(purchases.email_report_callback, pattern="^email_report$"))
    
    # User interaction handlers
    application.add_handler(CallbackQueryHandler(user_interactions.start_tutorial_callback, pattern="^start_tutorial$"))
    application.add_handler(CallbackQueryHandler(user_interactions.tutorial_step_2_callback, pattern="^tutorial_step_2$"))
    application.add_handler(CallbackQueryHandler(user_interactions.tutorial_step_3_callback, pattern="^tutorial_step_3$"))
    application.add_handler(CallbackQueryHandler(user_interactions.complete_tutorial_callback, pattern="^complete_tutorial$"))
    application.add_handler(CallbackQueryHandler(user_interactions.start_chatting_callback, pattern="^start_chatting$"))
    application.add_handler(CallbackQueryHandler(user_interactions.show_balance_callback, pattern="^show_balance$"))
    application.add_handler(CallbackQueryHandler(user_interactions.show_analytics_callback, pattern="^show_analytics$"))
    application.add_handler(CallbackQueryHandler(user_interactions.refresh_balance_callback, pattern="^refresh_balance$"))
    application.add_handler(CallbackQueryHandler(user_interactions.user_balance_callback, pattern="^user_balance$"))
    application.add_handler(CallbackQueryHandler(user_interactions.user_help_callback, pattern="^user_help$"))
    application.add_handler(CallbackQueryHandler(user_interactions.user_menu_callback, pattern="^user_menu$"))
    
    # Admin callback handlers
    application.add_handler(CallbackQueryHandler(admin.admin_conversations_callback, pattern="^admin_conversations$"))
    application.add_handler(CallbackQueryHandler(admin.admin_dashboard_callback, pattern="^admin_dashboard$"))
    application.add_handler(CallbackQueryHandler(admin.admin_users_callback, pattern="^admin_users$"))
    application.add_handler(CallbackQueryHandler(admin.admin_products_callback, pattern="^admin_products$"))
    application.add_handler(CallbackQueryHandler(admin.admin_main_callback, pattern="^admin_main$"))
    application.add_handler(CallbackQueryHandler(admin.admin_close_callback, pattern="^admin_close$"))
    application.add_handler(CallbackQueryHandler(admin.admin_ban_callback, pattern="^admin_ban_"))
    application.add_handler(CallbackQueryHandler(admin.admin_gift_callback, pattern="^admin_gift_"))
    application.add_handler(CallbackQueryHandler(admin.gift_credits_callback, pattern="^gift_credits_"))
    
    # Admin sub-menu handlers (now implemented in admin module)
    application.add_handler(CallbackQueryHandler(admin.admin_analytics_callback, pattern="^admin_analytics$"))
    application.add_handler(CallbackQueryHandler(admin_billing_callback, pattern="^admin_billing$"))  # Still placeholder
    application.add_handler(CallbackQueryHandler(admin.admin_broadcast_callback, pattern="^admin_broadcast$"))
    application.add_handler(CallbackQueryHandler(admin_mass_gift_callback, pattern="^admin_mass_gift$"))  # Still placeholder
    application.add_handler(CallbackQueryHandler(admin.admin_settings_callback, pattern="^admin_settings$"))
    application.add_handler(CallbackQueryHandler(admin_system_callback, pattern="^admin_system$"))  # Still placeholder
    application.add_handler(CallbackQueryHandler(admin_quick_replies_callback, pattern="^admin_quick_replies$"))  # Still placeholder
    application.add_handler(CallbackQueryHandler(admin_search_callback, pattern="^admin_search$"))  # Still placeholder
    application.add_handler(CallbackQueryHandler(admin_refresh_callback, pattern="^admin_refresh$"))  # Still placeholder
    
    # Additional admin callback handlers for new functionality
    application.add_handler(CallbackQueryHandler(admin.broadcast_all_users_callback, pattern="^broadcast_all_users$"))
    application.add_handler(CallbackQueryHandler(admin.broadcast_active_users_callback, pattern="^broadcast_active_users$"))
    application.add_handler(CallbackQueryHandler(admin.broadcast_compose_callback, pattern="^broadcast_compose$"))
    application.add_handler(CallbackQueryHandler(admin.settings_credits_callback, pattern="^settings_credits$"))
    application.add_handler(CallbackQueryHandler(admin.settings_tutorial_callback, pattern="^settings_tutorial$"))
    
    # Catch-all handler for admin sub-menu items (using placeholder for now)
    application.add_handler(CallbackQueryHandler(error_handlers.admin_placeholder_callback, pattern="^admin_.*"))
    
    # ==========================================================================
    # ERROR HANDLERS
    # ==========================================================================
    
    logger.info("⚠️ Registering error handlers...")
    
    # Add invalid callback data handler
    application.add_handler(CallbackQueryHandler(error_handlers.callback_data_error_handler, pattern=InvalidCallbackData))
    
    # Add catch-all callback handler for debugging (must be last)
    application.add_handler(CallbackQueryHandler(error_handlers.debug_callback_handler))
    
    # ==========================================================================
    # MESSAGE HANDLERS
    # ==========================================================================
    
    logger.info("💬 Registering message handlers...")
    
    # Add message handler (must be last among handlers)
    application.add_handler(MessageHandler(filters.ALL, message_router.master_message_handler))
    
    # ==========================================================================
    # GLOBAL ERROR HANDLER
    # ==========================================================================
    
    logger.info("🚨 Registering global error handler...")
    
    # Add global error handler
    application.add_error_handler(error_handlers.error_handler)
    
    logger.info("✅ Bot application configured successfully")
    logger.info(f"📊 Total handlers registered: {len(application.handlers[0])}")
    
    return application


# Temporary placeholder functions for admin callbacks that need implementation
# These should be moved to the admin module once implemented

async def admin_analytics_callback(update, context):
    """Placeholder for admin analytics callback."""
    await error_handlers.admin_placeholder_callback(update, context)

async def admin_billing_callback(update, context):
    """Placeholder for admin billing callback.""" 
    await error_handlers.admin_placeholder_callback(update, context)

async def admin_broadcast_callback(update, context):
    """Placeholder for admin broadcast callback."""
    await error_handlers.admin_placeholder_callback(update, context)

async def admin_mass_gift_callback(update, context):
    """Placeholder for admin mass gift callback."""
    await error_handlers.admin_placeholder_callback(update, context)

async def admin_settings_callback(update, context):
    """Placeholder for admin settings callback."""
    await error_handlers.admin_placeholder_callback(update, context)

async def admin_system_callback(update, context):
    """Placeholder for admin system callback."""
    await error_handlers.admin_placeholder_callback(update, context)

async def admin_quick_replies_callback(update, context):
    """Placeholder for admin quick replies callback."""
    await error_handlers.admin_placeholder_callback(update, context)

async def admin_search_callback(update, context):
    """Placeholder for admin search callback."""
    await error_handlers.admin_placeholder_callback(update, context)

async def admin_refresh_callback(update, context):
    """Placeholder for admin refresh callback."""
    await error_handlers.admin_placeholder_callback(update, context)


# All commands have now been properly organized into their respective modules 