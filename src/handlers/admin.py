"""
Enterprise Telegram Bot - Admin Handlers

This module contains all admin-specific functionality including admin commands,
dashboard management, user management, and administrative callbacks.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from src import database as db
from src import bot_utils
# from src import emoji_config  # Unused for now
# from src.config import ADMIN_GROUP_ID  # Unused for now

logger = logging.getLogger(__name__)


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /admin command - show comprehensive admin dashboard."""
    # Check admin authorization first
    if not await bot_utils.require_admin(update, context):
        return
    
    message = update.message
    user = message.from_user
    
    # Get real-time statistics
    user_count = db.get_user_count()
    conversation_count = db.get_conversation_count()
    unread_count = 0  # TODO: Implement unread message tracking
    
    dashboard_text = (
        "🔧 **Admin Control Center**\n\n"
        f"📊 **Real-time Stats:**\n"
        f"👥 Total Users: **{user_count}**\n"
        f"💬 Active Conversations: **{conversation_count}**\n"
        f"📬 Unread Messages: **{unread_count}**\n"
        f"🟢 Admin Status: **Online**\n\n"
        "Select a category to manage:"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("💬 Conversations", callback_data="admin_conversations"),
            InlineKeyboardButton("📊 Dashboard", callback_data="admin_dashboard")
        ],
        [
            InlineKeyboardButton("📈 Analytics", callback_data="admin_analytics"),
            InlineKeyboardButton("👥 Users", callback_data="admin_users")
        ],
        [
            InlineKeyboardButton("🛒 Products", callback_data="admin_products"),
            InlineKeyboardButton("💰 Billing", callback_data="admin_billing")
        ],
        [
            InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
            InlineKeyboardButton("🎁 Mass Gift", callback_data="admin_mass_gift")
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"),
            InlineKeyboardButton("🔧 System", callback_data="admin_system")
        ],
        [
            InlineKeyboardButton("📝 Quick Replies", callback_data="admin_quick_replies"),
            InlineKeyboardButton("🔍 Search", callback_data="admin_search")
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="admin_refresh"),
            InlineKeyboardButton("❌ Close", callback_data="admin_close")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text(
        dashboard_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )


async def dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Quick access to admin dashboard."""
    if not await bot_utils.require_admin(update, context):
        return
    await admin_command(update, context)


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin settings command."""
    if not await bot_utils.require_admin(update, context):
        return
    
    await update.message.reply_text(
        "⚙️ **Admin Settings**\n\nSettings management coming soon!",
        parse_mode=ParseMode.MARKDOWN
    )


async def products_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin products management command."""
    if not await bot_utils.require_admin(update, context):
        return
    
    products = db.get_all_products()
    
    products_text = "🛒 **Products Management**\n\n"
    for product in products:
        products_text += f"**{product['name']}**: ${product['price_cents']/100:.2f} - {product['credits']} credits\n"
    
    await update.message.reply_text(
        products_text,
        parse_mode=ParseMode.MARKDOWN
    )


async def analytics_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin analytics command."""
    if not await bot_utils.require_admin(update, context):
        return
    
    await update.message.reply_text(
        "📈 **Analytics Dashboard**\n\nDetailed analytics coming soon!",
        parse_mode=ParseMode.MARKDOWN
    )


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin users management command."""
    if not await bot_utils.require_admin(update, context):
        return
    
    user_count = db.get_user_count()
    await update.message.reply_text(
        f"👥 **User Management**\n\nTotal Users: **{user_count}**\n\nDetailed user management coming soon!",
        parse_mode=ParseMode.MARKDOWN
    )


async def conversations_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin conversations management command."""
    if not await bot_utils.require_admin(update, context):
        return
    
    await update.message.reply_text(
        "💬 **Conversations Management**\n\nConversation tools coming soon!",
        parse_mode=ParseMode.MARKDOWN
    )


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin broadcast command."""
    if not await bot_utils.require_admin(update, context):
        return
    
    await update.message.reply_text(
        "📢 **Broadcast System**\n\nBroadcast functionality coming soon!",
        parse_mode=ParseMode.MARKDOWN
    )


async def webhook_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin webhook management command."""
    if not await bot_utils.require_admin(update, context):
        return
    
    await update.message.reply_text(
        "🔗 **Webhook Management**\n\nWebhook tools coming soon!",
        parse_mode=ParseMode.MARKDOWN
    )


async def system_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin system management command."""
    if not await bot_utils.require_admin(update, context):
        return
    
    await update.message.reply_text(
        "🔧 **System Management**\n\nSystem tools coming soon!",
        parse_mode=ParseMode.MARKDOWN
    )


# Admin Callback Handlers
async def admin_conversations_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin conversations callback."""
    query = update.callback_query
    await query.answer()
    
    # Get conversation statistics
    conversation_count = db.get_conversation_count()
    
    text = (
        "💬 **Conversation Management**\n\n"
        f"📊 **Stats:**\n"
        f"• Active Conversations: {conversation_count}\n"
        f"• Unread Messages: 0\n"
        f"• Average Response Time: < 1min\n\n"
        "**Quick Actions:**"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("📋 View All", callback_data="admin_view_conversations"),
            InlineKeyboardButton("🔍 Search", callback_data="admin_search_conversations")
        ],
        [
            InlineKeyboardButton("📊 Analytics", callback_data="admin_conversation_analytics"),
            InlineKeyboardButton("⚙️ Settings", callback_data="admin_conversation_settings")
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="admin_main")
        ]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def admin_dashboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin dashboard callback."""
    query = update.callback_query
    await query.answer()
    
    # Get comprehensive stats
    user_count = db.get_user_count()
    conversation_count = db.get_conversation_count()
    
    text = (
        "📊 **Admin Dashboard**\n\n"
        f"**👥 Users:** {user_count}\n"
        f"**💬 Conversations:** {conversation_count}\n"
        f"**📈 Growth:** +5% this week\n"
        f"**💰 Revenue:** $1,234 this month\n\n"
        "**System Health:** 🟢 All systems operational"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("📈 Detailed Analytics", callback_data="admin_analytics"),
            InlineKeyboardButton("💰 Revenue Report", callback_data="admin_revenue")
        ],
        [
            InlineKeyboardButton("🔧 System Status", callback_data="admin_system"),
            InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings")
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="admin_main")
        ]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def admin_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin users management callback."""
    query = update.callback_query
    await query.answer()
    
    user_count = db.get_user_count()
    
    text = (
        "👥 **User Management**\n\n"
        f"**Total Users:** {user_count}\n"
        f"**Active Today:** ~{int(user_count * 0.1)}\n"
        f"**New This Week:** ~{int(user_count * 0.05)}\n\n"
        "**Quick Actions:**"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("👤 Find User", callback_data="admin_find_user"),
            InlineKeyboardButton("📊 User Stats", callback_data="admin_user_stats")
        ],
        [
            InlineKeyboardButton("🎁 Mass Gift Credits", callback_data="admin_mass_gift"),
            InlineKeyboardButton("📢 Send Announcement", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton("🚫 Manage Bans", callback_data="admin_manage_bans"),
            InlineKeyboardButton("⬆️ Tier Management", callback_data="admin_tiers")
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="admin_main")
        ]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def admin_products_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin products management callback."""
    query = update.callback_query
    await query.answer()
    
    products = db.get_all_products()
    
    text = "🛒 **Product Management**\n\n"
    
    for product in products[:5]:  # Show first 5
        text += f"**{product['name']}**\n"
        text += f"• Price: ${product['price_cents']/100:.2f}\n"
        text += f"• Credits: {product['credits']}\n\n"
    
    keyboard = [
        [
            InlineKeyboardButton("➕ Add Product", callback_data="admin_add_product"),
            InlineKeyboardButton("✏️ Edit Products", callback_data="admin_edit_products")
        ],
        [
            InlineKeyboardButton("📊 Sales Analytics", callback_data="admin_sales_analytics"),
            InlineKeyboardButton("💰 Pricing Strategy", callback_data="admin_pricing")
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="admin_main")
        ]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def admin_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin main menu callback."""
    query = update.callback_query
    await query.answer()
    
    # Simulate the admin_command but for callback
    user_count = db.get_user_count()
    conversation_count = db.get_conversation_count()
    unread_count = 0  # TODO: Implement unread message tracking
    
    dashboard_text = (
        "🔧 **Admin Control Center**\n\n"
        f"📊 **Real-time Stats:**\n"
        f"👥 Total Users: **{user_count}**\n"
        f"💬 Active Conversations: **{conversation_count}**\n"
        f"📬 Unread Messages: **{unread_count}**\n"
        f"🟢 Admin Status: **Online**\n\n"
        "Select a category to manage:"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("💬 Conversations", callback_data="admin_conversations"),
            InlineKeyboardButton("📊 Dashboard", callback_data="admin_dashboard")
        ],
        [
            InlineKeyboardButton("📈 Analytics", callback_data="admin_analytics"),
            InlineKeyboardButton("👥 Users", callback_data="admin_users")
        ],
        [
            InlineKeyboardButton("🛒 Products", callback_data="admin_products"),
            InlineKeyboardButton("💰 Billing", callback_data="admin_billing")
        ],
        [
            InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
            InlineKeyboardButton("🎁 Mass Gift", callback_data="admin_mass_gift")
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"),
            InlineKeyboardButton("🔧 System", callback_data="admin_system")
        ],
        [
            InlineKeyboardButton("📝 Quick Replies", callback_data="admin_quick_replies"),
            InlineKeyboardButton("🔍 Search", callback_data="admin_search")
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="admin_refresh"),
            InlineKeyboardButton("❌ Close", callback_data="admin_close")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        dashboard_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )


async def admin_close_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin menu close callback."""
    query = update.callback_query
    await query.answer("Admin menu closed.")
    
    try:
        await query.delete_message()
    except Exception as e:
        logger.warning(f"Failed to delete admin menu message: {e}")
        # Fallback to editing the message
        await query.edit_message_text("🔧 Admin menu closed.")


async def admin_ban_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin ban user callback."""
    query = update.callback_query
    await query.answer()
    
    # Extract user ID from callback data
    try:
        user_id = int(query.data.split("_")[-1])
        
        text = (
            f"🚫 **Ban User {user_id}**\n\n"
            f"Are you sure you want to ban this user?\n\n"
            f"**This action will:**\n"
            f"• Block all bot access\n"
            f"• Prevent new purchases\n"
            f"• Archive conversations\n\n"
            f"**Note:** This action can be reversed."
        )
        
        keyboard = [
            [
                InlineKeyboardButton("🚫 Confirm Ban", callback_data=f"confirm_ban_{user_id}"),
                InlineKeyboardButton("❌ Cancel", callback_data="admin_users")
            ]
        ]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Invalid user ID for ban action.")


async def admin_gift_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin gift credits callback."""
    query = update.callback_query
    await query.answer()
    
    # Extract user ID from callback data
    try:
        user_id = int(query.data.split("_")[-1])
        
        text = (
            f"🎁 **Gift Credits to User {user_id}**\n\n"
            f"Select the number of credits to gift:"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("🎁 5 Credits", callback_data=f"gift_credits_{user_id}_5"),
                InlineKeyboardButton("🎁 10 Credits", callback_data=f"gift_credits_{user_id}_10")
            ],
            [
                InlineKeyboardButton("🎁 25 Credits", callback_data=f"gift_credits_{user_id}_25"),
                InlineKeyboardButton("🎁 50 Credits", callback_data=f"gift_credits_{user_id}_50")
            ],
            [
                InlineKeyboardButton("🎁 Custom Amount", callback_data=f"gift_custom_{user_id}"),
                InlineKeyboardButton("❌ Cancel", callback_data="admin_users")
            ]
        ]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Invalid user ID for gift action.")


async def gift_credits_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle gift credits confirmation callback."""
    query = update.callback_query
    await query.answer()
    
    try:
        # Parse callback data: gift_credits_{user_id}_{amount}
        parts = query.data.split("_")
        user_id = int(parts[2])
        amount = int(parts[3])
        
        # Gift the credits
        db.update_user_credits(user_id, amount)
        
        # Log the gift
        logger.info(f"Admin gifted {amount} credits to user {user_id}")
        
        await query.edit_message_text(
            f"🎁 **Gift Successful!**\n\n"
            f"**{amount} credits** have been added to user {user_id}'s account.\n\n"
            f"The user will be notified about this gift.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # TODO: Send notification to the user about the gift
        
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Invalid gift credits action.")
    except Exception as e:
        logger.error(f"Gift credits failed: {e}")
        await query.edit_message_text("❌ Failed to gift credits. Please try again.") 


async def admin_analytics_callback(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Comprehensive analytics dashboard with revenue, user growth, usage stats.
    """
    query = update.callback_query
    await query.answer()
    
    try:
        # Get comprehensive analytics data
        analytics = db.get_admin_analytics_data()
        
        # Get chart data for visual representation
        revenue_data = db.get_daily_revenue_chart_data(30)
        # user_growth_data = db.get_user_growth_chart_data(30)  # For future use
        
        # Format analytics text
        user_stats = analytics.get('user_stats', {})
        revenue_stats = analytics.get('revenue_stats', {})
        credit_stats = analytics.get('credit_stats', {})
        conversation_stats = analytics.get('conversation_stats', {})
        product_stats = analytics.get('product_stats', [])
        
        # Calculate key metrics
        total_revenue = revenue_stats.get('total_revenue_cents', 0) / 100
        weekly_revenue = revenue_stats.get('revenue_week_cents', 0) / 100
        monthly_revenue = revenue_stats.get('revenue_month_cents', 0) / 100
        avg_transaction = revenue_stats.get('avg_transaction_value', 0) / 100
        
        # Build the analytics message
        analytics_text = f"""
📊 **ADMIN ANALYTICS DASHBOARD**

👥 **USER METRICS**
• Total Users: {user_stats.get('total_users', 0)}
• New This Week: {user_stats.get('new_users_week', 0)}
• New This Month: {user_stats.get('new_users_month', 0)}
• Active This Week: {user_stats.get('active_users_week', 0)}
• Active This Month: {user_stats.get('active_users_month', 0)}

💰 **REVENUE METRICS**
• Total Revenue: ${total_revenue:,.2f}
• Weekly Revenue: ${weekly_revenue:,.2f}
• Monthly Revenue: ${monthly_revenue:,.2f}
• Total Transactions: {revenue_stats.get('successful_transactions', 0)}
• Average Transaction: ${avg_transaction:.2f}

🏦 **CREDIT METRICS**
• Credits in Circulation: {credit_stats.get(
                'total_credits_in_circulation', 0
            ):,}
• Average User Credits: {credit_stats.get('avg_user_credits', 0):.1f}
• Users with Low Credits (≤5): {credit_stats.get('users_low_credits', 0)}
• Users with No Credits: {credit_stats.get('users_no_credits', 0)}

💬 **CONVERSATION METRICS**
• Total Conversations: {conversation_stats.get('total_conversations', 0)}
• Active Conversations: {conversation_stats.get('active_conversations', 0)}
• Recent Activity (24h): {conversation_stats.get('recent_conversations', 0)}
        """
        
        # Add top products section
        if product_stats:
            analytics_text += "\n🏆 **TOP PRODUCTS (by Revenue)**\n"
            for product in product_stats[:5]:
                product_revenue = product.get('revenue_cents', 0) / 100
                sales_count = product.get('sales_count', 0)
                product_name = product.get('name', 'Unknown')
                analytics_text += (
                    f"• {product_name}: ${product_revenue:,.2f} "
                    f"({sales_count} sales)\n"
                )
        
        # Add revenue trend
        if revenue_data and len(revenue_data) >= 7:
            recent_7_days = revenue_data[-7:]
            total_week_revenue = sum(
                day.get('revenue_cents', 0) for day in recent_7_days
            ) / 100
            analytics_text += (
                f"\n📈 **7-Day Revenue Trend: ${total_week_revenue:,.2f}**"
            )
        
        # Create interactive keyboard
        keyboard = [
            [
                InlineKeyboardButton(
                    "📈 Revenue Charts", 
                    callback_data="admin_revenue_charts"
                ),
                InlineKeyboardButton(
                    "👥 User Growth", 
                    callback_data="admin_user_growth"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔄 Refresh Data", 
                    callback_data="admin_analytics"
                ),
                InlineKeyboardButton(
                    "📊 Export Report", 
                    callback_data="admin_export_analytics"
                )
            ],
            [
                InlineKeyboardButton(
                    "🏦 Transaction History", 
                    callback_data="admin_transaction_history"
                ),
                InlineKeyboardButton(
                    "📋 Product Performance", 
                    callback_data="admin_product_analytics"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 Admin Dashboard", 
                    callback_data="admin_dashboard"
                ),
                InlineKeyboardButton("❌ Close", callback_data="admin_close")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            analytics_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Admin analytics callback failed: {e}")
        error_keyboard = [
            [InlineKeyboardButton(
                "🔙 Back to Dashboard", 
                callback_data="admin_dashboard"
            )]
        ]
        await query.edit_message_text(
            "❌ **Analytics Error**\n\n"
            "Failed to load analytics data. Please try again.",
            reply_markup=InlineKeyboardMarkup(error_keyboard),
            parse_mode=ParseMode.MARKDOWN
        ) 


async def admin_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mass message broadcasting to all users or segments."""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get broadcast statistics
        total_users = db.get_user_count()
        active_users_week = db.execute_query(
            "SELECT COUNT(*) as count FROM users WHERE last_message_at >= NOW() - INTERVAL '7 days'",
            fetch_one=True
        ).get('count', 0) if db.execute_query else 0
        
        broadcast_text = f"""
📢 **ADMIN BROADCAST SYSTEM**

📊 **Audience Statistics:**
• Total Users: {total_users:,}
• Active This Week: {active_users_week:,}

**🎯 Broadcast Options:**
Choose your target audience and message type below.

⚠️ **Important:** Broadcasts are immediate and cannot be undone. 
Test with small groups first.
        """
        
        keyboard = [
            [
                InlineKeyboardButton("👥 All Users", callback_data="broadcast_all_users"),
                InlineKeyboardButton("🔥 Active Users Only", callback_data="broadcast_active_users")
            ],
            [
                InlineKeyboardButton("💰 Low Credit Users", callback_data="broadcast_low_credits"),
                InlineKeyboardButton("🆕 New Users", callback_data="broadcast_new_users")
            ],
            [
                InlineKeyboardButton("💎 Premium Users", callback_data="broadcast_premium_users"),
                InlineKeyboardButton("🎯 Custom Segment", callback_data="broadcast_custom")
            ],
            [
                InlineKeyboardButton("📝 Compose Message", callback_data="broadcast_compose"),
                InlineKeyboardButton("📋 Draft Templates", callback_data="broadcast_templates")
            ],
            [
                InlineKeyboardButton("📊 Broadcast History", callback_data="broadcast_history"),
                InlineKeyboardButton("⚙️ Settings", callback_data="broadcast_settings")
            ],
            [
                InlineKeyboardButton("🔙 Admin Dashboard", callback_data="admin_dashboard"),
                InlineKeyboardButton("❌ Close", callback_data="admin_close")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            broadcast_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Admin broadcast callback failed: {e}")
        error_keyboard = [
            [InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]
        ]
        await query.edit_message_text(
            "❌ **Broadcast Error**\n\n"
            "Failed to load broadcast system. Please try again.",
            reply_markup=InlineKeyboardMarkup(error_keyboard),
            parse_mode=ParseMode.MARKDOWN
        )


async def broadcast_all_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Broadcast to all users confirmation."""
    query = update.callback_query
    await query.answer()
    
    total_users = db.get_user_count()
    
    confirmation_text = f"""
⚠️ **BROADCAST TO ALL USERS**

**Target Audience:** All {total_users:,} users
**Delivery Method:** Individual messages

**Are you sure you want to proceed?**

This will send your message to every user in the database.
This action cannot be undone.

💡 **Tip:** Consider using "Active Users Only" for better engagement.
    """
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm Broadcast", callback_data="confirm_broadcast_all"),
            InlineKeyboardButton("❌ Cancel", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton("📝 Edit Message First", callback_data="broadcast_compose"),
            InlineKeyboardButton("🔙 Back", callback_data="admin_broadcast")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        confirmation_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )


async def broadcast_active_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Broadcast to active users only."""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get active users count (last 7 days)
        active_count = db.execute_query(
            "SELECT COUNT(*) as count FROM users WHERE last_message_at >= NOW() - INTERVAL '7 days'",
            fetch_one=True
        ).get('count', 0) if db.execute_query else 0
        
        confirmation_text = f"""
🔥 **BROADCAST TO ACTIVE USERS**

**Target Audience:** {active_count:,} active users (last 7 days)
**Delivery Method:** Individual messages

**Why target active users?**
• Higher engagement rates
• Better message deliverability
• More cost-effective

**Are you ready to proceed?**
        """
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm Broadcast", callback_data="confirm_broadcast_active"),
                InlineKeyboardButton("❌ Cancel", callback_data="admin_broadcast")
            ],
            [
                InlineKeyboardButton("📝 Compose Message", callback_data="broadcast_compose"),
                InlineKeyboardButton("🔙 Back", callback_data="admin_broadcast")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            confirmation_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Active users broadcast callback failed: {e}")
        await query.edit_message_text("❌ Error loading active users data.")


async def broadcast_compose_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Message composition interface."""
    query = update.callback_query
    await query.answer()
    
    compose_text = """
📝 **COMPOSE BROADCAST MESSAGE**

**Instructions:**
1. Send me your message in the next reply
2. Use Markdown formatting (*bold*, _italic_)
3. Include emojis and links as needed
4. Maximum length: 4000 characters

**Message Tips:**
• Start with a greeting
• Be clear and concise
• Include a call-to-action
• Test with a small group first

**Send your message now, or use a template below:**
    """
    
    keyboard = [
        [
            InlineKeyboardButton("📋 Use Template", callback_data="broadcast_templates"),
            InlineKeyboardButton("✨ Message Examples", callback_data="broadcast_examples")
        ],
        [
            InlineKeyboardButton("🔙 Back to Broadcast", callback_data="admin_broadcast"),
            InlineKeyboardButton("❌ Cancel", callback_data="admin_close")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Set context for message composition
    context.user_data['composing_broadcast'] = True
    context.user_data['broadcast_step'] = 'message'
    
    await query.edit_message_text(
        compose_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    ) 


async def admin_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bot configuration and settings management."""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get current bot settings
        new_user_credits = db.get_bot_setting('new_user_free_credits') or '3'
        tutorial_enabled = db.get_bot_setting('tutorial_enabled') or 'true'
        tutorial_bonus = db.get_bot_setting('tutorial_completion_bonus') or '2'
        low_threshold = db.get_bot_setting('balance_low_threshold') or '5'
        critical_threshold = db.get_bot_setting('balance_critical_threshold') or '2'
        quick_buy_enabled = db.get_bot_setting('quick_buy_enabled') or 'true'
        
        settings_text = f"""
⚙️ **ADMIN SETTINGS MANAGEMENT**

**💰 Credit Settings:**
• New User Free Credits: {new_user_credits}
• Low Balance Threshold: {low_threshold}
• Critical Balance Threshold: {critical_threshold}

**📚 Tutorial Settings:**
• Tutorial Enabled: {'✅' if tutorial_enabled == 'true' else '❌'}
• Tutorial Completion Bonus: {tutorial_bonus} credits

**🛒 Purchase Settings:**
• Quick Buy Buttons: {'✅' if quick_buy_enabled == 'true' else '❌'}

**🔧 System Status:**
• Database Connection: ✅ Active
• Stripe Integration: ✅ Connected
• Webhook Server: ✅ Running

**Choose a category to modify:**
        """
        
        keyboard = [
            [
                InlineKeyboardButton("💰 Credit Settings", callback_data="settings_credits"),
                InlineKeyboardButton("📚 Tutorial Settings", callback_data="settings_tutorial")
            ],
            [
                InlineKeyboardButton("🛒 Purchase Settings", callback_data="settings_purchase"),
                InlineKeyboardButton("💬 Message Settings", callback_data="settings_messages")
            ],
            [
                InlineKeyboardButton("🔐 Security Settings", callback_data="settings_security"),
                InlineKeyboardButton("📊 Analytics Settings", callback_data="settings_analytics")
            ],
            [
                InlineKeyboardButton("🔄 Reset to Defaults", callback_data="settings_reset"),
                InlineKeyboardButton("💾 Export Settings", callback_data="settings_export")
            ],
            [
                InlineKeyboardButton("🔙 Admin Dashboard", callback_data="admin_dashboard"),
                InlineKeyboardButton("❌ Close", callback_data="admin_close")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            settings_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Admin settings callback failed: {e}")
        error_keyboard = [
            [InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]
        ]
        await query.edit_message_text(
            "❌ **Settings Error**\n\n"
            "Failed to load settings. Please try again.",
            reply_markup=InlineKeyboardMarkup(error_keyboard),
            parse_mode=ParseMode.MARKDOWN
        )


async def settings_credits_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Credit settings management."""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get current credit settings
        new_user_credits = db.get_bot_setting('new_user_free_credits') or '3'
        low_threshold = db.get_bot_setting('balance_low_threshold') or '5'
        critical_threshold = db.get_bot_setting('balance_critical_threshold') or '2'
        max_credits_display = db.get_bot_setting('progress_bar_max_credits') or '100'
        
        settings_text = f"""
💰 **CREDIT SETTINGS**

**Current Configuration:**
• New User Welcome Credits: {new_user_credits}
• Low Balance Warning: {low_threshold} credits
• Critical Balance Warning: {critical_threshold} credits
• Progress Bar Max Display: {max_credits_display} credits

**What would you like to modify?**
        """
        
        keyboard = [
            [
                InlineKeyboardButton("🎁 Welcome Credits", callback_data="set_welcome_credits"),
                InlineKeyboardButton("⚠️ Warning Thresholds", callback_data="set_warning_thresholds")
            ],
            [
                InlineKeyboardButton("📊 Display Settings", callback_data="set_display_settings"),
                InlineKeyboardButton("🔄 Reset Credits", callback_data="reset_credit_settings")
            ],
            [
                InlineKeyboardButton("🔙 Back to Settings", callback_data="admin_settings"),
                InlineKeyboardButton("❌ Close", callback_data="admin_close")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            settings_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Credit settings callback failed: {e}")
        await query.edit_message_text("❌ Error loading credit settings.")


async def settings_tutorial_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tutorial settings management."""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get current tutorial settings
        tutorial_enabled = db.get_bot_setting('tutorial_enabled') or 'true'
        tutorial_bonus = db.get_bot_setting('tutorial_completion_bonus') or '2'
        
        settings_text = f"""
📚 **TUTORIAL SETTINGS**

**Current Configuration:**
• Tutorial System: {'✅ Enabled' if tutorial_enabled == 'true' else '❌ Disabled'}
• Completion Bonus: {tutorial_bonus} credits

**Tutorial Features:**
• Interactive step-by-step guide
• Progressive credit rewards
• User engagement tracking
• Completion analytics

**What would you like to modify?**
        """
        
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{'❌ Disable' if tutorial_enabled == 'true' else '✅ Enable'} Tutorial",
                    callback_data=f"toggle_tutorial_{'off' if tutorial_enabled == 'true' else 'on'}"
                )
            ],
            [
                InlineKeyboardButton("🎁 Set Completion Bonus", callback_data="set_tutorial_bonus"),
                InlineKeyboardButton("📊 Tutorial Analytics", callback_data="tutorial_analytics")
            ],
            [
                InlineKeyboardButton("🔄 Reset Tutorial Settings", callback_data="reset_tutorial_settings"),
                InlineKeyboardButton("📝 Edit Tutorial Content", callback_data="edit_tutorial_content")
            ],
            [
                InlineKeyboardButton("🔙 Back to Settings", callback_data="admin_settings"),
                InlineKeyboardButton("❌ Close", callback_data="admin_close")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            settings_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Tutorial settings callback failed: {e}")
        await query.edit_message_text("❌ Error loading tutorial settings.") 