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
from src.config import BOT_TOKEN, ADMIN_GROUP_ID

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
    Core conversation bridge function. Gets existing topic or creates new one.
    
    Args:
        context: PTB context object
        user: Telegram User object
        
    Returns:
        Topic ID for the user's conversation thread
        
    Raises:
        BotError: If topic creation fails
    """
    # First check if topic already exists
    existing_topic_id = db.get_topic_id_from_user(user.id, ADMIN_GROUP_ID)
    if existing_topic_id:
        logger.info(f"Found existing topic {existing_topic_id} for user {user.id}")
        return existing_topic_id
    
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
        
        # Create admin action buttons using arbitrary callback data
        keyboard = [
            [
                InlineKeyboardButton("🚫 Ban User", callback_data=("admin_ban", user_id)),
                InlineKeyboardButton("🎁 Gift Credits", callback_data=("admin_gift", user_id)),
            ],
            [
                InlineKeyboardButton("📊 Full History", callback_data=("admin_history", user_id)),
                InlineKeyboardButton("⬆️ Upgrade Tier", callback_data=("admin_tier", user_id)),
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
    
    # Get or create user in database
    db_user = db.get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # Get welcome message from bot settings
    welcome_message = db.get_bot_setting('welcome_message') or "Welcome to our Enterprise Telegram Bot! 🤖"
    
    # Create start button using arbitrary callback data
    keyboard = [[InlineKeyboardButton("▶️ Start", callback_data=("show_products",))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
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
    """
    Handle quick buy commands like /buy10, /buy50, etc.
    """
    user = update.effective_user
    command = update.message.text
    
    # Extract amount from command (e.g., /buy10 -> 10)
    try:
        amount = int(command.replace('/buy', ''))
        logger.info(f"Quick buy command: {amount} credits for user {user.id}")
    except ValueError:
        await update.message.reply_text("❌ Invalid command format.")
        return
    
    # Find matching product
    products = db.get_active_products()
    matching_product = None
    
    for product in products:
        if product['product_type'] == 'credits' and product['amount'] == amount:
            matching_product = product
            break
    
    if not matching_product:
        await update.message.reply_text(f"❌ No product found for {amount} credits.")
        return
    
    # Import here to avoid circular imports
    from src.stripe_utils import create_checkout_session
    
    try:
        # Create Stripe checkout session
        checkout_url = create_checkout_session(
            user_id=user.id,
            price_id=matching_product['stripe_price_id']
        )
        
        price_dollars = matching_product['price_usd_cents'] / 100
        
        await update.message.reply_text(
            f"💳 **Quick Purchase: {amount} Credits**\n\n"
            f"Price: ${price_dollars:.2f}\n\n"
            f"[Complete Purchase]({checkout_url})",
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Quick buy failed for user {user.id}: {e}")
        await update.message.reply_text("❌ Unable to process purchase. Please try again later.")


# =============================================================================
# CALLBACK QUERY HANDLERS
# =============================================================================

async def show_products_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show available products when Start button is clicked.
    """
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    logger.info(f"Show products callback from user {user.id}")
    
    # Get active products
    products = db.get_active_products()
    if not products:
        await query.edit_message_text("❌ No products available at the moment.")
        return
    
    # Group products by type
    credits_products = [p for p in products if p['product_type'] == 'credits']
    time_products = [p for p in products if p['product_type'] == 'time']
    
    # Create product buttons
    keyboard = []
    
    if credits_products:
        keyboard.append([InlineKeyboardButton("💎 Credit Packages", callback_data=("product_type", "credits"))])
    
    if time_products:
        keyboard.append([InlineKeyboardButton("⏰ Time Packages", callback_data=("product_type", "time"))])
    
    keyboard.append([InlineKeyboardButton("🏦 Billing Settings", callback_data=("billing_portal",))])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🛍️ **Choose a product category:**\n\n"
        "Select what you'd like to purchase:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )


async def product_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show products of a specific type.
    """
    query = update.callback_query
    await query.answer()
    
    # Extract product type from callback data
    _, product_type = query.data
    
    logger.info(f"Product type callback: {product_type}")
    
    # Get products of this type
    products = [p for p in db.get_active_products() if p['product_type'] == product_type]
    
    if not products:
        await query.edit_message_text(f"❌ No {product_type} products available.")
        return
    
    # Create product buttons
    keyboard = []
    for product in products:
        price_dollars = product['price_usd_cents'] / 100
        button_text = f"{product['name']} - ${price_dollars:.2f}"
        keyboard.append([InlineKeyboardButton(
            button_text, 
            callback_data=("purchase_product", product['id'])
        )])
    
    # Add back button
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=("show_products",))])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    type_emoji = "💎" if product_type == "credits" else "⏰"
    await query.edit_message_text(
        f"{type_emoji} **{product_type.title()} Products:**\n\n"
        f"Choose a package:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )


async def purchase_product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle product purchase initiation.
    """
    query = update.callback_query
    await query.answer()
    
    # Extract product ID from callback data
    _, product_id = query.data
    
    user = query.from_user
    logger.info(f"Purchase product callback: product {product_id} for user {user.id}")
    
    # Get product details
    products = db.get_active_products()
    product = next((p for p in products if p['id'] == product_id), None)
    
    if not product:
        await query.edit_message_text("❌ Product not found.")
        return
    
    # Import here to avoid circular imports
    from src.stripe_utils import create_checkout_session
    
    try:
        # Create Stripe checkout session
        checkout_url = create_checkout_session(
            user_id=user.id,
            price_id=product['stripe_price_id']
        )
        
        price_dollars = product['price_usd_cents'] / 100
        
        await query.edit_message_text(
            f"💳 **Purchase: {product['name']}**\n\n"
            f"**Description:** {product.get('description', 'No description available')}\n"
            f"**Price:** ${price_dollars:.2f}\n\n"
            f"Click the link below to complete your purchase:\n"
            f"[Complete Purchase]({checkout_url})",
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Purchase initiation failed: {e}")
        await query.edit_message_text("❌ Unable to process purchase. Please try again later.")


# =============================================================================
# ADMIN CALLBACK HANDLERS
# =============================================================================

async def admin_ban_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin ban user action."""
    query = update.callback_query
    await query.answer()
    
    # Extract user ID from callback data
    _, target_user_id = query.data
    
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
    
    # Extract user ID from callback data
    _, target_user_id = query.data
    
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
        
        # Forward message to admin topic
        await context.bot.forward_message(
            chat_id=ADMIN_GROUP_ID,
            from_chat_id=message.chat_id,
            message_id=message.message_id,
            message_thread_id=topic_id
        )
        
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
        return
    
    try:
        # Forward admin message to user
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
        # React with X to indicate failure
        try:
            await context.bot.set_message_reaction(
                chat_id=message.chat_id,
                message_id=message.message_id,
                reaction="❌"
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
    
    # Add quick buy command handlers
    for amount in [10, 25, 50, 100]:
        application.add_handler(CommandHandler(f"buy{amount}", quick_buy_command))
    
    # Add callback query handlers
    application.add_handler(CallbackQueryHandler(show_products_callback, pattern="show_products"))
    application.add_handler(CallbackQueryHandler(product_type_callback, pattern="product_type"))
    application.add_handler(CallbackQueryHandler(purchase_product_callback, pattern="purchase_product"))
    
    # Add admin callback handlers
    application.add_handler(CallbackQueryHandler(admin_ban_callback, pattern="admin_ban"))
    application.add_handler(CallbackQueryHandler(admin_gift_callback, pattern="admin_gift"))
    application.add_handler(CallbackQueryHandler(gift_credits_callback, pattern="gift_credits"))
    
    # Add invalid callback data handler
    application.add_handler(CallbackQueryHandler(callback_data_error_handler, pattern=InvalidCallbackData))
    
    # Add message handler (must be last)
    application.add_handler(MessageHandler(filters.ALL, master_message_handler))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    logger.info("✅ Bot application configured successfully")
    return application 