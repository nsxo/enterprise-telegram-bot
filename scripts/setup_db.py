"""
Enterprise Telegram Bot - Database Setup Script

This script initializes the database schema by reading and executing the schema.sql file.
It should be run once when setting up the bot for the first time.
"""

import os
import sys
import logging
from pathlib import Path

import psycopg2

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config import DATABASE_URL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def setup_database() -> None:
    """
    Initialize database with the enhanced schema.

    Raises:
        Exception: If database setup fails
    """
    logger.info("🔧 Setting up Enterprise Telegram Bot database...")

    # Find schema file
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    schema_file = project_root / "project_documentation" / "docs" / "schema.sql"

    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_file}")

    # Read schema SQL
    logger.info(f"Reading schema from: {schema_file}")
    with open(schema_file, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    # Connect to database and execute schema
    connection = None
    cursor = None

    try:
        logger.info("Connecting to database...")
        connection = psycopg2.connect(DATABASE_URL)
        cursor = connection.cursor()

        logger.info("Executing schema SQL...")
        cursor.execute(schema_sql)

        # Verify tables were created
        cursor.execute(
            """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
              AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """
        )
        tables = cursor.fetchall()

        logger.info("Created tables:")
        for table in tables:
            logger.info(f"  ✅ {table[0]}")

        # Verify ENUM types were created
        cursor.execute(
            """
            SELECT typname 
            FROM pg_type 
            WHERE typtype = 'e'
            ORDER BY typname;
        """
        )
        enums = cursor.fetchall()

        logger.info("Created ENUM types:")
        for enum in enums:
            logger.info(f"  ✅ {enum[0]}")

        # Verify initial data
        cursor.execute("SELECT COUNT(*) FROM tiers;")
        tier_count = cursor.fetchone()[0]
        logger.info(f"Initial tiers created: {tier_count}")

        cursor.execute("SELECT COUNT(*) FROM bot_settings;")
        settings_count = cursor.fetchone()[0]
        logger.info(f"Initial bot settings created: {settings_count}")

        connection.commit()
        logger.info("✅ Database schema setup completed successfully")

        # Insert sample products for testing
        logger.info("🛍️ Adding sample products...")
        sample_products = [
            {
                "product_type": "credits",
                "name": "10 Credits Pack",
                "description": "Perfect for light usage - 10 message credits",
                "stripe_price_id": "price_10credits_test",  # You'll need to create these in Stripe
                "amount": 10,
                "price_usd_cents": 500,  # $5.00
                "sort_order": 1,
            },
            {
                "product_type": "credits",
                "name": "25 Credits Pack",
                "description": "Great value - 25 message credits",
                "stripe_price_id": "price_25credits_test",
                "amount": 25,
                "price_usd_cents": 1000,  # $10.00
                "sort_order": 2,
            },
            {
                "product_type": "credits",
                "name": "50 Credits Pack",
                "description": "Best value - 50 message credits",
                "stripe_price_id": "price_50credits_test",
                "amount": 50,
                "price_usd_cents": 1800,  # $18.00
                "sort_order": 3,
            },
            {
                "product_type": "time",
                "name": "7 Days Access",
                "description": "Unlimited messages for 7 days",
                "stripe_price_id": "price_7days_test",
                "amount": 7,
                "price_usd_cents": 1500,  # $15.00
                "sort_order": 4,
            },
            {
                "product_type": "time",
                "name": "30 Days Access",
                "description": "Unlimited messages for 30 days",
                "stripe_price_id": "price_30days_test",
                "amount": 30,
                "price_usd_cents": 5000,  # $50.00
                "sort_order": 5,
            },
        ]

        for product in sample_products:
            insert_query = """
                INSERT INTO products (product_type, name, description, stripe_price_id, amount, price_usd_cents, sort_order, is_active)
                VALUES (%(product_type)s, %(name)s, %(description)s, %(stripe_price_id)s, %(amount)s, %(price_usd_cents)s, %(sort_order)s, true)
                ON CONFLICT (stripe_price_id) DO NOTHING;
            """
            cursor.execute(insert_query, product)

        logger.info(f"✅ Added {len(sample_products)} sample products")

        connection.commit()
        logger.info(
            "✅ Database setup and sample data insertion completed successfully"
        )

    except psycopg2.Error as e:
        logger.error(f"❌ PostgreSQL error during setup: {e}")
        if connection:
            connection.rollback()
        raise

    except Exception as e:
        logger.error(f"❌ Database setup failed: {e}")
        if connection:
            connection.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
            logger.info("Database connection closed")


def verify_database() -> None:
    """
    Verify database is properly set up.
    """
    logger.info("🔍 Verifying database setup...")

    connection = None
    cursor = None

    try:
        connection = psycopg2.connect(DATABASE_URL)
        cursor = connection.cursor()

        # Check essential tables exist
        essential_tables = [
            "users",
            "products",
            "conversations",
            "transactions",
            "tiers",
            "bot_settings",
        ]

        for table in essential_tables:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                      AND table_name = %s
                );
            """,
                (table,),
            )

            if not cursor.fetchone()[0]:
                raise Exception(f"Essential table '{table}' not found")

            logger.info(f"  ✅ Table '{table}' exists")

        # Check views exist
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.views 
                WHERE table_schema = 'public' 
                  AND table_name = 'user_dashboard_view'
            );
        """
        )

        if cursor.fetchone()[0]:
            logger.info("  ✅ View 'user_dashboard_view' exists")
        else:
            logger.warning("  ⚠️ View 'user_dashboard_view' not found")

        # Check functions exist
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.routines 
                WHERE routine_schema = 'public' 
                  AND routine_name = 'get_bot_setting'
            );
        """
        )

        if cursor.fetchone()[0]:
            logger.info("  ✅ Function 'get_bot_setting' exists")

        logger.info("✅ Database verification completed successfully!")

    except Exception as e:
        logger.error(f"❌ Database verification failed: {e}")
        raise

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


if __name__ == "__main__":
    try:
        setup_database()
        verify_database()

        print("\n" + "=" * 60)
        print("🎉 Enterprise Telegram Bot Database Setup Complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Set up your environment variables in .env")
        print("2. Configure your Telegram bot token")
        print("3. Set up Stripe API keys")
        print("4. Start the bot application")
        print("\nFor help, see the project documentation in docs/")

    except Exception as e:
        logger.error(f"Setup failed: {e}")
        sys.exit(1)
