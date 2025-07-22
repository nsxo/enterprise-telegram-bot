"""
Enterprise Telegram Bot - Tutorial Plugin

This plugin handles the interactive onboarding tutorial for new users.
"""

import logging
from typing import Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, Application

from src.plugins.base_plugin import BasePlugin, PluginMetadata
from src import database as db

logger = logging.getLogger(__name__)


class TutorialPlugin(BasePlugin):
    """Plugin for the new user interactive tutorial."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="Tutorial",
            version="1.0.0",
            description="New user interactive onboarding tutorial",
            dependencies=[],
        )

    async def initialize(self, config: Dict[str, Any] = None) -> bool:
        """Initialize the tutorial plugin."""
        logger.info("Initializing Tutorial Plugin...")
        return True

    def register_handlers(self, application: Application) -> None:
        """Register all tutorial handlers."""
        application.add_handler(
            CallbackQueryHandler(
                self.start_tutorial_callback, pattern="^start_tutorial$"
            )
        )
        application.add_handler(
            CallbackQueryHandler(
                self.tutorial_step_2_callback, pattern="^tutorial_step_2$"
            )
        )
        application.add_handler(
            CallbackQueryHandler(
                self.tutorial_step_3_callback, pattern="^tutorial_step_3$"
            )
        )
        application.add_handler(
            CallbackQueryHandler(
                self.complete_tutorial_callback, pattern="^complete_tutorial$"
            )
        )
        application.add_handler(
            CallbackQueryHandler(
                self.start_chatting_callback, pattern="^start_chatting$"
            )
        )

    def get_commands(self) -> Dict[str, str]:
        """Get commands provided by this plugin."""
        return {}

    async def start_tutorial_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Starts the interactive tutorial for the user."""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        db.update_user_tutorial_state(user_id, step=1)

        text = """
Step 1: **Account Balance** 💰

Your account balance is where you can see how many message credits you have.

- Each message you send uses **1 credit**.
- You can buy more credits anytime with the `/buy` command.

Check your balance now to see your starting credits!
        """

        keyboard = [
            [InlineKeyboardButton("Check My Balance", callback_data="tutorial_step_2")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup)

    async def tutorial_step_2_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Shows the user their balance and proceeds to step 2."""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        db.update_user_tutorial_state(user_id, step=2)

        user_data = db.get_user(user_id)
        credits = user_data.get("message_credits", 0) if user_data else 0

        text = f"""
Step 2: **Sending a Message** ✉️

Awesome! You have **{credits} message credits**.

To start a conversation, simply send a message in this chat. Our team will get back to you right away.

Try sending a message now!
        """

        keyboard = [
            [InlineKeyboardButton("How It Works", callback_data="tutorial_step_3")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup)

    async def tutorial_step_3_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Explains the conversation process."""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        db.update_user_tutorial_state(user_id, step=3)

        text = """
Step 3: **How Conversations Work** 💬

When you send a message, we create a private topic for you in our admin group.

- Our team responds directly in that topic.
- Your replies will go to the same private topic.
- You can manage your conversations with the `/status` command.

Ready to get started?
        """

        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Finish Tutorial", callback_data="complete_tutorial"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup)

    async def complete_tutorial_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Marks the tutorial as complete."""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        db.update_user_tutorial_state(user_id, completed=True)

        text = """
🎉 **Tutorial Complete!** 🎉

You're all set to use the bot. Here are some quick tips:

- `/help` - See all available commands.
- `/status` - Check your account status and usage.
- `/buy` - Get more credits anytime.

Start chatting now!
        """

        keyboard = [
            [
                InlineKeyboardButton(
                    "Start Chatting Now!", callback_data="start_chatting"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup)

    async def start_chatting_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Final message to encourage user to start chatting."""
        query = update.callback_query
        await query.answer()

        text = "You can now send your first message. We're excited to hear from you!"

        await query.edit_message_text(text)
