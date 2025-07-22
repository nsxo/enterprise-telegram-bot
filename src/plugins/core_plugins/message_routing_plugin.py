"""
Enterprise Telegram Bot - Message Routing Plugin

This plugin handles the core logic for routing messages between
users and the admin group.
"""

import logging
from typing import Dict, Any
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters, Application

from src.plugins.base_plugin import BasePlugin, PluginMetadata
from src import database as db
from src import bot_utils
from src.config import ADMIN_GROUP_ID

logger = logging.getLogger(__name__)


class MessageRoutingPlugin(BasePlugin):
    """Plugin for routing messages between users and admins."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="MessageRouting",
            version="1.0.0",
            description="Routes messages between users and the admin group",
            dependencies=[],
        )

    async def initialize(self, config: Dict[str, Any] = None) -> bool:
        logger.info("Initializing Message Routing Plugin...")
        return True

    def register_handlers(self, application: Application) -> None:
        application.add_handler(
            MessageHandler(filters.ALL, self.master_message_handler)
        )

    def get_commands(self) -> Dict[str, str]:
        return {}

    async def master_message_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """The main message handler to route messages."""
        if update.message.chat.id == ADMIN_GROUP_ID:
            await self.handle_admin_message(update, context)
        else:
            await self.handle_user_message(update, context)

    async def handle_user_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle incoming messages from users."""
        user = update.effective_user
        topic_id = await bot_utils.get_or_create_user_topic(context, user)

        db.update_conversation_last_message(user.id, ADMIN_GROUP_ID)
        db.update_conversation_unread_count(user.id, ADMIN_GROUP_ID, 1)

        await context.bot.forward_message(
            chat_id=ADMIN_GROUP_ID,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id,
            message_thread_id=topic_id,
        )

    async def handle_admin_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle incoming messages from admins in the admin group."""
        message = update.message

        if message.reply_to_message and message.message_thread_id:
            topic_id = message.message_thread_id
            topic_info = db.get_topic_info(ADMIN_GROUP_ID, topic_id)

            if topic_info:
                target_user_id = topic_info["user_id"]

                await context.bot.send_message(
                    chat_id=target_user_id, text=message.text
                )

                db.mark_conversation_as_read(target_user_id, ADMIN_GROUP_ID)

                await message.reply_text(f"✅ Reply sent to user {target_user_id}")
