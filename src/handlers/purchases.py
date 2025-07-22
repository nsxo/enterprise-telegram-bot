"""
Enterprise Telegram Bot - Purchase & Billing Handlers

This module contains all purchase, billing, and payment-related functionality
including product displays, Stripe integration, and transaction management.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from src import database as db
from src import stripe_utils
from src import bot_utils

logger = logging.getLogger(__name__)


async def billing_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Enhanced /billing command with Stripe customer portal access.
    """
    user = update.effective_user
    logger.info(f"Billing command from user {user.id}")
    
    try:
        # Get user data
        user_data = db.get_user_dashboard_data(user.id)
        if not user_data:
            await update.message.reply_text("❌ User not found. Please use /start first.")
            return
        
        # Get billing information
        total_spent = user_data.get('total_spent_cents', 0) / 100
        total_purchases = user_data.get('total_purchases', 0)
        tier = user_data.get('tier_name', 'standard').title()
        
        billing_text = f"""
💳 **Billing & Account Management**

**📊 Account Summary:**
• Total Spent: ${total_spent:.2f}
• Total Purchases: {total_purchases}
• Account Tier: {tier}

**🔧 Billing Tools:**
• Manage payment methods
• View transaction history
• Download invoices
• Update billing information

**💡 Account Benefits:**
• Automatic receipt emails
• Purchase protection
• Priority customer support
• Flexible payment options
        """
        
        keyboard = [
            [
                InlineKeyboardButton("💳 Customer Portal", callback_data="billing_portal"),
                InlineKeyboardButton("📊 Purchase History", callback_data="purchase_history")
            ],
            [
                InlineKeyboardButton("🛒 Buy More Credits", callback_data="show_products"),
                InlineKeyboardButton("💰 Check Balance", callback_data="show_balance")
            ],
            [
                InlineKeyboardButton("📧 Email Report", callback_data="email_report"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="user_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            billing_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Billing command failed for user {user.id}: {e}")
        await update.message.reply_text("❌ Error accessing billing. Please try again.")


async def show_products_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Enhanced product showcase with personalized recommendations.
    """
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer()
        
        # Get user data for personalized recommendations
        user_data = db.get_user_dashboard_data(user.id)
        credits = user_data.get('message_credits', 0) if user_data else 0
        
        # Get available products
        products = db.get_all_products()
        if not products:
            await query.edit_message_text("❌ No products available at the moment.")
            return
        
        # Create personalized intro based on credit level
        if credits < 2:
            intro = "🚨 **Running Low on Credits!**\n\nDon't miss out on our conversation. Choose a package below:"
        elif credits < 10:
            intro = "💡 **Top Up Your Credits**\n\nGreat timing to refill! Here are our popular options:"
        else:
            intro = "🛒 **Credit Store**\n\nStock up for uninterrupted conversations:"
        
        # Build product showcase with enhanced presentation
        product_text = f"{intro}\n\n"
        
        # Group products by type for better presentation
        credit_products = [p for p in products if p.get('type') == 'credits' or not p.get('type')]
        unlimited_products = [p for p in products if p.get('type') == 'unlimited']
        
        if credit_products:
            product_text += "💰 **Credit Packages:**\n"
            for product in credit_products[:4]:  # Show top 4 credit products
                name = product['name']
                credits_amount = product['credits']
                price = product['price_cents'] / 100
                
                # Add value proposition
                if credits_amount == 10:
                    value = "⚡ Quick Start"
                elif credits_amount == 25:
                    value = "🌟 Popular Choice"
                elif credits_amount == 50:
                    value = "💎 Best Value"
                elif credits_amount >= 100:
                    value = "🏆 Premium"
                else:
                    value = "💰 Basic"
                
                product_text += f"• **{credits_amount} Credits** - ${price:.2f} {value}\n"
                product_text += f"  └ ${price/credits_amount:.3f} per credit\n"
        
        if unlimited_products:
            product_text += "\n🎯 **Unlimited Plans:**\n"
            for product in unlimited_products[:2]:  # Show top 2 unlimited plans
                name = product['name']
                price = product['price_cents'] / 100
                duration = "24 hours"  # Assuming daily plans
                
                product_text += f"• **{name}** - ${price:.2f}\n"
                product_text += f"  └ Unlimited messages for {duration}\n"
        
        # Create keyboard with product options
        keyboard = []
        
        # Add credit package buttons
        for product in credit_products[:3]:  # Top 3 credit packages
            credits_amount = product['credits']
            price = product['price_cents'] / 100
            keyboard.append([
                InlineKeyboardButton(
                    f"💳 Buy {credits_amount} Credits (${price:.2f})",
                    callback_data=f"purchase_product_{product['stripe_price_id']}"
                )
            ])
        
        # Add unlimited plan buttons if available
        for product in unlimited_products[:1]:  # Top unlimited plan
            price = product['price_cents'] / 100
            keyboard.append([
                InlineKeyboardButton(
                    f"🎯 {product['name']} (${price:.2f})",
                    callback_data=f"purchase_product_{product['stripe_price_id']}"
                )
            ])
        
        # Add navigation buttons
        keyboard.extend([
            [
                InlineKeyboardButton("💳 Billing Portal", callback_data="billing_portal"),
                InlineKeyboardButton("📊 My Analytics", callback_data="show_analytics")
            ],
            [
                InlineKeyboardButton("💰 Check Balance", callback_data="show_balance"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="user_menu")
            ]
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            product_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Show products callback failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Error loading products. Please try again.")


async def product_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle product type selection callback."""
    query = update.callback_query
    
    try:
        await query.answer()
        
        # Extract product type from callback data
        product_type = query.data.replace("product_type_", "")
        
        # Get products of specific type
        products = db.get_products_by_type(product_type)
        
        if not products:
            await query.edit_message_text(f"❌ No {product_type} products available.")
            return
        
        if product_type == "credits":
            type_text = "💰 **Credit Packages**\n\nChoose your credit package:"
        elif product_type == "unlimited":
            type_text = "🎯 **Unlimited Plans**\n\nUnlimited messaging for set periods:"
        else:
            type_text = f"🛒 **{product_type.title()} Products**\n\nAvailable options:"
        
        keyboard = []
        for product in products:
            price = product['price_cents'] / 100
            if product_type == "credits":
                button_text = f"💳 {product['credits']} Credits (${price:.2f})"
            else:
                button_text = f"💳 {product['name']} (${price:.2f})"
            
            keyboard.append([
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"purchase_product_{product['stripe_price_id']}"
                )
            ])
        
        # Add back button
        keyboard.append([
            InlineKeyboardButton("⬅️ Back to Products", callback_data="show_products")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            type_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Product type callback failed: {e}")
        await query.edit_message_text("❌ Error loading product type.")


async def billing_portal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle billing portal access callback.
    """
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer("🔄 Creating secure billing portal...")
        
        # Create Stripe customer portal session
        try:
            portal_url = stripe_utils.create_customer_portal_session(
                customer_email=user.username or f"user_{user.id}@telegram.bot"
            )
            
            portal_text = """
💳 **Secure Billing Portal**

Click the link below to access your secure billing portal where you can:

• 📊 View all transactions
• 💳 Update payment methods  
• 📧 Manage email preferences
• 📄 Download invoices
• ❌ Cancel subscriptions

**🔒 Security Note:**
This is a secure Stripe portal. Your payment information is protected by bank-level encryption.
            """
            
            keyboard = [
                [
                    InlineKeyboardButton("💳 Open Billing Portal", url=portal_url)
                ],
                [
                    InlineKeyboardButton("⬅️ Back to Billing", callback_data="show_products"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="user_menu")
                ]
            ]
            
        except stripe_utils.StripeError as e:
            logger.error(f"Stripe portal creation failed: {e}")
            portal_text = """
❌ **Portal Temporarily Unavailable**

We're unable to create your billing portal right now. This might be because:

• No previous purchases found
• Temporary service issue  
• Payment system maintenance

**Alternative Options:**
• Contact support for billing assistance
• Try again in a few minutes
• Use direct purchase options below
            """
            
            keyboard = [
                [
                    InlineKeyboardButton("🛒 Browse Products", callback_data="show_products"),
                    InlineKeyboardButton("💰 Check Balance", callback_data="show_balance")
                ],
                [
                    InlineKeyboardButton("🏠 Main Menu", callback_data="user_menu")
                ]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            portal_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Billing portal callback failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Error accessing billing portal. Please try again.")


async def purchase_product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle product purchase callback with Stripe Checkout.
    """
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer("🔄 Preparing checkout...")
        
        # Extract Stripe price ID from callback data
        stripe_price_id = query.data.replace("purchase_product_", "")
        
        # Get product details
        product = db.get_product_by_stripe_price_id(stripe_price_id)
        if not product:
            await query.edit_message_text("❌ Product not found.")
            return
        
        # Create Stripe checkout session
        try:
            checkout_data = stripe_utils.create_checkout_session(
                price_id=stripe_price_id,
                customer_email=user.username or f"user_{user.id}@telegram.bot",
                metadata={
                    'telegram_user_id': str(user.id),
                    'telegram_username': user.username or '',
                    'product_credits': str(product.get('credits', 0))
                }
            )
            
            checkout_url = checkout_data['url']
            session_id = checkout_data['id']
            
            # Store pending purchase
            db.create_pending_purchase(
                user_id=user.id,
                stripe_session_id=session_id,
                stripe_price_id=stripe_price_id,
                amount_cents=product['price_cents'],
                credits=product.get('credits', 0)
            )
            
            credits_text = f" • **Credits:** {product['credits']}" if product.get('credits') else ""
            price = product['price_cents'] / 100
            
            checkout_text = f"""
🛒 **Secure Checkout Ready**

**Product:** {product['name']}
**Price:** ${price:.2f}{credits_text}

Click below to complete your purchase using our secure Stripe checkout:

**🔒 Payment Security:**
• Bank-level encryption
• PCI DSS compliant
• No card details stored
• Instant delivery

Your credits will be added automatically after payment!
            """
            
            keyboard = [
                [
                    InlineKeyboardButton("💳 Complete Purchase", url=checkout_url)
                ],
                [
                    InlineKeyboardButton("⬅️ Back to Products", callback_data="show_products"),
                    InlineKeyboardButton("❌ Cancel", callback_data="user_menu")
                ]
            ]
            
        except stripe_utils.StripeError as e:
            logger.error(f"Stripe checkout creation failed: {e}")
            checkout_text = """
❌ **Checkout Temporarily Unavailable**

We're unable to process purchases right now due to a temporary issue.

**What you can do:**
• Try again in a few minutes
• Contact support if the issue persists
• Check our status page for updates

We apologize for the inconvenience!
            """
            
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Try Again", callback_data=f"purchase_product_{stripe_price_id}"),
                    InlineKeyboardButton("⬅️ Back", callback_data="show_products")
                ]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            checkout_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Purchase product callback failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Error preparing purchase. Please try again.")


# Quick Buy Callbacks
async def quick_buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle quick buy callbacks (quick_buy_10, quick_buy_25, etc.).
    """
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer("🔄 Setting up quick purchase...")
        
        # Extract amount from callback data
        amount = int(query.data.replace("quick_buy_", ""))
        
        # Find product with matching credit amount
        products = db.get_all_products()
        matching_product = None
        
        for product in products:
            if product.get('credits') == amount:
                matching_product = product
                break
        
        if not matching_product:
            await query.edit_message_text(
                f"❌ {amount}-credit package not available. Check our full product catalog."
            )
            return
        
        price = matching_product['price_cents'] / 100
        
        quick_buy_text = f"""
⚡ **Quick Buy: {amount} Credits**

**💰 Price:** ${price:.2f}
**⚡ Credits:** {amount}
**💡 Per Credit:** ${price/amount:.3f}

**✨ What's Included:**
• Instant credit delivery
• No subscription required
• Same high-quality responses
• 24/7 availability

Ready to purchase?
        """
        
        keyboard = [
            [
                InlineKeyboardButton(
                    f"💳 Buy Now (${price:.2f})",
                    callback_data=f"purchase_product_{matching_product['stripe_price_id']}"
                )
            ],
            [
                InlineKeyboardButton("🛒 View All Options", callback_data="show_products"),
                InlineKeyboardButton("💰 Check Balance", callback_data="show_balance")
            ],
            [
                InlineKeyboardButton("❌ Cancel", callback_data="user_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            quick_buy_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Quick buy callback failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Error processing quick buy. Please try again.")


# Purchase History Callbacks
async def refresh_history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle refresh purchase history callback."""
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer("🔄 Refreshing purchase history...")
        
        # Get updated purchase history
        purchases = db.get_user_purchase_history(user.id, limit=10)
        
        if not purchases:
            history_text = """
📋 **Purchase History** *(Refreshed)*

No purchases found yet.

🎁 **Get Started:**
• New users get 3 free credits
• First purchase often includes bonus credits
• Regular promotions and discounts available

Ready to make your first purchase?
            """
            
            keyboard = [
                [
                    InlineKeyboardButton("🛒 Browse Products", callback_data="show_products"),
                    InlineKeyboardButton("💰 Quick Buy 10", callback_data="quick_buy_10")
                ],
                [
                    InlineKeyboardButton("🏠 Main Menu", callback_data="user_menu")
                ]
            ]
        else:
            # Calculate totals
            total_spent = sum(p.get('amount_cents', 0) for p in purchases) / 100
            total_credits = sum(p.get('credits_purchased', 0) for p in purchases)
            
            history_text = f"""
📋 **Purchase History** *(Refreshed)*

**📊 Summary:**
• Total Spent: ${total_spent:.2f}
• Total Credits: {total_credits:,}
• Total Orders: {len(purchases)}

**📝 Recent Purchases:**
            """
            
            for purchase in purchases[:5]:  # Show last 5
                date = purchase.get('created_at', 'Unknown')
                amount = purchase.get('amount_cents', 0) / 100
                credits = purchase.get('credits_purchased', 0)
                status = purchase.get('status', 'unknown')
                
                status_emoji = {
                    'completed': '✅',
                    'pending': '⏳',
                    'failed': '❌',
                    'refunded': '🔄'
                }.get(status, '❓')
                
                history_text += f"\n{status_emoji} **${amount:.2f}** • {credits} credits"
                if date != 'Unknown':
                    history_text += f" • {date[:10]}"
            
            keyboard = [
                [
                    InlineKeyboardButton("📊 Detailed History", callback_data="detailed_history"),
                    InlineKeyboardButton("📧 Email Report", callback_data="email_report")
                ],
                [
                    InlineKeyboardButton("🛒 Buy More", callback_data="show_products"),
                    InlineKeyboardButton("💰 Check Balance", callback_data="show_balance")
                ],
                [
                    InlineKeyboardButton("🏠 Main Menu", callback_data="user_menu")
                ]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            history_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Refresh history callback failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Error refreshing purchase history.")


async def detailed_history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle detailed purchase history callback."""
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer()
        
        # Get comprehensive purchase history
        purchases = db.get_user_purchase_history(user.id, limit=20)
        
        if not purchases:
            await query.edit_message_text("📋 No purchase history available.")
            return
        
        # Create detailed history text
        history_text = "📋 **Detailed Purchase History**\n\n"
        
        for i, purchase in enumerate(purchases[:10], 1):  # Show top 10
            date = purchase.get('created_at', 'Unknown')
            amount = purchase.get('amount_cents', 0) / 100
            credits = purchase.get('credits_purchased', 0)
            status = purchase.get('status', 'unknown')
            transaction_id = purchase.get('stripe_payment_intent_id', 'N/A')
            
            status_emoji = {
                'completed': '✅',
                'pending': '⏳',
                'failed': '❌',
                'refunded': '🔄'
            }.get(status, '❓')
            
            history_text += f"**{i}.** {status_emoji} ${amount:.2f} • {credits} credits\n"
            if date != 'Unknown':
                history_text += f"   📅 {date[:10]}\n"
            if transaction_id != 'N/A':
                history_text += f"   🔗 ID: {transaction_id[:8]}...\n"
            history_text += "\n"
        
        keyboard = [
            [
                InlineKeyboardButton("📧 Email Full Report", callback_data="email_report"),
                InlineKeyboardButton("🔄 Refresh", callback_data="refresh_history")
            ],
            [
                InlineKeyboardButton("⬅️ Back", callback_data="purchase_history"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="user_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            history_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Detailed history callback failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Error loading detailed history.")


async def email_report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle email report callback."""
    query = update.callback_query
    user = query.from_user
    
    try:
        await query.answer("📧 Preparing email report...")
        
        report_text = """
📧 **Email Report Request**

**Feature Coming Soon!**

We're working on email reporting functionality that will include:

• 📊 Comprehensive purchase history
• 💰 Spending analytics  
• 📈 Usage statistics
• 📄 Downloadable PDF reports

**Current Options:**
• Screenshot this conversation
• Use the billing portal for invoices
• Contact support for manual reports

Thank you for your patience!
        """
        
        keyboard = [
            [
                InlineKeyboardButton("💳 Billing Portal", callback_data="billing_portal"),
                InlineKeyboardButton("📊 View Analytics", callback_data="show_analytics")
            ],
            [
                InlineKeyboardButton("⬅️ Back", callback_data="purchase_history"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="user_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            report_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Email report callback failed for user {user.id}: {e}")
        await query.edit_message_text("❌ Error preparing email report.") 