"""
Enterprise Telegram Bot - User Management Plugin

This plugin handles all admin functionality related to user management,
including user search, banning, gifting credits, and user analytics.
"""

import logging
from typing import Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    Application,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

from src.plugins.base_plugin import BasePlugin, PluginMetadata
from src.services.error_service import ErrorService, ErrorType
from src import database as db
from src import bot_utils

logger = logging.getLogger(__name__)

# States for conversation handler
SELECTING_ACTION, GETTING_USER_ID = range(2)

# Constants for pagination
ADMIN_PANEL_PAGE_SIZE = 10


class UserManagementPlugin(BasePlugin):
    """Plugin for admin user management functionality."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="UserManagement",
            version="1.0.0",
            description="Admin user management, banning, and credit gifting",
            dependencies=[],
        )

    async def initialize(self, config: Dict[str, Any] = None) -> bool:
        """Initialize the user management plugin."""
        try:
            logger.info("Initializing User Management Plugin...")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize User Management Plugin: {e}")
            return False

    def register_handlers(self, application: Application) -> None:
        """Register all user management handlers."""

        gift_conversation_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    self.gift_credits_callback, pattern="^gift_credits_.*"
                )
            ],
            states={
                GETTING_USER_ID: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, self.process_user_id_for_gift
                    )
                ]
            },
            fallbacks=[CallbackQueryHandler(self.cancel_gift, pattern="^cancel_gift$")],
            map_to_parent={
                # End conversation and return to main menu
                ConversationHandler.END: SELECTING_ACTION
            },
        )

        # Commands
        application.add_handler(CommandHandler("users", self.users_command))
        application.add_handler(CommandHandler("admin", self.admin_command))
        application.add_handler(gift_conversation_handler)

        # Callbacks
        application.add_handler(
            CallbackQueryHandler(self.admin_dashboard_callback, pattern="^admin_dashboard$")
        )
        application.add_handler(
            CallbackQueryHandler(self.admin_users_callback, pattern="^admin_users$")
        )
        application.add_handler(
            CallbackQueryHandler(self.admin_ban_callback, pattern="^admin_ban$")
        )
        application.add_handler(
            CallbackQueryHandler(self.admin_gift_callback, pattern="^admin_gift$")
        )
        application.add_handler(
            CallbackQueryHandler(self.ban_user_callback, pattern="^ban_user_.*")
        )
        application.add_handler(
            CallbackQueryHandler(self.unban_user_callback, pattern="^unban_user_.*")
        )
        application.add_handler(
            CallbackQueryHandler(self.admin_users_callback, pattern="^users_page_")
        )

    def get_commands(self) -> Dict[str, str]:
        """Get commands provided by this plugin."""
        return {
            "users": "Manage users - search, ban, gift credits",
            "admin": "Main admin dashboard with all admin functions"
        }

    async def admin_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Main admin dashboard command."""
        if not await bot_utils.require_admin(update, context):
            return

        await self.admin_dashboard_callback(update, context)

    async def admin_dashboard_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle admin dashboard callback - main admin interface."""
        query = update.callback_query
        if query:
            await query.answer()

        # Get quick stats for dashboard
        total_users = db.get_user_count()
        banned_users = db.get_banned_user_count()
        unread_count = db.get_total_unread_count(ADMIN_GROUP_ID)
        
        text = f"""
🔧 **Admin Dashboard**

**📊 Quick Stats:**
• Total Users: **{total_users}**
• Banned Users: **{banned_users}**
• Unread Messages: **{unread_count}**

**⚡ Admin Tools:**
        """

        keyboard = [
            [
                InlineKeyboardButton("👥 User Management", callback_data="admin_users"),
                InlineKeyboardButton("📊 Analytics", callback_data="admin_analytics"),
            ],
            [
                InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
                InlineKeyboardButton("🛍️ Products", callback_data="admin_products"),
            ],
            [
                InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"),
                InlineKeyboardButton("🔄 Refresh", callback_data="admin_dashboard"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if query:
            await query.edit_message_text(
                text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
            )

    async def users_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Admin users management command."""
        if not await bot_utils.require_admin(update, context):
            return

        keyboard = [
            [
                InlineKeyboardButton("👥 View All Users", callback_data="admin_users"),
                InlineKeyboardButton("🚫 Ban/Unban User", callback_data="admin_ban"),
            ],
            [
                InlineKeyboardButton("🎁 Gift Credits", callback_data="admin_gift"),
                InlineKeyboardButton(
                    "📊 User Analytics", callback_data="user_analytics"
                ),
            ],
            [
                InlineKeyboardButton("🔍 Search Users", callback_data="search_users"),
                InlineKeyboardButton(
                    "🔙 Back to Admin", callback_data="admin_dashboard"
                ),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = """
👥 **User Management Center**

Choose an action to manage users:

• **View All Users** - Browse user list with pagination
• **Ban/Unban User** - Moderate user access
• **Gift Credits** - Send credits to users
• **User Analytics** - View user statistics and behavior
• **Search Users** - Find specific users by criteria
        """

        await update.message.reply_text(
            text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )

    async def admin_users_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle admin users list callback."""
        query = update.callback_query
        await query.answer()

        try:
            page = 1
            if query.data and "users_page_" in query.data:
                page = int(query.data.split("_")[-1])

            limit = ADMIN_PANEL_PAGE_SIZE
            users = db.get_paginated_users(page, limit)
            total_users = db.get_user_count()

            if not users:
                await query.edit_message_text("📭 No users found.")
                return

            text = f"👥 **Users List** (Page {page})\n"
            text += f"Total Users: {total_users}\n\n"

            for i, user in enumerate(users, 1):
                status_emoji = "🟢" if not user.get("is_banned", False) else "🔴"
                text += (
                    f"{status_emoji} **{i}.** {user['first_name']}"
                    f"{' ' + user['last_name'] if user.get('last_name') else ''}\n"
                    f"   ID: `{user['telegram_id']}` | "
                    f"Credits: {user.get('message_credits', 0)}\n"
                    f"   Username: @{user.get('username', 'N/A')}\n\n"
                )

            keyboard = [
                [
                    InlineKeyboardButton(
                        "⬅️ Prev", callback_data=f"users_page_{page-1}"
                    ),
                    InlineKeyboardButton(
                        "➡️ Next", callback_data=f"users_page_{page+1}"
                    ),
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="admin_users")],
            ]

            # Disable navigation buttons if at boundaries
            if page <= 1:
                keyboard[0][0] = InlineKeyboardButton("⬅️ Prev", callback_data="noop")
            if page * limit >= total_users:
                keyboard[0][1] = InlineKeyboardButton("➡️ Next", callback_data="noop")

            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
            )

        except Exception as e:
            logger.error(f"Error in admin_users_callback: {e}")
            await query.edit_message_text("❌ Error loading users list.")

    async def admin_ban_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle admin ban user callback."""
        query = update.callback_query
        await query.answer()

        text = """
🚫 **Ban/Unban User**

To ban or unban a user, send their Telegram ID or username.

**Format:**
• `123456789` (Telegram ID)
• `@username` (Username)

The user will be banned/unbanned immediately.
        """

        keyboard = [
            [InlineKeyboardButton("🔙 Back to Users", callback_data="admin_users")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )

    async def admin_gift_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle admin gift credits callback."""
        query = update.callback_query
        await query.answer()

        keyboard = [
            [
                InlineKeyboardButton(
                    "🎁 Gift 10 Credits", callback_data="gift_credits_10"
                ),
                InlineKeyboardButton(
                    "🎁 Gift 25 Credits", callback_data="gift_credits_25"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🎁 Gift 50 Credits", callback_data="gift_credits_50"
                ),
                InlineKeyboardButton(
                    "🎁 Gift 100 Credits", callback_data="gift_credits_100"
                ),
            ],
            [InlineKeyboardButton("🔙 Back to Users", callback_data="admin_users")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        text = """
🎁 **Gift Credits to User**

Choose the number of credits to gift, then provide the user's Telegram ID.

**How it works:**
1. Select credit amount
2. Enter user's Telegram ID
3. Credits are added instantly
4. User receives notification
        """

        await query.edit_message_text(
            text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )

    async def gift_credits_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle gift credits action callback."""
        query = update.callback_query
        await query.answer()

        try:
            callback_data = query.data
            amount_str = callback_data.split("_")[-1]
            amount = int(amount_str)

            # Store the amount in context and ask for user ID
            context.user_data["gift_amount"] = amount

            await query.edit_message_text(
                f"🎁 You are gifting **{amount} credits**.\n\n"
                "Please send the Telegram ID of the user you want to gift credits to.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return GETTING_USER_ID

        except (ValueError, IndexError):
            await query.edit_message_text("❌ Invalid gift credits action.")
            return ConversationHandler.END

    async def process_user_id_for_gift(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Process the user ID provided by the admin for gifting."""
        user_id_str = update.message.text

        try:
            user_id = int(user_id_str)
            amount = context.user_data.get("gift_amount")

            if not amount:
                await update.message.reply_text(
                    "❌ Session expired. Please start over."
                )
                return ConversationHandler.END

            success = db.gift_credits_to_user(user_id, amount, update.effective_user.id)

            if success:
                await update.message.reply_text(
                    f"✅ Successfully gifted {amount} credits to user {user_id}."
                )
            else:
                await update.message.reply_text(
                    f"❌ Failed to gift credits to user {user_id}."
                )
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid user ID. Please send a valid number."
            )
            return GETTING_USER_ID
        finally:
            # Clean up context
            if "gift_amount" in context.user_data:
                del context.user_data["gift_amount"]

        return ConversationHandler.END

    async def cancel_gift(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Cancel the gift operation."""
        query = update.callback_query
        await query.answer()

        if "gift_amount" in context.user_data:
            del context.user_data["gift_amount"]

        await query.edit_message_text("🎁 Gift operation cancelled.")
        return ConversationHandler.END

    async def ban_user_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle ban user callback."""
        query = update.callback_query
        await query.answer()

        # Extract user ID from callback data
        try:
            user_id = int(query.data.split("_")[-1])

            # Ban the user
            success = db.ban_user(user_id, query.from_user.id, "Admin decision")

            if success:
                await query.edit_message_text(
                    f"✅ **User {user_id} has been banned.**",
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                await query.edit_message_text("❌ Failed to ban user.")

        except (ValueError, IndexError):
            await query.edit_message_text("❌ Invalid ban user action.")
        except Exception as e:
            logger.error(f"Ban user failed: {e}")
            await query.edit_message_text("❌ Failed to ban user.")

    async def unban_user_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle unban user callback."""
        query = update.callback_query
        await query.answer()

        # Extract user ID from callback data
        try:
            user_id = int(query.data.split("_")[-1])

            # Unban the user
            success = db.unban_user(user_id, query.from_user.id)

            if success:
                await query.edit_message_text(
                    f"✅ **User {user_id} has been unbanned.**",
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                await query.edit_message_text("❌ Failed to unban user.")

        except (ValueError, IndexError):
            await query.edit_message_text("❌ Invalid unban user action.")
        except Exception as e:
            logger.error(f"Unban user failed: {e}")
            await query.edit_message_text("❌ Failed to unban user.")
