"""
Enterprise Telegram Bot - Core Commands Plugin

This plugin handles the most essential user-facing commands like
/start, /help, /reset, and /status.
"""

import logging
from typing import Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, Application

from src.plugins.base_plugin import BasePlugin, PluginMetadata
from src import database as db
from src.config import ADMIN_GROUP_ID

logger = logging.getLogger(__name__)


class CoreCommandsPlugin(BasePlugin):
    """Plugin for essential user commands."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="CoreCommands",
            version="1.0.0",
            description="Essential commands like /start, /help, /reset, /status",
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

    def get_commands(self) -> Dict[str, str]:
        """Get commands provided by this plugin."""
        return {
            "start": "Start the bot and see the welcome message",
            "help": "Get help and see all available commands",
            "reset": "Reset your session and tutorial progress",
            "status": "Check your account status, balance, and usage",
        }

    async def start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle the /start command."""
        user = update.effective_user
        db.get_or_create_user(user.id, user.username, user.first_name, user.last_name)

        text = (
            f"Welcome, {user.first_name}! I'm the Enterprise Bot, ready to assist you."
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
        all_commands = plugin_manager.get_all_commands() if plugin_manager else {}

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
        db.execute_query(
            "UPDATE users SET tutorial_completed = FALSE, tutorial_step = 0 WHERE telegram_id = %s",
            (user.id,),
        )

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

        text = f"""
📊 **Your Account Status**

**Credits:** {user_data.get('message_credits', 0)}
**Membership Tier:** {user_data.get('tier_name', 'Standard')}
**Total Spent:** ${user_data.get('total_paid_usd', 0):.2f}
        """

        await update.message.reply_text(text)
