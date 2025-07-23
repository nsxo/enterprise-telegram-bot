"""
Enterprise Telegram Bot - Validation Utilities

This module contains reusable validation functions and patterns used throughout
the bot application to eliminate code duplication and ensure consistent validation.
"""

import logging
import re
from typing import Dict, Any, Optional, Union
from telegram import Update
from telegram.ext import ContextTypes

from src import database as db
from src.services.error_service import ErrorService, ErrorType

logger = logging.getLogger(__name__)


class UserValidator:
    """Centralized user validation and creation utilities."""

    @staticmethod
    async def ensure_user_exists(update: Update) -> Optional[Dict[str, Any]]:
        """
        Ensure user exists in database and return user data.
        Creates user if they don't exist.

        Args:
            update: Telegram update object

        Returns:
            User data dictionary or None if error
        """
        try:
            user = update.effective_user
            if not user:
                logger.warning("No effective user in update")
                return None

            user_data = db.get_or_create_user(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
            )

            logger.debug(f"User validated/created: {user.id}")
            return user_data

        except Exception as e:
            logger.error(f"Failed to ensure user exists: {e}")
            return None

    @staticmethod
    async def validate_and_get_user(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> Optional[Dict[str, Any]]:
        """
        Validate user and handle errors with user-friendly messages.

        Args:
            update: Telegram update object
            context: Bot context

        Returns:
            User data dictionary or None if validation failed
        """
        try:
            user_data = await UserValidator.ensure_user_exists(update)
            if not user_data:
                await ErrorService.handle_error(
                    update,
                    context,
                    ErrorType.SYSTEM_ERROR,
                    Exception("Failed to validate user"),
                    "Unable to process your request. Please try again.",
                )
                return None

            return user_data

        except Exception as e:
            await ErrorService.handle_error(
                update,
                context,
                ErrorType.SYSTEM_ERROR,
                e,
                "An error occurred while processing your request.",
            )
            return None

    @staticmethod
    def validate_credit_balance(
        user_data: Dict[str, Any], required_credits: int = 1
    ) -> tuple[bool, str]:
        """
        Validate if user has sufficient credits.

        Args:
            user_data: User data dictionary
            required_credits: Credits required for operation

        Returns:
            Tuple of (is_valid, error_message)
        """
        current_credits = user_data.get("message_credits", 0)

        if current_credits < required_credits:
            return (
                False,
                f"Insufficient credits. Required: {required_credits}, "
                f"Available: {current_credits}",
            )

        return True, ""

    @staticmethod
    async def check_user_banned(
        user_id: int, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """
        Check if user is banned and handle accordingly.

        Args:
            user_id: User's Telegram ID
            update: Telegram update object
            context: Bot context

        Returns:
            True if user is banned, False otherwise
        """
        try:
            user_data = db.get_user(user_id)
            if user_data and user_data.get("is_banned", False):
                await ErrorService.handle_error(
                    update,
                    context,
                    ErrorType.USER_ERROR,
                    Exception("User is banned"),
                    "Your account has been suspended. Contact support for assistance.",
                )
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking ban status for user {user_id}: {e}")
            return False


class InputValidator:
    """Input validation utilities."""

    @staticmethod
    def validate_telegram_id(telegram_id: Union[str, int]) -> tuple[bool, Optional[int]]:
        """
        Validate Telegram ID format and convert to int.

        Args:
            telegram_id: Telegram ID as string or int

        Returns:
            Tuple of (is_valid, converted_id)
        """
        try:
            tid = int(telegram_id)
            if tid > 0:
                return True, tid
            return False, None
        except (ValueError, TypeError):
            return False, None

    @staticmethod
    def validate_credit_amount(amount: Union[str, int]) -> tuple[bool, Optional[int]]:
        """
        Validate credit amount.

        Args:
            amount: Credit amount as string or int

        Returns:
            Tuple of (is_valid, converted_amount)
        """
        try:
            credit_amount = int(amount)
            if 1 <= credit_amount <= 10000:  # Reasonable limits
                return True, credit_amount
            return False, None
        except (ValueError, TypeError):
            return False, None

    @staticmethod
    def validate_product_id(product_id: Union[str, int]) -> tuple[bool, Optional[int]]:
        """
        Validate product ID format.

        Args:
            product_id: Product ID as string or int

        Returns:
            Tuple of (is_valid, converted_id)
        """
        try:
            pid = int(product_id)
            if pid > 0:
                return True, pid
            return False, None
        except (ValueError, TypeError):
            return False, None

    @staticmethod
    def sanitize_text_input(text: str, max_length: int = 1000) -> str:
        """
        Sanitize text input from users.

        Args:
            text: Raw text input
            max_length: Maximum allowed length

        Returns:
            Sanitized text
        """
        if not text:
            return ""

        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text.strip())

        # Truncate if too long
        if len(text) > max_length:
            text = text[:max_length].rstrip() + "..."

        return text

    @staticmethod
    def validate_username(username: str) -> bool:
        """
        Validate Telegram username format.

        Args:
            username: Username to validate

        Returns:
            True if valid username format
        """
        if not username:
            return False

        # Remove @ if present
        username = username.lstrip("@")

        # Check format: 5-32 characters, alphanumeric and underscores
        return bool(re.match(r"^[a-zA-Z0-9_]{5,32}$", username))


class CallbackDataValidator:
    """Callback data validation utilities."""

    @staticmethod
    def validate_callback_data(callback_data: Any) -> tuple[bool, str]:
        """
        Validate callback data structure.

        Args:
            callback_data: Callback data to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not callback_data:
            return False, "Empty callback data"

        if isinstance(callback_data, str):
            # Simple string callback data
            if len(callback_data) > 64:  # Telegram limit
                return False, "Callback data too long"
            return True, ""

        if isinstance(callback_data, (tuple, list)):
            # Structured callback data
            if len(callback_data) < 1:
                return False, "Empty structured callback data"

            action = callback_data[0]
            if not isinstance(action, str):
                return False, "First element must be action string"

            return True, ""

        return False, "Invalid callback data type"


# Convenience functions for common validation patterns
async def validate_user_and_credits(
    update: Update, context: ContextTypes.DEFAULT_TYPE, required_credits: int = 1
) -> Optional[Dict[str, Any]]:
    """
    Combined user and credit validation.

    Args:
        update: Telegram update object
        context: Bot context
        required_credits: Credits required for operation

    Returns:
        User data if validation passes, None otherwise
    """
    # Check if user is banned first
    user = update.effective_user
    if await UserValidator.check_user_banned(user.id, update, context):
        return None

    # Validate user exists
    user_data = await UserValidator.validate_and_get_user(update, context)
    if not user_data:
        return None

    # Check credit balance
    is_valid, error_msg = UserValidator.validate_credit_balance(
        user_data, required_credits
    )
    if not is_valid:
        await ErrorService.handle_error(
            update,
            context,
            ErrorType.CREDIT_ERROR,
            Exception("Insufficient credits"),
            error_msg,
        )
        return None

    return user_data


async def validate_admin_user(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """
    Validate if user is an admin.

    Args:
        update: Telegram update object
        context: Bot context

    Returns:
        True if user is admin, False otherwise
    """
    from src.bot_utils import require_admin
    
    return await require_admin(update, context) 