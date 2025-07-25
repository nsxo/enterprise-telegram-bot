"""
Enterprise Telegram Bot - Core Utilities

This module contains reusable utility functions and helpers used throughout
the bot application, including admin checks, progress bars, card formatting,
and topic management.
"""

import logging
import time
import asyncio
from collections import defaultdict, deque
from typing import Dict, Any, Optional, Callable, Awaitable
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
from enum import Enum

from src import database as db
from src.config import ADMIN_USER_ID, ADMIN_GROUP_ID, CREDIT_WARNING_THRESHOLD
from src.services.error_service import (
    ErrorService,
    ErrorType,
)

logger = logging.getLogger(__name__)


class BotError(Exception):
    """Raised when bot operations fail."""

    pass


# Rate limiting storage
class RateLimiter:
    """
    Optimized rate limiter for Telegram API calls.
    Uses efficient cleanup strategies to handle high-traffic scenarios.
    """
    
    def __init__(self):
        self.global_calls = deque()  # Global rate limit tracking
        self.chat_calls = defaultdict(deque)  # Per-chat rate limit tracking
        self.global_limit = 30  # 30 messages per second globally
        self.chat_limit = 1    # 1 message per second per chat
        self.last_cleanup = 0  # Track last cleanup time to avoid excessive calls
        
    async def wait_if_needed(self, chat_id: Optional[int] = None) -> None:
        """Wait if rate limits would be exceeded."""
        current_time = time.time()
        
        # Clean old entries periodically (not on every call)
        if current_time - self.last_cleanup > 0.1:  # Cleanup every 100ms max
            self._clean_old_entries(current_time)
            self.last_cleanup = current_time
        
        # Check global rate limit
        if len(self.global_calls) >= self.global_limit:
            sleep_time = 1.0 - (current_time - self.global_calls[0])
            if sleep_time > 0:
                logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s for global limit")
                await asyncio.sleep(sleep_time)
                self._clean_old_entries(time.time())
        
        # Check per-chat rate limit
        if chat_id:
            chat_calls = self.chat_calls[chat_id]
            if len(chat_calls) >= self.chat_limit:
                sleep_time = 1.0 - (current_time - chat_calls[0])
                if sleep_time > 0:
                    logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s for chat {chat_id}")
                    await asyncio.sleep(sleep_time)
                    self._clean_old_entries(time.time())
        
        # Record this call
        current_time = time.time()
        self.global_calls.append(current_time)
        if chat_id:
            self.chat_calls[chat_id].append(current_time)
    
    def _clean_old_entries(self, current_time: float) -> None:
        """
        Efficiently remove entries older than 1 second.
        Optimized for high-traffic scenarios.
        """
        cutoff = current_time - 1.0
        
        # Clean global calls efficiently
        while self.global_calls and self.global_calls[0] < cutoff:
            self.global_calls.popleft()
        
        # Clean per-chat calls with batch processing
        chats_to_remove = []
        for chat_id, chat_calls in self.chat_calls.items():
            # Fast cleanup: remove multiple entries at once if they're old
            original_length = len(chat_calls)
            while chat_calls and chat_calls[0] < cutoff:
                chat_calls.popleft()
            
            # Track empty chats for removal
            if not chat_calls:
                chats_to_remove.append(chat_id)
            elif len(chat_calls) < original_length:
                # Log cleanup efficiency for monitoring
                cleaned = original_length - len(chat_calls)
                if cleaned > 5:  # Only log significant cleanups
                    logger.debug(f"Cleaned {cleaned} old entries for chat {chat_id}")
        
        # Remove empty chat entries in batch
        for chat_id in chats_to_remove:
            del self.chat_calls[chat_id]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get rate limiter statistics for monitoring.
        
        Returns:
            Dictionary with current rate limiter statistics
        """
        return {
            "global_calls_count": len(self.global_calls),
            "active_chats": len(self.chat_calls),
            "total_chat_calls": sum(len(calls) for calls in self.chat_calls.values()),
            "global_limit": self.global_limit,
            "chat_limit": self.chat_limit,
            "last_cleanup": self.last_cleanup
        }


# Global rate limiter instance
rate_limiter = RateLimiter()


async def rate_limited_send(
    send_func: Callable[..., Awaitable], 
    chat_id: int, 
    *args, 
    **kwargs
) -> Any:
    """Wrapper for rate-limited message sending."""
    await rate_limiter.wait_if_needed(chat_id)
    return await send_func(*args, **kwargs)


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


class ProgressBarStyle(Enum):
    """Progress bar display styles."""
    BASIC = "basic"
    CREDITS = "credits"
    TIME = "time"
    GENERAL = "general"


def create_unified_progress_bar(
    current: int,
    max_value: int = None,
    style: ProgressBarStyle = ProgressBarStyle.BASIC,
    length: int = 10,
    show_percentage: bool = True,
    show_status_emoji: bool = True
) -> str:
    """
    Unified progress bar creation with multiple styles and options.
    Replaces create_progress_bar, create_enhanced_progress_bar functions.

    Args:
        current: Current value
        max_value: Maximum value for 100% (auto-detected if None)
        style: Progress bar style (ProgressBarStyle enum)
        length: Length of the progress bar (default 10)
        show_percentage: Whether to show percentage (default True)
        show_status_emoji: Whether to show status emoji (default True)

    Returns:
        Formatted progress bar string
    """
    # Auto-detect max_value for credits style
    if max_value is None:
        if style == ProgressBarStyle.CREDITS:
            max_value = int(db.get_bot_setting("progress_bar_max_credits") or "100")
        else:
            max_value = 100

    # Calculate percentage and filled length
    percentage = min(100, (current / max_value) * 100)
    filled_length = int(length * percentage / 100)

    # Create progress bar based on style
    if style == ProgressBarStyle.BASIC:
        filled_chars = "█" * filled_length
        empty_chars = "░" * (length - filled_length)
        bar = f"[{filled_chars}{empty_chars}]"
        status_emoji = ""

    elif style == ProgressBarStyle.CREDITS:
        if percentage >= 80:
            bar_fill = "🟢" * filled_length + "⚪" * (length - filled_length)
            status_emoji = "💚" if show_status_emoji else ""
        elif percentage >= 40:
            bar_fill = "🟡" * filled_length + "⚪" * (length - filled_length)
            status_emoji = "💛" if show_status_emoji else ""
        else:
            bar_fill = "🔴" * filled_length + "⚪" * (length - filled_length)
            status_emoji = "❤️" if show_status_emoji else ""
        bar = bar_fill

    elif style == ProgressBarStyle.TIME:
        bar_fill = "⏰" * filled_length + "⏳" * (length - filled_length)
        status_emoji = "🕐" if show_status_emoji else ""
        bar = bar_fill

    else:  # GENERAL
        bar_fill = "⭐" * filled_length + "⚪" * (length - filled_length)
        status_emoji = "✨" if show_status_emoji else ""
        bar = bar_fill

    # Format final output
    result_parts = []
    if status_emoji:
        result_parts.append(status_emoji)
    result_parts.append(bar)
    if show_percentage:
        result_parts.append(f"{percentage:.0f}%")

    return " ".join(result_parts)


def create_progress_bar(
    current_value: int, max_value: int = 100, length: int = 10
) -> str:
    """
    DEPRECATED: Use create_unified_progress_bar instead.
    Backward compatibility wrapper for create_progress_bar.
    """
    return create_unified_progress_bar(
        current=current_value,
        max_value=max_value,
        style=ProgressBarStyle.BASIC,
        length=length,
        show_percentage=True,
        show_status_emoji=False
    )


def create_enhanced_progress_bar(
    current: int, max_val: int = None, style: str = "credits"
) -> str:
    """
    DEPRECATED: Use create_unified_progress_bar instead.
    Backward compatibility wrapper for create_enhanced_progress_bar.
    """
    style_map = {
        "credits": ProgressBarStyle.CREDITS,
        "time": ProgressBarStyle.TIME,
        "general": ProgressBarStyle.GENERAL
    }
    
    progress_style = style_map.get(style, ProgressBarStyle.CREDITS)
    
    return create_unified_progress_bar(
        current=current,
        max_value=max_val,
        style=progress_style,
        length=10,
        show_percentage=True,
        show_status_emoji=True
    )


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

    progress_bar = create_unified_progress_bar(credits, style=ProgressBarStyle.CREDITS)

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

        # Test if topic still exists by trying to send a test message to it
        try:
            test_message = await context.bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                message_thread_id=existing_topic_id,
                text="🔄 Checking topic availability...",
                disable_notification=True,
            )
            
            # If successful, delete the test message immediately
            await context.bot.delete_message(
                chat_id=ADMIN_GROUP_ID, 
                message_id=test_message.message_id
            )
            
            logger.info(f"✅ Topic {existing_topic_id} verified for user {user.id}")
            return existing_topic_id
            
        except Exception as e:
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in [
                "thread not found", 
                "topic not found", 
                "message thread not found",
                "bad request"
            ]):
                logger.warning(
                    f"Topic {existing_topic_id} for user {user.id} was deleted: {e}"
                )
                # Clean up the database record and create a new topic
                db.delete_conversation_topic(user.id, ADMIN_GROUP_ID)
                logger.info(f"Cleaned up deleted topic record for user {user.id}")
            else:
                # Unexpected error, but assume topic exists to avoid unnecessary recreation
                logger.warning(
                    f"Unexpected error checking topic {existing_topic_id}: {e}"
                )
                return existing_topic_id

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

        # Format info card with enhanced information
        info_text = format_user_info_card(user_data)
        
        # Add topic link section
        topic_link = create_topic_link(ADMIN_GROUP_ID, topic_id)
        if topic_link:
            info_text += f"\n\n🔗 **Quick Access:** [Direct Topic Link]({topic_link})"

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
            [
                InlineKeyboardButton(
                    "🔗 Topic Link", url=topic_link
                ) if topic_link else InlineKeyboardButton(
                    "💬 Quick Reply", callback_data=f"admin_quick_reply_{user_id}"
                ),
                InlineKeyboardButton(
                    "🗂️ Archive", callback_data=f"admin_archive_{user_id}"
                ),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send message to topic with rate limiting
        message = await rate_limited_send(
            context.bot.send_message,
            ADMIN_GROUP_ID,
            chat_id=ADMIN_GROUP_ID,
            message_thread_id=topic_id,
            text=info_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )

        # Pin the message with rate limiting
        await rate_limited_send(
            context.bot.pin_chat_message,
            ADMIN_GROUP_ID,
            chat_id=ADMIN_GROUP_ID, 
            message_id=message.message_id
        )

        # Update database with pinned message ID
        db.create_conversation_topic(
            user_id, ADMIN_GROUP_ID, topic_id, message.message_id
        )

        logger.info(f"✅ Sent and pinned user info card for user {user_id} in topic {topic_id}")

    except Exception as e:
        logger.error(f"Failed to send user info card for user {user_id}: {e}")
        # Try to send a simple fallback message
        try:
            fallback_text = f"👤 **User {user_id}**\n\nError loading user details. Please check manually."
            await context.bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                message_thread_id=topic_id,
                text=fallback_text,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as fallback_error:
            logger.error(f"Failed to send fallback user info: {fallback_error}")


async def should_show_credit_warning(user_id: int) -> bool:
    """
    Determine if a credit warning should be shown to the user.
    """
    user_data = db.get_user(user_id)
    if not user_data:
        return False

    return user_data.get("message_credits", 0) <= CREDIT_WARNING_THRESHOLD


async def send_auto_recharge_prompt(user_id: int, product_id: int, bot_instance=None):
    """
    Sends a message to the user after their first purchase,
    prompting them to enable auto-recharge.
    
    Args:
        user_id: User's Telegram ID
        product_id: Product ID for auto-recharge
        bot_instance: Bot instance (required to avoid circular imports)
    """
    from src import database as db

    if not bot_instance:
        logger.error(f"Cannot send auto-recharge prompt to user {user_id}: No bot instance provided")
        return

    product = db.get_product_by_id(product_id)
    if not product:
        logger.warning(f"Cannot send auto-recharge prompt: Product {product_id} not found")
        return

    text = f"""
🎉 Thank you for your purchase of **{product['name']}**!

To make things easier next time, would you like to enable **Auto-Recharge**?

When your balance drops below 10 credits, we'll automatically top you up with this same package. You can change this or turn it off at any time from the /billing menu.
    """
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Yes, enable Auto-Recharge",
                callback_data=("autorecharge_enable", product_id),
            )
        ],
        [InlineKeyboardButton("❌ No, thanks", callback_data=("autorecharge_decline",))],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await bot_instance.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info(f"Sent auto-recharge prompt to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to send auto-recharge prompt to {user_id}: {e}")


def get_user_dashboard_url(user_id: int) -> str:
    # In a real app, this would point to a web dashboard
    return f"https://yourapp.com/dashboard/{user_id}"
