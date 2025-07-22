#!/usr/bin/env python3
"""
Add default products to the database for the Enterprise Telegram Bot.
This script adds sample credit packages and time passes.
"""

import os
import sys
import uuid

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.database import get_db_connection, execute_query
from src.config import validate_config

def add_default_products():
    """Add default products to the database."""
    
    # Validate configuration
    validate_config()
    
    # Default products to add
    default_products = [
        {
            'product_type': 'credits',
            'name': '10 Credits',
            'description': '10 message credits for basic communication',
            'stripe_price_id': 'price_10credits',  # You'll need to create this in Stripe
            'amount': 10,
            'price_usd_cents': 500,  # $5.00
            'sort_order': 1
        },
        {
            'product_type': 'credits',
            'name': '25 Credits',
            'description': '25 message credits for regular users',
            'stripe_price_id': 'price_25credits',  # You'll need to create this in Stripe
            'amount': 25,
            'price_usd_cents': 1000,  # $10.00
            'sort_order': 2
        },
        {
            'product_type': 'credits',
            'name': '50 Credits',
            'description': '50 message credits for power users',
            'stripe_price_id': 'price_50credits',  # You'll need to create this in Stripe
            'amount': 50,
            'price_usd_cents': 1800,  # $18.00
            'sort_order': 3
        },
        {
            'product_type': 'credits',
            'name': '100 Credits',
            'description': '100 message credits for heavy users',
            'stripe_price_id': 'price_100credits',  # You'll need to create this in Stripe
            'amount': 100,
            'price_usd_cents': 3000,  # $30.00
            'sort_order': 4
        },
        {
            'product_type': 'time',
            'name': '1 Day Access',
            'description': '24 hours of unlimited messaging',
            'stripe_price_id': 'price_1day',  # You'll need to create this in Stripe
            'amount': 86400,  # 24 hours in seconds
            'price_usd_cents': 200,  # $2.00
            'sort_order': 5
        },
        {
            'product_type': 'time',
            'name': '7 Day Access',
            'description': '7 days of unlimited messaging',
            'stripe_price_id': 'price_7days',  # You'll need to create this in Stripe
            'amount': 604800,  # 7 days in seconds
            'price_usd_cents': 1000,  # $10.00
            'sort_order': 6
        }
    ]
    
    print("🔄 Adding default products to database...")
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for product in default_products:
                    # Check if product already exists
                    cur.execute(
                        "SELECT id FROM products WHERE stripe_price_id = %s",
                        (product['stripe_price_id'],)
                    )
                    
                    if cur.fetchone():
                        print(f"⚠️  Product {product['name']} already exists, skipping...")
                        continue
                    
                    # Insert new product
                    cur.execute("""
                        INSERT INTO products (
                            product_type, name, description, stripe_price_id,
                            amount, price_usd_cents, sort_order, is_active
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        product['product_type'],
                        product['name'],
                        product['description'],
                        product['stripe_price_id'],
                        product['amount'],
                        product['price_usd_cents'],
                        product['sort_order'],
                        True
                    ))
                    
                    print(f"✅ Added product: {product['name']} - ${product['price_usd_cents']/100:.2f}")
        
        print("🎉 Default products added successfully!")
        print("\n📝 Next steps:")
        print("1. Create corresponding products in your Stripe dashboard")
        print("2. Update the stripe_price_id values in the database with real Stripe price IDs")
        print("3. Test the bot's billing functionality")
        
    except Exception as e:
        print(f"❌ Error adding default products: {e}")
        sys.exit(1)

if __name__ == "__main__":
    add_default_products() 