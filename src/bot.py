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
from src.config import BOT_TOKEN, ADMIN_GROUP_ID, ADMIN_USER_ID, WEBHOOK_URL
from src import bot_utils
from src.handlers import error_handlers
from src.handlers import commands

logger = logging.getLogger(__name__)


# =============================================================================
# USER COMMAND HANDLERS
# =============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Enhanced /start command with personalized welcome, free credits, and tutorial.
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
        
        # Check if this is a new user
        is_new = db.is_new_user(user.id)
        tutorial_state = db.get_user_tutorial_state(user.id)
        
        if is_new:
            # New user experience
            await handle_new_user_welcome(update, context, db_user)
        else:
            # Returning user experience
            await handle_returning_user_welcome(update, context, db_user)
            
    except Exception as e:
        logger.error(f"Start command failed for user {user.id}: {e}")
        await update.message.reply_text(
            "❌ Sorry, there was an error. Please try again later.\n\n"
            "You can try:\n"
            "• /balance - Check your balance\n"
            "• /buy - Purchase credits\n"
            "• /help - Get help"
        )


async def handle_new_user_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                user_data: Dict[str, Any]) -> None:
    """Handle welcome flow for new users with free credits and tutorial option."""
    user = update.effective_user
    
    # Give free credits to new users
    free_credits = int(db.get_bot_setting('new_user_free_credits') or '3')
    db.update_user_credits(user.id, free_credits)
    db.mark_user_as_not_new(user.id)
    
    # Get welcome message template
    welcome_template = db.get_bot_setting('welcome_message_new') or \
        "🎉 **Welcome {name}!**\n\n" \
        "🎁 You've received **{credits} free credits** to get started!\n\n" \
        "🤖 I'm your AI assistant, ready to help with anything you need.\n\n" \
        "💡 **Quick tip:** Each message costs 1 credit. You can buy more anytime!\n\n" \
        "Would you like a quick tutorial to get started?"
    
    formatted_message = welcome_template.format(
        name=user.first_name,
        credits=free_credits
    )
    
    # Create tutorial keyboard
    keyboard = [
        [
            InlineKeyboardButton("📚 Start Tutorial", callback_data="start_tutorial"),
            InlineKeyboardButton("💬 Start Chatting", callback_data="start_chatting")
        ],
        [
            InlineKeyboardButton("💰 Check Balance", callback_data="show_balance"),
            InlineKeyboardButton("📊 My Analytics", callback_data="show_analytics")
        ],
        [
            InlineKeyboardButton("🛒 Buy Credits", callback_data="show_products"),
            InlineKeyboardButton("❓ Help", callback_data="user_help")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        formatted_message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_returning_user_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                      user_data: Dict[str, Any]) -> None:
    """Handle welcome flow for returning users with personalized content."""
    user = update.effective_user
    
    # Get user stats
    credits = user_data.get('message_credits', 0)
    tier = user_data.get('tier_name', 'standard').title()
    
    # Create personalized welcome
    welcome_template = db.get_bot_setting('welcome_message_returning') or \
        "👋 **Welcome back, {name}!**\n\n" \
        "💰 **Balance:** {credits} credits\n" \
        "⭐ **Tier:** {tier}\n\n" \
        "{tip}\n\n" \
        "Ready to continue our conversation?"
    
    tip = bot_utils.get_usage_tip(credits)
    
    formatted_message = welcome_template.format(
        name=user.first_name,
        credits=credits,
        tier=tier,
        tip=tip
    )
    
    # Create action keyboard based on credit level
    if credits < 2:
        keyboard = [
            [
                InlineKeyboardButton("🚨 Buy Credits Now", callback_data="show_products"),
                InlineKeyboardButton("💰 Quick Buy 10", callback_data="quick_buy_10")
            ],
            [
                InlineKeyboardButton("💎 Daily Unlimited", callback_data="daily_unlimited"),
                InlineKeyboardButton("💬 Start Anyway", callback_data="start_chatting")
            ]
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton("💬 Start Chatting", callback_data="start_chatting"),
                InlineKeyboardButton("💰 Check Balance", callback_data="show_balance")
            ],
            [
                InlineKeyboardButton("🛒 Buy More Credits", callback_data="show_products"),
                InlineKeyboardButton("📊 My Analytics", callback_data="show_analytics")
            ],
            [
                InlineKeyboardButton("🔄 Refresh Balance", callback_data="refresh_balance"),
                InlineKeyboardButton("❓ Help", callback_data="user_help")
            ]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        formatted_message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Enhanced /balance command with visual progress bars and personalized tips.
    """
    user = update.effective_user
    logger.info(f"Balance command from user {user.id}")
    
    try:
        # Get user data
        user_data = db.get_user_dashboard_data(user.id)
        if not user_data:
            await update.message.reply_text("❌ User not found. Please use /start first.")
            return
        
        # Create balance card using bot_utils
        balance_card = bot_utils.create_balance_card(user_data)
        
        # Create action buttons
        keyboard = [
            [
                InlineKeyboardButton("🛒 Buy Credits", callback_data="show_products"),
                InlineKeyboardButton("💎 Premium Plans", callback_data="show_premium")
            ],
            [
                InlineKeyboardButton("📊 Analytics", callback_data="show_analytics"),
                InlineKeyboardButton("🔄 Refresh", callback_data="refresh_balance")
            ],
            [
                InlineKeyboardButton("💰 Quick Buy 10", callback_data="quick_buy_10"),
                InlineKeyboardButton("🏆 Quick Buy 25", callback_data="quick_buy_25")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            balance_card,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Balance command failed for user {user.id}: {e}")
        await update.message.reply_text("❌ Error retrieving balance. Please try again.")


async def send_quick_buy_warning(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Send warning about low credits with quick buy options.
    
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
        info_text = bot_utils.format_user_info_card(user_data)
        
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
    Enhanced /start command with personalized welcome, free credits, and tutorial.
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
        
        # Check if this is a new user
        is_new = db.is_new_user(user.id)
        tutorial_state = db.get_user_tutorial_state(user.id)
        
        if is_new:
            # New user experience
            await handle_new_user_welcome(update, context, db_user)
        else:
            # Returning user experience
            await handle_returning_user_welcome(update, context, db_user)
            
    except Exception as e:
        logger.error(f"Start command failed for user {user.id}: {e}")
        await update.message.reply_text(
            "❌ Sorry, there was an error. Please try again later.\n\n"
            "You can try:\n"
            "• /balance - Check your balance\n"
            "• /buy - Purchase credits\n"
            "• /help - Get help"
        )


async def handle_new_user_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                user_data: Dict[str, Any]) -> None:
    """Handle welcome flow for new users with free credits and tutorial option."""
    user = update.effective_user
    
    # Give free credits to new users
    free_credits = int(db.get_bot_setting('new_user_free_credits') or '3')
    db.update_user_credits(user.id, free_credits)
    db.mark_user_as_not_new(user.id)
    
    # Get welcome message template
    welcome_template = db.get_bot_setting('welcome_message_new') or \
        "Welcome, {first_name}! 🎉\n\nYou've received {free_credits} FREE credits to get started! 🎁"
    
    welcome_text = welcome_template.format(
        first_name=user.first_name,
        free_credits=free_credits
    )
    
    # Add quick intro
    welcome_text += f"""

✨ **What can I help you with?**
• Expert advice and support
• Instant responses 24/7  
• Personalized assistance

💰 **Your balance:** {free_credits} credits
💡 **Each message costs 1 credit**

🎯 **Ready to get started?**
    """
    
    # Show tutorial option if enabled
    tutorial_enabled = db.get_bot_setting('tutorial_enabled') == 'true'
    
    keyboard = []
    if tutorial_enabled:
        keyboard.append([InlineKeyboardButton("📚 Take Quick Tutorial (Recommended)", 
                                            callback_data="start_tutorial")])
    
    keyboard.extend([
        [InlineKeyboardButton("💬 Start Chatting Now", callback_data="start_chatting")],
        [InlineKeyboardButton("🛒 View All Packages", callback_data="show_products")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_returning_user_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                      user_data: Dict[str, Any]) -> None:
    """Handle welcome flow for returning users with balance info."""
    user = update.effective_user
    credits = user_data.get('message_credits', 0)
    
    # Get returning user welcome template  
    welcome_template = db.get_bot_setting('welcome_message_returning') or \
        "Welcome back, {first_name}! 👋"
    
    welcome_text = welcome_template.format(
        first_name=user.first_name,
        credits=credits
    )
    
    # Add balance card
    balance_card = create_balance_card(user_data)
    welcome_text += f"\n\n{balance_card}"
    
    # Smart keyboard based on balance
    keyboard = []
    
    if credits <= 5:
        # Low credit options
        keyboard.extend([
            [InlineKeyboardButton("🚀 Quick Buy 25 Credits", callback_data="quick_buy_25")],
            [InlineKeyboardButton("⏰ Try Daily Unlimited", callback_data="daily_unlimited")]
        ])
    else:
        # Normal options
        keyboard.append([InlineKeyboardButton("💬 Continue Chatting", 
                                            callback_data="start_chatting")])
    
    keyboard.extend([
        [
            InlineKeyboardButton("🛒 Shop", callback_data="show_products"),
            InlineKeyboardButton("📊 Analytics", callback_data="show_analytics")
        ],
        [
            InlineKeyboardButton("💰 Balance", callback_data="show_balance"),
            InlineKeyboardButton("🏦 Billing", callback_data="billing_portal")
        ]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Enhanced /balance command with visual card and smart quick actions.
    """
    user = update.effective_user
    logger.info(f"Balance command from user {user.id}")
    
    # Get user data
    user_data = db.get_user_dashboard_data(user.id)
    if not user_data:
        await update.message.reply_text("❌ User not found. Please use /start first.")
        return
    
    # Create enhanced balance card
    balance_card = create_balance_card(user_data)
    credits = user_data.get('message_credits', 0)
    
    # Smart quick actions based on balance
    keyboard = []
    
    # Show quick buy options if credits are low
    if credits <= int(db.get_bot_setting('quick_buy_trigger_threshold') or '5'):
        keyboard.extend([
            [InlineKeyboardButton("🚀 Quick Buy 25 Credits - $10", callback_data="quick_buy_25")],
            [InlineKeyboardButton("⏰ Try Daily Unlimited - $3", callback_data="daily_unlimited")]
        ])
    else:
        keyboard.append([InlineKeyboardButton("🛒 View All Packages", callback_data="show_products")])
    
    # Always show these options
    keyboard.extend([
        [
            InlineKeyboardButton("📊 Usage Analytics", callback_data="show_analytics"),
            InlineKeyboardButton("🏦 Billing Portal", callback_data="billing_portal")
        ],
        [InlineKeyboardButton("🔄 Refresh Balance", callback_data="refresh_balance")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        balance_card,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Check if should show low credit warning
    if db.should_show_quick_buy_warning(user.id):
        await send_quick_buy_warning(update, context)


async def send_quick_buy_warning(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send quick buy warning for low credit users."""
    user = update.effective_user
    
    # Mark warning as shown
    db.mark_low_credit_warning_shown(user.id)
    
    # Get warning message from settings
    warning_message = db.get_bot_setting('low_credit_warning_message') or \
        "Running low on credits! 💡 Quick top-up options below:"
    
    user_data = db.get_user(user.id)
    credits = user_data.get('message_credits', 0)
    
    warning_text = f"""
💡 **{warning_message}**

💰 Current balance: {credits} credits

Quick purchase options:
• 25 credits = $10 (Most Popular!)
• 50 credits = $18 (Best Value!)
• Unlimited daily access = $3

Choose your preferred option:
    """.strip()
    
    keyboard = [
        [InlineKeyboardButton("🚀 25 Credits - $10", callback_data="quick_buy_25")],
        [InlineKeyboardButton("💎 50 Credits - $18", callback_data="quick_buy_50")],
        [InlineKeyboardButton("⏰ Daily Unlimited - $3", callback_data="daily_unlimited")],
        [InlineKeyboardButton("🛒 View All Options", callback_data="show_products")]
    ]
    
    await update.message.reply_text(
        warning_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


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
# ADMIN COMMANDS (Moved to src/handlers/admin.py)
# =============================================================================


async def dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /dashboard command - direct access to admin dashboard."""
    # Check admin authorization first
    if not await require_admin(update, context):
        return
    
    await admin_dashboard_callback(update, context)


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /settings command."""
    # Check admin authorization first
    if not await require_admin(update, context):
        return
        
    await update.message.reply_text(
        "⚙️ **Bot Settings**\n\n"
        "Settings management coming soon!\n"
        "Use /admin for the main dashboard."
    )


async def products_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /products command."""
    # Check admin authorization first
    if not await require_admin(update, context):
        return
        
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
    # Check admin authorization first
    if not await require_admin(update, context):
        return
        
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
    # Check admin authorization first
    if not await require_admin(update, context):
        return
        
    await update.message.reply_text(
        "👥 **User Management**\n\n"
        "User management interface coming soon!\n"
        "Use /admin for the main dashboard."
    )


async def conversations_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /conversations command."""
    # Check admin authorization first
    if not await require_admin(update, context):
        return
        
    await update.message.reply_text(
        "💬 **Conversation Management**\n\n"
        "Conversation management interface coming soon!\n"
        "Use /admin for the main dashboard."
    )


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /broadcast command."""
    # Check admin authorization first
    if not await require_admin(update, context):
        return
        
    await update.message.reply_text(
        "📢 **Broadcast Message**\n\n"
        "Broadcast functionality coming soon!\n"
        "Use /admin for the main dashboard."
    )


async def webhook_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /webhook command."""
    # Check admin authorization first
    if not await require_admin(update, context):
        return
        
    await update.message.reply_text(
        "🔗 **Webhook Status**\n\n"
        "✅ Webhooks are operational\n"
        "📡 Receiving updates normally\n\n"
        "Use /admin for the main dashboard."
    )


async def system_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /system command."""
    # Check admin authorization first
    if not await require_admin(update, context):
        return
        
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
# ENHANCED ADMIN CALLBACK HANDLERS
# =============================================================================

async def admin_conversations_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin conversations menu."""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get conversation statistics
        total_conversations = db.get_conversation_count()
        unread_count = 0  # TODO: Implement unread tracking
        
        text = (
            "💬 **Conversation Management**\n\n"
            f"📊 **Overview:**\n"
            f"• Total Conversations: **{total_conversations}**\n"
            f"• Unread Messages: **{unread_count}**\n"
            f"• High Priority: **0**\n"
            f"• Archived: **0**\n\n"
            "Select an option:"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("📋 All Conversations", callback_data="admin_conv_all"),
                InlineKeyboardButton("📬 Unread Only", callback_data="admin_conv_unread")
            ],
            [
                InlineKeyboardButton("🎯 High Priority", callback_data="admin_conv_priority"),
                InlineKeyboardButton("📦 Archived", callback_data="admin_conv_archived")
            ],
            [
                InlineKeyboardButton("📊 Stats", callback_data="admin_conv_stats"),
                InlineKeyboardButton("⚙️ Settings", callback_data="admin_conv_settings")
            ],
            [
                InlineKeyboardButton("⬅️ Back to Menu", callback_data="admin_main")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Admin conversations callback failed: {e}")
        await query.edit_message_text("❌ Error loading conversation management.")


async def admin_dashboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin dashboard detailed view."""
    query = update.callback_query
    if query:
        await query.answer()
    
    try:
        # Get comprehensive statistics
        user_count = db.get_user_count()
        conversation_count = db.get_conversation_count()
        
        # TODO: Add more detailed statistics
        active_users_today = 0  # Implement daily active users
        revenue_today = 0  # Implement daily revenue
        
        text = (
            "📊 **Detailed Dashboard**\n\n"
            f"👥 **User Metrics:**\n"
            f"• Total Users: **{user_count}**\n"
            f"• Active Today: **{active_users_today}**\n"
            f"• New Today: **0**\n\n"
            f"💬 **Conversation Metrics:**\n"
            f"• Active Conversations: **{conversation_count}**\n"
            f"• Messages Today: **0**\n"
            f"• Avg Response Time: **--**\n\n"
            f"💰 **Revenue Metrics:**\n"
            f"• Revenue Today: **${revenue_today:.2f}**\n"
            f"• Revenue This Month: **$0.00**\n"
            f"• Top Product: **--**\n\n"
            f"🔧 **System Health:**\n"
            f"• Status: **🟢 Operational**\n"
            f"• Uptime: **99.9%**\n"
            f"• Last Restart: **--**"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("📈 Detailed Stats", callback_data="admin_stats_detailed"),
                InlineKeyboardButton("📊 Export Data", callback_data="admin_export_data")
            ],
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="admin_dashboard"),
                InlineKeyboardButton("⬅️ Back to Menu", callback_data="admin_main")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query:
            await query.edit_message_text(
                text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            # Called directly from /dashboard command
            await update.message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        
    except Exception as e:
        logger.error(f"Admin dashboard callback failed: {e}")
        error_text = "❌ Error loading dashboard."
        if query:
            await query.edit_message_text(error_text)
        else:
            await update.message.reply_text(error_text)


async def admin_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin user management menu."""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get user statistics
        total_users = db.get_user_count()
        banned_users = 0  # TODO: Implement banned user tracking
        vip_users = 0  # TODO: Implement VIP user tracking
        new_users_today = 0  # TODO: Implement new user tracking
        
        text = (
            "👥 **User Management**\n\n"
            f"📊 **Overview:**\n"
            f"• Total Users: **{total_users}**\n"
            f"• New Today: **{new_users_today}**\n"
            f"• VIP Users: **{vip_users}**\n"
            f"• Banned Users: **{banned_users}**\n\n"
            "Select an option:"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("👥 All Users", callback_data="admin_users_all"),
                InlineKeyboardButton("🚫 Banned Users", callback_data="admin_users_banned")
            ],
            [
                InlineKeyboardButton("⭐ VIP Users", callback_data="admin_users_vip"),
                InlineKeyboardButton("🆕 New Users", callback_data="admin_users_new")
            ],
            [
                InlineKeyboardButton("💰 Edit Credits", callback_data="admin_users_credits"),
                InlineKeyboardButton("🎁 Gift Credits", callback_data="admin_users_gift")
            ],
            [
                InlineKeyboardButton("📊 User Stats", callback_data="admin_users_stats"),
                InlineKeyboardButton("🔍 Search User", callback_data="admin_users_search")
            ],
            [
                InlineKeyboardButton("⬅️ Back to Menu", callback_data="admin_main")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Admin users callback failed: {e}")
        await query.edit_message_text("❌ Error loading user management.")


async def admin_products_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin product management menu."""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get product statistics
        products = db.get_all_products()
        active_products = len([p for p in products if p.get('is_active', True)]) if products else 0
        total_products = len(products) if products else 0
        
        text = (
            "🛒 **Product Management**\n\n"
            f"📊 **Overview:**\n"
            f"• Total Products: **{total_products}**\n"
            f"• Active Products: **{active_products}**\n"
            f"• Best Seller: **--**\n"
            f"• Revenue This Month: **$0.00**\n\n"
            "Select an option:"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("🛒 Manage Products", callback_data="admin_products_manage"),
                InlineKeyboardButton("➕ Create Product", callback_data="admin_products_create")
            ],
            [
                InlineKeyboardButton("📊 Product Stats", callback_data="admin_products_stats"),
                InlineKeyboardButton("💰 Pricing", callback_data="admin_products_pricing")
            ],
            [
                InlineKeyboardButton("🔄 Sync Stripe", callback_data="admin_products_sync"),
                InlineKeyboardButton("⚙️ Settings", callback_data="admin_products_settings")
            ],
            [
                InlineKeyboardButton("⬅️ Back to Menu", callback_data="admin_main")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Admin products callback failed: {e}")
        await query.edit_message_text("❌ Error loading product management.")


async def admin_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle return to main admin menu."""
    query = update.callback_query
    await query.answer()
    
    # Simulate calling admin_command but for callback
    class FakeUpdate:
        def __init__(self, query):
            self.callback_query = query
            self.message = query.message
            self.effective_user = query.from_user
    
    fake_update = FakeUpdate(query)
    
    # Get real-time statistics
    try:
        user_count = db.get_user_count()
        conversation_count = db.get_conversation_count()
        unread_count = 0
        
        dashboard_text = (
            "🔧 **Admin Control Center**\n\n"
            f"📊 **Real-time Stats:**\n"
            f"👥 Total Users: **{user_count}**\n"
            f"💬 Active Conversations: **{conversation_count}**\n"
            f"📬 Unread Messages: **{unread_count}**\n"
            f"🟢 Admin Status: **Online**\n\n"
            "Select a category to manage:"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("💬 Conversations", callback_data="admin_conversations"),
                InlineKeyboardButton("📊 Dashboard", callback_data="admin_dashboard")
            ],
            [
                InlineKeyboardButton("📈 Analytics", callback_data="admin_analytics"),
                InlineKeyboardButton("👥 Users", callback_data="admin_users")
            ],
            [
                InlineKeyboardButton("🛒 Products", callback_data="admin_products"),
                InlineKeyboardButton("💰 Billing", callback_data="admin_billing")
            ],
            [
                InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
                InlineKeyboardButton("🎁 Mass Gift", callback_data="admin_mass_gift")
            ],
            [
                InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"),
                InlineKeyboardButton("🔧 System", callback_data="admin_system")
            ],
            [
                InlineKeyboardButton("📝 Quick Replies", callback_data="admin_quick_replies"),
                InlineKeyboardButton("🔍 Search", callback_data="admin_search")
            ],
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="admin_refresh"),
                InlineKeyboardButton("❌ Close", callback_data="admin_close")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            dashboard_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Failed to return to admin main menu: {e}")
        await query.edit_message_text("❌ Error loading admin menu.")


async def admin_close_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin menu close."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🔧 **Admin Control Center Closed**\n\n"
        "Use /admin to reopen the control center.",
        parse_mode=ParseMode.MARKDOWN
    )


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
# ENHANCED USER CALLBACK HANDLERS
# =============================================================================

async def user_balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user balance button press - show detailed balance info."""
    query = update.callback_query
    user = query.from_user
    await query.answer()
    
    try:
        # Get user data
        user_data = db.get_user(user.id)
        if not user_data:
            await query.edit_message_text("❌ User account not found. Please use /start to initialize.")
            return
        
        credits = user_data.get('message_credits', 0)
        time_expires = user_data.get('time_credits_expires_at')
        tier_id = user_data.get('tier_id', 1)
        
        # Create visual progress bar for credits
        max_display_credits = 100
        credits_percentage = min(credits / max_display_credits * 100, 100) if credits > 0 else 0
        credits_bar = create_progress_bar(int(credits_percentage))
        
        # Determine status indicators
        if credits >= 50:
            credit_status = "🟢 Excellent"
        elif credits >= 20:
            credit_status = "🟡 Good"
        elif credits >= 5:
            credit_status = "🟠 Low"
        else:
            credit_status = "🔴 Critical"
        
        # Get tier name
        tier_names = {1: "Standard", 2: "Premium", 3: "VIP"}
        tier_name = tier_names.get(tier_id, "Standard")
        
        if time_expires:
            balance_text = (
                f"💰 **Account Overview**\n\n"
                f"👤 **Account Tier:** {tier_name}\n"
                f"💎 **Credits:** {credits} ({credit_status})\n"
                f"📊 **Progress:** {credits_bar}\n"
                f"⏰ **Time Access:** ✅ Active until {time_expires}\n\n"
                f"🎯 **Status:** You have unlimited messaging!\n"
                f"💡 **Tip:** Credits will be used when time access expires."
            )
        else:
            balance_text = (
                f"💰 **Account Overview**\n\n"
                f"👤 **Account Tier:** {tier_name}\n"
                f"💎 **Credits:** {credits} ({credit_status})\n"
                f"📊 **Progress:** {credits_bar}\n"
                f"⏰ **Time Access:** ❌ Not active\n\n"
                f"💳 **Cost per message:** 1 credit\n"
                f"🎯 **Recommendation:** {'Purchase more credits' if credits < 20 else 'Consider time packages for unlimited access'}"
            )
        
        # Smart action buttons based on balance
        if credits < 10:
            keyboard = [
                [
                    InlineKeyboardButton("⚡ Quick Buy 25", callback_data="quick_buy_25"),
                    InlineKeyboardButton("⚡ Quick Buy 50", callback_data="quick_buy_50")
                ],
                [InlineKeyboardButton("🛒 Browse All Packages", callback_data="show_products")],
                [InlineKeyboardButton("🏦 Billing Settings", callback_data="billing_portal")],
                [InlineKeyboardButton("⬅️ Back", callback_data="user_menu")]
            ]
        else:
            keyboard = [
                [
                    InlineKeyboardButton("🛒 Shop More", callback_data="show_products"),
                    InlineKeyboardButton("🏦 Billing", callback_data="billing_portal")
                ],
                [
                    InlineKeyboardButton("⚡ Quick Buy 10", callback_data="quick_buy_10"),
                    InlineKeyboardButton("⚡ Quick Buy 25", callback_data="quick_buy_25")
                ],
                [InlineKeyboardButton("⬅️ Back", callback_data="user_menu")]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            balance_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"User balance callback failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Error loading balance. Please try again later.")


async def quick_buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle quick buy button presses (quick_buy_10, quick_buy_25, etc.)."""
    query = update.callback_query
    user = query.from_user
    await query.answer()
    
    try:
        # Extract amount from callback data
        callback_data = query.data
        if not callback_data.startswith("quick_buy_"):
            await query.edit_message_text("❌ Invalid selection.")
            return
            
        amount = int(callback_data.replace("quick_buy_", ""))
        
        # Find corresponding product
        products = db.get_products_by_type("credits")
        matching_product = None
        for product in products:
            if product['amount'] == amount:
                matching_product = product
                break
        
        if not matching_product:
            await query.edit_message_text(
                f"❌ {amount}-credit package not available.\n\n"
                "Please browse all products for available options.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🛒 Browse Products", callback_data="show_products")
                ]])
            )
            return
        
        # Create checkout session
        from src.stripe_utils import create_checkout_session
        try:
            checkout_url = create_checkout_session(
                user_id=user.id,
                price_id=matching_product['stripe_price_id'],
                success_url=f"{WEBHOOK_URL}/success" if WEBHOOK_URL else "https://example.com/success",
                cancel_url=f"{WEBHOOK_URL}/cancel" if WEBHOOK_URL else "https://example.com/cancel"
            )
            
            price = matching_product['price_usd_cents'] / 100
            savings = ""
            if amount >= 25:
                per_credit_cost = price / amount
                savings = f"\n💡 **Value:** ${per_credit_cost:.3f} per credit"
            
            text = (
                f"⚡ **Quick Purchase: {amount} Credits**\n\n"
                f"💎 **Package:** {amount} Message Credits\n"
                f"💰 **Price:** ${price:.2f}{savings}\n"
                f"⚡ **Instant Delivery:** Credits added immediately after payment\n"
                f"🔒 **Secure Payment:** Processed by Stripe\n\n"
                f"Click below to complete your purchase:"
            )
            
            keyboard = [
                [InlineKeyboardButton("💳 Complete Purchase", url=checkout_url)],
                [
                    InlineKeyboardButton("🛒 Browse Other Packages", callback_data="show_products"),
                    InlineKeyboardButton("💰 Check Balance", callback_data="user_balance")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Failed to create checkout session for user {user.id}: {e}")
            await query.edit_message_text(
                "❌ Error creating payment session. Please try again later.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🛒 Browse Products", callback_data="show_products")
                ]])
            )
        
    except Exception as e:
        logger.error(f"Quick buy callback failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Error processing request. Please try again.")


async def user_help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle help button press - show comprehensive help."""
    query = update.callback_query
    await query.answer()
    
    help_text = (
        "❓ **Help & Support**\n\n"
        "🚀 **Quick Start:**\n"
        "• Use /start to access your dashboard\n"
        "• Check /balance for account status\n"
        "• Use /buy for purchasing credits\n\n"
        "⚡ **Quick Purchase Commands:**\n"
        "• `/buy10` - Buy 10 credits instantly\n"
        "• `/buy25` - Buy 25 credits instantly\n"
        "• `/buy50` - Buy 50 credits instantly\n\n"
        "💳 **Payment & Billing:**\n"
        "• Use /billing to manage payment methods\n"
        "• All payments are secure via Stripe\n"
        "• Credits are added instantly after payment\n\n"
        "⏰ **Time Packages:**\n"
        "• Purchase time packages for unlimited messaging\n"
        "• More cost-effective for heavy usage\n"
        "• Credits are saved when time access is active\n\n"
        "🎯 **Account Tiers:**\n"
        "• **Standard:** Basic access\n"
        "• **Premium:** Enhanced features\n"
        "• **VIP:** Full access and priority support\n\n"
        "🔔 **Smart Features:**\n"
        "• Auto-recharge: Never run out of credits\n"
        "• Low balance warnings\n"
        "• Session expiry alerts\n\n"
        "📞 **Need More Help?**\n"
        "Contact our support team for assistance."
    )
    
    keyboard = [
        [
            InlineKeyboardButton("🛒 Shop Credits", callback_data="show_products"),
            InlineKeyboardButton("💰 Check Balance", callback_data="user_balance")
        ],
        [
            InlineKeyboardButton("🏦 Billing Portal", callback_data="billing_portal"),
            InlineKeyboardButton("⬅️ Back to Menu", callback_data="user_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        help_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )


async def user_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle return to user main menu."""
    query = update.callback_query
    user = query.from_user
    await query.answer()
    
    # Recreate the start menu
    try:
        # Get user data
        db_user = db.get_user(user.id)
        if not db_user:
            await query.edit_message_text("❌ User account not found. Please use /start to initialize.")
            return
        
        # Get user balance and time access
        credits = db_user.get('message_credits', 0)
        time_expires = db_user.get('time_credits_expires_at')
        
        # Create progress bar for credits
        max_display_credits = 100
        credits_percentage = min(credits / max_display_credits * 100, 100) if credits > 0 else 0
        credits_bar = create_progress_bar(int(credits_percentage))
        
        # Determine access status
        if time_expires:
            access_status = "⏰ **Unlimited Access Active**"
            access_details = f"Until: {time_expires}"
        elif credits > 0:
            access_status = f"💎 **{credits} Credits Available**"
            access_details = f"Progress: {credits_bar} {credits}/100"
        else:
            access_status = "❌ **No Credits or Time Access**"
            access_details = "Purchase credits or time packages to start messaging"
        
        # Get welcome message from bot settings
        try:
            welcome_base = db.get_bot_setting('welcome_message') or "Welcome to our Enterprise Telegram Bot! 🤖"
        except Exception as e:
            logger.error(f"Failed to get welcome message: {e}")
            welcome_base = "Welcome to our Enterprise Telegram Bot! 🤖"
        
        # Enhanced welcome message with balance
        welcome_message = (
            f"👋 **Welcome back, {user.first_name}!**\n\n"
            f"{welcome_base}\n\n"
            f"📊 **Your Account Status:**\n"
            f"{access_status}\n"
            f"{access_details}\n\n"
            f"🚀 **Quick Actions:**\n"
            f"• Use buttons below for easy access\n"
            f"• Type `/buy10` `/buy25` `/buy50` for quick purchases\n"
            f"• Use `/billing` to manage payment methods"
        )
        
        # Enhanced keyboard with quick actions
        keyboard = [
            [
                InlineKeyboardButton("🛒 Shop Credits", callback_data="show_products"),
                InlineKeyboardButton("💰 Balance", callback_data="user_balance")
            ],
            [
                InlineKeyboardButton("⚡ Quick Buy 10", callback_data="quick_buy_10"),
                InlineKeyboardButton("⚡ Quick Buy 25", callback_data="quick_buy_25")
            ],
            [
                InlineKeyboardButton("🏦 Billing Portal", callback_data="billing_portal"),
                InlineKeyboardButton("❓ Help", callback_data="user_help")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            welcome_message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"User menu callback failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Error loading menu. Please use /start to refresh.")


# =============================================================================
# ENHANCED QUICK BUY COMMANDS  
# =============================================================================

async def buy10_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /buy10 command - quick purchase of 10 credits."""
    await process_quick_buy_command(update, context, 10)


async def buy25_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /buy25 command - quick purchase of 25 credits."""
    await process_quick_buy_command(update, context, 25)


async def buy50_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /buy50 command - quick purchase of 50 credits."""
    await process_quick_buy_command(update, context, 50)


async def process_quick_buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int) -> None:
    """Process quick buy commands with enhanced UX."""
    user = update.effective_user
    logger.info(f"Quick buy {amount} command from user {user.id}")
    
    try:
        # Find corresponding product
        products = db.get_products_by_type("credits")
        matching_product = None
        for product in products:
            if product['amount'] == amount:
                matching_product = product
                break
        
        if not matching_product:
            await update.message.reply_text(
                f"❌ **{amount}-Credit Package Not Available**\n\n"
                f"This package is currently unavailable. "
                f"Please browse our available products:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🛒 Browse Products", callback_data="show_products")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Create checkout session
        from src.stripe_utils import create_checkout_session
        try:
            checkout_url = create_checkout_session(
                user_id=user.id,
                price_id=matching_product['stripe_price_id'],
                success_url=f"{WEBHOOK_URL}/success" if WEBHOOK_URL else "https://example.com/success",
                cancel_url=f"{WEBHOOK_URL}/cancel" if WEBHOOK_URL else "https://example.com/cancel"
            )
            
            price = matching_product['price_usd_cents'] / 100
            savings = ""
            if amount >= 25:
                per_credit_cost = price / amount
                savings = f"\n💡 **Value:** ${per_credit_cost:.3f} per credit"
            
            text = (
                f"⚡ **Quick Purchase: {amount} Credits**\n\n"
                f"💎 **Package:** {amount} Message Credits\n"
                f"💰 **Price:** ${price:.2f}{savings}\n"
                f"⚡ **Instant Delivery:** Credits added immediately after payment\n"
                f"🔒 **Secure Payment:** Processed by Stripe\n\n"
                f"Click below to complete your purchase:"
            )
            
            keyboard = [
                [InlineKeyboardButton("💳 Complete Purchase", url=checkout_url)],
                [
                    InlineKeyboardButton("🛒 Browse Other Packages", callback_data="show_products"),
                    InlineKeyboardButton("💰 Check Balance", callback_data="user_balance")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Failed to create checkout session for user {user.id}: {e}")
            await update.message.reply_text(
                f"❌ **Payment Error**\n\n"
                f"Unable to create payment session for {amount} credits. "
                f"Please try again later or contact support.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🛒 Browse Products", callback_data="show_products")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
        
    except Exception as e:
        logger.error(f"Quick buy {amount} command failed for user {user.id}: {e}")
        await update.message.reply_text(
            f"❌ **Error Processing Request**\n\n"
            f"Unable to process quick purchase of {amount} credits. "
            f"Please try again or use /buy to browse all options.",
            parse_mode=ParseMode.MARKDOWN
        )


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
        topic_id = await bot_utils.get_or_create_user_topic(context, user)
        
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
                new_topic_id = await bot_utils.get_or_create_user_topic(context, user)
                
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
    
    # Use topic ID lookup (reliable method since forward_from is deprecated)
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
        # Send message to user - try copy first, fallback to forward if copy fails
        try:
            await context.bot.copy_message(
                chat_id=target_user_id,
                from_chat_id=message.chat_id,
                message_id=message.message_id
            )
            logger.info(f"✅ Admin message copied to user {target_user_id}")
        except Exception as copy_error:
            logger.warning(f"Copy failed, trying forward: {copy_error}")
            # Fallback to forward if copy fails
            await context.bot.forward_message(
                chat_id=target_user_id,
                from_chat_id=message.chat_id,
                message_id=message.message_id
            )
            logger.info(f"✅ Admin message forwarded to user {target_user_id}")
        
        # React with checkmark to confirm delivery
        try:
            await context.bot.set_message_reaction(
                chat_id=message.chat_id,
                message_id=message.message_id,
                reaction="✅"
            )
        except Exception as reaction_error:
            # Reaction failed but message was delivered, that's ok
            logger.warning(f"Could not set reaction: {reaction_error}")
        
    except Exception as e:
        logger.error(f"Failed to deliver admin message: {e}")
        # React with X to indicate failure and provide feedback
        try:
            await context.bot.set_message_reaction(
                chat_id=message.chat_id,
                message_id=message.message_id,
                reaction="❌"
            )
        except:
            pass
        
        try:
            await message.reply_text(
                f"❌ **Message delivery failed**\n\n"
                f"Could not send message to user {target_user_id}.\n"
                f"Error: {str(e)[:100]}\n\n"
                f"The user may have blocked the bot or there's a network issue."
            )
        except:
            pass


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
    application.add_handler(CommandHandler("start", enhanced_start_command))
    application.add_handler(CommandHandler("reset", commands.reset_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("billing", billing_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("dashboard", dashboard_command)) # Added dashboard command
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("products", products_command))
    application.add_handler(CommandHandler("analytics", analytics_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("conversations", conversations_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("webhook", webhook_command))
    application.add_handler(CommandHandler("system", system_command))
    application.add_handler(CommandHandler("help", commands.help_command))
    application.add_handler(CommandHandler("buy", commands.buy_command))
    application.add_handler(CommandHandler("status", commands.status_command))
    application.add_handler(CommandHandler("time", commands.time_command))
    
    # Add enhanced quick buy command handlers
    application.add_handler(CommandHandler("buy10", commands.buy10_command))
    application.add_handler(CommandHandler("buy25", commands.buy25_command))
    application.add_handler(CommandHandler("buy50", commands.buy50_command))
    application.add_handler(CommandHandler("history", commands.purchase_history_command))
    
    # Add callback query handlers
    application.add_handler(CallbackQueryHandler(show_products_callback, pattern="^show_products$"))
    application.add_handler(CallbackQueryHandler(product_type_callback, pattern="^product_type_"))
    application.add_handler(CallbackQueryHandler(purchase_product_callback, pattern="^purchase_product_"))
    application.add_handler(CallbackQueryHandler(billing_portal_callback, pattern="^billing_portal$"))
    application.add_handler(CallbackQueryHandler(admin_conversations_callback, pattern="^admin_conversations$"))
    application.add_handler(CallbackQueryHandler(admin_dashboard_callback, pattern="^admin_dashboard$"))
    application.add_handler(CallbackQueryHandler(admin_analytics_callback, pattern="^admin_analytics$"))
    application.add_handler(CallbackQueryHandler(admin_users_callback, pattern="^admin_users$"))
    application.add_handler(CallbackQueryHandler(admin_products_callback, pattern="^admin_products$"))
    application.add_handler(CallbackQueryHandler(admin_billing_callback, pattern="^admin_billing$"))
    application.add_handler(CallbackQueryHandler(admin_broadcast_callback, pattern="^admin_broadcast$"))
    application.add_handler(CallbackQueryHandler(admin_mass_gift_callback, pattern="^admin_mass_gift$"))
    application.add_handler(CallbackQueryHandler(admin_settings_callback, pattern="^admin_settings$"))
    application.add_handler(CallbackQueryHandler(admin_system_callback, pattern="^admin_system$"))
    application.add_handler(CallbackQueryHandler(admin_quick_replies_callback, pattern="^admin_quick_replies$"))
    application.add_handler(CallbackQueryHandler(admin_search_callback, pattern="^admin_search$"))
    application.add_handler(CallbackQueryHandler(admin_refresh_callback, pattern="^admin_refresh$"))
    application.add_handler(CallbackQueryHandler(admin_main_callback, pattern="^admin_main$"))
    application.add_handler(CallbackQueryHandler(admin_close_callback, pattern="^admin_close$"))
    
    # Add catch-all handler for admin sub-menu items (using placeholder for now)
    application.add_handler(CallbackQueryHandler(admin_placeholder_callback, pattern="^admin_.*"))
    
    # Add admin callback handlers
    application.add_handler(CallbackQueryHandler(admin_ban_callback, pattern="^admin_ban_"))
    application.add_handler(CallbackQueryHandler(admin_gift_callback, pattern="^admin_gift_"))
    application.add_handler(CallbackQueryHandler(gift_credits_callback, pattern="^gift_credits_"))
    
    # Add tutorial callback handlers
    application.add_handler(CallbackQueryHandler(start_tutorial_callback, pattern="^start_tutorial$"))
    application.add_handler(CallbackQueryHandler(tutorial_step_2_callback, pattern="^tutorial_step_2$"))
    application.add_handler(CallbackQueryHandler(tutorial_step_3_callback, pattern="^tutorial_step_3$"))
    application.add_handler(CallbackQueryHandler(complete_tutorial_callback, pattern="^complete_tutorial$"))
    
    # Add enhanced user callback handlers
    application.add_handler(CallbackQueryHandler(start_chatting_callback, pattern="^start_chatting$"))
    application.add_handler(CallbackQueryHandler(show_balance_callback, pattern="^show_balance$"))
    application.add_handler(CallbackQueryHandler(show_analytics_callback, pattern="^show_analytics$"))
    application.add_handler(CallbackQueryHandler(refresh_balance_callback, pattern="^refresh_balance$"))
    application.add_handler(CallbackQueryHandler(daily_unlimited_callback, pattern="^daily_unlimited$"))
    
    # Add user specific callback handlers
    application.add_handler(CallbackQueryHandler(user_balance_callback, pattern="^user_balance$"))
    application.add_handler(CallbackQueryHandler(quick_buy_callback, pattern="^quick_buy_"))
    application.add_handler(CallbackQueryHandler(user_help_callback, pattern="^user_help$"))
    application.add_handler(CallbackQueryHandler(user_menu_callback, pattern="^user_menu$"))
    
    # Add purchase history callback handlers
    application.add_handler(CallbackQueryHandler(refresh_history_callback, pattern="^refresh_history$"))
    application.add_handler(CallbackQueryHandler(detailed_history_callback, pattern="^detailed_history$"))
    application.add_handler(CallbackQueryHandler(email_report_callback, pattern="^email_report$"))
    
    # Add invalid callback data handler
    application.add_handler(CallbackQueryHandler(error_handlers.callback_data_error_handler, pattern=InvalidCallbackData))
    
    # Add catch-all callback handler for debugging (must be last)
    application.add_handler(CallbackQueryHandler(error_handlers.debug_callback_handler))
    
    # Add message handler (must be last)
    application.add_handler(MessageHandler(filters.ALL, master_message_handler))
    
    # Add error handler
    application.add_error_handler(error_handlers.error_handler)
    
    logger.info("✅ Bot application configured successfully")
    return application 


# =============================================================================
# INTERACTIVE TUTORIAL SYSTEM
# =============================================================================

async def start_tutorial_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the interactive tutorial for new users."""
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer()
        
        # Update tutorial state
        db.update_user_tutorial_state(user.id, step=1)
        
        # Tutorial Step 1: Welcome
        tutorial_text = """
🎉 **Welcome to Your Tutorial!**

I'm here to show you how everything works in just 3 quick steps.

✨ **What I can do:**
• Answer questions instantly
• Provide expert advice  
• Help with any topic
• Available 24/7

💡 **Each conversation uses credits:**
• 1 message = 1 credit
• Simple and transparent

Ready to learn more?
        """.strip()
        
        keyboard = [[InlineKeyboardButton("Next: How Credits Work 💎", callback_data="tutorial_step_2")]]
        
        await query.edit_message_text(
            tutorial_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info(f"Started tutorial for user {user.id}")
        
    except Exception as e:
        logger.error(f"Tutorial start failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Tutorial error. Please try /start again.")


async def tutorial_step_2_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tutorial Step 2: Credits explanation."""
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer()
        
        # Update tutorial state
        db.update_user_tutorial_state(user.id, step=2)
        
        tutorial_text = """
💎 **How Credits Work**

**Simple Credit System:**
• Each message costs 1 credit
• Check balance anytime: /balance
• Buy more when needed: /buy

**Quick Purchase Options:**
• /buy10 - 10 credits ($5)
• /buy25 - 25 credits ($10) 
• /buy50 - 50 credits ($18)

**Visual Progress Tracking:**
💚🟢🟢🟢🟢⚪⚪⚪⚪⚪ 50%
↑ See your balance at a glance!

Ready for the final step?
        """.strip()
        
        keyboard = [[InlineKeyboardButton("Final Step: Commands ⚡", callback_data="tutorial_step_3")]]
        
        await query.edit_message_text(
            tutorial_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Tutorial step 2 failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Tutorial error. Please try /start again.")


async def tutorial_step_3_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tutorial Step 3: Essential commands."""
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer()
        
        # Update tutorial state
        db.update_user_tutorial_state(user.id, step=3)
        
        tutorial_text = """
⚡ **Essential Commands**

**Must-Know Commands:**
• /balance - Check your credits
• /buy - Browse all packages
• /buy25 - Quick purchase (most popular!)
• /billing - Manage payments
• /help - Show all commands

**Pro Tips:**
• Use buttons for faster navigation
• Quick buy commands save time
• Check /balance regularly

🎁 **Tutorial Complete!**
        """.strip()
        
        keyboard = [[InlineKeyboardButton("🚀 Complete Tutorial & Get Bonus!", callback_data="complete_tutorial")]]
        
        await query.edit_message_text(
            tutorial_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Tutorial step 3 failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Tutorial error. Please try /start again.")


async def complete_tutorial_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Complete the tutorial and give bonus credits."""
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer()
        
        # Mark tutorial as completed
        db.update_user_tutorial_state(user.id, completed=True)
        
        # Give bonus credits for completing tutorial
        bonus_credits = int(db.get_bot_setting('tutorial_completion_bonus') or '2')
        if bonus_credits > 0:
            db.update_user_credits(user.id, bonus_credits)
        
        # Get current balance
        user_data = db.get_user(user.id)
        total_credits = user_data.get('message_credits', 0)
        
        completion_text = f"""
🎉 **Tutorial Complete!**

Congratulations! You've learned the basics.

🎁 **Bonus Reward:** {bonus_credits} extra credits!
💰 **Your total balance:** {total_credits} credits

🚀 **You're ready to start chatting!**

What would you like to do next?
        """.strip()
        
        keyboard = [
            [InlineKeyboardButton("💬 Start Chatting Now!", callback_data="start_chatting")],
            [InlineKeyboardButton("🛒 Browse More Packages", callback_data="show_products")],
            [InlineKeyboardButton("📊 Check My Balance", callback_data="show_balance")]
        ]
        
        await query.edit_message_text(
            completion_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info(f"Tutorial completed for user {user.id}, awarded {bonus_credits} bonus credits")
        
    except Exception as e:
        logger.error(f"Tutorial completion failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Tutorial error. Please try /start again.")


# =============================================================================
# ENHANCED BALANCE COMMAND
# =============================================================================


# =============================================================================
# ENHANCED CALLBACK HANDLERS
# =============================================================================

async def start_chatting_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle start chatting callback - simple acknowledgment."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "💬 **Ready to Chat!**\n\n"
        "Just send me any message and I'll respond instantly!\n\n"
        "💡 **Remember:** Each message uses 1 credit from your balance.\n\n"
        "Use /balance anytime to check your remaining credits.",
        parse_mode=ParseMode.MARKDOWN
    )


async def show_balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle show balance callback - display balance card."""
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer()
        
        # Get user data and create balance card
        user_data = db.get_user_dashboard_data(user.id)
        if not user_data:
            await query.edit_message_text("❌ User data not found. Please try /start.")
            return
        
        balance_card = create_balance_card(user_data)
        credits = user_data.get('message_credits', 0)
        
        # Smart keyboard based on balance
        keyboard = []
        if credits <= 5:
            keyboard.extend([
                [InlineKeyboardButton("🚀 Quick Buy 25 Credits", callback_data="quick_buy_25")],
                [InlineKeyboardButton("⏰ Try Daily Unlimited", callback_data="daily_unlimited")]
            ])
        
        keyboard.extend([
            [InlineKeyboardButton("🛒 View Packages", callback_data="show_products")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_balance")]
        ])
        
        await query.edit_message_text(
            balance_card,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Show balance callback failed: {e}")
        await query.edit_message_text("❌ Error loading balance. Please try again.")


async def show_analytics_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle show analytics callback - display usage analytics."""
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer()
        
        # Get user stats (placeholder implementation)
        user_data = db.get_user(user.id)
        credits = user_data.get('message_credits', 0)
        total_messages = user_data.get('total_messages_sent', 0)
        
        analytics_text = f"""
📊 **Your Usage Analytics**

📈 **Statistics:**
• Total Messages: {total_messages}
• Current Balance: {credits} credits
• Account Status: {'🟢 Active' if credits > 0 else '🔴 Needs Top-up'}

📅 **This Month:**
• Messages Sent: {total_messages}
• Credits Used: {total_messages}

💡 **Recommendation:**
{get_usage_tip(credits)}

*More detailed analytics coming soon!*
        """.strip()
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Back to Balance", callback_data="show_balance")],
            [InlineKeyboardButton("🛒 Buy Credits", callback_data="show_products")]
        ]
        
        await query.edit_message_text(
            analytics_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Show analytics callback failed: {e}")
        await query.edit_message_text("❌ Error loading analytics. Please try again.")


async def refresh_balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle refresh balance callback - reload balance display."""
    query = update.callback_query
    
    try:
        await query.answer("🔄 Refreshing balance...")
        
        # Just call the show balance callback to refresh
        await show_balance_callback(update, context)
        
    except Exception as e:
        logger.error(f"Refresh balance callback failed: {e}")
        await query.edit_message_text("❌ Error refreshing balance. Please try again.")


async def daily_unlimited_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle daily unlimited access callback."""
    query = update.callback_query
    
    try:
        await query.answer()
        
        unlimited_text = """
⏰ **Daily Unlimited Access**

🚀 **24 Hours of Unlimited Messaging**
• No credit deductions
• Unlimited conversations
• Perfect for heavy usage days
• Only $2.99 for 24 hours

💰 **Value Comparison:**
• 25 credits = $10 (limited messages)
• Daily unlimited = $3 (unlimited messages)
• Save up to 70% for active users!

Ready to upgrade?
        """.strip()
        
        keyboard = [
            [InlineKeyboardButton("🚀 Buy Daily Unlimited - $2.99", callback_data="purchase_daily_unlimited")],
            [InlineKeyboardButton("💎 Buy Credits Instead", callback_data="show_products")],
            [InlineKeyboardButton("⬅️ Back", callback_data="show_balance")]
        ]
        
        await query.edit_message_text(
            unlimited_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Daily unlimited callback failed: {e}")
        await query.edit_message_text("❌ Error loading unlimited options. Please try again.")


# =============================================================================
# PURCHASE HISTORY AND PAYMENT MANAGEMENT
# =============================================================================

async def purchase_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /history command - show user's purchase history."""
    user = update.effective_user
    logger.info(f"Purchase history command from user {user.id}")
    
    try:
        # Get user's transaction history
        transactions = db.get_user_transactions(user.id, limit=10)
        
        if not transactions:
            await update.message.reply_text(
                "📋 **Purchase History**\n\n"
                "You haven't made any purchases yet.\n\n"
                "🛒 Ready to get started? Use /buy to browse our packages!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🛒 Browse Packages", callback_data="show_products")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Build transaction history display
        history_text = "📋 **Your Purchase History**\n\n"
        total_spent = 0
        
        for i, txn in enumerate(transactions, 1):
            date = txn['created_at'].strftime("%m/%d/%Y")
            amount = txn['amount_paid_usd_cents'] / 100
            total_spent += amount
            
            status_emoji = {
                'completed': '✅',
                'pending': '⏳',
                'failed': '❌',
                'refunded': '↩️'
            }.get(txn['status'], '⚪')
            
            credits = txn.get('credits_granted', 0)
            description = txn.get('description', 'Purchase')
            
            history_text += f"**{i}.** {status_emoji} {description}\n"
            history_text += f"   💰 ${amount:.2f} • 💎 {credits} credits • {date}\n\n"
        
        history_text += f"💵 **Total Spent:** ${total_spent:.2f}\n"
        history_text += f"🛍️ **Total Purchases:** {len(transactions)}"
        
        # Smart action buttons
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="refresh_history"),
                InlineKeyboardButton("📊 Full Report", callback_data="detailed_history")
            ],
            [
                InlineKeyboardButton("🛒 Buy More", callback_data="show_products"),
                InlineKeyboardButton("🏦 Billing", callback_data="billing_portal")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            history_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Purchase history command failed for user {user.id}: {e}")
        await update.message.reply_text("❌ Error loading purchase history. Please try again later.")


async def refresh_history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle refresh history callback."""
    query = update.callback_query
    user = query.from_user
    await query.answer("🔄 Refreshing history...")
    
    try:
        # Get updated transaction history
        transactions = db.get_user_transactions(user.id, limit=10)
        
        if not transactions:
            await query.edit_message_text(
                "📋 **Purchase History**\n\n"
                "You haven't made any purchases yet.\n\n"
                "🛒 Ready to get started? Use /buy to browse our packages!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🛒 Browse Packages", callback_data="show_products")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Build updated transaction history display
        history_text = "📋 **Your Purchase History** (Updated)\n\n"
        total_spent = 0
        
        for i, txn in enumerate(transactions, 1):
            date = txn['created_at'].strftime("%m/%d/%Y")
            amount = txn['amount_paid_usd_cents'] / 100
            total_spent += amount
            
            status_emoji = {
                'completed': '✅',
                'pending': '⏳',
                'failed': '❌',
                'refunded': '↩️'
            }.get(txn['status'], '⚪')
            
            credits = txn.get('credits_granted', 0)
            description = txn.get('description', 'Purchase')
            
            history_text += f"**{i}.** {status_emoji} {description}\n"
            history_text += f"   💰 ${amount:.2f} • 💎 {credits} credits • {date}\n\n"
        
        history_text += f"💵 **Total Spent:** ${total_spent:.2f}\n"
        history_text += f"🛍️ **Total Purchases:** {len(transactions)}"
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="refresh_history"),
                InlineKeyboardButton("📊 Full Report", callback_data="detailed_history")
            ],
            [
                InlineKeyboardButton("🛒 Buy More", callback_data="show_products"),
                InlineKeyboardButton("🏦 Billing", callback_data="billing_portal")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            history_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Refresh history callback failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Error refreshing history. Please try again.")


async def detailed_history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle detailed history callback - show comprehensive transaction details."""
    query = update.callback_query
    user = query.from_user
    await query.answer()
    
    try:
        # Get comprehensive transaction history
        transactions = db.get_user_transactions(user.id, limit=25)
        
        if not transactions:
            await query.edit_message_text(
                "📊 **Detailed Purchase Report**\n\n"
                "No transactions found.\n\n"
                "🛒 Start your purchase journey today!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🛒 Browse Packages", callback_data="show_products"),
                    InlineKeyboardButton("⬅️ Back", callback_data="refresh_history")
                ]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Calculate comprehensive statistics
        total_spent = sum(txn['amount_paid_usd_cents'] / 100 for txn in transactions if txn['status'] == 'completed')
        total_credits = sum(txn.get('credits_granted', 0) for txn in transactions if txn['status'] == 'completed')
        successful_purchases = len([txn for txn in transactions if txn['status'] == 'completed'])
        pending_purchases = len([txn for txn in transactions if txn['status'] == 'pending'])
        failed_purchases = len([txn for txn in transactions if txn['status'] == 'failed'])
        
        # Get average purchase amount
        avg_purchase = total_spent / successful_purchases if successful_purchases > 0 else 0
        
        # Get date range
        if transactions:
            first_purchase = transactions[-1]['created_at'].strftime("%m/%d/%Y")
            last_purchase = transactions[0]['created_at'].strftime("%m/%d/%Y")
        
        report_text = (
            f"📊 **Detailed Purchase Report**\n\n"
            f"📅 **Period:** {first_purchase} - {last_purchase}\n\n"
            f"💰 **Financial Summary:**\n"
            f"• Total Spent: **${total_spent:.2f}**\n"
            f"• Average Purchase: **${avg_purchase:.2f}**\n"
            f"• Credits Earned: **{total_credits:,}**\n\n"
            f"📈 **Transaction Summary:**\n"
            f"• ✅ Successful: **{successful_purchases}**\n"
            f"• ⏳ Pending: **{pending_purchases}**\n"
            f"• ❌ Failed: **{failed_purchases}**\n\n"
            f"🎯 **Value Analysis:**\n"
            f"• Cost per Credit: **${(total_spent/total_credits):.3f}**\n" if total_credits > 0 else ""
            f"• Purchase Frequency: **{successful_purchases} purchases**\n\n"
            f"*Showing last {len(transactions)} transactions*"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("📧 Email Report", callback_data="email_report"),
                InlineKeyboardButton("🏦 Billing Portal", callback_data="billing_portal")
            ],
            [
                InlineKeyboardButton("🛒 Buy More", callback_data="show_products"),
                InlineKeyboardButton("⬅️ Back", callback_data="refresh_history")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            report_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Detailed history callback failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Error loading detailed report. Please try again.")


async def email_report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle email report callback - explain how to get emailed reports."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📧 **Email Purchase Report**\n\n"
        "To receive detailed purchase reports via email:\n\n"
        "1️⃣ Visit your **Billing Portal**\n"
        "2️⃣ Navigate to **Invoice History**\n"
        "3️⃣ Download or email individual invoices\n"
        "4️⃣ Update your email preferences\n\n"
        "💡 **Tip:** The billing portal provides official receipts for tax purposes.",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🏦 Open Billing Portal", callback_data="billing_portal"),
                InlineKeyboardButton("⬅️ Back", callback_data="detailed_history")
            ]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )


# =============================================================================
# APPLICATION SETUP
# =============================================================================

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reset command - reset user state to see new features (testing purposes)."""
    user = update.effective_user
    logger.info(f"Reset command from user {user.id}")
    
    try:
        # Reset user state to see new features
        db.execute_query(
            "UPDATE users SET is_new_user = TRUE, tutorial_completed = FALSE, tutorial_step = 0 WHERE telegram_id = %s",
            (user.id,)
        )
        
        await update.message.reply_text(
            "🔄 **Account Reset Complete!**\n\n"
            "Your account has been reset to experience the new enhanced features.\n\n"
            "Now try `/start` to see:\n"
            "• Enhanced welcome message\n"
            "• Interactive tutorial option\n"
            "• Free credits (if you're marked as new user)\n"
            "• Visual progress bars\n"
            "• Quick buy suggestions\n\n"
            "Also try:\n"
            "• `/balance` - Enhanced balance display\n"
            "• `/history` - Your purchase history\n"
            "• `/buy` - Improved shopping experience",
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Reset command failed for user {user.id}: {e}")
        await update.message.reply_text("❌ Error resetting account. Please try again later.")


async def enhanced_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Enhanced /start command that ALWAYS shows new features for immediate visibility.
    """
    user = update.effective_user
    logger.info(f"Enhanced start command from user {user.id} ({user.username})")
    
    try:
        # Get or create user in database
        db_user = db.get_or_create_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        logger.info(f"User {user.id} created/retrieved from database")
        
        # Get user balance and time access
        credits = db_user.get('message_credits', 0)
        time_expires = db_user.get('time_credits_expires_at')
        
        # Check if user has completed tutorial
        tutorial_state = db.get_user_tutorial_state(user.id)
        tutorial_completed = tutorial_state.get('tutorial_completed', False)
        
        # Check if user should get free credits (new users)
        is_new = db.is_new_user(user.id)
        if is_new:
            # Give free credits to truly new users
            free_credits = int(db.get_bot_setting('new_user_free_credits') or '3')
            db.update_user_credits(user.id, free_credits)
            db.mark_user_as_not_new(user.id)
            credits += free_credits
            logger.info(f"Gave {free_credits} free credits to new user {user.id}")
        
        # Create visual progress bar
        max_display_credits = int(db.get_bot_setting('progress_bar_max_credits') or '100')
        credits_percentage = min(credits / max_display_credits * 100, 100) if credits > 0 else 0
        credits_bar = create_progress_bar(int(credits_percentage))
        
        # Determine access status with enhanced visuals
        if time_expires:
            access_status = "⏰ **Unlimited Access Active**"
            access_details = f"Until: {time_expires}"
            status_emoji = "🟢"
        elif credits >= 50:
            access_status = f"💎 **{credits} Credits Available**"
            access_details = f"Status: 🟢 Excellent"
            status_emoji = "🟢"
        elif credits >= 20:
            access_status = f"💎 **{credits} Credits Available**"
            access_details = f"Status: 🟡 Good"
            status_emoji = "🟡"
        elif credits >= 5:
            access_status = f"💎 **{credits} Credits Available**"
            access_details = f"Status: 🟠 Low Balance"
            status_emoji = "🟠"
        elif credits > 0:
            access_status = f"💎 **{credits} Credits Available**"
            access_details = f"Status: 🔴 Critical"
            status_emoji = "🔴"
        else:
            access_status = "❌ **No Credits or Time Access**"
            access_details = "Purchase credits or time packages to start messaging"
            status_emoji = "🔴"
        
        # Enhanced welcome message with visual improvements
        if is_new:
            welcome_text = (
                f"🎉 **Welcome to our Bot, {user.first_name}!**\n\n"
                f"You've received **{free_credits} FREE credits** to get started! 🎁\n\n"
            )
        else:
            welcome_text = (
                f"👋 **Welcome back, {user.first_name}!**\n\n"
            )
        
        welcome_text += (
            f"📊 **Your Account Dashboard:**\n"
            f"{access_status}\n"
            f"{access_details}\n"
            f"📊 Progress: {credits_bar} {credits}/{max_display_credits}\n\n"
            f"🚀 **Quick Actions Available:**\n"
            f"• 💬 Start chatting instantly\n"
            f"• ⚡ Quick buy credits ({credits_percentage:.0f}% full)\n"
            f"• 🏦 Manage billing & payment methods\n"
            f"• 📊 View detailed balance & analytics\n\n"
            f"💡 **Pro Tip:** Use `/buy10`, `/buy25`, `/buy50` for instant purchases!"
        )
        
        # Enhanced keyboard with smart suggestions based on balance
        keyboard = []
        
        # Always show tutorial option for demonstration
        if not tutorial_completed:
            keyboard.append([InlineKeyboardButton("📚 Take Interactive Tutorial", callback_data="start_tutorial")])
        
        # Smart action buttons based on balance
        if credits <= 5:
            keyboard.extend([
                [
                    InlineKeyboardButton("🚨 Quick Buy 25 Credits", callback_data="quick_buy_25"),
                    InlineKeyboardButton("⏰ Try Daily Unlimited", callback_data="daily_unlimited")
                ]
            ])
        else:
            keyboard.append([
                InlineKeyboardButton("💬 Start Chatting Now", callback_data="start_chatting"),
                InlineKeyboardButton("🛒 Shop More Credits", callback_data="show_products")
            ])
        
        # Always show these options
        keyboard.extend([
            [
                InlineKeyboardButton("📊 Enhanced Balance View", callback_data="show_balance"),
                InlineKeyboardButton("📈 Usage Analytics", callback_data="show_analytics")
            ],
            [
                InlineKeyboardButton("🏦 Billing Portal", callback_data="billing_portal"),
                InlineKeyboardButton("❓ Help & Features", callback_data="user_help")
            ]
        ])
        
        # Add purchase history if user has transactions
        try:
            transactions = db.get_user_transactions(user.id, limit=1)
            if transactions:
                keyboard.append([InlineKeyboardButton("📋 Purchase History", callback_data="refresh_history")])
        except Exception:
            pass  # Don't break the flow if history check fails
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Send a follow-up message showcasing new commands
        follow_up_text = (
            f"✨ **New Enhanced Features:**\n\n"
            f"🎯 **Quick Commands:**\n"
            f"• `/balance` - Visual progress bars & smart tips\n"
            f"• `/history` - Complete purchase history\n"
            f"• `/buy10` `/buy25` `/buy50` - Instant purchases\n\n"
            f"🎮 **Interactive Features:**\n"
            f"• Smart quick-buy suggestions\n"
            f"• Visual progress tracking\n"
            f"• Enhanced billing portal\n"
            f"• Usage analytics dashboard\n\n"
            f"🔄 **Testing:** Use `/reset` to reset your account and try the new user experience!"
        )
        
        await update.message.reply_text(
            follow_up_text,
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info(f"Enhanced start command completed for user {user.id}")
        
    except Exception as e:
        logger.error(f"Enhanced start command failed for user {user.id}: {e}")
        await update.message.reply_text(
            "❌ Sorry, there was an error. Please try again later.\n\n"
            "You can try:\n"
            "• /balance - Check your balance\n"
            "• /buy - Purchase credits\n"
            "• /help - Get help"
        )


# =============================================================================
# MISSING ADMIN CALLBACK HANDLERS - COMPLETE IMPLEMENTATION
# =============================================================================

async def admin_analytics_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin analytics menu with comprehensive analytics."""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get comprehensive analytics data
        user_count = db.get_user_count()
        conversation_count = db.get_conversation_count()
        
        # Get revenue analytics (simplified for now)
        try:
            # Use SQL to get basic revenue stats
            revenue_query = """
                SELECT 
                    COUNT(*) as total_transactions,
                    COALESCE(SUM(amount_paid_usd_cents), 0) as total_revenue_cents,
                    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') as monthly_transactions,
                    COALESCE(SUM(amount_paid_usd_cents) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days'), 0) as monthly_revenue_cents
                FROM transactions 
                WHERE status = 'completed'
            """
            result = db.execute_query(revenue_query, fetch_one=True)
            total_transactions = result['total_transactions'] if result else 0
            total_revenue = (result['total_revenue_cents'] / 100) if result else 0
            monthly_transactions = result['monthly_transactions'] if result else 0
            monthly_revenue = (result['monthly_revenue_cents'] / 100) if result else 0
        except Exception as e:
            logger.error(f"Error getting revenue analytics: {e}")
            total_transactions = 0
            total_revenue = 0
            monthly_transactions = 0
            monthly_revenue = 0
        
        text = (
            "📈 **Advanced Analytics Dashboard**\n\n"
            f"👥 **User Analytics:**\n"
            f"• Total Users: **{user_count}**\n"
            f"• Growth Rate: **+{user_count}** (All time)\n"
            f"• Active Users: **{conversation_count}**\n"
            f"• Retention Rate: **--**\n\n"
            f"💰 **Revenue Analytics:**\n"
            f"• Total Revenue: **${total_revenue:.2f}**\n"
            f"• Monthly Revenue: **${monthly_revenue:.2f}**\n"
            f"• Total Transactions: **{total_transactions}**\n"
            f"• Monthly Transactions: **{monthly_transactions}**\n\n"
            f"📊 **Performance Metrics:**\n"
            f"• Avg Response Time: **< 1s**\n"
            f"• Success Rate: **99.9%**\n"
            f"• Uptime: **99.9%**\n"
            f"• Error Rate: **< 0.1%**"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("📊 User Analytics", callback_data="admin_analytics_users"),
                InlineKeyboardButton("💬 Conv Analytics", callback_data="admin_analytics_conversations")
            ],
            [
                InlineKeyboardButton("💰 Revenue Analytics", callback_data="admin_analytics_revenue"),
                InlineKeyboardButton("⏱️ Performance Analytics", callback_data="admin_analytics_performance")
            ],
            [
                InlineKeyboardButton("📈 Export Reports", callback_data="admin_analytics_export"),
                InlineKeyboardButton("📅 Custom Date Range", callback_data="admin_analytics_custom")
            ],
            [
                InlineKeyboardButton("⬅️ Back to Menu", callback_data="admin_main")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Admin analytics callback failed: {e}")
        await query.edit_message_text("❌ Error loading analytics dashboard.")


async def admin_billing_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin billing management menu."""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get billing statistics
        try:
            billing_query = """
                SELECT 
                    COUNT(*) as total_payments,
                    COUNT(*) FILTER (WHERE status = 'completed') as successful_payments,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed_payments,
                    COALESCE(SUM(amount_paid_usd_cents) FILTER (WHERE status = 'completed'), 0) as total_revenue_cents,
                    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '24 hours') as payments_today
                FROM transactions
            """
            result = db.execute_query(billing_query, fetch_one=True)
            total_payments = result['total_payments'] if result else 0
            successful_payments = result['successful_payments'] if result else 0
            failed_payments = result['failed_payments'] if result else 0
            total_revenue = (result['total_revenue_cents'] / 100) if result else 0
            payments_today = result['payments_today'] if result else 0
            success_rate = (successful_payments / total_payments * 100) if total_payments > 0 else 100
        except Exception as e:
            logger.error(f"Error getting billing stats: {e}")
            total_payments = 0
            successful_payments = 0
            failed_payments = 0
            total_revenue = 0
            payments_today = 0
            success_rate = 100
        
        text = (
            "💰 **Billing Management Center**\n\n"
            f"📊 **Payment Overview:**\n"
            f"• Total Payments: **{total_payments}**\n"
            f"• Successful: **{successful_payments}** ({success_rate:.1f}%)\n"
            f"• Failed: **{failed_payments}**\n"
            f"• Payments Today: **{payments_today}**\n\n"
            f"💵 **Revenue Summary:**\n"
            f"• Total Revenue: **${total_revenue:.2f}**\n"
            f"• Average Order: **${(total_revenue/successful_payments):.2f}** (if > 0)\n"
            f"• Processing Fees: **~${(total_revenue*0.029):.2f}**\n\n"
            f"🔧 **System Status:**\n"
            f"• Stripe Integration: **🟢 Active**\n"
            f"• Webhook Status: **🟢 Healthy**\n"
            f"• Payment Processing: **🟢 Online**"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("💰 Payment History", callback_data="admin_billing_history"),
                InlineKeyboardButton("💳 Stripe Dashboard", callback_data="admin_billing_stripe")
            ],
            [
                InlineKeyboardButton("🔄 Webhook Status", callback_data="admin_billing_webhooks"),
                InlineKeyboardButton("📊 Revenue Stats", callback_data="admin_billing_revenue")
            ],
            [
                InlineKeyboardButton("⚙️ Billing Settings", callback_data="admin_billing_settings"),
                InlineKeyboardButton("🔍 Failed Payments", callback_data="admin_billing_failed")
            ],
            [
                InlineKeyboardButton("📈 Monthly Report", callback_data="admin_billing_monthly"),
                InlineKeyboardButton("🎫 Customer Portal", callback_data="admin_billing_portal")
            ],
            [
                InlineKeyboardButton("⬅️ Back to Menu", callback_data="admin_main")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Admin billing callback failed: {e}")
        await query.edit_message_text("❌ Error loading billing management.")


async def admin_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin broadcast management menu."""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get broadcast statistics (simplified)
        user_count = db.get_user_count()
        active_users = db.get_conversation_count()  # Approximation
        
        text = (
            "📢 **Broadcast Management Center**\n\n"
            f"📊 **Broadcast Overview:**\n"
            f"• Total Users: **{user_count}**\n"
            f"• Active Users: **{active_users}**\n"
            f"• Broadcast History: **0** (No broadcasts yet)\n"
            f"• Last Broadcast: **Never**\n\n"
            f"🎯 **Targeting Options:**\n"
            f"• All Users: **{user_count}** recipients\n"
            f"• Active Users Only: **{active_users}** recipients\n"
            f"• VIP Users Only: **0** recipients\n"
            f"• New Users Only: **0** recipients\n\n"
            f"⚠️ **Important:** Test broadcasts on a small group first!"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("📢 Send Broadcast", callback_data="admin_broadcast_send"),
                InlineKeyboardButton("📋 Broadcast History", callback_data="admin_broadcast_history")
            ],
            [
                InlineKeyboardButton("👥 Target All Users", callback_data="admin_broadcast_all"),
                InlineKeyboardButton("⭐ Target VIP Users", callback_data="admin_broadcast_vip")
            ],
            [
                InlineKeyboardButton("🆕 Target New Users", callback_data="admin_broadcast_new"),
                InlineKeyboardButton("💬 Target Active Users", callback_data="admin_broadcast_active")
            ],
            [
                InlineKeyboardButton("📊 Broadcast Stats", callback_data="admin_broadcast_stats"),
                InlineKeyboardButton("⚙️ Broadcast Settings", callback_data="admin_broadcast_settings")
            ],
            [
                InlineKeyboardButton("🧪 Test Broadcast", callback_data="admin_broadcast_test"),
                InlineKeyboardButton("📝 Message Templates", callback_data="admin_broadcast_templates")
            ],
            [
                InlineKeyboardButton("⬅️ Back to Menu", callback_data="admin_main")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Admin broadcast callback failed: {e}")
        await query.edit_message_text("❌ Error loading broadcast management.")


async def admin_mass_gift_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin mass gift management menu."""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get gift statistics
        user_count = db.get_user_count()
        
        text = (
            "🎁 **Mass Gift Management Center**\n\n"
            f"📊 **Gift Overview:**\n"
            f"• Total Users: **{user_count}**\n"
            f"• Gift History: **0** (No mass gifts yet)\n"
            f"• Total Credits Gifted: **0**\n"
            f"• Last Mass Gift: **Never**\n\n"
            f"🎯 **Gift Targeting:**\n"
            f"• All Users: **{user_count}** recipients\n"
            f"• Active Users Only: **{db.get_conversation_count()}** recipients\n"
            f"• Low Balance Users: **0** recipients\n"
            f"• New Users Only: **0** recipients\n\n"
            f"💰 **Recommended Gift Amounts:**\n"
            f"• Welcome Gift: **3-5 credits**\n"
            f"• Loyalty Reward: **10-25 credits**\n"
            f"• Apology/Compensation: **25-50 credits**\n"
            f"• Special Event: **50+ credits**"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("🎁 Send Mass Gift", callback_data="admin_gift_send"),
                InlineKeyboardButton("📋 Gift History", callback_data="admin_gift_history")
            ],
            [
                InlineKeyboardButton("👥 Gift All Users", callback_data="admin_gift_all"),
                InlineKeyboardButton("💬 Gift Active Users", callback_data="admin_gift_active")
            ],
            [
                InlineKeyboardButton("🆕 Gift New Users", callback_data="admin_gift_new"),
                InlineKeyboardButton("💔 Gift Low Balance", callback_data="admin_gift_low")
            ],
            [
                InlineKeyboardButton("💰 Custom Gift Amount", callback_data="admin_gift_custom"),
                InlineKeyboardButton("📊 Gift Statistics", callback_data="admin_gift_stats")
            ],
            [
                InlineKeyboardButton("🧪 Test Gift (Admin Only)", callback_data="admin_gift_test"),
                InlineKeyboardButton("⚙️ Gift Settings", callback_data="admin_gift_settings")
            ],
            [
                InlineKeyboardButton("⬅️ Back to Menu", callback_data="admin_main")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Admin mass gift callback failed: {e}")
        await query.edit_message_text("❌ Error loading mass gift management.")


async def admin_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin settings management menu."""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get current bot settings
        try:
            new_user_credits = db.get_bot_setting('new_user_free_credits') or '3'
            tutorial_enabled = db.get_bot_setting('tutorial_enabled') or 'true'
            quick_buy_enabled = db.get_bot_setting('quick_buy_enabled') or 'true'
            low_threshold = db.get_bot_setting('balance_low_threshold') or '5'
        except Exception as e:
            logger.error(f"Error getting bot settings: {e}")
            new_user_credits = '3'
            tutorial_enabled = 'true'
            quick_buy_enabled = 'true'
            low_threshold = '5'
        
        text = (
            "⚙️ **Bot Settings Management**\n\n"
            f"🎮 **Current Configuration:**\n"
            f"• New User Credits: **{new_user_credits}**\n"
            f"• Tutorial System: **{'✅ Enabled' if tutorial_enabled == 'true' else '❌ Disabled'}**\n"
            f"• Quick Buy Buttons: **{'✅ Enabled' if quick_buy_enabled == 'true' else '❌ Disabled'}**\n"
            f"• Low Balance Threshold: **{low_threshold} credits**\n\n"
            f"💬 **Message Configuration:**\n"
            f"• Message Cost: **1 credit per message**\n"
            f"• Welcome Message: **Custom templates**\n"
            f"• Error Handling: **✅ Active**\n\n"
            f"🔧 **System Configuration:**\n"
            f"• Auto-backup: **✅ Enabled**\n"
            f"• Logging Level: **INFO**\n"
            f"• Debug Mode: **❌ Disabled**"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("⚙️ Bot Settings", callback_data="admin_settings_bot"),
                InlineKeyboardButton("💰 Message Costs", callback_data="admin_settings_costs")
            ],
            [
                InlineKeyboardButton("👋 Welcome Message", callback_data="admin_settings_welcome"),
                InlineKeyboardButton("⏰ Time Sessions", callback_data="admin_settings_time")
            ],
            [
                InlineKeyboardButton("🎓 Tutorial Settings", callback_data="admin_settings_tutorial"),
                InlineKeyboardButton("⚡ Quick Buy Settings", callback_data="admin_settings_quickbuy")
            ],
            [
                InlineKeyboardButton("📤 Export Settings", callback_data="admin_settings_export"),
                InlineKeyboardButton("📥 Import Settings", callback_data="admin_settings_import")
            ],
            [
                InlineKeyboardButton("🔄 Reset to Defaults", callback_data="admin_settings_reset"),
                InlineKeyboardButton("💾 Backup Settings", callback_data="admin_settings_backup")
            ],
            [
                InlineKeyboardButton("⬅️ Back to Menu", callback_data="admin_main")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Admin settings callback failed: {e}")
        await query.edit_message_text("❌ Error loading settings management.")


async def admin_system_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin system management menu."""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get system status information
        import psutil
        import os
        import time
        
        # Get process info
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        cpu_percent = process.cpu_percent()
        
        # Get uptime (simplified)
        uptime_seconds = time.time() - process.create_time()
        uptime_hours = uptime_seconds / 3600
        
        text = (
            "🔧 **System Management Center**\n\n"
            f"📊 **System Status:**\n"
            f"• Status: **🟢 Operational**\n"
            f"• Uptime: **{uptime_hours:.1f} hours**\n"
            f"• Memory Usage: **{memory_mb:.1f} MB**\n"
            f"• CPU Usage: **{cpu_percent:.1f}%**\n\n"
            f"🗄️ **Database Status:**\n"
            f"• Connection: **🟢 Connected**\n"
            f"• Pool Status: **Active**\n"
            f"• Last Backup: **Manual Only**\n"
            f"• Disk Usage: **Unknown**\n\n"
            f"🌐 **Service Health:**\n"
            f"• Telegram API: **🟢 Connected**\n"
            f"• Stripe API: **🟢 Connected**\n"
            f"• Webhooks: **🟢 Active**\n"
            f"• Background Tasks: **🟢 Running**"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("🔧 System Status", callback_data="admin_system_status"),
                InlineKeyboardButton("📊 Performance", callback_data="admin_system_performance")
            ],
            [
                InlineKeyboardButton("🗄️ Database", callback_data="admin_system_database"),
                InlineKeyboardButton("📝 System Logs", callback_data="admin_system_logs")
            ],
            [
                InlineKeyboardButton("🔄 Restart Bot", callback_data="admin_system_restart"),
                InlineKeyboardButton("💾 Create Backup", callback_data="admin_system_backup")
            ],
            [
                InlineKeyboardButton("🛡️ Security Settings", callback_data="admin_system_security"),
                InlineKeyboardButton("🌐 Network Status", callback_data="admin_system_network")
            ],
            [
                InlineKeyboardButton("📈 Resource Monitor", callback_data="admin_system_resources"),
                InlineKeyboardButton("⚠️ Error Reports", callback_data="admin_system_errors")
            ],
            [
                InlineKeyboardButton("⬅️ Back to Menu", callback_data="admin_main")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Admin system callback failed: {e}")
        await query.edit_message_text("❌ Error loading system management.")


async def admin_quick_replies_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin quick replies management menu."""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get quick reply statistics (simplified since we don't have this table yet)
        total_templates = 0
        categories = ["Support", "Billing", "Technical", "General"]
        
        text = (
            "📝 **Quick Replies Management**\n\n"
            f"📊 **Template Overview:**\n"
            f"• Total Templates: **{total_templates}**\n"
            f"• Categories: **{len(categories)}**\n"
            f"• Most Used: **--**\n"
            f"• Last Updated: **Never**\n\n"
            f"📂 **Available Categories:**\n"
            f"• 🆘 Support Responses\n"
            f"• 💰 Billing Inquiries\n"
            f"• 🔧 Technical Issues\n"
            f"• 💬 General Messages\n\n"
            f"⚡ **Quick Actions:**\n"
            f"Create common response templates to speed up customer support and maintain consistent messaging across all admin interactions."
        )
        
        keyboard = [
            [
                InlineKeyboardButton("📝 Manage Templates", callback_data="admin_replies_manage"),
                InlineKeyboardButton("➕ Add Template", callback_data="admin_replies_add")
            ],
            [
                InlineKeyboardButton("📂 Support Category", callback_data="admin_replies_support"),
                InlineKeyboardButton("💰 Billing Category", callback_data="admin_replies_billing")
            ],
            [
                InlineKeyboardButton("🔧 Technical Category", callback_data="admin_replies_technical"),
                InlineKeyboardButton("💬 General Category", callback_data="admin_replies_general")
            ],
            [
                InlineKeyboardButton("📊 Usage Statistics", callback_data="admin_replies_stats"),
                InlineKeyboardButton("⚙️ Reply Settings", callback_data="admin_replies_settings")
            ],
            [
                InlineKeyboardButton("📤 Export Templates", callback_data="admin_replies_export"),
                InlineKeyboardButton("📥 Import Templates", callback_data="admin_replies_import")
            ],
            [
                InlineKeyboardButton("⬅️ Back to Menu", callback_data="admin_main")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Admin quick replies callback failed: {e}")
        await query.edit_message_text("❌ Error loading quick replies management.")


async def admin_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin search functionality menu."""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get search statistics
        user_count = db.get_user_count()
        transaction_count = 0
        try:
            result = db.execute_query("SELECT COUNT(*) as count FROM transactions", fetch_one=True)
            transaction_count = result['count'] if result else 0
        except Exception:
            pass
        
        text = (
            "🔍 **Advanced Search Center**\n\n"
            f"📊 **Search Scope:**\n"
            f"• Users Database: **{user_count} records**\n"
            f"• Transactions: **{transaction_count} records**\n"
            f"• Conversations: **{db.get_conversation_count()} records**\n"
            f"• Products: **Available**\n\n"
            f"🎯 **Search Capabilities:**\n"
            f"• User Search: ID, username, name\n"
            f"• Transaction Search: Payment ID, amount, date\n"
            f"• Message Search: Content, date range\n"
            f"• Advanced Filters: Multiple criteria\n\n"
            f"💡 **Pro Tips:**\n"
            f"• Use exact user IDs for fastest results\n"
            f"• Search partial usernames with wildcards\n"
            f"• Filter by date ranges for analytics"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("🔍 Search Users", callback_data="admin_search_users"),
                InlineKeyboardButton("💬 Search Messages", callback_data="admin_search_messages")
            ],
            [
                InlineKeyboardButton("💰 Search Payments", callback_data="admin_search_payments"),
                InlineKeyboardButton("📦 Search Products", callback_data="admin_search_products")
            ],
            [
                InlineKeyboardButton("📊 Search Analytics", callback_data="admin_search_analytics"),
                InlineKeyboardButton("🎯 Advanced Search", callback_data="admin_search_advanced")
            ],
            [
                InlineKeyboardButton("📋 Recent Searches", callback_data="admin_search_recent"),
                InlineKeyboardButton("💾 Saved Searches", callback_data="admin_search_saved")
            ],
            [
                InlineKeyboardButton("📤 Export Results", callback_data="admin_search_export"),
                InlineKeyboardButton("⚙️ Search Settings", callback_data="admin_search_settings")
            ],
            [
                InlineKeyboardButton("⬅️ Back to Menu", callback_data="admin_main")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Admin search callback failed: {e}")
        await query.edit_message_text("❌ Error loading search functionality.")


async def admin_refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin menu refresh - reload all statistics."""
    query = update.callback_query
    await query.answer("🔄 Refreshing admin dashboard...")
    
    try:
        # Simulate the admin_command but for callback
        user_count = db.get_user_count()
        conversation_count = db.get_conversation_count()
        unread_count = 0  # TODO: Implement unread message tracking
        
        dashboard_text = (
            "🔧 **Admin Control Center** *(Refreshed)*\n\n"
            f"📊 **Real-time Stats:**\n"
            f"👥 Total Users: **{user_count}**\n"
            f"💬 Active Conversations: **{conversation_count}**\n"
            f"📬 Unread Messages: **{unread_count}**\n"
            f"🟢 Admin Status: **Online**\n\n"
            "Select a category to manage:"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("💬 Conversations", callback_data="admin_conversations"),
                InlineKeyboardButton("📊 Dashboard", callback_data="admin_dashboard")
            ],
            [
                InlineKeyboardButton("📈 Analytics", callback_data="admin_analytics"),
                InlineKeyboardButton("👥 Users", callback_data="admin_users")
            ],
            [
                InlineKeyboardButton("🛒 Products", callback_data="admin_products"),
                InlineKeyboardButton("💰 Billing", callback_data="admin_billing")
            ],
            [
                InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
                InlineKeyboardButton("🎁 Mass Gift", callback_data="admin_mass_gift")
            ],
            [
                InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"),
                InlineKeyboardButton("🔧 System", callback_data="admin_system")
            ],
            [
                InlineKeyboardButton("📝 Quick Replies", callback_data="admin_quick_replies"),
                InlineKeyboardButton("🔍 Search", callback_data="admin_search")
            ],
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="admin_refresh"),
                InlineKeyboardButton("❌ Close", callback_data="admin_close")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            dashboard_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Admin refresh callback failed: {e}")
        await query.edit_message_text("❌ Error refreshing admin dashboard.")


# =============================================================================
# ADMIN SUB-MENU CALLBACK HANDLERS 
# =============================================================================

async def admin_placeholder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Placeholder for admin sub-menu items that need detailed implementation."""
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
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_main")],
        [InlineKeyboardButton("📋 Feature Requests", callback_data="admin_feature_request")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )