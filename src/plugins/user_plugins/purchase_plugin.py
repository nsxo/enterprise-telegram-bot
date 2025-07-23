"""
Enterprise Telegram Bot - Purchase Plugin

This plugin handles all user-facing purchase functionality including
product catalog, checkout flow, Stripe integration, and billing management.
"""

import logging
from typing import Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, Application
from telegram.constants import ParseMode

from src.plugins.base_plugin import BasePlugin, PluginMetadata
from src import database as db
from src import stripe_utils

logger = logging.getLogger(__name__)


class PurchasePlugin(BasePlugin):
    """Plugin for user purchase and billing functionality."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="Purchase",
            version="1.0.0",
            description="User product catalog, checkout, and billing",
            dependencies=[],
        )

    async def initialize(self, config: Dict[str, Any] = None) -> bool:
        """Initialize the purchase plugin."""
        try:
            logger.info("Initializing Purchase Plugin...")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Purchase Plugin: {e}")
            return False

    def register_handlers(self, application: Application) -> None:
        """Register all purchase handlers."""
        application.add_handler(CommandHandler("buy", self.buy_command))
        application.add_handler(CommandHandler("buy10", self.buy10_command))
        application.add_handler(CommandHandler("buy25", self.buy25_command))
        application.add_handler(CommandHandler("buy50", self.buy50_command))
        application.add_handler(CommandHandler("billing", self.billing_command))
        application.add_handler(
            CallbackQueryHandler(self.show_products_callback, pattern="^show_products$")
        )
        application.add_handler(
            CallbackQueryHandler(self.process_buy_callback, pattern="^process_buy_.*")
        )
        application.add_handler(
            CallbackQueryHandler(self.quick_buy_callback, pattern="^quick_buy_.*")
        )
        application.add_handler(
            CallbackQueryHandler(self.show_time_options, pattern="^show_time$")
        )
        application.add_handler(
            CallbackQueryHandler(
                self.process_time_buy_callback, pattern="^buy_time_.*"
            )
        )
        # Add auto-recharge handlers
        application.add_handler(
            CallbackQueryHandler(self.setup_auto_recharge_callback, pattern="^setup_auto_recharge$")
        )
        application.add_handler(
            CallbackQueryHandler(self.toggle_auto_recharge_callback, pattern="^toggle_auto_recharge$")
        )
        application.add_handler(
            CallbackQueryHandler(self.auto_recharge_product_callback, pattern="^auto_recharge_product_.*")
        )

    def get_commands(self) -> Dict[str, str]:
        """Get commands provided by this plugin."""
        return {
            "buy": "Browse and buy credits or time-based access",
            "buy10": "Quick buy 10 credits",
            "buy25": "Quick buy 25 credits",
            "buy50": "Quick buy 50 credits",
            "billing": "Manage your billing and payment methods",
        }

    async def buy_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle the /buy command."""
        await self.show_products_callback(update, context)

    async def buy10_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /buy10 quick buy command."""
        await self.process_quick_buy_command(update, context, 10)

    async def buy25_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /buy25 quick buy command."""
        await self.process_quick_buy_command(update, context, 25)

    async def buy50_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /buy50 quick buy command."""
        await self.process_quick_buy_command(update, context, 50)

    async def billing_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /billing command to redirect to Stripe portal."""
        user = update.effective_user

        try:
            # Get user data from database to find Stripe customer ID
            user_data = db.get_user(user.id)
            if not user_data:
                await update.message.reply_text(
                    "❌ User not found. Please contact support."
                )
                return

            stripe_customer_id = user_data.get("stripe_customer_id")
            if not stripe_customer_id:
                await update.message.reply_text(
                    "❌ No billing account found. Please make a purchase first to set up billing."
                )
                return

            portal_url = stripe_utils.create_billing_portal_session(stripe_customer_id)

            if portal_url:
                text = """
💳 **Manage Your Billing**

Click the button below to manage your payment methods, view invoices,
and update your subscription details securely in our billing portal.
                """

                keyboard = [
                    [InlineKeyboardButton("🔐 Open Billing Portal", url=portal_url)]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_text(
                    text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
                )

            else:
                await update.message.reply_text(
                    "❌ Could not create a billing session. Please try again later."
                )

        except Exception as e:
            logger.error(f"Error creating billing portal for user {user.id}: {e}")
            await update.message.reply_text(
                "❌ An error occurred. Please try again later."
            )

    async def show_products_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Show available products to the user."""
        query = update.callback_query
        if query:
            await query.answer()

        try:
            products = db.get_active_products()

            if not products:
                text = "😔 No products available at this time. Please check back later."
                keyboard = None
            else:
                text = """
🛒 **Purchase Options**

Choose from our available credit packs and time-based access:

**Credit Packs:**
                """

                credit_buttons = []
                for p in products:
                    if p.get("product_type") == "credits":
                        price_in_dollars = p.get('price_usd_cents', 0) / 100
                        credit_buttons.append(
                            InlineKeyboardButton(
                                f"{p.get('name', 'N/A')} - ${price_in_dollars:.2f}",
                                callback_data=f"process_buy_{p.get('id')}",
                            )
                        )

                # Arrange buttons in rows of 2
                keyboard = [
                    credit_buttons[i : i + 2] for i in range(0, len(credit_buttons), 2)
                ]

                text += "\n\n**Time-Based Access:**\n"

                time_buttons = [
                    InlineKeyboardButton(
                        "⏳ View Time Options", callback_data="show_time"
                    )
                ]
                keyboard.append(time_buttons)

            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

            if query:
                await query.edit_message_text(
                    text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
                )

        except Exception as e:
            logger.error(f"Error in show_products_callback: {e}")
            error_text = "❌ Error loading products."

            if query:
                await query.edit_message_text(error_text)
            else:
                await update.message.reply_text(error_text)

    async def process_quick_buy_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int
    ) -> None:
        """Process a quick buy command for a specified credit amount."""
        user = update.effective_user
        
        # Get the product ID from the database based on the credit amount
        product = db.get_product_by_credit_amount(amount)
        
        if not product:
            await update.message.reply_text(f"❌ No product found for {amount} credits.")
            return
            
        await self._create_checkout_session(update, context, user, product["id"])

    async def process_buy_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Process a buy callback for a specific product ID."""
        query = update.callback_query
        await query.answer()
        user = update.effective_user

        try:
            product_id = int(query.data.split("_")[-1])
            await self._create_checkout_session(
                update, context, user, product_id, is_callback=True
            )

        except (ValueError, IndexError):
            await query.edit_message_text("❌ Invalid product selection.")
        except Exception as e:
            logger.error(f"Error processing buy callback for user {user.id}: {e}")
            await query.edit_message_text("❌ Error creating checkout session.")

    async def _create_checkout_session(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user,
        product_id: int,
        is_callback: bool = False,
    ) -> None:
        """Create and send a Stripe checkout session URL."""
        try:
            product = db.get_product_by_id(product_id)
            if not product:
                error_msg = "❌ Product not found."
                if is_callback and update.callback_query:
                    await update.callback_query.edit_message_text(error_msg)
                else:
                    await update.message.reply_text(error_msg)
                return

            checkout_url = stripe_utils.create_checkout_session(
                user.id, product["stripe_price_id"]
            )

            if checkout_url:
                text = """
💳 **Complete Your Purchase**

Click the button below to complete your purchase securely.
Your credits will be added automatically after payment.
                """

                keyboard = [[InlineKeyboardButton("🔒 Pay Now", url=checkout_url)]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # Edit message if from callback, else reply
                if is_callback and update.callback_query:
                    await update.callback_query.edit_message_text(
                        text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await update.message.reply_text(
                        text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
                    )
            else:
                error_msg = "❌ Could not create a checkout session."
                if is_callback and update.callback_query:
                    await update.callback_query.edit_message_text(error_msg)
                else:
                    await update.message.reply_text(error_msg)

        except Exception as e:
            logger.error(f"Error creating checkout session for user {user.id}: {e}")
            error_msg = "❌ An error occurred. Please try again later."
            if is_callback and update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
            else:
                await update.message.reply_text(error_msg)

    async def quick_buy_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle quick buy callbacks."""
        query = update.callback_query
        await query.answer()

        amount_map = {"quick_buy_10": 10, "quick_buy_25": 25, "quick_buy_50": 50}
        amount = amount_map.get(query.data)

        if amount:
            await self.process_quick_buy_command(update, context, amount)

    async def show_time_options(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Show time-based purchase options."""
        query = update.callback_query
        await query.answer()
        
        time_products = db.get_products_by_type('time')
        
        text = "⏳ **Time-Based Access**\n\nEnjoy unlimited conversations for a set period:"
        
        keyboard = []
        for p in time_products:
            price_in_dollars = p.get("price_usd_cents", 0) / 100
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{p['name']} - ${price_in_dollars:.2f}",
                        callback_data=f"buy_time_{p['id']}",
                    )
                ]
            )
            
        keyboard.append(
            [InlineKeyboardButton("🔙 Back to Credits", callback_data="show_products")]
        )
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

    async def process_time_buy_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Process a buy callback for a time-based product."""
        query = update.callback_query
        await query.answer()
        user = update.effective_user

        try:
            product_id = int(query.data.split("_")[-1])
            await self._create_checkout_session(
                update, context, user, product_id, is_callback=True
            )

        except (ValueError, IndexError):
            await query.edit_message_text("❌ Invalid product selection.")
        except Exception as e:
            logger.error(f"Error processing time buy for user {user.id}: {e}")
            await query.edit_message_text("❌ Error creating checkout session.")
