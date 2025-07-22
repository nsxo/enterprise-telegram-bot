"""
Enterprise Telegram Bot - Error Handler

This module provides comprehensive error handling, logging, and monitoring
for all bot operations with proper categorization and recovery mechanisms.
"""

import logging
import traceback
import sys
from typing import Optional, Dict, Any
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError, BadRequest, Forbidden, TimedOut, NetworkError

from src.config import ADMIN_GROUP_ID, DEV_MODE

logger = logging.getLogger(__name__)


class BotErrorHandler:
    """
    Centralized error handler for the Enterprise Telegram Bot.
    Provides error categorization, logging, and recovery mechanisms.
    """
    
    def __init__(self):
        self.error_counts = {}
        self.critical_errors = []
    
    
    async def handle_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Main error handler for all bot errors.
        
        Args:
            update: Telegram update object
            context: PTB context object with error information
        """
        error = context.error
        error_type = type(error).__name__
        
        # Increment error count
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        # Log the error with context
        self._log_error(error, update, context)
        
        # Handle specific error types
        if isinstance(error, TelegramError):
            await self._handle_telegram_error(error, update, context)
        elif isinstance(error, Exception):
            await self._handle_generic_error(error, update, context)
        
        # Report critical errors to admin
        if self._is_critical_error(error):
            await self._report_critical_error(error, update, context)
    
    
    def _log_error(self, error: Exception, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Log error with comprehensive context information.
        
        Args:
            error: The exception that occurred
            update: Telegram update object
            context: PTB context object
        """
        error_type = type(error).__name__
        error_message = str(error)
        
        # Extract update information
        update_info = "No update"
        if isinstance(update, Update):
            update_info = f"Update ID: {update.update_id}"
            if update.effective_user:
                update_info += f", User: {update.effective_user.id} (@{update.effective_user.username})"
            if update.effective_chat:
                update_info += f", Chat: {update.effective_chat.id}"
            if update.message:
                update_info += f", Message: {update.message.text[:50] if update.message.text else 'No text'}"
        
        # Log with appropriate level
        if self._is_critical_error(error):
            logger.critical(
                f"CRITICAL ERROR: {error_type}: {error_message}\n"
                f"Update Info: {update_info}\n"
                f"Traceback: {traceback.format_exc()}"
            )
            self.critical_errors.append({
                'error_type': error_type,
                'error_message': error_message,
                'update_info': update_info,
                'traceback': traceback.format_exc()
            })
        else:
            logger.error(
                f"ERROR: {error_type}: {error_message}\n"
                f"Update Info: {update_info}"
            )
        
        # Debug logging in development
        if DEV_MODE:
            logger.debug(f"Full traceback:\n{traceback.format_exc()}")
    
    
    async def _handle_telegram_error(self, error: TelegramError, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle Telegram-specific errors with appropriate responses.
        
        Args:
            error: TelegramError instance
            update: Telegram update object
            context: PTB context object
        """
        if isinstance(error, BadRequest):
            await self._handle_bad_request(error, update, context)
        elif isinstance(error, Forbidden):
            await self._handle_forbidden(error, update, context)
        elif isinstance(error, TimedOut):
            await self._handle_timeout(error, update, context)
        elif isinstance(error, NetworkError):
            await self._handle_network_error(error, update, context)
        else:
            logger.error(f"Unhandled Telegram error: {type(error).__name__}: {error}")
    
    
    async def _handle_bad_request(self, error: BadRequest, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle BadRequest errors (400)."""
        error_message = str(error).lower()
        
        if "message is not modified" in error_message:
            logger.debug("Attempted to edit message with same content - ignoring")
            return
        
        if "message can't be deleted" in error_message:
            logger.warning("Attempted to delete undeletable message")
            return
        
        if "chat not found" in error_message:
            logger.warning("Chat not found - user may have blocked bot")
            return
        
        if "message to edit not found" in error_message:
            logger.warning("Message to edit not found - may have been deleted")
            return
        
        if "query is too old" in error_message:
            logger.warning("Callback query too old - user took too long to respond")
            if isinstance(update, Update) and update.callback_query:
                try:
                    await update.callback_query.answer(
                        "This button has expired. Please start over.",
                        show_alert=True
                    )
                except:
                    pass
            return
        
        # Log unhandled BadRequest errors
        logger.error(f"Unhandled BadRequest: {error}")
    
    
    async def _handle_forbidden(self, error: Forbidden, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle Forbidden errors (403)."""
        error_message = str(error).lower()
        
        if "bot was blocked by the user" in error_message:
            logger.info("User blocked the bot")
            # Could implement logic to mark user as inactive
            return
        
        if "not enough rights" in error_message:
            logger.error("Bot lacks required permissions")
            # Could send alert to admins
            return
        
        if "user is deactivated" in error_message:
            logger.info("User account is deactivated")
            return
        
        logger.error(f"Unhandled Forbidden error: {error}")
    
    
    async def _handle_timeout(self, error: TimedOut, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle timeout errors."""
        logger.warning(f"Request timed out: {error}")
        
        # For webhook scenarios, timeout is often not critical
        # The update will be retried by Telegram if webhook returns error
        
        # Could implement retry logic here if needed
    
    
    async def _handle_network_error(self, error: NetworkError, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle network-related errors."""
        logger.warning(f"Network error: {error}")
        
        # Network errors are usually temporary
        # Telegram will retry webhook deliveries automatically
        
        # Could implement exponential backoff retry logic here
    
    
    async def _handle_generic_error(self, error: Exception, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle non-Telegram errors."""
        error_type = type(error).__name__
        
        # Database errors
        if "database" in str(error).lower() or "connection" in str(error).lower():
            logger.error(f"Database error: {error}")
            await self._handle_database_error(error, update, context)
            return
        
        # Stripe errors
        if "stripe" in error_type.lower():
            logger.error(f"Stripe error: {error}")
            await self._handle_stripe_error(error, update, context)
            return
        
        # Generic application errors
        logger.error(f"Generic application error: {error_type}: {error}")
    
    
    async def _handle_database_error(self, error: Exception, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle database-related errors."""
        logger.critical(f"Database error: {error}")
        
        # Could implement database reconnection logic here
        # For now, just log and hope the connection pool handles it
        
        # Send user-friendly message if possible
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "⚠️ We're experiencing technical difficulties. Please try again in a moment."
                )
            except:
                pass  # Don't fail on error message delivery
    
    
    async def _handle_stripe_error(self, error: Exception, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle Stripe-related errors."""
        logger.error(f"Stripe error: {error}")
        
        # Send user-friendly payment error message
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "💳 Payment processing is temporarily unavailable. Please try again later."
                )
            except:
                pass
    
    
    def _is_critical_error(self, error: Exception) -> bool:
        """
        Determine if an error is critical and needs immediate attention.
        
        Args:
            error: The exception to evaluate
            
        Returns:
            True if error is critical
        """
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # Critical error types
        critical_types = [
            'DatabaseError', 'ConnectionError', 'OperationalError',
            'SecurityError', 'AuthenticationError', 'ConfigurationError'
        ]
        
        if error_type in critical_types:
            return True
        
        # Critical error messages
        critical_messages = [
            'connection refused', 'authentication failed', 'permission denied',
            'database unavailable', 'stripe api key', 'webhook secret'
        ]
        
        if any(msg in error_message for msg in critical_messages):
            return True
        
        # High frequency of same error type indicates critical issue
        if self.error_counts.get(error_type, 0) > 10:
            return True
        
        return False
    
    
    async def _report_critical_error(self, error: Exception, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Report critical errors to administrators.
        
        Args:
            error: The critical exception
            update: Telegram update object
            context: PTB context object
        """
        try:
            error_type = type(error).__name__
            error_message = str(error)
            
            # Prepare error report
            report = f"""
🚨 **CRITICAL ERROR ALERT** 🚨

**Error Type:** {error_type}
**Error Message:** {error_message}
**Error Count:** {self.error_counts.get(error_type, 1)}

**Update Info:**
{self._format_update_info(update)}

**Time:** {context.bot_data.get('error_time', 'Unknown')}

⚠️ **Immediate attention required!**
            """.strip()
            
            # Send to admin group if configured
            if ADMIN_GROUP_ID:
                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_GROUP_ID,
                        text=report,
                        parse_mode='Markdown'
                    )
                    logger.info("Critical error reported to admin group")
                except Exception as e:
                    logger.error(f"Failed to send critical error report: {e}")
            
        except Exception as e:
            logger.error(f"Failed to report critical error: {e}")
    
    
    def _format_update_info(self, update: object) -> str:
        """Format update information for error reports."""
        if not isinstance(update, Update):
            return "No update information available"
        
        info_parts = [f"Update ID: {update.update_id}"]
        
        if update.effective_user:
            user = update.effective_user
            info_parts.append(f"User: {user.id} (@{user.username}) - {user.first_name}")
        
        if update.effective_chat:
            chat = update.effective_chat
            info_parts.append(f"Chat: {chat.id} ({chat.type})")
        
        if update.message and update.message.text:
            text = update.message.text[:100] + "..." if len(update.message.text) > 100 else update.message.text
            info_parts.append(f"Message: {text}")
        
        return "\n".join(info_parts)
    
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get error statistics for monitoring.
        
        Returns:
            Dictionary with error statistics
        """
        return {
            'error_counts': self.error_counts.copy(),
            'critical_errors_count': len(self.critical_errors),
            'total_errors': sum(self.error_counts.values()),
            'most_common_error': max(self.error_counts.items(), key=lambda x: x[1]) if self.error_counts else None
        }
    
    
    def clear_error_statistics(self) -> None:
        """Clear error statistics (useful for periodic cleanup)."""
        self.error_counts.clear()
        self.critical_errors.clear()
        logger.info("Error statistics cleared")


# Global error handler instance
error_handler = BotErrorHandler()


# Convenience function for use in bot application
async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Main error handler function for use with PTB Application.
    
    Args:
        update: Telegram update object
        context: PTB context object
    """
    await error_handler.handle_error(update, context)


# Exception hook for uncaught exceptions
def exception_hook(exc_type, exc_value, exc_traceback):
    """
    Handle uncaught exceptions globally.
    
    Args:
        exc_type: Exception type
        exc_value: Exception value
        exc_traceback: Exception traceback
    """
    if issubclass(exc_type, KeyboardInterrupt):
        # Allow keyboard interrupt to work normally
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    logger.critical(
        "Uncaught exception",
        exc_info=(exc_type, exc_value, exc_traceback)
    )


# Install the exception hook
sys.excepthook = exception_hook


# Configure logging format
def configure_logging():
    """Configure logging format and handlers."""
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    
    # File handler for errors
    error_file_handler = logging.FileHandler('errors.log')
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(log_format)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(error_file_handler)
    
    logger.info("Error handling system initialized")


# Initialize logging on import
configure_logging() 