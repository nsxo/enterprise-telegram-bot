"""
Enterprise Telegram Bot - Core Utilities

This module contains reusable utility functions and helpers used throughout
the bot application, including admin checks, progress bars, card formatting,
and topic management.
"""

import logging
from typing import Dict, Any
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    User,
    ForumTopic,
)
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telegram.error import TelegramError

from src import database as db
from src.config import ADMIN_USER_ID, ADMIN_GROUP_ID, CREDIT_WARNING_THRESHOLD

logger = logging.getLogger(__name__)


class BotError(Exception):
    """Raised when bot operations fail."""

    pass


def is_admin_user(user_id: int) -> bool:
    """
    Check if a user is an admin.

    Args:
        user_id: Telegram user ID to check

    Returns:
        True if user is an admin, False otherwise
    """
    if not ADMIN_USER_ID:
        return False
    return user_id == ADMIN_USER_ID


async def require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Check if the user is an admin and send error message if not.

    Args:
        update: Telegram update object
        context: Telegram context object

    Returns:
        True if user is admin, False otherwise
    """
    user = update.effective_user
    if not is_admin_user(user.id):
        await update.message.reply_text(
            "🚫 **Access Denied**\n\n"
            "This command is restricted to administrators only.\n\n"
            "Available commands for users:\n"
            "• /start - Get started\n"
            "• /balance - Check your balance\n"
            "• /billing - Billing portal\n"
            "• /buy - Purchase credits\n"
            "• /help - Get help\n"
            "• /status - Bot status\n"
            "• /time - Current time",
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.warning(
            f"Unauthorized admin command attempt by user {user.id} ({user.username})"
        )
        return False
    return True


def create_progress_bar(
    current_value: int, max_value: int = 100, length: int = 10
) -> str:
    """
    Generate a text-based progress bar.

    Args:
        current_value: Current credit count
        max_value: Maximum value for 100% (default 100)
        length: Number of characters for the bar (default 10)

    Returns:
        Formatted progress bar string
    """
    # Calculate percentage, capping at 100%
    percentage = min(100, (current_value / max_value) * 100)

    # Calculate filled and empty characters
    filled_length = int(length * percentage / 100)
    filled_chars = "█" * filled_length
    empty_chars = "░" * (length - filled_length)

    return f"[{filled_chars}{empty_chars}] {percentage:.0f}%"


def create_enhanced_progress_bar(
    current: int, max_val: int = None, style: str = "credits"
) -> str:
    """
    Create enhanced visual progress bars with status indicators.

    Args:
        current: Current value (credits, etc.)
        max_val: Maximum value for 100% (from settings if None)
        style: Style of progress bar ('credits', 'time')

    Returns:
        Enhanced progress bar with status indicators
    """
    if max_val is None:
        max_val = int(db.get_bot_setting("progress_bar_max_credits") or "100")

    percentage = min(100, (current / max_val) * 100)
    filled = int(10 * percentage / 100)

    if style == "credits":
        if percentage >= 80:
            bar_fill = "🟢" * filled + "⚪" * (10 - filled)
            status_emoji = "💚"
        elif percentage >= 40:
            bar_fill = "🟡" * filled + "⚪" * (10 - filled)
            status_emoji = "💛"
        else:
            bar_fill = "🔴" * filled + "⚪" * (10 - filled)
            status_emoji = "❤️"
    elif style == "time":
        bar_fill = "⏰" * filled + "⏳" * (10 - filled)
        status_emoji = "🕐"
    else:
        bar_fill = "⭐" * filled + "⚪" * (10 - filled)
        status_emoji = "✨"

    return f"{status_emoji} {bar_fill} {percentage:.0f}%"


def create_balance_card(user_data: Dict[str, Any]) -> str:
    """
    Create enhanced balance display card with visual elements.

    Args:
        user_data: User data dictionary

    Returns:
        Formatted balance card with status and tips
    """
    credits = user_data.get("message_credits", 0)
    tier = user_data.get("tier_name", "standard").title()

    # Get thresholds from settings
    low_threshold = int(db.get_bot_setting("balance_low_threshold") or "5")
    critical_threshold = int(db.get_bot_setting("balance_critical_threshold") or "2")

    # Status determination
    if credits >= low_threshold:
        status = "🟢 Excellent"
        tip = "You're all set for extended conversations! 🎉"
    elif credits >= critical_threshold:
        status = "🟡 Running Low"
        tip = "Consider topping up soon to avoid interruptions 💡"
    else:
        status = "🔴 Critical"
        tip = "⚠️ Add credits now to continue chatting!"

    progress_bar = create_enhanced_progress_bar(credits, style="credits")

    return f"""
🏦 **Your Account Dashboard**

{progress_bar}
💰 **Balance:** {credits} credits
📊 **Status:** {status}
⭐ **Tier:** {tier}

💡 **Tip:** {tip}
    """.strip()


def get_usage_tip(credits: int) -> str:
    """
    Provide contextual usage tips based on credit balance.

    Args:
        credits: Current credit balance

    Returns:
        Contextual tip message
    """
    if credits < 2:
        return "Running low! Use quick buy options below 🚨"
    elif credits < 5:
        return "Consider /buy25 for great value 💡"
    elif credits < 20:
        return "Try unlimited daily access for heavy usage ⏰"
    else:
        return "You're all set for extended conversations! 🎉"


def create_topic_link(group_id: int, topic_id: int) -> str:
    """
    Generate a t.me deep link to a topic in a private group.

    Args:
        group_id: Full group ID (e.g., -1001234567890)
        topic_id: Topic message thread ID

    Returns:
        Deep link to the topic
    """
    if not str(group_id).startswith("-100"):
        logger.warning(f"Invalid group ID format: {group_id}")
        return ""

    # Remove -100 prefix to get short chat ID
    chat_id_short = str(group_id)[4:]
    return f"https://t.me/c/{chat_id_short}/{topic_id}"


def format_user_info_card(user_data: Dict[str, Any]) -> str:
    """
    Format user information card for admin topics.

    Args:
        user_data: User data from database

    Returns:
        Formatted user info text
    """
    username = (
        f"@{user_data['username']}" if user_data.get("username") else "No username"
    )
    full_name = f"{user_data['first_name']} {user_data.get('last_name', '')}".strip()

    credits = user_data.get("message_credits", 0)
    tier_name = user_data.get("tier_name", "standard")
    total_spent = user_data.get("total_spent_cents", 0) / 100  # Convert to dollars
    total_purchases = user_data.get("total_purchases", 0)

    info = f"""
👤 **User Information**

**Name:** {full_name}
**Username:** {username}
**User ID:** `{user_data['telegram_id']}`
**Tier:** {tier_name.title()}

💰 **Account Status**
**Credits:** {credits}
**Total Spent:** ${total_spent:.2f}
**Total Purchases:** {total_purchases}

📅 **Account Created:** {user_data.get('user_since', 'Unknown')}
    """.strip()

    return info


async def get_or_create_user_topic(
    context: ContextTypes.DEFAULT_TYPE, user: User
) -> int:
    """
    Get existing topic ID or create new topic for user.
    Handles deleted topics by recreating them.

    Args:
        context: Telegram context
        user: User object

    Returns:
        Topic ID for the user's conversation thread

    Raises:
        BotError: If topic creation fails
    """
    # First check if topic already exists
    existing_topic_id = db.get_topic_id_from_user(user.id, ADMIN_GROUP_ID)
    if existing_topic_id:
        logger.info(f"Found existing topic {existing_topic_id} for user {user.id}")

        # Test if topic still exists by trying to send a test message
        try:
            # Try to get the topic info (this will fail if topic was deleted)
            await context.bot.get_chat(chat_id=ADMIN_GROUP_ID)
            # If we get here, the topic should exist, return it
            return existing_topic_id
        except Exception as e:
            logger.warning(
                f"Topic {existing_topic_id} for user {user.id} may have been deleted: {e}"
            )
            # Clean up the database record and create a new topic
            db.delete_conversation_topic(user.id, ADMIN_GROUP_ID)
            logger.info(f"Cleaned up deleted topic record for user {user.id}")

    # Create new topic
    topic_name = f"👤 {user.first_name}"
    if user.username:
        topic_name += f" (@{user.username})"
    topic_name += f" - {user.id}"

    try:
        logger.info(f"Creating new topic for user {user.id}")
        topic: ForumTopic = await context.bot.create_forum_topic(
            chat_id=ADMIN_GROUP_ID, name=topic_name
        )

        topic_id = topic.message_thread_id

        # Save to database immediately (atomic operation)
        db.create_conversation_topic(user.id, ADMIN_GROUP_ID, topic_id)

        # Send and pin user info card
        await send_user_info_card(context, user.id, topic_id)

        logger.info(f"✅ Created topic {topic_id} for user {user.id}")
        return topic_id

    except TelegramError as e:
        logger.error(f"Failed to create topic for user {user.id}: {e}")
        if "not enough rights" in str(e).lower():
            raise BotError(
                "Bot lacks permission to create topics. Please check bot admin rights."
            )
        raise BotError(f"Failed to create conversation topic: {e}")


async def send_user_info_card(
    context: ContextTypes.DEFAULT_TYPE, user_id: int, topic_id: int
) -> None:
    """
    Send and pin user information card in the topic.

    Args:
        context: PTB context object
        user_id: User's Telegram ID
        topic_id: Topic message thread ID
    """
    try:
        # Get comprehensive user data
        user_data = db.get_user_dashboard_data(user_id)
        if not user_data:
            logger.warning(f"No user data found for {user_id}")
            return

        # Format info card
        info_text = format_user_info_card(user_data)

        # Create admin action buttons using string callback data
        keyboard = [
            [
                InlineKeyboardButton(
                    "🚫 Ban User", callback_data=f"admin_ban_{user_id}"
                ),
                InlineKeyboardButton(
                    "🎁 Gift Credits", callback_data=f"admin_gift_{user_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "📊 Full History", callback_data=f"admin_history_{user_id}"
                ),
                InlineKeyboardButton(
                    "⬆️ Upgrade Tier", callback_data=f"admin_tier_{user_id}"
                ),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send message to topic
        message = await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            message_thread_id=topic_id,
            text=info_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
        )

        # Pin the message
        await context.bot.pin_chat_message(
            chat_id=ADMIN_GROUP_ID, message_id=message.message_id
        )

        # Update database with pinned message ID
        db.create_conversation_topic(
            user_id, ADMIN_GROUP_ID, topic_id, message.message_id
        )

        logger.info(
            f"✅ Sent and pinned user info card for {user_id} in topic {topic_id}"
        )

    except Exception as e:
        logger.error(f"Failed to send user info card: {e}")


async def should_show_credit_warning(user_id: int) -> bool:
    """
    Determine if a credit warning should be shown to the user.
    """
    user_data = db.get_user(user_id)
    if not user_data:
        return False

    return user_data.get("message_credits", 0) <= CREDIT_WARNING_THRESHOLD
