#!/usr/bin/env python3
"""
Ensure products exist in the database.
This script can be run on production to add missing products.
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    """Main function to ensure products exist."""
    # Import after path modification to avoid linter error
    from src.database import (
        ensure_sample_products,
        get_active_products,
        init_connection_pool,
    )
    
    print("🔄 Checking and ensuring products exist...")

    try:
        # Initialize database connection pool
        init_connection_pool()

        # Check current products
        existing_products = get_active_products()
        print(f"📊 Found {len(existing_products)} existing products")

        if len(existing_products) == 0:
            print("📦 No products found, creating sample products...")
            ensure_sample_products()

            # Check again
            new_products = get_active_products()
            print(f"✅ Created {len(new_products)} products")

            for product in new_products:
                price = product["price_usd_cents"] / 100
                print(f"  • {product['name']} - ${price:.2f}")
        else:
            print("✅ Products already exist:")
            for product in existing_products:
                price = product["price_usd_cents"] / 100
                print(f"  • {product['name']} - ${price:.2f}")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    print("🎉 Product check completed successfully!")


if __name__ == "__main__":
    main() 