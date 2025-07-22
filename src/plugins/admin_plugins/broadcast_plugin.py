"""
Enterprise Telegram Bot - Broadcast Plugin

This plugin handles all admin broadcast functionality including
mass messaging, targeted notifications, and broadcast analytics.
"""

import logging
from typing import Dict, Any, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, Application
from telegram.constants import ParseMode

from src.plugins.base_plugin import BasePlugin, PluginMetadata
from src import database as db
from src import bot_utils

logger = logging.getLogger(__name__)


class BroadcastPlugin(BasePlugin):
    """Plugin for admin broadcast and messaging functionality."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="Broadcast",
            version="1.0.0",
            description="Admin broadcast messaging and notifications",
            dependencies=[],
        )

    async def initialize(self, config: Dict[str, Any] = None) -> bool:
        """Initialize the broadcast plugin."""
        try:
            logger.info("Initializing Broadcast Plugin...")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Broadcast Plugin: {e}")
            return False

    def register_handlers(self, application: Application) -> None:
        """Register all broadcast handlers."""
        # Commands
        application.add_handler(CommandHandler("broadcast", self.broadcast_command))

        # Callbacks
        application.add_handler(
            CallbackQueryHandler(
                self.admin_broadcast_callback, pattern="^admin_broadcast$"
            )
        )
        application.add_handler(
            CallbackQueryHandler(
                self.broadcast_all_users_callback, pattern="^broadcast_all_users$"
            )
        )
        application.add_handler(
            CallbackQueryHandler(
                self.broadcast_active_users_callback, pattern="^broadcast_active_users$"
            )
        )
        application.add_handler(
            CallbackQueryHandler(
                self.broadcast_compose_callback, pattern="^broadcast_compose$"
            )
        )
        application.add_handler(
            CallbackQueryHandler(
                self.broadcast_schedule_callback, pattern="^broadcast_schedule$"
            )
        )

    def get_commands(self) -> Dict[str, str]:
        """Get commands provided by this plugin."""
        return {"broadcast": "Send messages to users - mass notifications"}

    async def broadcast_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Admin broadcast command."""
        if not await bot_utils.require_admin(update, context):
            return

        await self.admin_broadcast_callback(update, context)

    async def admin_broadcast_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle admin broadcast callback."""
        query = update.callback_query
        if query:
            await query.answer()

        keyboard = [
            [
                InlineKeyboardButton(
                    "📢 Broadcast to All", callback_data="broadcast_all_users"
                ),
                InlineKeyboardButton(
                    "🎯 Broadcast to Active", callback_data="broadcast_active_users"
                ),
            ],
            [
                InlineKeyboardButton(
                    "✍️ Compose Message", callback_data="broadcast_compose"
                ),
                InlineKeyboardButton(
                    "⏰ Schedule Broadcast", callback_data="broadcast_schedule"
                ),
            ],
            [
                InlineKeyboardButton(
                    "📊 Broadcast History", callback_data="broadcast_history"
                ),
                InlineKeyboardButton(
                    "🔙 Back to Admin", callback_data="admin_dashboard"
                ),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = """
📢 **Broadcast Management Center**

Choose how you want to send messages to users:

• **Broadcast to All** - Send to all registered users
• **Broadcast to Active** - Send to recently active users only
• **Compose Message** - Create custom broadcast messages
• **Schedule Broadcast** - Schedule messages for later
• **Broadcast History** - View previous broadcasts and stats

⚠️ **Important:** Use broadcasts responsibly to avoid spamming users.
        """

        if query:
            await query.edit_message_text(
                text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
            )

    async def broadcast_all_users_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle broadcast to all users callback."""
        query = update.callback_query
        await query.answer()

        # Get user statistics
        total_users = db.get_user_count()
        banned_users = (
            db.get_banned_user_count() if hasattr(db, "get_banned_user_count") else 0
        )
        eligible_users = total_users - banned_users

        text = f"""
📢 **Broadcast to All Users**

**📊 Target Audience:**
• Total Registered Users: **{total_users}**
• Banned Users (excluded): **{banned_users}**
• **Eligible Recipients: {eligible_users}**

**⚠️ Warning:** This will send a message to ALL active users. 

**Instructions:**
1. Click "Confirm Broadcast" below
2. Send your message in the next chat
3. Confirm to start the broadcast

**Estimated Delivery Time:** {self._estimate_delivery_time(eligible_users)}
        """

        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Confirm Broadcast", callback_data="confirm_broadcast_all"
                ),
                InlineKeyboardButton("❌ Cancel", callback_data="admin_broadcast"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )

    async def broadcast_active_users_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle broadcast to active users callback."""
        query = update.callback_query
        await query.answer()

        # Get active user statistics
        active_24h = 45  # This would be from actual analytics
        active_7d = 123
        active_30d = 234

        text = f"""
🎯 **Broadcast to Active Users**

**📊 Active User Segments:**
• Active in last 24 hours: **{active_24h}**
• Active in last 7 days: **{active_7d}**
• Active in last 30 days: **{active_30d}**

Choose your target audience:
        """

        keyboard = [
            [
                InlineKeyboardButton(
                    f"🔥 24h Active ({active_24h})",
                    callback_data="broadcast_active_24h",
                ),
                InlineKeyboardButton(
                    f"⭐ 7d Active ({active_7d})", callback_data="broadcast_active_7d"
                ),
            ],
            [
                InlineKeyboardButton(
                    f"📅 30d Active ({active_30d})",
                    callback_data="broadcast_active_30d",
                ),
                InlineKeyboardButton("❌ Cancel", callback_data="admin_broadcast"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )

    async def broadcast_compose_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle broadcast compose callback."""
        query = update.callback_query
        await query.answer()

        text = """
✍️ **Compose Broadcast Message**

Create a professional message for your users:

**📝 Message Templates:**
• **Announcement** - New features, updates, maintenance
• **Promotion** - Special offers, discounts, events  
• **Welcome** - Onboarding, tutorials, tips
• **Support** - Help, FAQ, contact information

**✅ Best Practices:**
• Keep messages concise and clear
• Include a clear call-to-action
• Use emojis sparingly for better readability
• Test with a small group first

Click a template below or send your custom message:
        """

        keyboard = [
            [
                InlineKeyboardButton(
                    "📣 Announcement", callback_data="template_announcement"
                ),
                InlineKeyboardButton(
                    "🎉 Promotion", callback_data="template_promotion"
                ),
            ],
            [
                InlineKeyboardButton("👋 Welcome", callback_data="template_welcome"),
                InlineKeyboardButton("🆘 Support", callback_data="template_support"),
            ],
            [
                InlineKeyboardButton(
                    "💬 Custom Message", callback_data="compose_custom"
                ),
                InlineKeyboardButton("🔙 Back", callback_data="admin_broadcast"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )

    async def broadcast_schedule_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle broadcast schedule callback."""
        query = update.callback_query
        await query.answer()

        text = """
⏰ **Schedule Broadcast**

Schedule your broadcast for optimal delivery times:

**🕐 Suggested Times (based on user activity):**
• **Peak Hours:** 9:00 AM - 11:00 AM, 7:00 PM - 9:00 PM
• **Weekend:** Saturday 10:00 AM - 2:00 PM
• **Avoid:** Late night (11 PM - 6 AM)

**📅 Schedule Options:**
        """

        keyboard = [
            [
                InlineKeyboardButton(
                    "🌅 Next Morning (9 AM)", callback_data="schedule_morning"
                ),
                InlineKeyboardButton(
                    "🌆 This Evening (7 PM)", callback_data="schedule_evening"
                ),
            ],
            [
                InlineKeyboardButton(
                    "📅 Custom Date/Time", callback_data="schedule_custom"
                ),
                InlineKeyboardButton(
                    "📊 Best Time Analysis", callback_data="analyze_best_time"
                ),
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_broadcast")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )

    def _estimate_delivery_time(self, user_count: int) -> str:
        """Estimate broadcast delivery time based on user count."""
        # Assuming 30 messages per second limit
        messages_per_second = 30
        total_seconds = user_count / messages_per_second

        if total_seconds < 60:
            return f"~{int(total_seconds)} seconds"
        elif total_seconds < 3600:
            minutes = int(total_seconds / 60)
            return f"~{minutes} minutes"
        else:
            hours = int(total_seconds / 3600)
            minutes = int((total_seconds % 3600) / 60)
            return f"~{hours}h {minutes}m"

    async def _send_broadcast_message(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        message_text: str,
        user_ids: List[int],
        admin_id: int,
    ) -> Dict[str, int]:
        """
        Send broadcast message to specified users.

        Returns:
            Dictionary with delivery statistics
        """
        delivered = 0
        failed = 0

        for user_id in user_ids:
            try:
                await context.bot.send_message(
                    chat_id=user_id, text=message_text, parse_mode=ParseMode.MARKDOWN
                )
                delivered += 1

                # Rate limiting - respect Telegram limits
                if delivered % 30 == 0:
                    import asyncio

                    await asyncio.sleep(1)

            except Exception as e:
                logger.warning(f"Failed to send broadcast to user {user_id}: {e}")
                failed += 1

        # Log broadcast statistics
        logger.info(
            f"Broadcast completed by admin {admin_id}: "
            f"{delivered} delivered, {failed} failed"
        )

        return {"delivered": delivered, "failed": failed, "total": len(user_ids)}
