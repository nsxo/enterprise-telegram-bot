"""
Enterprise Telegram Bot - Error Handlers

This module contains centralized error handling functionality for the bot,
including callback data errors, general error handlers, and debug utilities.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


async def callback_data_error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle InvalidCallbackData errors when users click expired buttons.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "❌ **This button has expired.**\n\n"
            "Please use /start to get a fresh menu with updated options.",
            parse_mode=ParseMode.MARKDOWN
        )
    logger.warning(f"Invalid callback data from user {update.effective_user.id}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Global error handler for the bot.
    
    Args:
        update: Telegram update object (can be None)
        context: Telegram context object
    """
    logger.error(f"Exception while handling an update: {context.error}")
    
    # Try to send error message to user if update is available
    if update and hasattr(update, 'effective_user') and update.effective_user:
        try:
            if hasattr(update, 'message') and update.message:
                await update.message.reply_text(
                    "❌ Sorry, something went wrong. Please try again or use /help for assistance."
                )
            elif hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.answer(
                    "❌ Error occurred. Please try again.",
                    show_alert=True
                )
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")


async def debug_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Debug handler for unmatched callback queries.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    if query:
        await query.answer()
        logger.debug(f"Unhandled callback data: {query.data}")
        await query.edit_message_text(
            f"🐛 **Debug Info**\n\n"
            f"Callback data: `{query.data}`\n\n"
            f"This callback is not implemented yet. Please use /start for the main menu.",
            parse_mode=ParseMode.MARKDOWN
        )


async def admin_placeholder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Placeholder for admin sub-menu items that need detailed implementation.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    query = update.callback_query
    await query.answer()
    
    # Extract the callback type for contextual message
    callback_type = query.data.replace("admin_", "").replace("_", " ").title()
    
    text = (
        f"🚧 **{callback_type} - Coming Soon**\n\n"
        f"This feature is currently under development and will be available in a future update.\n\n"
        f"**What's Coming:**\n"
        f"• Full {callback_type.lower()} functionality\n"
        f"• Advanced management tools\n"
        f"• Detailed reporting\n"
        f"• Export capabilities\n\n"
        f"In the meantime, you can use the main category features or contact support for manual assistance."
    )
    
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_main")],
        [InlineKeyboardButton("📋 Feature Requests", callback_data="admin_feature_request")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    ) 