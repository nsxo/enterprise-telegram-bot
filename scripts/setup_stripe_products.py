#!/usr/bin/env python3
"""
Set up Stripe products and update database with real price IDs.
This script creates the necessary products in Stripe and updates the database.
Integrated with UX enhancements and auto-recharge features.
"""

import os
import sys
import stripe
import logging

# Add the project root to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

# Import after path is set
try:
    from src.config import validate_config, STRIPE_API_KEY
    from src.database import get_db_connection
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the project's root directory.")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = STRIPE_API_KEY


def create_stripe_product_and_price(
    name: str, description: str, amount_cents: int, metadata: dict = None
) -> str:
    """
    Create a Stripe product and price, and return the price ID.

    Args:
        name: The name of the product.
        description: The description of the product.
        amount_cents: The price of the product in cents.
        metadata: Additional metadata for the product.

    Returns:
        The Stripe price ID, or None if creation fails.
    """
    try:
        product_data = {"name": name, "description": description, "type": "service"}
        if metadata:
            product_data["metadata"] = metadata

        product = stripe.Product.create(**product_data)
        logger.info(f"✅ Created Stripe product: {name} (ID: {product.id})")

        price = stripe.Price.create(product=product.id, unit_amount=amount_cents, currency="usd")
        logger.info(f"✅ Created Stripe price: {price.id} for ${amount_cents/100:.2f}")

        return price.id

    except stripe.error.StripeError as e:
        logger.error(f"❌ Failed to create Stripe product {name}: {e}")
        return None


def setup_stripe_products():
    """Set up all Stripe products and update the database with new price IDs."""
    validate_config()

    products_to_create = [
        {
            "name": "10 Credits Pack",
            "description": "Perfect for light usage - 10 message credits",
            "amount_cents": 500,
            "old_price_id": "price_10credits_test",
            "metadata": {"product_type": "credits", "credits_granted": "10"},
        },
        {
            "name": "25 Credits Pack",
            "description": "Great value - 25 message credits",
            "amount_cents": 1000,
            "old_price_id": "price_25credits_test",
            "metadata": {"product_type": "credits", "credits_granted": "25"},
        },
        {
            "name": "50 Credits Pack",
            "description": "Best value - 50 message credits",
            "amount_cents": 1800,
            "old_price_id": "price_50credits_test",
            "metadata": {"product_type": "credits", "credits_granted": "50"},
        },
        {
            "name": "7 Days Access",
            "description": "Unlimited messages for 7 days",
            "amount_cents": 1500,
            "old_price_id": "price_7days_test",
            "metadata": {"product_type": "time", "time_granted_seconds": str(7 * 24 * 60 * 60)},
        },
        {
            "name": "30 Days Access",
            "description": "Unlimited messages for 30 days",
            "amount_cents": 5000,
            "old_price_id": "price_30days_test",
            "metadata": {"product_type": "time", "time_granted_seconds": str(30 * 24 * 60 * 60)},
        },
    ]

    logger.info("🚀 Setting up Stripe products...")
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for product_info in products_to_create:
                    logger.info(f"--- Processing: {product_info['name']} ---")
                    cur.execute(
                        "SELECT stripe_price_id FROM products WHERE stripe_price_id = %s",
                        (product_info["old_price_id"],),
                    )
                    result = cur.fetchone()

                    if not result:
                        logger.warning(f"⚠️  Product with old ID '{product_info['old_price_id']}' not found in DB. Skipping.")
                        continue

                    if result[0].startswith("price_") and "_test" in result[0]:
                        new_price_id = create_stripe_product_and_price(
                            product_info["name"],
                            product_info["description"],
                            product_info["amount_cents"],
                            product_info["metadata"],
                        )
                        if new_price_id:
                            cur.execute(
                                "UPDATE products SET stripe_price_id = %s WHERE stripe_price_id = %s",
                                (new_price_id, product_info["old_price_id"]),
                            )
                            if cur.rowcount > 0:
                                logger.info(f"✅ DB Updated: {product_info['old_price_id']} → {new_price_id}")
                            else:
                                logger.warning(f"⚠️  No DB rows updated for {product_info['old_price_id']}")
                        else:
                            logger.error(f"❌ Failed to create Stripe product for {product_info['name']}. Halting.")
                            conn.rollback()
                            return
                    else:
                        logger.info(f"✅ Product '{product_info['name']}' already has a real Stripe ID: {result[0]}. Skipping creation.")
                conn.commit()
                logger.info("✅ All product price IDs updated successfully in the database!")
    except Exception as e:
        logger.error(f"❌ An error occurred during Stripe product setup: {e}")
        raise


def verify_stripe_products():
    """Verify that all products in the database have valid, retrievable Stripe price IDs."""
    logger.info("🔍 Verifying Stripe product setup...")
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, stripe_price_id FROM products WHERE is_active = true")
                products_in_db = cur.fetchall()
                if not products_in_db:
                    logger.warning("No active products found to verify.")
                    return
                for prod_id, name, price_id in products_in_db:
                    if not price_id or not price_id.startswith("price_"):
                        logger.error(f"❌ Invalid Price ID format for '{name}' (DB ID: {prod_id}): '{price_id}'")
                        continue
                    try:
                        stripe.Price.retrieve(price_id)
                        logger.info(f"✅ Verified: '{name}' → {price_id}")
                    except stripe.error.InvalidRequestError:
                        logger.error(f"❌ Unretrievable Price ID for '{name}': {price_id}")
                    except Exception as e:
                        logger.error(f"❌ Error verifying '{name}' ({price_id}): {e}")
    except Exception as e:
        logger.error(f"❌ Error during product verification: {e}")


if __name__ == "__main__":
    print("This script will create products in your Stripe account and update your database.")
    print("WARNING: This is a potentially destructive action and assumes your database contains test price IDs.")
    confirm = input("Are you sure you want to continue? (y/n): ")
    if confirm.lower() == "y":
        logger.info("🔧 Starting Stripe product setup...")
        setup_stripe_products()
        logger.info("\n🔍 Verifying products post-setup...")
        verify_stripe_products()
        logger.info("\n🎉 Stripe setup completed!")
        logger.info("Run your application to use the new product IDs.")
    else:
        logger.info("Aborted by user.") 