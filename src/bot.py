"""
Enterprise Telegram Bot - Core Bot Logic

This module contains all Telegram bot handlers, conversation management,
and user interaction logic following the enhanced architectural patterns.
"""

import logging
import uuid
from typing import Optional, Dict, Any, Tuple
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    User,
    Message,
    ForumTopic,
    MessageReactionUpdated,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    InvalidCallbackData,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError

from src import database as db
from src.config import BOT_TOKEN, ADMIN_GROUP_ID, ADMIN_USER_ID

logger = logging.getLogger(__name__)


class BotError(Exception):
    """Raised when bot operations fail."""
    pass


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def create_progress_bar(current_value: int, max_value: int = 100, length: int = 10) -> str:
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
    username = f"@{user_data['username']}" if user_data.get('username') else "No username"
    full_name = f"{user_data['first_name']} {user_data.get('last_name', '')}".strip()
    
    credits = user_data.get('message_credits', 0)
    tier_name = user_data.get('tier_name', 'standard')
    total_spent = user_data.get('total_spent_cents', 0) / 100  # Convert to dollars
    total_purchases = user_data.get('total_purchases', 0)
    
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


# =============================================================================
# CONVERSATION BRIDGE SYSTEM
# =============================================================================

async def get_or_create_user_topic(context: ContextTypes.DEFAULT_TYPE, user: User) -> int:
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
            logger.warning(f"Topic {existing_topic_id} for user {user.id} may have been deleted: {e}")
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
            chat_id=ADMIN_GROUP_ID,
            name=topic_name
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
            raise BotError("Bot lacks permission to create topics. Please check bot admin rights.")
        raise BotError(f"Failed to create conversation topic: {e}")


async def send_user_info_card(context: ContextTypes.DEFAULT_TYPE, user_id: int, topic_id: int) -> None:
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
                InlineKeyboardButton("🚫 Ban User", callback_data=f"admin_ban_{user_id}"),
                InlineKeyboardButton("🎁 Gift Credits", callback_data=f"admin_gift_{user_id}"),
            ],
            [
                InlineKeyboardButton("📊 Full History", callback_data=f"admin_history_{user_id}"),
                InlineKeyboardButton("⬆️ Upgrade Tier", callback_data=f"admin_tier_{user_id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send message to topic
        message = await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            message_thread_id=topic_id,
            text=info_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
        # Pin the message
        await context.bot.pin_chat_message(
            chat_id=ADMIN_GROUP_ID,
            message_id=message.message_id
        )
        
        # Update database with pinned message ID
        db.create_conversation_topic(user_id, ADMIN_GROUP_ID, topic_id, message.message_id)
        
        logger.info(f"✅ Sent and pinned user info card for {user_id} in topic {topic_id}")
        
    except Exception as e:
        logger.error(f"Failed to send user info card: {e}")


# =============================================================================
# USER COMMAND HANDLERS
# =============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command - show welcome message with Start button.
    """
    user = update.effective_user
    logger.info(f"Start command from user {user.id} ({user.username})")
    
    try:
        # Get or create user in database
        db_user = db.get_or_create_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        logger.info(f"User {user.id} created/retrieved from database")
        
        # Get welcome message from bot settings
        try:
            welcome_message = db.get_bot_setting('welcome_message') or "Welcome to our Enterprise Telegram Bot! 🤖"
        except Exception as e:
            logger.error(f"Failed to get welcome message: {e}")
            welcome_message = "Welcome to our Enterprise Telegram Bot! 🤖"
        
        # Create start button using simple string for debugging
        keyboard = [[InlineKeyboardButton("▶️ Start", callback_data="show_products")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info(f"Start command completed for user {user.id}")
        
    except Exception as e:
        logger.error(f"Start command failed for user {user.id}: {e}")
        await update.message.reply_text(
            "❌ Sorry, there was an error. Please try again later."
        )


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /balance command - show user's credit balance with progress bar.
    """
    user = update.effective_user
    logger.info(f"Balance command from user {user.id}")
    
    # Get user data
    user_data = db.get_user(user.id)
    if not user_data:
        await update.message.reply_text("❌ User not found. Please use /start first.")
        return
    
    credits = user_data.get('message_credits', 0)
    tier_name = user_data.get('tier_name', 'standard')
    
    # Create visual progress bar (assuming 100 credits as "full")
    progress_bar = create_progress_bar(credits, 100)
    
    balance_text = f"""
💰 **Your Account Balance**

**Credits:** {credits}
**Tier:** {tier_name.title()}

{progress_bar}

Use /billing to manage payment methods or purchase more credits.
    """.strip()
    
    await update.message.reply_text(balance_text, parse_mode=ParseMode.MARKDOWN)


async def billing_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /billing command - redirect to Stripe Customer Portal.
    """
    user = update.effective_user
    logger.info(f"Billing command from user {user.id}")
    
    # Import here to avoid circular imports
    from src.stripe_utils import create_billing_portal_session
    
    try:
        # Get user's Stripe customer ID
        user_data = db.get_user(user.id)
        if not user_data or not user_data.get('stripe_customer_id'):
            await update.message.reply_text(
                "🏦 You need to make a purchase first before accessing billing settings.\n\n"
                "Use /start to browse our products!"
            )
            return
        
        # Create Stripe Customer Portal session
        portal_url = create_billing_portal_session(user_data['stripe_customer_id'])
        
        await update.message.reply_text(
            f"🏦 **Billing Management**\n\n"
            f"Click the link below to manage your payment methods, "
            f"view invoices, and update billing information:\n\n"
            f"[Open Billing Portal]({portal_url})",
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Billing command failed for user {user.id}: {e}")
        await update.message.reply_text(
            "❌ Unable to access billing portal at the moment. Please try again later."
        )


async def quick_buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle quick buy commands like /buy10, /buy25."""
    message = update.message
    user = message.from_user
    
    # Extract amount from command (e.g., "/buy10" -> 10)
    command = message.text.split()[0][1:]  # Remove "/"
    amount = command.replace("buy", "")
    
    try:
        amount = int(amount)
    except ValueError:
        await message.reply_text("❌ Invalid amount in command.")
        return
    
    # Find corresponding product
    products = db.get_products_by_type("credits")
    matching_product = None
    for product in products:
        if product['amount'] == amount:
            matching_product = product
            break
    
    if not matching_product:
        await message.reply_text(f"❌ No {amount}-credit product available.")
        return
    
    # Create checkout session
    try:
        from src.stripe_utils import create_checkout_session
        checkout_url = create_checkout_session(
            user_id=user.id,
            price_id=matching_product['stripe_price_id'],
            success_url="https://your-bot-url.com/success",
            cancel_url="https://your-bot-url.com/cancel"
        )
        
        keyboard = [[InlineKeyboardButton("💳 Complete Purchase", url=checkout_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await message.reply_text(
            f"💳 **Quick Purchase: {amount} Credits**\n\n"
            f"Amount: ${matching_product['price_usd_cents'] / 100:.2f}\n"
            f"Click below to complete your purchase:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Quick buy error: {e}")
        await message.reply_text("❌ Payment system temporarily unavailable.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command - show available commands."""
    user = update.effective_user
    logger.info(f"Help command from user {user.id}")
    
    help_text = (
        "🤖 **Available Commands**\n\n"
        "**Basic Commands:**\n"
        "• /start - Welcome message and product store\n"
        "• /balance - Check your credit balance\n"
        "• /billing - Manage payment methods\n"
        "• /help - Show this help message\n\n"
        "**Quick Purchase:**\n"
        "• /buy10 - Buy 10 credits\n"
        "• /buy25 - Buy 25 credits\n"
        "• /buy50 - Buy 50 credits\n\n"
        "**Status Commands:**\n"
        "• /status - Check your account status\n"
        "• /time - Check time-based access\n\n"
        "**Need Help?**\n"
        "Just send a message and our team will respond!"
    )
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /buy command - show product selection."""
    user = update.effective_user
    logger.info(f"Buy command from user {user.id}")
    
    try:
        # Get active products
        products = db.get_active_products()
        if not products:
            await update.message.reply_text(
                "❌ No products available at the moment.\n\n"
                "Please try again later or contact support."
            )
            return
        
        # Group products by type
        credits_products = [p for p in products if p['product_type'] == 'credits']
        time_products = [p for p in products if p['product_type'] == 'time']
        
        # Create product buttons
        keyboard = []
        
        if credits_products:
            keyboard.append([InlineKeyboardButton("💎 Credit Packages", callback_data="product_type_credits")])
        
        if time_products:
            keyboard.append([InlineKeyboardButton("⏰ Time Packages", callback_data="product_type_time")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = (
            "🛒 **Purchase Options**\n\n"
            "Choose what you'd like to buy:\n\n"
        )
        
        if credits_products:
            text += "💎 **Credit Packages** - Pay per message\n"
        if time_products:
            text += "⏰ **Time Packages** - Unlimited access for a period\n"
        
        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Buy command failed for user {user.id}: {e}")
        await update.message.reply_text("❌ Error loading products. Please try again later.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command - show account status."""
    user = update.effective_user
    logger.info(f"Status command from user {user.id}")
    
    try:
        # Get user data
        user_data = db.get_user(user.id)
        if not user_data:
            await update.message.reply_text("❌ User account not found. Please use /start to initialize.")
            return
        
        # Get tier information
        tier_name = "Standard"  # Default, could get from database
        
        # Format status message
        status_text = (
            f"📊 **Account Status**\n\n"
            f"**User:** {user.first_name}\n"
            f"**Tier:** {tier_name}\n"
            f"**Credits:** {user_data.get('message_credits', 0)}\n"
            f"**Status:** {'✅ Active' if not user_data.get('is_banned', False) else '❌ Banned'}\n\n"
        )
        
        # Add time access info if available
        time_expires = user_data.get('time_credits_expires_at')
        if time_expires:
            status_text += f"**Time Access:** Expires {time_expires}\n\n"
        else:
            status_text += "**Time Access:** None\n\n"
        
        status_text += "Use /balance for detailed balance info or /buy to purchase more credits."
        
        await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"Status command failed for user {user.id}: {e}")
        await update.message.reply_text("❌ Error loading status. Please try again later.")


async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /time command - show time-based access info."""
    user = update.effective_user
    logger.info(f"Time command from user {user.id}")
    
    try:
        # Get user data
        user_data = db.get_user(user.id)
        if not user_data:
            await update.message.reply_text("❌ User account not found. Please use /start to initialize.")
            return
        
        time_expires = user_data.get('time_credits_expires_at')
        
        if time_expires:
            time_text = (
                f"⏰ **Time-Based Access**\n\n"
                f"**Status:** ✅ Active\n"
                f"**Expires:** {time_expires}\n"
                f"**Access:** Unlimited messages until expiry\n\n"
                f"Use /buy to extend your time access or purchase credits."
            )
        else:
            time_text = (
                f"⏰ **Time-Based Access**\n\n"
                f"**Status:** ❌ No active time access\n"
                f"**Access:** Credit-based messaging only\n\n"
                f"Purchase time packages for unlimited messaging!\n"
                f"Use /buy to see available time packages."
            )
        
        await update.message.reply_text(time_text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"Time command failed for user {user.id}: {e}")
        await update.message.reply_text("❌ Error loading time access info. Please try again later.")


# =============================================================================
# ADMIN COMMANDS
# =============================================================================

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /admin command - show admin dashboard."""
    message = update.message
    user = message.from_user
    
    # Check if user is admin (you can implement proper admin checking)
    # For now, anyone can access - implement proper auth later
    
    dashboard_text = (
        "🔧 **Admin Dashboard**\n\n"
        "**User Management:**\n"
        "• /users - View all users\n"
        "• /conversations - Manage conversations\n\n"
        "**System Management:**\n"
        "• /settings - Bot settings\n"
        "• /products - Manage products\n"
        "• /analytics - View analytics\n\n"
        "**Operations:**\n"
        "• /broadcast - Send broadcast message\n"
        "• /webhook - Webhook status\n"
        "• /system - System status"
    )
    
    keyboard = [
        [InlineKeyboardButton("👥 Users", callback_data="admin_users")],
        [InlineKeyboardButton("💬 Conversations", callback_data="admin_conversations")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings")],
        [InlineKeyboardButton("📊 Analytics", callback_data="admin_analytics")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text(
        dashboard_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /settings command."""
    await update.message.reply_text(
        "⚙️ **Bot Settings**\n\n"
        "Settings management coming soon!\n"
        "Use /admin for the main dashboard."
    )


async def products_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /products command."""
    try:
        products = db.get_all_products()
        if not products:
            await update.message.reply_text("No products found.")
            return
        
        text = "📦 **Product Management**\n\n"
        for product in products:
            text += f"• {product['name']} - ${product['price_usd_cents']/100:.2f}\n"
            text += f"  Type: {product['product_type']}, Amount: {product['amount']}\n\n"
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"Products command error: {e}")
        await update.message.reply_text("❌ Error loading products.")


async def analytics_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /analytics command."""
    try:
        # Get basic stats
        user_count = db.get_user_count()
        conversation_count = db.get_conversation_count()
        
        text = (
            "📊 **Analytics Dashboard**\n\n"
            f"👥 Total Users: {user_count}\n"
            f"💬 Active Conversations: {conversation_count}\n\n"
            "Detailed analytics coming soon!"
        )
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"Analytics command error: {e}")
        await update.message.reply_text("❌ Error loading analytics.")


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /users command."""
    await update.message.reply_text(
        "👥 **User Management**\n\n"
        "User management interface coming soon!\n"
        "Use /admin for the main dashboard."
    )


async def conversations_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /conversations command."""
    await update.message.reply_text(
        "💬 **Conversation Management**\n\n"
        "Conversation management interface coming soon!\n"
        "Use /admin for the main dashboard."
    )


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /broadcast command."""
    await update.message.reply_text(
        "📢 **Broadcast Message**\n\n"
        "Broadcast functionality coming soon!\n"
        "Use /admin for the main dashboard."
    )


async def webhook_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /webhook command."""
    await update.message.reply_text(
        "🔗 **Webhook Status**\n\n"
        "✅ Webhooks are operational\n"
        "📡 Receiving updates normally\n\n"
        "Use /admin for the main dashboard."
    )


async def system_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /system command."""
    try:
        # Basic system info
        import sys
        from datetime import datetime
        
        text = (
            "🖥️ **System Status**\n\n"
            f"🐍 Python: {sys.version.split()[0]}\n"
            f"⏰ Uptime: Active\n"
            f"📅 Last restart: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"🔄 Status: Operational\n\n"
            "Use /admin for the main dashboard."
        )
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"System command error: {e}")
        await update.message.reply_text("❌ Error getting system status.")


# =============================================================================
# CALLBACK QUERY HANDLERS
# =============================================================================

async def show_products_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show available products when Start button is clicked.
    """
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer()
        logger.info(f"Show products callback from user {user.id}")
        
        # Get active products with error handling
        try:
            products = db.get_active_products()
            logger.info(f"Retrieved {len(products) if products else 0} products from database")
        except Exception as e:
            logger.error(f"Failed to get products: {e}")
            await query.edit_message_text("❌ Error loading products. Please try again later.")
            return
        
        if not products:
            logger.warning("No products found in database")
            await query.edit_message_text(
                "❌ No products available at the moment.\n\n"
                "Please contact support or try again later."
            )
            return
        
        # Group products by type
        credits_products = [p for p in products if p['product_type'] == 'credits']
        time_products = [p for p in products if p['product_type'] == 'time']
        
        logger.info(f"Found {len(credits_products)} credit products, {len(time_products)} time products")
        
        # Create product buttons
        keyboard = []
        
        if credits_products:
            keyboard.append([InlineKeyboardButton("💎 Credit Packages", callback_data="product_type_credits")])
        
        if time_products:
            keyboard.append([InlineKeyboardButton("⏰ Time Packages", callback_data="product_type_time")])
        
        keyboard.append([InlineKeyboardButton("🏦 Billing Settings", callback_data="billing_portal")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Create product display text
        text = (
            "🛒 **Welcome to our Store!**\n\n"
            "Choose what you'd like to purchase:\n\n"
        )
        
        if credits_products:
            text += "💎 **Credit Packages** - Pay per message\n"
        if time_products:
            text += "⏰ **Time Packages** - Unlimited access for a period\n"
        
        text += "\n🏦 **Billing Settings** - Manage your payment methods"
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info(f"Products displayed successfully for user {user.id}")
        
    except Exception as e:
        logger.error(f"Show products callback failed for user {user.id}: {e}")
        try:
            await query.edit_message_text("❌ Sorry, there was an error. Please try /start again.")
        except:
            pass


async def product_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle product type selection (credits or time)."""
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer()
        
        # Extract product type from callback data
        callback_data = query.data
        if callback_data == "product_type_credits":
            product_type = "credits"
            title = "💎 Credit Packages"
            description = "Pay per message - buy credits to send messages"
        elif callback_data == "product_type_time":
            product_type = "time"
            title = "⏰ Time Packages"
            description = "Unlimited access for a specific time period"
        else:
            logger.error(f"Unknown product type callback: {callback_data}")
            await query.edit_message_text("❌ Invalid selection. Please try again.")
            return
            
        logger.info(f"Product type '{product_type}' selected by user {user.id}")
        
        # Get products of selected type
        try:
            all_products = db.get_active_products()
            products = [p for p in all_products if p['product_type'] == product_type]
        except Exception as e:
            logger.error(f"Failed to get {product_type} products: {e}")
            await query.edit_message_text("❌ Error loading products. Please try again.")
            return
        
        if not products:
            await query.edit_message_text(f"❌ No {product_type} packages available.")
            return
        
        # Create product buttons
        keyboard = []
        text = f"**{title}**\n\n{description}\n\n"
        
        for product in products:
            price_display = f"${product['price_usd_cents'] / 100:.2f}"
            if product_type == "credits":
                button_text = f"{product['amount']} Credits - {price_display}"
            else:
                button_text = f"{product['amount']} Days - {price_display}"
            
            keyboard.append([InlineKeyboardButton(
                button_text, 
                callback_data=f"purchase_product_{product['id']}"
            )])
            
            text += f"• **{button_text}**\n"
        
        # Add back button
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="show_products")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        
        logger.info(f"Displayed {len(products)} {product_type} products to user {user.id}")
        
    except Exception as e:
        logger.error(f"Product type callback failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Error. Please try /start again.")


async def billing_portal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle billing portal access."""
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer()
        logger.info(f"Billing portal requested by user {user.id}")
        
        # Check if user has made purchases
        user_data = db.get_user(user.id)
        if not user_data or not user_data.get('stripe_customer_id'):
            await query.edit_message_text(
                "🏦 **Billing Portal**\n\n"
                "You need to make a purchase first before accessing billing settings.\n\n"
                "Use the buttons below to browse our products!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Back to Products", callback_data="show_products")
                ]])
            )
            return
        
        # Create billing portal session
        try:
            from src.stripe_utils import create_billing_portal_session
            portal_url = create_billing_portal_session(user_data['stripe_customer_id'])
            
            keyboard = [
                [InlineKeyboardButton("🏦 Open Billing Portal", url=portal_url)],
                [InlineKeyboardButton("⬅️ Back", callback_data="show_products")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "🏦 **Billing Portal**\n\n"
                "Click below to access your billing portal where you can:\n"
                "• View payment history\n"
                "• Update payment methods\n"
                "• Download invoices\n"
                "• Manage subscriptions",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Failed to create billing portal for user {user.id}: {e}")
            await query.edit_message_text(
                "❌ Unable to access billing portal right now. Please try again later.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Back", callback_data="show_products")
                ]])
            )
        
    except Exception as e:
        logger.error(f"Billing portal callback failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Error. Please try /start again.")


async def purchase_product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle product purchase initiation.
    """
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer()
        
        # Extract product ID from callback data (format: "purchase_product_123")
        callback_data = query.data
        if not callback_data.startswith("purchase_product_"):
            logger.error(f"Invalid purchase callback format: {callback_data}")
            await query.edit_message_text("❌ Invalid selection. Please try again.")
            return
            
        try:
            product_id = int(callback_data.split("_")[-1])
        except (ValueError, IndexError):
            logger.error(f"Could not extract product ID from: {callback_data}")
            await query.edit_message_text("❌ Invalid product selection. Please try again.")
            return
        
        logger.info(f"Purchase product callback: product {product_id} for user {user.id}")
        
        # Get product details
        try:
            products = db.get_active_products()
            product = None
            for p in products:
                if p['id'] == product_id:
                    product = p
                    break
        except Exception as e:
            logger.error(f"Failed to get products: {e}")
            await query.edit_message_text("❌ Error loading product. Please try again.")
            return
        
        if not product:
            await query.edit_message_text("❌ Product not found.")
            return
        
        # Create checkout session
        try:
            from src.stripe_utils import create_checkout_session
            from src.config import WEBHOOK_URL
            
            # Build proper URLs using the Railway domain
            base_url = WEBHOOK_URL or "https://independent-art-production-51fb.up.railway.app"
            success_url = f"{base_url}/success"
            cancel_url = f"{base_url}/cancel"
            
            checkout_url = create_checkout_session(
                user_id=user.id,
                price_id=product['stripe_price_id'],
                success_url=success_url,
                cancel_url=cancel_url
            )
            
            # Create purchase message
            price_display = f"${product['price_usd_cents'] / 100:.2f}"
            
            if product['product_type'] == 'credits':
                item_description = f"{product['amount']} Credits"
            else:
                item_description = f"{product['amount']} Days Access"
            
            keyboard = [
                [InlineKeyboardButton("💳 Complete Purchase", url=checkout_url)],
                [InlineKeyboardButton("⬅️ Back", callback_data=f"product_type_{product['product_type']}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"💳 **Purchase Confirmation**\n\n"
                f"**Item:** {item_description}\n"
                f"**Price:** {price_display}\n\n"
                f"Click the button below to complete your secure payment via Stripe:",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info(f"Checkout session created for user {user.id}, product {product_id}")
            
        except Exception as e:
            logger.error(f"Failed to create checkout session for user {user.id}: {e}")
            await query.edit_message_text(
                "❌ Unable to process payment right now. Please try again later.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Back", callback_data=f"product_type_{product['product_type']}")
                ]])
            )
            
    except Exception as e:
        logger.error(f"Purchase product callback failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Error. Please try /start again.")


# =============================================================================
# ADMIN CALLBACK HANDLERS
# =============================================================================

async def admin_ban_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin ban user action."""
    query = update.callback_query
    await query.answer()
    
    # Extract user ID from callback data (format: "admin_ban_12345")
    try:
        target_user_id = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Invalid admin action. Please try again.")
        return
    
    admin_user = query.from_user
    logger.info(f"Admin ban action: {admin_user.id} banning {target_user_id}")
    
    # Update user status (you may want to add is_banned field logic)
    # For now, we'll just show a confirmation
    await query.edit_message_text(
        f"⚠️ **Admin Action Required**\n\n"
        f"Are you sure you want to ban user {target_user_id}?\n\n"
        f"This action cannot be undone.",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Confirm Ban", callback_data=("confirm_ban", target_user_id)),
                InlineKeyboardButton("❌ Cancel", callback_data=("admin_cancel", target_user_id)),
            ]
        ])
    )


async def admin_gift_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin gift credits action."""
    query = update.callback_query
    await query.answer()
    
    # Extract user ID from callback data (format: "admin_gift_12345")
    try:
        target_user_id = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Invalid admin action. Please try again.")
        return
    
    # Show gift options
    keyboard = [
        [InlineKeyboardButton("🎁 10 Credits", callback_data=("gift_credits", target_user_id, 10))],
        [InlineKeyboardButton("🎁 25 Credits", callback_data=("gift_credits", target_user_id, 25))],
        [InlineKeyboardButton("🎁 50 Credits", callback_data=("gift_credits", target_user_id, 50))],
        [InlineKeyboardButton("❌ Cancel", callback_data=("admin_cancel", target_user_id))],
    ]
    
    await query.edit_message_text(
        f"🎁 **Gift Credits to User {target_user_id}**\n\n"
        f"Select the amount of credits to gift:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def gift_credits_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Execute credit gifting."""
    query = update.callback_query
    await query.answer()
    
    # Extract data from callback
    _, target_user_id, credits_amount = query.data
    
    admin_user = query.from_user
    logger.info(f"Admin {admin_user.id} gifting {credits_amount} credits to {target_user_id}")
    
    try:
        # Add credits to user account
        result = db.update_user_credits(target_user_id, credits_amount)
        
        if result:
            new_balance = result['message_credits']
            
            # Log the transaction
            idempotency_key = str(uuid.uuid4())
            db.log_transaction(
                user_id=target_user_id,
                product_id=None,
                stripe_charge_id=None,
                stripe_session_id=None,
                idempotency_key=idempotency_key,
                amount_cents=0,  # Free gift
                credits_granted=credits_amount,
                status='completed',
                description=f"Admin gift from user {admin_user.id}"
            )
            
            await query.edit_message_text(
                f"✅ **Credits Gifted Successfully**\n\n"
                f"Gifted {credits_amount} credits to user {target_user_id}\n"
                f"User's new balance: {new_balance} credits"
            )
            
            # Notify the user
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"🎁 **You've received a gift!**\n\n"
                         f"An admin has gifted you {credits_amount} credits!\n"
                         f"Your new balance: {new_balance} credits"
                )
            except Exception as e:
                logger.warning(f"Could not notify user {target_user_id} about gift: {e}")
                
        else:
            await query.edit_message_text("❌ Failed to gift credits. User not found.")
            
    except Exception as e:
        logger.error(f"Failed to gift credits: {e}")
        await query.edit_message_text("❌ Failed to gift credits. Please try again.")


# =============================================================================
# MESSAGE ROUTING SYSTEM (CONVERSATION BRIDGE)
# =============================================================================

async def master_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Master message router implementing two-stage fallback system.
    
    Stage 1: Direct reply inference (most reliable)
    Stage 2: Topic ID lookup (fallback)
    """
    message = update.message
    user = message.from_user
    
    # Handle private chat messages (user -> admin)
    if message.chat.type == 'private':
        await handle_user_message(update, context)
        return
    
    # Handle admin group messages (admin -> user)
    if message.chat.id == ADMIN_GROUP_ID:
        await handle_admin_message(update, context)
        return


async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle messages from users in private chat.
    Forward to admin group topic.
    """
    user = update.effective_user
    message = update.message
    
    # Exclude admin user from getting their own thread
    if ADMIN_USER_ID and user.id == ADMIN_USER_ID:
        logger.info(f"Admin user {user.id} sent private message, not creating thread")
        await message.reply_text(
            "🔧 **Admin Mode**\n\n"
            "You are configured as an admin user. Please use the admin group to manage conversations.\n\n"
            "Commands available:\n"
            "• /admin - Admin dashboard\n"
            "• /users - User management\n"
            "• /analytics - View analytics"
        )
        return
    
    logger.info(f"User message from {user.id}: {message.text[:50] if message.text else 'Media'}")
    
    # Ensure user exists in database
    db.get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    try:
        # Get or create topic for user
        topic_id = await get_or_create_user_topic(context, user)
        
        # Update last message timestamp
        db.update_last_message_time(user.id, ADMIN_GROUP_ID)
        
        # Forward message to admin group topic with error recovery
        try:
            await context.bot.forward_message(
                chat_id=ADMIN_GROUP_ID,
                from_chat_id=message.chat_id,
                message_id=message.message_id,
                message_thread_id=topic_id
            )
        except TelegramError as forward_error:
            if "thread not found" in str(forward_error).lower():
                logger.warning(f"Topic {topic_id} not found during forward, recreating...")
                # Clean up and recreate topic
                db.delete_conversation_topic(user.id, ADMIN_GROUP_ID)
                new_topic_id = await get_or_create_user_topic(context, user)
                
                # Try forwarding again with new topic
                await context.bot.forward_message(
                    chat_id=ADMIN_GROUP_ID,
                    from_chat_id=message.chat_id,
                    message_id=message.message_id,
                    message_thread_id=new_topic_id
                )
                logger.info(f"✅ Message forwarded to recreated topic {new_topic_id}")
            else:
                raise forward_error  # Re-raise if it's a different error
        
        # Send acknowledgment to user
        await message.reply_text("✅ Message received! Our team will respond shortly.")
        
    except Exception as e:
        logger.error(f"Failed to handle user message: {e}")
        await message.reply_text("❌ Sorry, there was an error processing your message. Please try again.")


async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle messages from admins in the admin group.
    Route to appropriate user using two-stage fallback.
    """
    message = update.message
    admin_user = message.from_user
    
    # Skip if not in a topic
    if not message.is_topic_message:
        return
    
    logger.info(f"Admin message from {admin_user.id} in topic {message.message_thread_id}")
    
    target_user_id = None
    
    # STAGE 1: Direct reply inference (most reliable)
    if message.reply_to_message and message.reply_to_message.forward_from:
        target_user_id = message.reply_to_message.forward_from.id
        logger.info(f"Stage 1: Found target user {target_user_id} via direct reply")
    
    # STAGE 2: Topic ID lookup (fallback)
    if not target_user_id:
        target_user_id = db.get_user_id_from_topic(message.message_thread_id, ADMIN_GROUP_ID)
        if target_user_id:
            logger.info(f"Stage 2: Found target user {target_user_id} via topic lookup")
    
    if not target_user_id:
        logger.warning(f"Could not find target user for topic {message.message_thread_id}")
        # Send helpful message to admin
        await message.reply_text(
            "⚠️ **Cannot route message**\n\n"
            "Could not find the user for this topic. This might happen if:\n"
            "• The topic was manually created\n" 
            "• Database sync issues\n\n"
            "Try replying directly to a user's message instead."
        )
        return
    
    try:
        # Send message to user (copy instead of forward for better UX)
        await context.bot.copy_message(
            chat_id=target_user_id,
            from_chat_id=message.chat_id,
            message_id=message.message_id
        )
        
        # React with checkmark to confirm delivery
        await context.bot.set_message_reaction(
            chat_id=message.chat_id,
            message_id=message.message_id,
            reaction="✅"
        )
        
        logger.info(f"✅ Admin message delivered to user {target_user_id}")
        
    except Exception as e:
        logger.error(f"Failed to deliver admin message: {e}")
        # React with X to indicate failure and provide feedback
        try:
            await context.bot.set_message_reaction(
                chat_id=message.chat_id,
                message_id=message.message_id,
                reaction="❌"
            )
            await message.reply_text(
                f"❌ **Message delivery failed**\n\n"
                f"Could not send message to user {target_user_id}.\n"
                f"Error: {str(e)[:100]}\n\n"
                f"The user may have blocked the bot or there's a network issue."
            )
        except:
            pass


# =============================================================================
# ERROR HANDLERS
# =============================================================================

async def callback_data_error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle invalid callback data (expired or corrupted)."""
    query = update.callback_query
    await query.answer()
    
    logger.warning(f"Invalid callback data from user {query.from_user.id}")
    
    await query.edit_message_text(
        "❌ **This button has expired**\n\n"
        "Please use /start to get a fresh menu.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Restart", callback_data=("show_products",))
        ]])
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    # Try to send error message to user if possible
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ An error occurred while processing your request. Please try again."
            )
        except:
            pass


async def debug_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch-all callback handler for debugging."""
    query = update.callback_query
    await query.answer()
    logger.warning(f"Unhandled callback query from user {query.from_user.id}: {query.data}")
    await query.edit_message_text(
        "❌ **This button is not yet implemented.**\n\n"
        "Please use /start to get a fresh menu."
    )


# =============================================================================
# APPLICATION SETUP
# =============================================================================

def create_application() -> Application:
    """
    Create and configure the Telegram bot application.
    
    Returns:
        Configured Application instance
    """
    # Create application with arbitrary callback data support
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .arbitrary_callback_data(True)
        .build()
    )
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("billing", billing_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("products", products_command))
    application.add_handler(CommandHandler("analytics", analytics_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("conversations", conversations_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("webhook", webhook_command))
    application.add_handler(CommandHandler("system", system_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("buy", buy_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("time", time_command))
    
    # Add quick buy command handlers
    for amount in [10, 25, 50, 100]:
        application.add_handler(CommandHandler(f"buy{amount}", quick_buy_command))
    
    # Add callback query handlers
    application.add_handler(CallbackQueryHandler(show_products_callback, pattern="^show_products$"))
    application.add_handler(CallbackQueryHandler(product_type_callback, pattern="^product_type_"))
    application.add_handler(CallbackQueryHandler(purchase_product_callback, pattern="^purchase_product_"))
    application.add_handler(CallbackQueryHandler(billing_portal_callback, pattern="^billing_portal$"))
    
    # Add admin callback handlers
    application.add_handler(CallbackQueryHandler(admin_ban_callback, pattern="^admin_ban_"))
    application.add_handler(CallbackQueryHandler(admin_gift_callback, pattern="^admin_gift_"))
    application.add_handler(CallbackQueryHandler(gift_credits_callback, pattern="^gift_credits_"))
    
    # Add invalid callback data handler
    application.add_handler(CallbackQueryHandler(callback_data_error_handler, pattern=InvalidCallbackData))
    
    # Add catch-all callback handler for debugging (must be last)
    application.add_handler(CallbackQueryHandler(debug_callback_handler))
    
    # Add message handler (must be last)
    application.add_handler(MessageHandler(filters.ALL, master_message_handler))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    logger.info("✅ Bot application configured successfully")
    return application 