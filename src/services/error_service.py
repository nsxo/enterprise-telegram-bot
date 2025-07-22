"""
Enterprise Telegram Bot - Error Service

This service provides structured error handling with user-friendly messages
and proper logging for different types of errors.
"""

import logging
from enum import Enum
from typing import Dict, Optional
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Different types of errors that can occur in the bot."""

    USER_ERROR = "user_error"  # User input errors
    CREDIT_ERROR = "credit_error"  # Credit-related errors
    PAYMENT_ERROR = "payment_error"  # Payment processing errors
    DATABASE_ERROR = "database_error"  # Database connection/query errors
    API_ERROR = "api_error"  # Telegram API errors
    SYSTEM_ERROR = "system_error"  # Internal system errors


class ErrorService:
    """Service for handling errors with user-friendly messages."""

    # Error messages mapped to error types
    ERROR_MESSAGES: Dict[ErrorType, Dict[str, str]] = {
        ErrorType.USER_ERROR: {
            "title": "❌ **Input Error**",
            "message": "Please check your input and try again.",
            "suggestion": "Make sure you're using the correct format.",
        },
        ErrorType.CREDIT_ERROR: {
            "title": "💰 **Credit Issue**",
            "message": "There was a problem with your credits.",
            "suggestion": "Check your balance with /balance or buy more credits with /buy.",
        },
        ErrorType.PAYMENT_ERROR: {
            "title": "💳 **Payment Issue**",
            "message": "Payment processing encountered an error.",
            "suggestion": "Please try again or contact support if the issue persists.",
        },
        ErrorType.DATABASE_ERROR: {
            "title": "🔧 **System Issue**",
            "message": "We're experiencing technical difficulties.",
            "suggestion": "Please try again in a moment. Our team has been notified.",
        },
        ErrorType.API_ERROR: {
            "title": "📡 **Connection Issue**",
            "message": "There was a problem communicating with our services.",
            "suggestion": "Please try again in a few moments.",
        },
        ErrorType.SYSTEM_ERROR: {
            "title": "⚠️ **System Error**",
            "message": "An unexpected error occurred.",
            "suggestion": "Our technical team has been automatically notified.",
        },
    }

    @classmethod
    async def handle_error(
        cls,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        error_type: ErrorType,
        error: Exception,
        custom_message: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> None:
        """
        Handle an error with structured logging and user notification.

        Args:
            update: Telegram update object
            context: Bot context
            error_type: Type of error that occurred
            error: The actual exception
            custom_message: Custom message to show user (optional)
            user_id: User ID for logging (optional)
        """
        # Get user ID for logging
        if not user_id and update and update.effective_user:
            user_id = update.effective_user.id

        # Log the error with appropriate level
        error_msg = f"Error for user {user_id}: {str(error)}"

        if error_type in [ErrorType.SYSTEM_ERROR, ErrorType.DATABASE_ERROR]:
            logger.error(error_msg, exc_info=True)
        elif error_type == ErrorType.API_ERROR:
            logger.warning(error_msg)
        else:
            logger.info(error_msg)

        # Send user-friendly message
        if update and update.effective_chat:
            try:
                error_config = cls.ERROR_MESSAGES[error_type]

                if custom_message:
                    user_message = f"{error_config['title']}\n\n{custom_message}"
                else:
                    user_message = f"""
{error_config['title']}

{error_config['message']}

💡 **Suggestion:** {error_config['suggestion']}
                    """

                if update.callback_query:
                    await update.callback_query.answer()
                    if update.callback_query.message:
                        await update.callback_query.message.reply_text(
                            user_message, parse_mode=ParseMode.MARKDOWN
                        )
                elif update.message:
                    await update.message.reply_text(
                        user_message, parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    # Fallback: send to user directly
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=user_message,
                        parse_mode=ParseMode.MARKDOWN,
                    )

            except Exception as notification_error:
                logger.error(f"Failed to send error notification: {notification_error}")

    @classmethod
    def format_validation_error(cls, field_name: str, expected: str) -> str:
        """Format a validation error message."""
        return f"Invalid {field_name}. Expected: {expected}"

    @classmethod
    def format_credit_error(cls, required: int, available: int) -> str:
        """Format a credit insufficiency error."""
        return f"Insufficient credits. Required: {required}, Available: {available}"

    @classmethod
    async def handle_payment_error(
        cls,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        error: Exception,
        payment_intent_id: Optional[str] = None,
    ) -> None:
        """Handle payment-specific errors with additional context."""
        custom_message = "Payment processing failed."

        if payment_intent_id:
            custom_message += f"\n\n**Reference ID:** `{payment_intent_id}`"
            custom_message += (
                "\n\nPlease save this reference ID and contact support if needed."
            )

        await cls.handle_error(
            update, context, ErrorType.PAYMENT_ERROR, error, custom_message
        )

    @classmethod
    async def handle_database_error(
        cls,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        error: Exception,
        operation: str = "database operation",
    ) -> None:
        """Handle database errors with operation context."""
        custom_message = f"Failed to complete {operation}."

        await cls.handle_error(
            update, context, ErrorType.DATABASE_ERROR, error, custom_message
        )


# Convenience functions for common error scenarios
async def handle_insufficient_credits(
    update: Update, context: ContextTypes.DEFAULT_TYPE, required: int, available: int
) -> None:
    """Handle insufficient credits error."""
    message = ErrorService.format_credit_error(required, available)
    await ErrorService.handle_error(
        update,
        context,
        ErrorType.CREDIT_ERROR,
        ValueError("Insufficient credits"),
        message,
    )


async def handle_invalid_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE, field_name: str, expected: str
) -> None:
    """Handle invalid user input error."""
    message = ErrorService.format_validation_error(field_name, expected)
    await ErrorService.handle_error(
        update, context, ErrorType.USER_ERROR, ValueError("Invalid input"), message
    )
