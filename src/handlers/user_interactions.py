"""
Enterprise Telegram Bot - User Interactions

This module contains all user-facing interaction handlers including tutorials,
user menu callbacks, balance displays, and analytics dashboards.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from src import database as db
from src import bot_utils

logger = logging.getLogger(__name__)


# Tutorial System
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
• 1 credit per message
• Get precise, helpful responses
• No time limits or restrictions

Ready to learn how to use your credits wisely?
        """
        
        keyboard = [
            [
                InlineKeyboardButton("📚 Next: How Credits Work", callback_data="tutorial_step_2"),
                InlineKeyboardButton("⏭️ Skip Tutorial", callback_data="complete_tutorial")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            tutorial_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Tutorial start failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Tutorial error. Use /start to continue.")


async def tutorial_step_2_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tutorial step 2: Credits explanation."""
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer()
        
        # Update tutorial state
        db.update_user_tutorial_state(user.id, step=2)
        
        tutorial_text = """
💰 **Step 2: Understanding Credits**

**How Credits Work:**
• Each message you send costs 1 credit
• I respond with detailed, helpful answers
• Check your balance anytime with /balance

**Getting More Credits:**
• Quick buy: /buy10, /buy25, /buy50
• Full store: /buy for all options
• Daily unlimited plans available

**💡 Pro Tips:**
• Be specific in questions for better value
• One detailed question often better than several short ones
• Premium tiers offer better rates

Let's check your current balance!
        """
        
        keyboard = [
            [
                InlineKeyboardButton("💰 Check My Balance", callback_data="show_balance"),
                InlineKeyboardButton("📚 Next Step", callback_data="tutorial_step_3")
            ],
            [
                InlineKeyboardButton("⏭️ Finish Tutorial", callback_data="complete_tutorial")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            tutorial_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Tutorial step 2 failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Tutorial error. Use /start to continue.")


async def tutorial_step_3_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tutorial step 3: Getting started."""
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer()
        
        # Update tutorial state
        db.update_user_tutorial_state(user.id, step=3)
        
        tutorial_text = """
🚀 **Step 3: Ready to Chat!**

**You're all set! Here's what to do next:**

**💬 Start Chatting:**
• Ask me anything - I'm here to help!
• Get instant, intelligent responses
• No topic is off-limits

**📊 Track Your Usage:**
• /balance - Check credits anytime
• /history - View purchase history
• /analytics - See usage patterns

**🛒 Need More Credits?**
• /buy - Browse all packages
• Quick options: /buy10, /buy25, /buy50

Ready to begin your first conversation?
        """
        
        keyboard = [
            [
                InlineKeyboardButton("💬 Start Chatting", callback_data="start_chatting"),
                InlineKeyboardButton("🛒 Buy More Credits", callback_data="show_products")
            ],
            [
                InlineKeyboardButton("✅ Complete Tutorial", callback_data="complete_tutorial")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            tutorial_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Tutorial step 3 failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Tutorial error. Use /start to continue.")


async def complete_tutorial_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Complete the tutorial and mark user as onboarded."""
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer("Tutorial completed! 🎉")
        
        # Mark tutorial as completed
        db.update_user_tutorial_state(user.id, step=4, completed=True)
        
        # Get user data for personalized completion message
        user_data = db.get_user_dashboard_data(user.id)
        credits = user_data.get('message_credits', 0) if user_data else 0
        
        completion_text = f"""
🎉 **Tutorial Complete - Welcome Aboard!**

**You're now ready to use your AI assistant!**

**💰 Current Balance:** {credits} credits
**🎁 As a new user, you received free starter credits**

**🚀 Quick Actions:**
        """
        
        if credits >= 5:
            completion_text += "\n• You have plenty of credits to get started!"
        elif credits >= 2:
            completion_text += "\n• Consider topping up soon for extended conversations"
        else:
            completion_text += "\n• ⚠️ Low credits - consider purchasing more"
        
        keyboard = [
            [
                InlineKeyboardButton("💬 Start First Conversation", callback_data="start_chatting"),
                InlineKeyboardButton("💰 Check Balance", callback_data="show_balance")
            ],
            [
                InlineKeyboardButton("🛒 Buy Credits", callback_data="show_products"),
                InlineKeyboardButton("📊 My Dashboard", callback_data="user_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            completion_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Tutorial completion failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Tutorial error. Use /start to continue.")


# User Menu & Navigation
async def start_chatting_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle start chatting callback."""
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer("Ready to chat! Send me a message 💬")
        
        # Get user credits for warning if low
        user_data = db.get_user_dashboard_data(user.id)
        credits = user_data.get('message_credits', 0) if user_data else 0
        
        if credits >= 5:
            chat_text = """
💬 **Ready to Chat!**

I'm here and ready to help with anything you need!

**💡 Tips for great conversations:**
• Be specific with your questions
• Ask follow-up questions if needed
• Use /balance to check credits anytime

Just send me a message below to get started! 🚀
            """
        elif credits >= 1:
            chat_text = f"""
💬 **Ready to Chat!**

**⚠️ Credit Warning:** You have {credits} credits remaining.

Consider topping up to avoid interruptions:
• /buy10 - Quick 10 credits
• /buy25 - Popular choice
• /buy50 - Best value

Still ready to chat? Send me a message! 🚀
            """
        else:
            chat_text = """
❌ **Insufficient Credits**

You need at least 1 credit to start chatting.

**Quick Options:**
• /buy10 - Get 10 credits instantly
• /buy25 - Popular package
• /buy50 - Best value option

Purchase credits to continue! 💳
            """
        
        keyboard = []
        if credits < 2:
            keyboard = [
                [
                    InlineKeyboardButton("💰 Buy 10 Credits", callback_data="quick_buy_10"),
                    InlineKeyboardButton("🏆 Buy 25 Credits", callback_data="quick_buy_25")
                ],
                [
                    InlineKeyboardButton("🛒 View All Options", callback_data="show_products"),
                    InlineKeyboardButton("💰 Check Balance", callback_data="show_balance")
                ]
            ]
        else:
            keyboard = [
                [
                    InlineKeyboardButton("💰 Check Balance", callback_data="show_balance"),
                    InlineKeyboardButton("🛒 Buy More Credits", callback_data="show_products")
                ]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        
        await query.edit_message_text(
            chat_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Start chatting callback failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Error. Use /start to try again.")


async def show_balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle show balance callback."""
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer()
        
        # Get user data
        user_data = db.get_user_dashboard_data(user.id)
        if not user_data:
            await query.edit_message_text("❌ User data not found. Use /start to initialize.")
            return
        
        # Create balance card using bot_utils
        balance_card = bot_utils.create_balance_card(user_data)
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh Balance", callback_data="refresh_balance"),
                InlineKeyboardButton("🛒 Buy Credits", callback_data="show_products")
            ],
            [
                InlineKeyboardButton("📊 Usage Analytics", callback_data="show_analytics"),
                InlineKeyboardButton("📋 Purchase History", callback_data="purchase_history")
            ],
            [
                InlineKeyboardButton("💬 Start Chatting", callback_data="start_chatting"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="user_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            balance_card,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Show balance callback failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Error loading balance. Try /balance command.")


async def show_analytics_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle analytics dashboard callback."""
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer()
        
        # Get user analytics data
        user_data = db.get_user_dashboard_data(user.id)
        if not user_data:
            await query.edit_message_text("❌ Analytics data not available.")
            return
        
        credits = user_data.get('message_credits', 0)
        total_spent = user_data.get('total_spent_cents', 0) / 100
        total_purchases = user_data.get('total_purchases', 0)
        tier = user_data.get('tier_name', 'standard').title()
        
        analytics_text = f"""
📊 **Your Analytics Dashboard**

**💰 Account Overview:**
• Current Credits: {credits}
• Total Spent: ${total_spent:.2f}
• Total Purchases: {total_purchases}
• Account Tier: {tier}

**📈 Usage Insights:**
• Average session: ~3-5 messages
• Most active time: Varies by user
• Favorite topics: General assistance

**💡 Optimization Tips:**
• Ask detailed questions for better value
• Consider bulk purchases for savings
• Premium tiers offer better rates
        """
        
        keyboard = [
            [
                InlineKeyboardButton("💰 Check Balance", callback_data="show_balance"),
                InlineKeyboardButton("🛒 Upgrade Plan", callback_data="show_products")
            ],
            [
                InlineKeyboardButton("📋 Purchase History", callback_data="purchase_history"),
                InlineKeyboardButton("🔄 Refresh Data", callback_data="show_analytics")
            ],
            [
                InlineKeyboardButton("🏠 Main Menu", callback_data="user_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            analytics_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Analytics callback failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Error loading analytics. Please try again.")


async def refresh_balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle refresh balance callback."""
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer("🔄 Refreshing balance...")
        
        # Re-fetch user data
        user_data = db.get_user_dashboard_data(user.id)
        if not user_data:
            await query.edit_message_text("❌ Unable to refresh balance data.")
            return
        
        # Create updated balance card
        balance_card = bot_utils.create_balance_card(user_data)
        balance_card += "\n\n🔄 *Balance refreshed just now*"
        
        keyboard = [
            [
                InlineKeyboardButton("🛒 Buy Credits", callback_data="show_products"),
                InlineKeyboardButton("📊 View Analytics", callback_data="show_analytics")
            ],
            [
                InlineKeyboardButton("💬 Start Chatting", callback_data="start_chatting"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="user_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            balance_card,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Refresh balance callback failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Error refreshing balance.")


async def user_balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user balance callback - same as show_balance_callback."""
    await show_balance_callback(update, context)


async def user_help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user help callback."""
    query = update.callback_query
    
    try:
        await query.answer()
        
        help_text = """
🤖 **Help Center**

**Getting Started:**
• Each message costs 1 credit
• Ask me anything - I'm here to help!
• Check balance with /balance

**Quick Commands:**
• `/start` - Main menu
• `/buy` - Purchase credits
• `/help` - This help menu
• `/status` - Bot status

**Need Support?**
• Common issues are auto-resolved
• Questions? Just ask me directly!
• Feature requests welcome

**💡 Pro Tips:**
• Be specific for better answers
• Use bulk purchases for savings
• Premium users get priority support
        """
        
        keyboard = [
            [
                InlineKeyboardButton("💬 Ask a Question", callback_data="start_chatting"),
                InlineKeyboardButton("💰 Check Balance", callback_data="show_balance")
            ],
            [
                InlineKeyboardButton("🛒 Buy Credits", callback_data="show_products"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="user_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            help_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"User help callback failed: {e}")
        await query.edit_message_text("❌ Error loading help. Use /help command.")


async def user_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user main menu callback."""
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer()
        
        # Get user data for personalized menu
        user_data = db.get_user_dashboard_data(user.id)
        credits = user_data.get('message_credits', 0) if user_data else 0
        tier = user_data.get('tier_name', 'standard') if user_data else 'standard'
        
        menu_text = f"""
🏠 **Main Menu**

**Welcome back, {user.first_name}!**

**💰 Balance:** {credits} credits
**⭐ Tier:** {tier.title()}
**🟢 Status:** {"Active" if credits > 0 else "Low Credits"}

**What would you like to do?**
        """
        
        keyboard = [
            [
                InlineKeyboardButton("💬 Start Chatting", callback_data="start_chatting"),
                InlineKeyboardButton("💰 Check Balance", callback_data="show_balance")
            ],
            [
                InlineKeyboardButton("🛒 Buy Credits", callback_data="show_products"),
                InlineKeyboardButton("📊 My Analytics", callback_data="show_analytics")
            ],
            [
                InlineKeyboardButton("📋 Purchase History", callback_data="purchase_history"),
                InlineKeyboardButton("❓ Help & Support", callback_data="user_help")
            ]
        ]
        
        # Add quick buy options if credits are low
        if credits < 5:
            keyboard.append([
                InlineKeyboardButton("⚡ Quick Buy 10", callback_data="quick_buy_10"),
                InlineKeyboardButton("🏆 Quick Buy 25", callback_data="quick_buy_25")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            menu_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"User menu callback failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Error loading menu. Use /start to try again.") 