"""
Enterprise Telegram Bot - Purchase Plugin

This plugin handles all user-facing purchase functionality including
product catalog, checkout flow, Stripe integration, and billing management.
"""

import logging

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ParseMode,
)
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
)

from src.plugins.base_plugin import BasePlugin
from src import database as db
from src import stripe_utils

logger = logging.getLogger(__name__)

# Conversation states
SELECTING_AUTO_RECHARGE_PRODUCT = range(1)


class PurchasePlugin(BasePlugin):
    """
    Handles all purchasing, billing, and auto-recharge functionality.
    """

    def __init__(self):
        super().__init__()
        self.name = "Purchase"
        self.description = "Handles product purchases and billing management."
        self.version = "2.0.0"
        self.author = "Your Name"

    def register_handlers(self, application) -> None:
        """Register all handlers for this plugin."""
        # Main Commands
        application.add_handler(CommandHandler("buy", self.show_products_command))
        application.add_handler(CommandHandler("billing", self.billing_command))

        # Quick Buy Commands
        application.add_handler(
            CommandHandler("buy10", lambda u, c: self.process_quick_buy_command(u, c, 10))
        )
        application.add_handler(
            CommandHandler("buy25", lambda u, c: self.process_quick_buy_command(u, c, 25))
        )
        application.add_handler(
            CommandHandler("buy50", lambda u, c: self.process_quick_buy_command(u, c, 50))
        )

        # Auto-recharge prompt handlers
        application.add_handler(
            CallbackQueryHandler(
                self.handle_auto_recharge_prompt, pattern=("autorecharge_enable",)
            )
        )
        application.add_handler(
            CallbackQueryHandler(
                self.handle_auto_recharge_prompt, pattern=("autorecharge_decline",)
            )
        )

        # Main callback for product purchase
        application.add_handler(
            CallbackQueryHandler(self.process_buy_callback, pattern=r"^buy_product_")
        )

        # Billing and auto-recharge management conversation
        conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    self.setup_auto_recharge_callback,
                    pattern=r"^autorecharge_setup",
                ),
                CallbackQueryHandler(
                    self.toggle_auto_recharge_callback,
                    pattern=r"^autorecharge_toggle",
                ),
                CallbackQueryHandler(
                    self.billing_command, pattern=r"^return_billing"
                ),
            ],
            states={
                SELECTING_AUTO_RECHARGE_PRODUCT: [
                    CallbackQueryHandler(
                        self.auto_recharge_product_callback,
                        pattern=r"^autorecharge_product_",
                    )
                ]
            },
            fallbacks=[
                CallbackQueryHandler(self.cancel_callback, pattern=r"^cancel"),
                CommandHandler("billing", self.billing_command),
            ],
            map_to_parent={-1: -1},
        )
        application.add_handler(conv_handler)
        application.add_handler(
            CallbackQueryHandler(
                self.view_billing_callback, pattern=r"^view_billing$"
            )
        )


    async def show_products_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        await self.show_products_callback(update, context)

    async def show_products_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Display active products to the user."""
        query = update.callback_query
        if query:
            await query.answer()

        try:
            credit_products = db.get_products_by_type("credits")
            time_products = db.get_products_by_type("time")

            text = "🛍️ **Product Catalog**\n\n"
            keyboard = []

            if credit_products:
                text += "C R E D I T S\n"
                for p in credit_products:
                    button_text = f"{p['name']} - ${p['price_usd_cents']/100:.2f}"
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                button_text,
                                callback_data=f"buy_product_{p['id']}",
                            )
                        ]
                    )
            if time_products:
                text += "\nT I M E - B A S E D   A C C E S S\n"
                for p in time_products:
                    button_text = f"{p['name']} - ${p['price_usd_cents']/100:.2f}"
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                button_text,
                                callback_data=f"buy_product_{p['id']}",
                            )
                        ]
                    )

            if not keyboard:
                text = "❌ No products are currently available. Please check back later."

            reply_markup = InlineKeyboardMarkup(keyboard)
            edit_or_reply = (
                query.edit_message_text if query else update.message.reply_text
            )
            await edit_or_reply(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            logger.error(f"Error in show_products_callback: {e}")
            await handle_error(update, context, "Error loading products.")

    async def billing_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /billing command to show the billing management menu."""
        query = update.callback_query
        if query:
            await query.answer()
        user = update.effective_user
        user_data = db.get_user(user.id)

        if not user_data:
            await handle_error(update, context, "User not found.")
            return

        stripe_customer_id = user_data.get("stripe_customer_id")
        auto_recharge_enabled = user_data.get("auto_recharge_enabled", False)
        auto_recharge_product_id = user_data.get("auto_recharge_product_id")

        text = "💳 **Billing & Auto-Recharge**\n\n"
        keyboard = []

        if auto_recharge_enabled and auto_recharge_product_id:
            product = db.get_product_by_id(auto_recharge_product_id)
            text += (
                f"✅ Auto-Recharge is **ON**.\n"
                "We will automatically purchase "
                f"**{product['name']}** for you when your balance drops below "
                f"**{user_data.get('auto_recharge_threshold', 10)}** credits.\n"
            )
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "❌ Disable Auto-Recharge",
                        callback_data="autorecharge_toggle",
                    )
                ]
            )
        else:
            text += (
                "☑️ Auto-Recharge is **OFF**.\n"
                "Enable it to automatically top up your credits when you're "
                "running low. Never get interrupted again!\n"
            )
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "✅ Enable Auto-Recharge",
                        callback_data="autorecharge_setup",
                    )
                ]
            )

        text += "\nManage your saved payment methods or view invoices on Stripe."
        if stripe_customer_id:
            portal_url = stripe_utils.create_billing_portal_session(stripe_customer_id)
            keyboard.append([
                InlineKeyboardButton("🔐 Open Stripe Billing Portal", url=portal_url)
            ])

        reply_markup = InlineKeyboardMarkup(keyboard)
        edit_or_reply = (
            query.edit_message_text if query else update.message.reply_text
        )
        await edit_or_reply(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

    async def _create_checkout_session(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user,
        product_id: int,
        is_callback: bool = False,
    ) -> None:
        """Create and send an enhanced Stripe checkout session message."""
        try:
            product = db.get_product_by_id(product_id)
            if not product:
                await handle_error(update, context, "Product not found.")
                return

            user_data = db.get_user(user.id)
            has_payment_method = bool(user_data.get("stripe_customer_id"))
            is_first_purchase = not db.has_user_made_purchases(user.id)

            checkout_url = stripe_utils.create_checkout_session(
                user.id, product["stripe_price_id"]
            )

            if checkout_url:
                text = f"💳 **Complete Your Purchase - {product['name']}**\n\n"
                if has_payment_method:
                    text += "⚡ Using your saved payment method for a faster checkout.\n\n"
                else:
                    text += "💾 Your payment method will be saved for faster future purchases.\n\n"

                text += (
                    f"📦 **Product Details:**\n"
                    f"💰 **Price:** ${product['price_usd_cents']/100:.2f}\n"
                    f"🎯 **Credits:** {product.get('amount', 'N/A')} credits\n"
                    f"📝 **Description:** {product['description']}\n\n"
                    f"✅ **What happens next:**\n"
                    "• Secure payment processing via Stripe\n"
                    "• Credits added instantly to your account\n"
                    "• Email receipt sent automatically\n"
                )
                if is_first_purchase:
                    text += (
                        "🎉 **First purchase bonus:** You can set up auto-recharge "
                        "after this purchase!\n"
                    )

                keyboard = [[InlineKeyboardButton("🔒 Pay Now", url=checkout_url)]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                edit_or_reply = (
                    update.callback_query.edit_message_text
                    if is_callback and update.callback_query
                    else update.message.reply_text
                )
                await edit_or_reply(
                    text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
                )
            else:
                await handle_error(update, context, "Could not create a checkout session.")
        except Exception as e:
            logger.error(f"Error creating checkout session for user {user.id}: {e}")
            await handle_error(update, context, "An error occurred while creating the checkout session.")


    async def handle_auto_recharge_prompt(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handles the user's response to the initial auto-recharge prompt."""
        query = update.callback_query
        await query.answer()
        action = query.data[0]

        if action == "autorecharge_enable":
            product_id = query.data[1]
            db.enable_auto_recharge(update.effective_user.id, product_id)
            await query.edit_message_text(
                "✅ **Auto-Recharge Enabled!**\n\n"
                "You're all set! We'll top you up automatically. You can manage "
                "this anytime via /billing."
            )
        elif action == "autorecharge_decline":
            await query.edit_message_text(
                "👍 **Got it.**\n\nYou can enable auto-recharge anytime from "
                "the /billing menu."
            )

    async def setup_auto_recharge_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Starts the process of setting up auto-recharge."""
        query = update.callback_query
        await query.answer()
        
        products = db.get_products_by_type("credits")
        if not products:
            await query.edit_message_text("❌ No credit products available for auto-recharge.")
            return ConversationHandler.END

        text = (
            "**Setup Auto-Recharge**\n\n"
            "Please select a credit package to automatically purchase when "
            "your balance runs low."
        )
        keyboard = []
        for p in products:
            button_text = f"{p['name']} (${p['price_usd_cents']/100:.2f})"
            keyboard.append(
                [
                    InlineKeyboardButton(
                        button_text,
                        callback_data=f"autorecharge_product_{p['id']}",
                    )
                ]
            )
        keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="cancel")])

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN,
        )
        return SELECTING_AUTO_RECHARGE_PRODUCT

    async def auto_recharge_product_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handles the user's product selection for auto-recharge."""
        query = update.callback_query
        await query.answer()
        product_id = int(query.data.split("_")[-1])
        
        db.enable_auto_recharge(update.effective_user.id, product_id)

        await query.edit_message_text(
            "✅ **Auto-Recharge Enabled!**\n\n"
            "You're all set! We'll top you up automatically. You can manage "
            "this anytime via /billing."
        )
        return ConversationHandler.END
        
    async def toggle_auto_recharge_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Toggles auto-recharge on or off."""
        query = update.callback_query
        await query.answer()
        user = update.effective_user
        user_data = db.get_user(user.id)
        
        if user_data.get("auto_recharge_enabled"):
            db.disable_auto_recharge(user.id)
            await query.edit_message_text("❌ Auto-Recharge has been **disabled**.")
        else:
            # This path should ideally not be hit if the button is only for disabling
            await self.setup_auto_recharge_callback(update, context)
            return SELECTING_AUTO_RECHARGE_PRODUCT

        # Show the updated billing menu
        await self.billing_command(update, context)
        return ConversationHandler.END

    async def cancel_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Cancels the current conversation and shows the billing menu."""
        query = update.callback_query
        await query.answer()
        await self.billing_command(update, context)
        return ConversationHandler.END

    async def view_billing_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler to simply show the billing menu, useful for returns."""
        await self.billing_command(update, context)

    # These methods remain mostly the same, but now call the new _create_checkout_session
    async def process_quick_buy_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int
    ) -> None:
        user = update.effective_user
        product = db.get_product_by_credit_amount(amount)
        if not product:
            await handle_error(
                update, context, f"No product found for {amount} credits."
            )
            return
        await self._create_checkout_session(update, context, user, product["id"])

    async def process_buy_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        await query.answer()
        user = update.effective_user
        try:
            product_id = int(query.data.split("_")[-1])
            await self._create_checkout_session(
                update, context, user, product_id, is_callback=True
            )
        except (ValueError, IndexError):
            await handle_error(update, context, "Invalid product selection.")
        except Exception as e:
            logger.error(f"Error processing buy callback for user {user.id}: {e}")
            await handle_error(update, context, "Error creating checkout session.")

async def handle_error(update: Update, context: ContextTypes.DEFAULT_TYPE, message: str):
    """A local error handler for cleaner code."""
    if update.callback_query:
        await update.callback_query.edit_message_text(f"❌ {message}")
    else:
        await update.message.reply_text(f"❌ {message}")
