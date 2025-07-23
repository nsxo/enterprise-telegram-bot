"""
Enterprise Telegram Bot - Core Commands Plugin

This plugin handles the most essential user-facing commands like
/start, /help, /reset, /status, and /balance.
"""

import logging
from typing import Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, Application

from src.plugins.base_plugin import BasePlugin, PluginMetadata
from src.services.error_service import ErrorService, ErrorType
from src import database as db
from src import bot_utils
from src.config import ADMIN_GROUP_ID

logger = logging.getLogger(__name__)


class CoreCommandsPlugin(BasePlugin):
    """Plugin for essential user commands."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="CoreCommands",
            version="1.0.0",
            description=(
                "Essential commands like /start, /help, /reset, /status, /balance"
            ),
            dependencies=[],
        )

    async def initialize(self, config: Dict[str, Any] = None) -> bool:
        """Initialize the core commands plugin."""
        logger.info("Initializing Core Commands Plugin...")
        return True

    def register_handlers(self, application: Application) -> None:
        """Register all core command handlers."""
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("reset", self.reset_command))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_handler(
            CommandHandler("balance", self.balance_command)
        )
        application.add_handler(CommandHandler("time", self.time_command))

    def get_commands(self) -> Dict[str, str]:
        """Get commands provided by this plugin."""
        return {
            "start": "Start the bot and see the welcome message",
            "help": "Get help and see all available commands",
            "reset": "Reset your session and tutorial progress",
            "status": "Check your account status, balance, and usage",
            "balance": "Check your credit balance with visual progress bar",
            "time": "Show current time",
        }

    async def start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle the /start command."""
        user = update.effective_user
        db.get_or_create_user(
            user.id, user.username, user.first_name, user.last_name
        )

        text = (
            f"Welcome, {user.first_name}! "
            "I'm the Enterprise Bot, ready to assist you."
        )
        keyboard = [
            [
                InlineKeyboardButton(
                    "🚀 Take a Quick Tour", callback_data="start_tutorial"
                )
            ],
            [
                InlineKeyboardButton(
                    "💬 Start Chatting Now", callback_data="start_chatting"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(text, reply_markup=reply_markup)

    async def help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle the /help command."""
        plugin_manager = context.bot_data.get("plugin_manager")
        all_commands = (
            plugin_manager.get_all_commands() if plugin_manager else {}
        )

        text = "Here are the available commands:\n\n"
        for command, description in sorted(all_commands.items()):
            text += f"/{command} - {description}\n"

        await update.message.reply_text(text)

    async def reset_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle the /reset command."""
        user = update.effective_user

        # Reset tutorial state
        reset_query = (
            "UPDATE users SET tutorial_completed = FALSE, tutorial_step = 0 "
            "WHERE telegram_id = %s"
        )
        db.execute_query(reset_query, (user.id,))

        # Mark conversations as read
        if ADMIN_GROUP_ID:
            db.mark_conversation_as_read(user.id, ADMIN_GROUP_ID)

        await update.message.reply_text("Your session has been reset.")

    async def status_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle the /status command."""
        user = update.effective_user
        user_data = db.get_user_dashboard_data(user.id)

        if not user_data:
            await update.message.reply_text("Could not retrieve your status.")
            return

        total_spent = user_data.get('total_spent_cents', 0) / 100
        text = f"""
📊 **Your Account Status**

**Credits:** {user_data.get('message_credits', 0)}
**Membership Tier:** {user_data.get('tier_name', 'Standard')}
**Total Spent:** ${total_spent:.2f}
        """

        await update.message.reply_text(text)

    async def balance_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle the /balance command with enhanced visual display."""
        user = update.effective_user
        
        try:
            # Get user data
            user_data = db.get_user_dashboard_data(user.id)
            
            if not user_data:
                await update.message.reply_text(
                    "❌ Could not retrieve your balance. "
                    "Please try again later."
                )
                return

            # Create enhanced balance card
            balance_card = bot_utils.create_balance_card(user_data)
            
            # Check if user should see quick buy options
            credits = user_data.get('message_credits', 0)
            should_show_quick_buy = db.should_show_quick_buy_warning(user.id)
            
            keyboard = []
            
            if should_show_quick_buy and credits <= 10:
                # Add quick buy options for low credit users
                quick_buy_message = (
                    db.get_bot_setting("low_credit_warning_message") 
                    or "Quick top-up options:"
                )
                balance_card += f"\n\n💡 **{quick_buy_message}**"
                
                keyboard = [
                    [
                        InlineKeyboardButton(
                            "⚡ Buy 10 Credits", callback_data="quick_buy_10"
                        ),
                        InlineKeyboardButton(
                            "⚡ Buy 25 Credits", callback_data="quick_buy_25"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "🛒 View All Options", callback_data="show_products"
                        ),
                    ],
                ]
                
                # Mark that warning was shown
                db.mark_low_credit_warning_shown(user.id)
            else:
                # Regular options for users with sufficient credits
                keyboard = [
                    [
                        InlineKeyboardButton(
                            "🛒 Buy More Credits", callback_data="show_products"
                        ),
                        InlineKeyboardButton(
                            "💳 Billing Portal", 
                            url="https://billing.stripe.com"
                        ),
                    ],
                ]
            
            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            
            await update.message.reply_text(
                balance_card, 
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Error in balance_command for user {user.id}: {e}")
            error_msg = (
                "❌ An error occurred while retrieving your balance. "
                "Please try again later."
            )
            await update.message.reply_text(error_msg)

    async def time_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle the /time command to show current time."""
        from datetime import datetime
        
        current_time = datetime.now()
        formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S UTC")
        
        text = f"🕐 **Current Time**\n\n{formatted_time}"
        
        await update.message.reply_text(text, parse_mode="Markdown")
