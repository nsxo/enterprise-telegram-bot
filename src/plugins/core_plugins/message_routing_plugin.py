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
from src.services.error_service import ErrorService, ErrorType
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
        
        try:
            # Get or create topic for this user
            topic_id = await bot_utils.get_or_create_user_topic(context, user)

            # Update conversation metadata
            db.update_conversation_last_message(user.id, ADMIN_GROUP_ID)
            db.update_conversation_unread_count(user.id, ADMIN_GROUP_ID, 1)

            # Forward message to admin group topic with rate limiting
            forwarded_msg = await bot_utils.rate_limited_send(
                context.bot.forward_message,
                ADMIN_GROUP_ID,
                chat_id=ADMIN_GROUP_ID,
                from_chat_id=update.message.chat_id,
                message_id=update.message.message_id,
                message_thread_id=topic_id,
            )

            # Store message reference for audit trail
            db.store_message_reference(
                update.message.message_id,
                forwarded_msg.message_id,
                user.id,
                topic_id
            )

            logger.info(
                f"✅ Forwarded message from user {user.id} to topic {topic_id} "
                f"(msg: {update.message.message_id} -> {forwarded_msg.message_id})"
            )

        except Exception as e:
            logger.error(f"Failed to handle user message from {user.id}: {e}")
            
            # Send error message to user
            try:
                await update.message.reply_text(
                    "❌ Sorry, there was an issue processing your message. "
                    "Please try again later or contact support."
                )
            except Exception as reply_error:
                logger.error(f"Failed to send error reply to user {user.id}: {reply_error}")

    async def handle_admin_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle incoming messages from admins in the admin group."""
        message = update.message
        target_user_id = None
        topic_id = None

        # Stage 1: Direct reply inference (preferred method)
        if message.reply_to_message and message.message_thread_id:
            topic_id = message.message_thread_id
            topic_info = db.get_topic_info(ADMIN_GROUP_ID, topic_id)
            
            if topic_info:
                target_user_id = topic_info["user_id"]
                logger.info(f"Admin reply via direct reply in topic {topic_id} to user {target_user_id}")
            
        # Stage 2: Topic ID lookup fallback
        elif message.message_thread_id:
            topic_id = message.message_thread_id
            topic_info = db.get_topic_info(ADMIN_GROUP_ID, topic_id)
            
            if topic_info:
                target_user_id = topic_info["user_id"]
                logger.info(f"Admin message via topic fallback in topic {topic_id} to user {target_user_id}")

        # Process the message if we found a target user
        if target_user_id and topic_id:
            try:
                # Support all message types
                sent_message = None
                
                if message.text:
                    sent_message = await bot_utils.rate_limited_send(
                        context.bot.send_message,
                        target_user_id,
                        chat_id=target_user_id, 
                        text=message.text,
                        entities=message.entities  # Preserve formatting
                    )
                elif message.photo:
                    sent_message = await bot_utils.rate_limited_send(
                        context.bot.send_photo,
                        target_user_id,
                        chat_id=target_user_id, 
                        photo=message.photo[-1].file_id, 
                        caption=message.caption,
                        caption_entities=message.caption_entities
                    )
                elif message.document:
                    sent_message = await bot_utils.rate_limited_send(
                        context.bot.send_document,
                        target_user_id,
                        chat_id=target_user_id, 
                        document=message.document.file_id, 
                        caption=message.caption,
                        caption_entities=message.caption_entities
                    )
                elif message.video:
                    sent_message = await bot_utils.rate_limited_send(
                        context.bot.send_video,
                        target_user_id,
                        chat_id=target_user_id, 
                        video=message.video.file_id, 
                        caption=message.caption,
                        caption_entities=message.caption_entities,
                        duration=message.video.duration,
                        width=message.video.width,
                        height=message.video.height
                    )
                elif message.voice:
                    sent_message = await bot_utils.rate_limited_send(
                        context.bot.send_voice,
                        target_user_id,
                        chat_id=target_user_id, 
                        voice=message.voice.file_id,
                        duration=message.voice.duration,
                        caption=message.caption,
                        caption_entities=message.caption_entities
                    )
                elif message.audio:
                    sent_message = await bot_utils.rate_limited_send(
                        context.bot.send_audio,
                        target_user_id,
                        chat_id=target_user_id, 
                        audio=message.audio.file_id,
                        duration=message.audio.duration,
                        performer=message.audio.performer,
                        title=message.audio.title,
                        caption=message.caption,
                        caption_entities=message.caption_entities
                    )
                elif message.video_note:
                    sent_message = await bot_utils.rate_limited_send(
                        context.bot.send_video_note,
                        target_user_id,
                        chat_id=target_user_id,
                        video_note=message.video_note.file_id,
                        duration=message.video_note.duration,
                        length=message.video_note.length
                    )
                elif message.sticker:
                    sent_message = await bot_utils.rate_limited_send(
                        context.bot.send_sticker,
                        target_user_id,
                        chat_id=target_user_id, 
                        sticker=message.sticker.file_id
                    )
                elif message.animation:
                    sent_message = await bot_utils.rate_limited_send(
                        context.bot.send_animation,
                        target_user_id,
                        chat_id=target_user_id,
                        animation=message.animation.file_id,
                        duration=message.animation.duration,
                        width=message.animation.width,
                        height=message.animation.height,
                        caption=message.caption,
                        caption_entities=message.caption_entities
                    )
                elif message.location:
                    sent_message = await bot_utils.rate_limited_send(
                        context.bot.send_location,
                        target_user_id,
                        chat_id=target_user_id,
                        latitude=message.location.latitude,
                        longitude=message.location.longitude
                    )
                elif message.contact:
                    sent_message = await bot_utils.rate_limited_send(
                        context.bot.send_contact,
                        target_user_id,
                        chat_id=target_user_id,
                        phone_number=message.contact.phone_number,
                        first_name=message.contact.first_name,
                        last_name=message.contact.last_name
                    )
                elif message.poll:
                    # For polls, we need to forward since we can't recreate them easily
                    sent_message = await bot_utils.rate_limited_send(
                        context.bot.forward_message,
                        target_user_id,
                        chat_id=target_user_id,
                        from_chat_id=ADMIN_GROUP_ID,
                        message_id=message.message_id
                    )
                else:
                    # Forward the message if type not explicitly handled
                    sent_message = await bot_utils.rate_limited_send(
                        context.bot.forward_message,
                        target_user_id,
                        chat_id=target_user_id,
                        from_chat_id=ADMIN_GROUP_ID,
                        message_id=message.message_id
                    )

                # Mark conversation as read and store message reference
                db.mark_conversation_as_read(target_user_id, ADMIN_GROUP_ID)
                
                if sent_message:
                    # Store message reference for audit trail
                    db.store_message_reference(
                        message.message_id,
                        sent_message.message_id,
                        target_user_id,
                        topic_id
                    )

                # Confirm to admin with appropriate emoji based on message type
                if message.photo:
                    confirm_emoji = "📸"
                elif message.document:
                    confirm_emoji = "📄"
                elif message.video:
                    confirm_emoji = "🎥"
                elif message.voice:
                    confirm_emoji = "🎤"
                elif message.sticker:
                    confirm_emoji = "😀"
                elif message.audio:
                    confirm_emoji = "🎵"
                else:
                    confirm_emoji = "✅"

                await message.reply_text(
                    f"{confirm_emoji} Reply sent to user {target_user_id}"
                )

            except Exception as e:
                logger.error(f"Failed to send admin reply to user {target_user_id}: {e}")
                await message.reply_text(
                    f"❌ Failed to send reply to user {target_user_id}. Error: {str(e)[:100]}"
                )
        else:
            # Message not in a user topic or couldn't identify target user
            logger.debug(f"Admin message not routed - no topic match. Thread ID: {message.message_thread_id}")
