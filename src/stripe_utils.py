"""
Enterprise Telegram Bot - Stripe Utilities

This module handles all Stripe API interactions including checkout sessions,
customer portal, webhook processing, and payment management with proper
security and idempotency handling.
"""

import logging
import uuid
from typing import Optional, Dict, Any
import stripe
import os

from src.config import STRIPE_API_KEY, STRIPE_WEBHOOK_SECRET, WEBHOOK_URL
from src import database as db

# Configure Stripe
stripe.api_key = STRIPE_API_KEY

logger = logging.getLogger(__name__)


class StripeError(Exception):
    """Raised when Stripe operations fail."""

    pass


# =============================================================================
# CHECKOUT SESSION MANAGEMENT
# =============================================================================


def create_checkout_session(
    user_id: int,
    price_id: str,
    success_url: Optional[str] = None,
    cancel_url: Optional[str] = None,
) -> str:
    """
    Create Stripe checkout session for user purchase.

    Args:
        user_id: User's Telegram ID
        price_id: Stripe price ID for the product
        success_url: Custom success URL (optional)
        cancel_url: Custom cancel URL (optional)

    Returns:
        Checkout session URL

    Raises:
        StripeError: If session creation fails
    """
    logger.info(f"Creating checkout session for user {user_id}, price {price_id}")

    # Generate idempotency key for safe retries
    idempotency_key = str(uuid.uuid4())

    try:
        # Get or create user
        user_data = db.get_user(user_id)
        if not user_data:
            raise StripeError(f"User {user_id} not found in database")

        # Get product information
        product = db.get_product_by_stripe_price_id(price_id)
        if not product:
            raise StripeError(f"Product with price ID {price_id} not found")

        # Set default URLs if not provided
        if not success_url:
            success_url = f"{WEBHOOK_URL}/success?session_id={{CHECKOUT_SESSION_ID}}"
        if not cancel_url:
            cancel_url = f"{WEBHOOK_URL}/cancel"

        # Create or get Stripe customer
        customer_id = user_data.get("stripe_customer_id")
        if not customer_id:
            customer_id = create_stripe_customer(user_id, user_data)

        # Determine if this is the user's first purchase for the auto-recharge prompt
        is_first_purchase = not db.has_user_made_purchases(user_id)

        # Pre-calculate credits and time for clarity
        credits_to_grant = (
            product.get("amount", 0)
            if product.get("product_type") == "credits"
            else 0
        )
        time_to_grant = (
            product.get("amount", 0) if product.get("product_type") == "time" else 0
        )

        transaction = db.log_transaction(
            user_id=user_id,
            product_id=product["id"],
            stripe_charge_id=None,
            stripe_session_id=None,  # Will be updated after session creation
            idempotency_key=idempotency_key,
            amount_cents=product["price_usd_cents"],
            credits_granted=credits_to_grant,
            time_granted_seconds=time_to_grant,
            status="pending",
            description=f"Purchase: {product['name']}",
        )

        # Create checkout session with idempotency key
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="payment",
            customer=customer_id,
            client_reference_id=str(user_id),
            metadata={
                "user_id": str(user_id),
                "product_id": str(product["id"]),
                "transaction_id": str(transaction["id"]),
                "credits_granted": str(credits_to_grant),
                "time_granted_seconds": str(time_to_grant),
                "is_first_purchase": str(is_first_purchase),
            },
            success_url=success_url,
            cancel_url=cancel_url,
            idempotency_key=idempotency_key,
        )

        # Update transaction with session ID
        db.update_transaction_status(
            transaction_id=transaction["id"],
            status="pending",
            stripe_charge_id=session.id,
        )

        logger.info(f"✅ Created checkout session {session.id} for user {user_id}")
        return session.url

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {e}")
        raise StripeError(f"Failed to create checkout session: {e}")
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        raise StripeError(f"Failed to create checkout session: {e}")


def create_stripe_customer(user_id: int, user_data: Dict[str, Any]) -> str:
    """
    Create Stripe customer for user.

    Args:
        user_id: User's Telegram ID
        user_data: User data from database

    Returns:
        Stripe customer ID
    """
    logger.info(f"Creating Stripe customer for user {user_id}")

    try:
        # Generate idempotency key
        idempotency_key = str(uuid.uuid4())

        # Create customer
        customer = stripe.Customer.create(
            email=f"user.{user_id}@{os.getenv('STRIPE_CUSTOMER_EMAIL_DOMAIN', 'example.com')}",
            name=f"{user_data['first_name']} {user_data.get('last_name', '')}".strip(),
            metadata={
                "telegram_id": str(user_id),
                "username": user_data.get("username", ""),
            },
            idempotency_key=idempotency_key,
        )

        # Update user record with Stripe customer ID
        db.update_user_stripe_customer(user_id, customer.id)

        logger.info(f"✅ Created Stripe customer {customer.id} for user {user_id}")
        return customer.id

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating customer: {e}")
        raise StripeError(f"Failed to create Stripe customer: {e}")


# =============================================================================
# CUSTOMER PORTAL MANAGEMENT
# =============================================================================


def create_billing_portal_session(
    customer_id: str, return_url: Optional[str] = None
) -> str:
    """
    Create Stripe Customer Portal session for billing management.

    Args:
        customer_id: Stripe customer ID
        return_url: URL to return to after portal session

    Returns:
        Customer portal URL

    Raises:
        StripeError: If portal session creation fails
    """
    logger.info(f"Creating billing portal session for customer {customer_id}")

    try:
        # Set default return URL if not provided
        if not return_url:
            return_url = f"{WEBHOOK_URL}/billing-complete"

        # Generate idempotency key
        idempotency_key = str(uuid.uuid4())

        # Create portal session
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
            idempotency_key=idempotency_key,
        )

        logger.info(f"✅ Created billing portal session for customer {customer_id}")
        return session.url

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating portal session: {e}")
        raise StripeError(f"Failed to create billing portal session: {e}")


# =============================================================================
# WEBHOOK PROCESSING
# =============================================================================


def verify_webhook_signature(payload: bytes, signature: str) -> Dict[str, Any]:
    """
    Verify Stripe webhook signature and return event.

    Args:
        payload: Raw request body as bytes
        signature: Stripe signature header

    Returns:
        Verified Stripe event

    Raises:
        StripeError: If signature verification fails
    """
    try:
        event = stripe.Webhook.construct_event(
            payload, signature, STRIPE_WEBHOOK_SECRET
        )
        logger.info(f"✅ Verified webhook event: {event['type']}")
        return event

    except ValueError as e:
        logger.error(f"Invalid webhook payload: {e}")
        raise StripeError("Invalid payload")

    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid webhook signature: {e}")
        raise StripeError("Invalid signature")


# =============================================================================
# AUTO-RECHARGE SYSTEM
# =============================================================================


def trigger_auto_recharge(
    user_id: int, product_price_id: str, product_name: str
) -> bool:
    """
    Trigger auto-recharge for a user with low credits.

    Args:
        user_id: User's Telegram ID
        product_price_id: Stripe price ID for auto-recharge product
        product_name: Name of the product for logging

    Returns:
        True if auto-recharge was triggered successfully
    """
    logger.info(f"Triggering auto-recharge for user {user_id}, product: {product_name}")

    try:
        # Get user data
        user_data = db.get_user(user_id)
        if not user_data or not user_data.get("stripe_customer_id"):
            logger.warning(f"Cannot auto-recharge user {user_id}: No Stripe customer")
            return False

        # Check for recent failed payments
        recent_failures = db.check_failed_payments(user_id, days=7)
        if recent_failures >= 3:
            logger.warning(
                f"Skipping auto-recharge for user {user_id}: {recent_failures} recent failed payments"
            )
            # Disable auto-recharge to prevent continued failures
            db.disable_auto_recharge(user_id)
            return False

        # Generate idempotency key
        idempotency_key = str(uuid.uuid4())

        # Create payment intent for auto-recharge (not checkout session)
        payment_intent = stripe.PaymentIntent.create(
            amount=db.get_product_by_stripe_price_id(product_price_id)[
                "price_usd_cents"
            ],
            currency="usd",
            customer=user_data["stripe_customer_id"],
            confirm=True,
            off_session=True,  # Indicates this is for an existing customer
            metadata={
                "user_id": str(user_id),
                "auto_recharge": "true",
                "product_name": product_name,
            },
            idempotency_key=idempotency_key,
        )

        logger.info(
            f"✅ Auto-recharge payment intent created for user {user_id}: {payment_intent.id}"
        )
        return True

    except stripe.error.CardError as e:
        # Card was declined
        logger.warning(f"Auto-recharge card declined for user {user_id}: {e}")
        return False

    except stripe.error.AuthenticationError as e:
        # Authentication with Stripe failed
        logger.error(f"Auto-recharge authentication error: {e}")
        return False

    except Exception as e:
        logger.error(f"Auto-recharge failed for user {user_id}: {e}")
        return False


async def process_auto_recharge_users(telegram_app):
    """
    Process all users who need auto-recharge.
    Should be called periodically (e.g., every hour).

    Args:
        telegram_app: Telegram application instance for sending notifications
    """
    logger.info("🔄 Processing auto-recharge users...")

    try:
        users_needing_recharge = db.get_users_needing_auto_recharge()

        if not users_needing_recharge:
            logger.info("No users need auto-recharge at this time")
            return

        logger.info(f"Found {len(users_needing_recharge)} users needing auto-recharge")

        for user_data in users_needing_recharge:
            user_id = user_data["telegram_id"]
            product_name = user_data["product_name"]
            price_id = user_data["stripe_price_id"]

            try:
                # Attempt auto-recharge
                success = trigger_auto_recharge(user_id, price_id, product_name)

                if success:
                    # Send success notification to user
                    message = (
                        f"🔄 **Auto-Recharge Successful!**\n\n"
                        f"Your account has been automatically recharged with **{product_name}**.\n\n"
                        f"💰 **Credits added to your balance**\n"
                        f"🔔 **Auto-recharge keeps you connected**\n\n"
                        f"Use /balance to see your updated balance."
                    )

                    try:
                        await telegram_app.bot.send_message(
                            chat_id=user_id, text=message, parse_mode="Markdown"
                        )
                    except Exception as msg_error:
                        logger.warning(
                            f"Failed to send auto-recharge success message to user {user_id}: {msg_error}"
                        )

                else:
                    # Send failure notification to user
                    message = (
                        "⚠️ **Auto-Recharge Failed**\n\n"
                        "We couldn't automatically recharge your account.\n\n"
                        "💳 **Please check your payment method**\n"
                        "🔧 **Update billing info:** /billing\n"
                        "🛒 **Manual purchase:** /buy\n\n"
                        "Your auto-recharge is still enabled and will try again when your credits get low."
                    )

                    try:
                        await telegram_app.bot.send_message(
                            chat_id=user_id, text=message, parse_mode="Markdown"
                        )
                    except Exception as msg_error:
                        logger.warning(
                            f"Failed to send auto-recharge failure message to user {user_id}: {msg_error}"
                        )

            except Exception as e:
                logger.error(f"Error processing auto-recharge for user {user_id}: {e}")
                continue

        logger.info(
            f"✅ Completed auto-recharge processing for {len(users_needing_recharge)} users"
        )

    except Exception as e:
        logger.error(f"Error in auto-recharge processing: {e}")


# =============================================================================
# PAYMENT FAILURE HANDLING
# =============================================================================


def process_payment_failed(event: Dict[str, Any]) -> bool:
    """
    Enhanced payment failure processing with user notifications.

    Args:
        event: Stripe webhook event

    Returns:
        True if processed successfully
    """
    payment_intent = event["data"]["object"]
    logger.info(f"Processing payment failed: {payment_intent['id']}")

    try:
        # Extract user info from metadata
        user_id = payment_intent["metadata"].get("user_id")
        if not user_id:
            logger.warning("No user_id in payment intent metadata")
            return True

        user_id = int(user_id)
        is_auto_recharge = payment_intent["metadata"].get("auto_recharge") == "true"

        # Get failure reason
        last_error = payment_intent.get("last_payment_error", {})
        failure_code = last_error.get("code", "unknown")
        failure_message = last_error.get("message", "Payment failed")

        logger.info(
            f"Payment failed for user {user_id}: {failure_code} - {failure_message}"
        )

        # Check if this user has had multiple recent failures
        recent_failures = db.check_failed_payments(user_id, days=7)

        # Disable auto-recharge if too many failures
        if is_auto_recharge and recent_failures >= 2:
            db.disable_auto_recharge(user_id)
            logger.info(
                f"Disabled auto-recharge for user {user_id} due to {recent_failures + 1} failed payments"
            )

        # Log the failure in our database (you may want to implement this)
        # db.log_payment_failure(user_id, payment_intent['id'], failure_code, failure_message)

        return True

    except Exception as e:
        logger.error(f"Error processing payment failed: {e}")
        return False


def process_dispute_created(event: Dict[str, Any]) -> bool:
    """
    Process charge.dispute.created webhook event.

    Args:
        event: Stripe webhook event

    Returns:
        True if processed successfully
    """
    dispute = event["data"]["object"]
    charge_id = dispute["charge"]

    logger.warning(f"Dispute created for charge {charge_id}")

    try:
        # Get charge details
        charge = stripe.Charge.retrieve(charge_id)

        # Extract customer and user information
        customer_id = charge.get("customer")
        if customer_id:
            customer = stripe.Customer.retrieve(customer_id)
            user_id = customer["metadata"].get("telegram_id")

            if user_id:
                logger.warning(
                    f"🚨 DISPUTE ALERT: User {user_id} initiated chargeback for charge {charge_id}"
                )

                # You could implement logic here to:
                # 1. Flag the user account
                # 2. Send alert to admin group
                # 3. Revoke granted credits/access
                # 4. Log for fraud analysis

        return True

    except Exception as e:
        logger.error(f"Error processing dispute created: {e}")
        return False


def process_customer_subscription_deleted(event: Dict[str, Any]) -> bool:
    """
    Process customer.subscription.deleted webhook event.

    Args:
        event: Stripe webhook event

    Returns:
        True if processed successfully
    """
    subscription = event["data"]["object"]
    customer_id = subscription["customer"]

    logger.info(f"Subscription deleted for customer {customer_id}")

    try:
        # Get customer details
        customer = stripe.Customer.retrieve(customer_id)
        user_id = customer["metadata"].get("telegram_id")

        if user_id:
            user_id = int(user_id)

            # Disable auto-recharge for user
            # This would require adding auto_recharge_enabled field to users table
            logger.info(f"✅ Disabled auto-recharge for user {user_id}")

            # You could implement logic here to:
            # 1. Update user's auto_recharge_enabled to False
            # 2. Send notification to user about cancellation
            # 3. Log the cancellation for business intelligence

        return True

    except Exception as e:
        logger.error(f"Error processing subscription deleted: {e}")
        return False


# =============================================================================
# WEBHOOK EVENT DISPATCHER
# =============================================================================


def process_webhook_event(event: Dict[str, Any]) -> bool:
    """
    Main webhook event processor.

    Args:
        event: Verified Stripe webhook event

    Returns:
        True if event was processed successfully
    """
    event_type = event["type"]
    logger.info(f"Processing webhook event: {event_type}")

    try:
        if event_type == "checkout.session.completed":
            return process_checkout_completed(event)

        elif event_type == "payment_intent.payment_failed":
            return process_payment_failed(event)

        elif event_type == "charge.dispute.created":
            return process_dispute_created(event)

        elif event_type == "customer.subscription.deleted":
            return process_customer_subscription_deleted(event)

        elif event_type == "payment_method.attached":
            logger.info("Payment method attached - no action needed")
            return True

        else:
            logger.info(f"Unhandled webhook event type: {event_type}")
            return True  # Return True for unhandled events to avoid retries

    except Exception as e:
        logger.error(f"Error processing webhook event {event_type}: {e}")
        return False


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def get_customer_by_user_id(user_id: int) -> Optional[str]:
    """
    Get Stripe customer ID for user.

    Args:
        user_id: User's Telegram ID

    Returns:
        Stripe customer ID or None
    """
    user_data = db.get_user(user_id)
    return user_data.get("stripe_customer_id") if user_data else None


def format_price(amount_cents: int) -> str:
    """
    Format price in cents to dollar string.

    Args:
        amount_cents: Price in cents

    Returns:
        Formatted price string (e.g., "$12.99")
    """
    return f"${amount_cents / 100:.2f}"


# Test Stripe connection on module import
def process_checkout_completed(event: Dict[str, Any]) -> bool:
    """
    Enhanced checkout completion processing.

    Args:
        event: Stripe webhook event

    Returns:
        True if processed successfully
    """
    session = event["data"]["object"]
    logger.info(f"Processing checkout completed: {session['id']}")

    try:
        metadata = session.get("metadata", {})
        user_id = int(metadata["user_id"])
        transaction_id = metadata["transaction_id"]
        credits_granted = int(metadata.get("credits_granted", 0))
        time_granted_seconds = int(metadata.get("time_granted_seconds", 0))

        # Check if this is user's first purchase (before completing the transaction)
        is_first_purchase = metadata.get("is_first_purchase") == "True"

        # Update database - mark transaction as completed
        success = db.complete_transaction_and_add_credits(
            user_id=user_id,
            transaction_id=transaction_id,
            credits_granted=credits_granted,
            time_granted_seconds=time_granted_seconds,
        )

        if success:
            logger.info(
                f"✅ Successfully processed checkout for user {user_id}"
            )
            # After successful processing, check if we need to trigger the auto-recharge prompt
            if is_first_purchase:
                product_id = int(metadata.get("product_id"))
                
                # Schedule auto-recharge prompt via database storage
                # to avoid circular import with bot_factory
                logger.info(
                    f"Auto-recharge prompt needed for user {user_id}, "
                    f"product {product_id}"
                )
                
                # Store in database for processing by next user interaction
                db.store_pending_auto_recharge_prompt(user_id, product_id)

            return True
        else:
            logger.error(
                f"Failed to complete transaction and add credits for user {user_id}"
            )
            return False

    except Exception as e:
        logger.error(f"Error processing checkout completed: {e}")
        return False


try:
    # Try to list a small number of products to test connection
    stripe.Product.list(limit=1)
    logger.info("✅ Stripe connection verified successfully")
except Exception as e:
    logger.error(f"❌ Stripe connection failed: {e}")
    logger.error("Check your STRIPE_API_KEY configuration")
