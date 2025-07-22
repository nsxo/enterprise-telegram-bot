"""
Enterprise Telegram Bot - Message Router

This module handles message routing and processing, including user message
handling, admin message forwarding, and conversation management.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from src import database as db
from src import bot_utils
from src.config import ADMIN_GROUP_ID

logger = logging.getLogger(__name__)


async def master_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Master message handler that routes messages based on user type and context.
    
    This function serves as the central dispatcher for all incoming messages,
    routing them to appropriate handlers based on user permissions and message type.
    """
    user = update.effective_user
    message = update.message
    
    if not user or not message:
        return
    
    logger.info(f"Message from user {user.id} ({user.username}): {message.text[:50] if message.text else 'Non-text message'}")
    
    try:
        # Check if user is admin
        if bot_utils.is_admin_user(user.id):
            await handle_admin_message(update, context)
        else:
            await handle_user_message(update, context)
            
    except Exception as e:
        logger.error(f"Master message handler failed for user {user.id}: {e}")
        try:
            await message.reply_text(
                "❌ Sorry, there was an error processing your message. Please try again or use /help for assistance."
            )
        except Exception as reply_error:
            logger.error(f"Failed to send error reply: {reply_error}")


async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle messages from regular users with credit management and admin forwarding.
    
    This function processes user messages, manages credit deduction, forwards messages
    to admin group, and handles conversation state management.
    """
    user = update.effective_user
    message = update.message
    
    # Get or create user in database
    user_data = db.get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # Check if user has sufficient credits
    credits = user_data.get('message_credits', 0)
    
    if credits < 1:
        # User has insufficient credits
        low_credits_text = """
❌ **Insufficient Credits**

You need at least 1 credit to send a message.

**💡 Quick Solutions:**
• /buy10 - Get 10 credits instantly ($2.99)
• /buy25 - Popular choice ($6.99)
• /buy50 - Best value ($12.99)

**Or browse all options with /buy**
        """
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
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
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await message.reply_text(
            low_credits_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Deduct 1 credit for the message
    try:
        db.update_user_credits(user.id, -1)
        logger.info(f"Deducted 1 credit from user {user.id}. Remaining: {credits - 1}")
        
        # Update user's last message timestamp
        db.update_user_last_message(user.id)
        
    except Exception as e:
        logger.error(f"Failed to deduct credits for user {user.id}: {e}")
        await message.reply_text("❌ Error processing your message. Credits not deducted.")
        return
    
    # Forward message to admin group with conversation management
    try:
        # Get or create topic for user
        topic_id = await bot_utils.get_or_create_user_topic(context, user)
        
        # Update last message timestamp
        db.update_conversation_last_message(user.id, ADMIN_GROUP_ID)
        
        # Forward the message to the admin group topic
        forwarded_message = await context.bot.forward_message(
            chat_id=ADMIN_GROUP_ID,
            from_chat_id=message.chat_id,
            message_id=message.message_id,
            message_thread_id=topic_id
        )
        
        # Store the forwarded message reference
        db.store_message_reference(
            user_message_id=message.message_id,
            admin_message_id=forwarded_message.message_id,
            user_id=user.id,
            topic_id=topic_id
        )
        
        logger.info(f"✅ Forwarded message from user {user.id} to admin topic {topic_id}")
        
        # Get updated credit count after deduction
        updated_user = db.get_user(user.id)
        remaining_credits = updated_user.get('message_credits', 0) if updated_user else credits - 1
        
        if remaining_credits <= 1:
            # Warning for low credits
            confirmation_text = f"""
✅ **Message sent successfully!**

⚠️ **Credit Warning:** You have {remaining_credits} credit{'s' if remaining_credits != 1 else ''} remaining.

💡 Consider topping up to continue the conversation:
            """
            
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
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
            reply_markup = InlineKeyboardMarkup(keyboard)
        elif remaining_credits <= 5:
            # Medium warning for moderately low credits
            confirmation_text = f"""
✅ **Message sent successfully!**

💰 **Credits remaining:** {remaining_credits}
🤖 **I'm processing your message and will respond shortly!**

💡 **Tip:** Consider buying more credits soon to avoid interruptions.
            """
            
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = [
                [
                    InlineKeyboardButton("🛒 Buy Credits", callback_data="show_products"),
                    InlineKeyboardButton("💰 Check Balance", callback_data="show_balance")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
        else:
            # Standard confirmation
            confirmation_text = f"""
✅ **Message sent successfully!**

💰 **Credits remaining:** {remaining_credits}
🤖 **I'm processing your message and will respond shortly!**

💡 **Tip:** The more specific your question, the better I can help you.
            """
            reply_markup = None
        
        await message.reply_text(
            confirmation_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Failed to forward message to admin group: {e}")
        
        # Refund the credit since message forwarding failed
        try:
            db.update_user_credits(user.id, 1)
            logger.info(f"Refunded 1 credit to user {user.id} due to forwarding failure")
        except Exception as refund_error:
            logger.error(f"Failed to refund credit to user {user.id}: {refund_error}")
        
        await message.reply_text(
            "❌ **Message delivery failed**\n\n"
            "Your credit has been refunded. Please try again in a moment.\n\n"
            "If the problem persists, use /status to check system health."
        )


async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle messages from admin users with intelligent routing and reply management.
    
    This function processes admin messages, determines the target user based on context,
    and routes replies appropriately using the topic system.
    """
    message = update.message
    admin_user = update.effective_user
    
    # Check if this is a reply to a user message in a topic
    if message.reply_to_message and message.message_thread_id:
        # This is a reply in a topic - route to specific user
        topic_id = message.message_thread_id
        
        try:
            # Find the user associated with this topic
            topic_info = db.get_topic_info(ADMIN_GROUP_ID, topic_id)
            
            if not topic_info:
                await message.reply_text(
                    "❌ **Topic not found**\n\n"
                    "This topic might have been deleted or is not properly configured."
                )
                return
            
            target_user_id = topic_info['user_id']
            
            # Forward admin reply to the user
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=message.text,
                    parse_mode=ParseMode.MARKDOWN if message.entities else None
                )
                
                # Add confirmation reaction or reply
                await message.reply_text(
                    f"✅ **Reply sent to user {target_user_id}**",
                    message_thread_id=topic_id
                )
                
                logger.info(f"✅ Admin reply forwarded from topic {topic_id} to user {target_user_id}")
                
            except Exception as e:
                logger.error(f"Failed to forward admin reply to user {target_user_id}: {e}")
                await message.reply_text(
                    f"❌ **Failed to send reply to user {target_user_id}**\n\n"
                    f"Error: {str(e)[:100]}"
                )
                
        except Exception as e:
            logger.error(f"Failed to process admin reply in topic {topic_id}: {e}")
            await message.reply_text(
                "❌ **Reply routing failed**\n\n"
                "Unable to determine target user for this reply."
            )
    
    elif message.message_thread_id:
        # Message in topic but not a reply - show topic info
        topic_id = message.message_thread_id
        
        try:
            topic_info = db.get_topic_info(ADMIN_GROUP_ID, topic_id)
            
            if topic_info:
                user_id = topic_info['user_id']
                user_data = db.get_user_dashboard_data(user_id)
                
                if user_data:
                    info_text = f"""
🔍 **Topic Information**

**User:** {user_data['first_name']} {user_data.get('last_name', '')}
**Username:** @{user_data.get('username', 'N/A')}
**User ID:** {user_id}
**Credits:** {user_data.get('message_credits', 0)}
**Last Active:** {topic_info.get('last_message_at', 'Unknown')}

**💡 Tip:** Reply to any message in this topic to respond to the user.
                    """
                    
                    await message.reply_text(
                        info_text,
                        message_thread_id=topic_id,
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await message.reply_text(
                        f"ℹ️ **Topic for User ID:** {user_id}\n\n"
                        f"User data not available.",
                        message_thread_id=topic_id
                    )
            else:
                await message.reply_text(
                    "❌ **Unknown Topic**\n\n"
                    "This topic is not associated with any user."
                )
                
        except Exception as e:
            logger.error(f"Failed to get topic info for {topic_id}: {e}")
            
    else:
        # General admin message - provide help
        admin_help_text = """
🔧 **Admin Message Handler**

**How to use:**
• **Reply to user messages** in topics to respond directly
• **Use admin commands** like /admin for the dashboard
• **Topic messages** show user info and context

**Available Commands:**
• `/admin` - Main admin dashboard
• `/users` - User management
• `/analytics` - System analytics
• `/products` - Product management
• `/broadcast` - Send announcements

**Need help?** Reply to user messages in their topics to communicate directly.
        """
        
        await message.reply_text(
            admin_help_text,
            parse_mode=ParseMode.MARKDOWN
        )


async def send_admin_notification(context: ContextTypes.DEFAULT_TYPE, message: str, topic_id: int = None) -> None:
    """
    Send notification to admin group.
    
    Args:
        context: Telegram context
        message: Notification message
        topic_id: Optional topic ID for threaded notifications
    """
    try:
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=message,
            message_thread_id=topic_id,
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info(f"✅ Admin notification sent to topic {topic_id}")
        
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")


async def handle_conversation_cleanup(user_id: int, reason: str = "User request") -> None:
    """
    Handle conversation cleanup and archiving.
    
    Args:
        user_id: User ID to clean up conversation for
        reason: Reason for cleanup
    """
    try:
        # Mark conversation as archived
        db.archive_conversation(user_id, ADMIN_GROUP_ID, reason=reason)
        
        logger.info(f"✅ Conversation archived for user {user_id}: {reason}")
        
    except Exception as e:
        logger.error(f"Failed to cleanup conversation for user {user_id}: {e}") 