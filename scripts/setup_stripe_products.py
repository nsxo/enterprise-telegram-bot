#!/usr/bin/env python3
"""
Set up Stripe products and update database with real price IDs.
This script creates the necessary products in Stripe and updates the database.
"""

import os
import sys

# Add the project root to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

import stripe
import logging

# Import after path is set
try:
    from src.config import validate_config, STRIPE_API_KEY
    from src.database import get_db_connection
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = STRIPE_API_KEY

def create_stripe_product_and_price(name: str, description: str, amount_cents: int) -> str:
    """
    Create a Stripe product and price, return the price ID.
    """
    try:
        # Create product
        product = stripe.Product.create(
            name=name,
            description=description,
            type='service'
        )
        logger.info(f"✅ Created Stripe product: {name}")

        # Create price
        price = stripe.Price.create(
            product=product.id,
            unit_amount=amount_cents,
            currency='usd',
        )
        logger.info(f"✅ Created Stripe price: {price.id} for ${amount_cents/100:.2f}")

        return price.id

    except stripe.error.StripeError as e:
        logger.error(f"❌ Failed to create Stripe product {name}: {e}")
        return None

def setup_stripe_products():
    """Set up all Stripe products and update the database."""
    
    validate_config()
    
    # Define the products we need to create
    products_to_create = [
        {
            "name": "10 Credits Pack",
            "description": "Perfect for light usage - 10 message credits",
            "amount_cents": 500,  # $5.00
            "old_price_id": "price_10credits_test"
        },
        {
            "name": "25 Credits Pack", 
            "description": "Great value - 25 message credits",
            "amount_cents": 1000,  # $10.00
            "old_price_id": "price_25credits_test"
        },
        {
            "name": "50 Credits Pack",
            "description": "Best value - 50 message credits", 
            "amount_cents": 1800,  # $18.00
            "old_price_id": "price_50credits_test"
        },
        {
            "name": "7 Days Access",
            "description": "Unlimited messages for 7 days",
            "amount_cents": 1500,  # $15.00
            "old_price_id": "price_7days_test"
        },
        {
            "name": "30 Days Access",
            "description": "Unlimited messages for 30 days",
            "amount_cents": 5000,  # $50.00
            "old_price_id": "price_30days_test"
        }
    ]

    logger.info("🚀 Setting up Stripe products...")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for product_info in products_to_create:
                    # Create the Stripe product and price
                    new_price_id = create_stripe_product_and_price(
                        product_info["name"],
                        product_info["description"], 
                        product_info["amount_cents"]
                    )

                    if new_price_id:
                        # Update the database with the real price ID
                        update_query = """
                            UPDATE products 
                            SET stripe_price_id = %s 
                            WHERE stripe_price_id = %s
                        """
                        cur.execute(update_query, (new_price_id, product_info["old_price_id"]))
                        
                        if cur.rowcount > 0:
                            logger.info(f"✅ Updated database: {product_info['old_price_id']} → {new_price_id}")
                        else:
                            logger.warning(f"⚠️ No database rows updated for {product_info['old_price_id']}")
                    else:
                        logger.error(f"❌ Failed to create Stripe product for {product_info['name']}")

                # Commit all changes
                conn.commit()
                logger.info("✅ All products updated successfully!")

    except Exception as e:
        logger.error(f"❌ Error setting up Stripe products: {e}")
        raise

def verify_stripe_products():
    """Verify that all products in the database have valid Stripe price IDs."""
    
    logger.info("🔍 Verifying Stripe products...")
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get all products from database
                cur.execute("SELECT id, name, stripe_price_id FROM products WHERE is_active = true")
                products = cur.fetchall()

                for product in products:
                    try:
                        # Try to retrieve the price from Stripe
                        price = stripe.Price.retrieve(product[2])  # stripe_price_id
                        logger.info(f"✅ Verified: {product[1]} → {price.id}")
                    except stripe.error.StripeError as e:
                        logger.error(f"❌ Invalid price ID for {product[1]}: {product[2]} - {e}")

    except Exception as e:
        logger.error(f"❌ Error verifying Stripe products: {e}")

if __name__ == "__main__":
    print("🔧 Setting up Stripe products...")
    setup_stripe_products()
    print("\n🔍 Verifying products...")
    verify_stripe_products()
    print("\n🎉 Stripe setup completed!")
    print("\n📝 Next steps:")
    print("1. Test the bot's purchase functionality")
    print("2. Check the Stripe dashboard to confirm products were created")
    print("3. Deploy the updated bot") 