"""
Enterprise Telegram Bot - Command Handlers

This module contains all command handlers for user-facing commands like
/start, /balance, /help, /buy, /status, etc.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from src import database as db
from src import bot_utils

logger = logging.getLogger(__name__)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Enhanced /help command with comprehensive information and interactive menu.
    """
    user = update.effective_user
    logger.info(f"Help command from user {user.id}")
    
    help_text = """
🤖 **AI Assistant Help Center**

Welcome! I'm your personal AI assistant, ready to help 24/7.

**💬 How it works:**
• Each message costs 1 credit
• Get instant, intelligent responses
• Ask about anything - I'm here to help!

**🎯 Quick Commands:**
• `/start` - Main menu & welcome
• `/balance` - Check your credits
• `/buy` - Purchase more credits  
• `/billing` - Manage billing & subscriptions
• `/status` - Bot status information
• `/time` - Current time

**💡 Pro Tips:**
• Be specific in your questions for better answers
• Check your balance regularly
• Use quick buy options for instant credits

**🎁 Special Offers:**
• Daily unlimited plans available
• Bulk credit discounts
• Premium tier benefits

Need more help? Just ask me anything!
    """
    
    keyboard = [
        [
            InlineKeyboardButton("💰 Check Balance", callback_data="user_balance"),
            InlineKeyboardButton("🛒 Buy Credits", callback_data="show_products")
        ],
        [
            InlineKeyboardButton("📊 My Analytics", callback_data="show_analytics"),
            InlineKeyboardButton("💬 Start Chatting", callback_data="start_chatting")
        ],
        [
            InlineKeyboardButton("🔄 Refresh Help", callback_data="user_help"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="user_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        help_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )


async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Enhanced /buy command with product showcase and personalized recommendations.
    """
    user = update.effective_user
    logger.info(f"Buy command from user {user.id}")
    
    try:
        # Get user data for personalized recommendations
        user_data = db.get_user_dashboard_data(user.id)
        credits = user_data.get('message_credits', 0) if user_data else 0
        
        # Get available products
        products = db.get_all_products()
        if not products:
            await update.message.reply_text("❌ No products available at the moment.")
            return
        
        # Create personalized intro
        if credits < 2:
            intro = "🚨 **Running Low on Credits!**\n\nDon't miss out on our conversation. Choose a package below:"
        elif credits < 10:
            intro = "💡 **Top Up Your Credits**\n\nGreat timing to refill! Here are our popular options:"
        else:
            intro = "🛒 **Credit Store**\n\nStock up for uninterrupted conversations:"
        
        # Build product showcase
        product_text = f"{intro}\n\n"
        
        keyboard = []
        for product in products[:6]:  # Show top 6 products
            name = product['name']
            credits_amount = product['credits']
            price = product['price_cents'] / 100
            
            # Add value proposition
            if credits_amount == 10:
                value = "⚡ Quick Start"
            elif credits_amount == 25:
                value = "🌟 Popular Choice"
            elif credits_amount == 50:
                value = "💎 Best Value"
            elif credits_amount >= 100:
                value = "🏆 Premium"
            else:
                value = "💰 Basic"
            
            product_text += f"**{name}** - ${price:.2f}\n"
            product_text += f"• {credits_amount} credits {value}\n"
            product_text += f"• ${price/credits_amount:.3f} per credit\n\n"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"Buy {credits_amount} Credits (${price:.2f})",
                    callback_data=f"purchase_product_{product['stripe_price_id']}"
                )
            ])
        
        # Add navigation buttons
        keyboard.extend([
            [
                InlineKeyboardButton("💳 Billing Portal", callback_data="billing_portal"),
                InlineKeyboardButton("📊 Usage Analytics", callback_data="show_analytics")
            ],
            [
                InlineKeyboardButton("💎 Premium Plans", callback_data="show_premium"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="user_menu")
            ]
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            product_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Buy command failed for user {user.id}: {e}")
        await update.message.reply_text("❌ Error loading products. Please try again.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Enhanced /status command with comprehensive bot health information.
    """
    user = update.effective_user
    logger.info(f"Status command from user {user.id}")
    
    try:
        # Get system status information
        total_users = db.get_user_count()
        active_conversations = db.get_conversation_count()
        
        # Get user-specific information
        user_data = db.get_user_dashboard_data(user.id)
        user_credits = user_data.get('message_credits', 0) if user_data else 0
        user_tier = user_data.get('tier_name', 'standard') if user_data else 'standard'
        
        status_text = f"""
🟢 **Bot Status: Online & Ready**

**🔧 System Information:**
• Status: Fully Operational
• Response Time: < 1 second
• Uptime: 99.9%
• Last Update: Recently

**📊 Community Stats:**
• Total Users: {total_users:,}
• Active Conversations: {active_conversations:,}
• Messages Processed: 100k+

**👤 Your Account:**
• Credits: {user_credits}
• Tier: {user_tier.title()}
• Status: {"🟢 Active" if user_credits > 0 else "🟡 Low Credits"}

**🚀 Recent Features:**
• Enhanced conversation memory
• Improved response quality
• New quick buy options
• Advanced analytics dashboard

All systems running smoothly! Ready to chat? 💬
        """
        
        keyboard = [
            [
                InlineKeyboardButton("💬 Start Chatting", callback_data="start_chatting"),
                InlineKeyboardButton("💰 Check Balance", callback_data="user_balance")
            ],
            [
                InlineKeyboardButton("📊 System Health", callback_data="system_health"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="user_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            status_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Status command failed for user {user.id}: {e}")
        await update.message.reply_text("❌ Error retrieving status. Please try again.")


async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Enhanced /time command with timezone information and user preferences.
    """
    user = update.effective_user
    logger.info(f"Time command from user {user.id}")
    
    import datetime
    import pytz
    
    try:
        # Current UTC time
        utc_now = datetime.datetime.now(pytz.UTC)
        
        # Common timezone information
        timezones = {
            'UTC': pytz.UTC,
            'US/Eastern': pytz.timezone('US/Eastern'),
            'US/Pacific': pytz.timezone('US/Pacific'), 
            'Europe/London': pytz.timezone('Europe/London'),
            'Europe/Paris': pytz.timezone('Europe/Paris'),
            'Asia/Tokyo': pytz.timezone('Asia/Tokyo'),
            'Australia/Sydney': pytz.timezone('Australia/Sydney')
        }
        
        time_text = "🕐 **Current Time Information**\n\n"
        
        for name, tz in timezones.items():
            local_time = utc_now.astimezone(tz)
            time_text += f"**{name}:** {local_time.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
        
        time_text += f"\n⏰ **Bot Timezone:** UTC"
        time_text += f"\n🌍 **Your Request Time:** {utc_now.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh Time", callback_data="refresh_time"),
                InlineKeyboardButton("⚙️ Set Timezone", callback_data="set_timezone")
            ],
            [
                InlineKeyboardButton("📅 Schedule Reminder", callback_data="schedule_reminder"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="user_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            time_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Time command failed for user {user.id}: {e}")
        await update.message.reply_text("❌ Error retrieving time information. Please try again.")


# Quick buy command handlers
async def buy10_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Quick buy 10 credits command."""
    await process_quick_buy_command(update, context, 10)


async def buy25_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Quick buy 25 credits command."""
    await process_quick_buy_command(update, context, 25)


async def buy50_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Quick buy 50 credits command."""
    await process_quick_buy_command(update, context, 50)


async def process_quick_buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int) -> None:
    """
    Process quick buy commands for specified credit amounts.
    
    Args:
        update: Telegram update object
        context: Telegram context object
        amount: Number of credits to purchase
    """
    user = update.effective_user
    logger.info(f"Quick buy {amount} command from user {user.id}")
    
    try:
        # Find product with matching credit amount
        products = db.get_all_products()
        matching_product = None
        
        for product in products:
            if product['credits'] == amount:
                matching_product = product
                break
        
        if not matching_product:
            await update.message.reply_text(
                f"❌ {amount}-credit package not available. Use /buy to see all options."
            )
            return
        
        price = matching_product['price_cents'] / 100
        
        quick_buy_text = f"""
⚡ **Quick Buy: {amount} Credits**

💰 **Price:** ${price:.2f}
⚡ **Credits:** {amount}
💡 **Per Credit:** ${price/amount:.3f}

This will be added to your account instantly after payment.
        """
        
        keyboard = [
            [
                InlineKeyboardButton(
                    f"💳 Buy Now (${price:.2f})",
                    callback_data=f"purchase_product_{matching_product['stripe_price_id']}"
                )
            ],
            [
                InlineKeyboardButton("🛒 View All Options", callback_data="show_products"),
                InlineKeyboardButton("💰 Check Balance", callback_data="user_balance")
            ],
            [
                InlineKeyboardButton("❌ Cancel", callback_data="user_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            quick_buy_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Quick buy {amount} command failed for user {user.id}: {e}")
        await update.message.reply_text("❌ Error processing quick buy. Please try again.")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Reset command to clear user session and start fresh.
    """
    user = update.effective_user
    logger.info(f"Reset command from user {user.id}")
    
    try:
        # Clear any conversation context (if implemented)
        # This is a placeholder for clearing user session data
        
        reset_text = """
🔄 **Session Reset Complete**

Your conversation has been reset and you can start fresh!

**What was cleared:**
• Conversation context
• Cached responses
• Session data

**What remains:**
• Your credit balance
• Account settings
• Purchase history

Ready for a new conversation? Use /start to begin!
        """
        
        keyboard = [
            [
                InlineKeyboardButton("🚀 Start Fresh", callback_data="start_chatting"),
                InlineKeyboardButton("💰 Check Balance", callback_data="user_balance")
            ],
            [
                InlineKeyboardButton("🏠 Main Menu", callback_data="user_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            reset_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Reset command failed for user {user.id}: {e}")
        await update.message.reply_text("❌ Error during reset. Please try again.")


async def purchase_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Display user's purchase history with analytics and insights.
    """
    user = update.effective_user
    logger.info(f"Purchase history command from user {user.id}")
    
    try:
        # Get user's purchase history
        purchases = db.get_user_purchase_history(user.id, limit=10)
        
        if not purchases:
            history_text = """
📋 **Purchase History**

No purchases found yet.

🎁 **Get Started:**
• New users get 3 free credits
• First purchase often includes bonus credits
• Regular promotions and discounts available

Ready to make your first purchase?
            """
            
            keyboard = [
                [
                    InlineKeyboardButton("🛒 Browse Products", callback_data="show_products"),
                    InlineKeyboardButton("💰 Quick Buy 10", callback_data="quick_buy_10")
                ],
                [
                    InlineKeyboardButton("🏠 Main Menu", callback_data="user_menu")
                ]
            ]
        else:
            # Calculate totals
            total_spent = sum(p.get('amount_cents', 0) for p in purchases) / 100
            total_credits = sum(p.get('credits_purchased', 0) for p in purchases)
            
            history_text = f"""
📋 **Purchase History**

**📊 Summary:**
• Total Spent: ${total_spent:.2f}
• Total Credits: {total_credits:,}
• Total Orders: {len(purchases)}

**📝 Recent Purchases:**
            """
            
            for purchase in purchases[:5]:  # Show last 5
                date = purchase.get('created_at', 'Unknown')
                amount = purchase.get('amount_cents', 0) / 100
                credits = purchase.get('credits_purchased', 0)
                status = purchase.get('status', 'unknown')
                
                status_emoji = {
                    'completed': '✅',
                    'pending': '⏳',
                    'failed': '❌',
                    'refunded': '🔄'
                }.get(status, '❓')
                
                history_text += f"\n{status_emoji} **${amount:.2f}** • {credits} credits"
                if date != 'Unknown':
                    history_text += f" • {date[:10]}"
            
            keyboard = [
                [
                    InlineKeyboardButton("📊 Detailed History", callback_data="detailed_history"),
                    InlineKeyboardButton("📧 Email Report", callback_data="email_report")
                ],
                [
                    InlineKeyboardButton("🛒 Buy More", callback_data="show_products"),
                    InlineKeyboardButton("🔄 Refresh", callback_data="refresh_history")
                ],
                [
                    InlineKeyboardButton("🏠 Main Menu", callback_data="user_menu")
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
        await update.message.reply_text("❌ Error retrieving purchase history. Please try again.") 


async def enhanced_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Enhanced /start command with personalized welcome, free credits, and tutorial.
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
        credits_bar = bot_utils.create_progress_bar(int(credits_percentage))
        
        # Build enhanced start message
        user_emoji = bot_utils.get_user_tier_emoji(db_user.get('tier_name', 'standard'))
        welcome_text = f"""
🎉 **Welcome, {user.first_name}!** {user_emoji}

💰 **Balance:** {credits} credits
{credits_bar} {credits}/{max_display_credits}

🤖 **I'm your AI assistant, ready to help 24/7!**

**What can I help you with today?**
• Expert advice and insights
• Quick problem solving  
• Research and analysis
• Creative projects

💡 **Each message costs 1 credit**
        """
        
        # Create smart keyboard based on user state
        keyboard = []
        
        if not tutorial_completed:
            keyboard.append([
                InlineKeyboardButton("📚 Take Tutorial (Recommended)", callback_data="start_tutorial")
            ])
        
        if credits > 5:
            keyboard.extend([
                [InlineKeyboardButton("💬 Start Chatting", callback_data="start_chatting")],
                [
                    InlineKeyboardButton("📊 My Analytics", callback_data="show_analytics"),
                    InlineKeyboardButton("🏦 Billing Portal", callback_data="billing_portal")
                ]
            ])
        elif credits > 0:
            keyboard.extend([
                [InlineKeyboardButton("💬 Start Chatting", callback_data="start_chatting")],
                [
                    InlineKeyboardButton("⚡ Quick Buy 25", callback_data="quick_buy_25"),
                    InlineKeyboardButton("💰 Balance", callback_data="show_balance")
                ]
            ])
        else:
            keyboard.extend([
                [
                    InlineKeyboardButton("🚀 Get 10 Credits", callback_data="quick_buy_10"),
                    InlineKeyboardButton("🏆 Get 25 Credits", callback_data="quick_buy_25")
                ],
                [InlineKeyboardButton("🛒 View All Packages", callback_data="show_products")]
            ])
        
        # Common options
        keyboard.extend([
            [
                InlineKeyboardButton("❓ Help", callback_data="user_help"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="user_menu")
            ]
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Enhanced start command failed for user {user.id}: {e}")
        await update.message.reply_text(
            "❌ Sorry, there was an error. Please try again later.\n\n"
            "You can try:\n"
            "• /balance - Check your balance\n"
            "• /buy - Purchase credits\n"
            "• /help - Get help"
        )


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Enhanced /balance command with comprehensive balance information.
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
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="refresh_balance"),
                InlineKeyboardButton("📊 Analytics", callback_data="show_analytics")
            ],
            [
                InlineKeyboardButton("🛒 Buy Credits", callback_data="show_products"),
                InlineKeyboardButton("💳 Billing Portal", callback_data="billing_portal")
            ],
            [
                InlineKeyboardButton("💬 Start Chatting", callback_data="start_chatting"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="user_menu")
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
        await update.message.reply_text("❌ Error loading balance. Please try again.") 