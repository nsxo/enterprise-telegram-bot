"""
Enterprise Telegram Bot - Database Module

This module handles all database connections and operations using ThreadedConnectionPool
for thread-safe operations in a Gunicorn multi-worker environment.
"""

import contextlib
import logging
import uuid
from typing import Optional, Dict, List, Any, Union
import psycopg2
import psycopg2.pool
import psycopg2.extras
from psycopg2.extras import RealDictCursor

from src.config import DATABASE_URL, DB_POOL_MIN_CONN, get_db_pool_size

logger = logging.getLogger(__name__)

# Global connection pool
connection_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None


class DatabaseError(Exception):
    """Raised when database operations fail."""

    pass


def init_connection_pool(min_conn: int = None, max_conn: int = None) -> None:
    """
    Initialize PostgreSQL connection pool.
    CRITICAL: Uses ThreadedConnectionPool for multi-threaded Gunicorn environment.

    Args:
        min_conn: Minimum connections in pool
        max_conn: Maximum connections in pool
    """
    global connection_pool

    if connection_pool is not None:
        logger.warning("Connection pool already initialized")
        return

    min_conn = min_conn or DB_POOL_MIN_CONN
    max_conn = max_conn or get_db_pool_size()

    try:
        # MUST use ThreadedConnectionPool for production with Gunicorn workers
        # SimpleConnectionPool is NOT thread-safe and will cause race conditions
        connection_pool = psycopg2.pool.ThreadedConnectionPool(
            min_conn,
            max_conn,
            DATABASE_URL,
            cursor_factory=RealDictCursor,  # Return dict-like results
        )
        logger.info(
            f"ThreadedConnectionPool created with {min_conn}-{max_conn} connections"
        )
    except Exception as e:
        logger.error(f"Error creating connection pool: {e}")
        raise DatabaseError(f"Failed to initialize connection pool: {e}")


def close_connection_pool() -> None:
    """Close all connections in the pool."""
    global connection_pool
    if connection_pool:
        connection_pool.closeall()
        connection_pool = None
        logger.info("Connection pool closed")


@contextlib.contextmanager
def get_db_connection():
    """
    Context manager to get a connection from the pool.
    Ensures connections are properly returned to the pool.
    """
    if connection_pool is None:
        init_connection_pool()

    conn = None
    try:
        conn = connection_pool.getconn()
        if conn is None:
            raise DatabaseError("Failed to get connection from pool")
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise DatabaseError(f"Database operation failed: {e}")
    finally:
        if conn:
            connection_pool.putconn(conn)


def execute_query(
    query: str,
    params: Optional[tuple] = None,
    fetch_one: bool = False,
    fetch_all: bool = False,
) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]], int]]:
    """
    Master function for all database operations.
    Handles connection acquisition, execution, and cleanup.

    Args:
        query: SQL query to execute
        params: Parameters for the query
        fetch_one: Return single row
        fetch_all: Return all rows

    Returns:
        Query result or row count
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)

            if fetch_one:
                return cursor.fetchone()
            elif fetch_all:
                return cursor.fetchall()
            else:
                return cursor.rowcount


# =============================================================================
# USER MANAGEMENT FUNCTIONS
# =============================================================================


def get_or_create_user(
    telegram_id: int,
    username: Optional[str],
    first_name: str,
    last_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get existing user or create new one (upsert operation).
    Uses INSERT ... ON CONFLICT for atomic operation.

    Args:
        telegram_id: User's Telegram ID
        username: User's username (can be None)
        first_name: User's first name
        last_name: User's last name (optional)

    Returns:
        User record as dictionary
    """
    query = """
        INSERT INTO users (telegram_id, username, first_name, last_name, created_at, updated_at)
        VALUES (%s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT (telegram_id) 
        DO UPDATE SET 
            username = EXCLUDED.username,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            updated_at = NOW()
        RETURNING *;
    """
    return execute_query(
        query, (telegram_id, username, first_name, last_name), fetch_one=True
    )


def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Get user by Telegram ID."""
    query = "SELECT * FROM users WHERE telegram_id = %s"
    return execute_query(query, (telegram_id,), fetch_one=True)


def update_user_credits(
    telegram_id: int, credit_amount: int
) -> Optional[Dict[str, Any]]:
    """
    Add credits to user account.

    Args:
        telegram_id: User's Telegram ID
        credit_amount: Credits to add (can be negative to subtract)

    Returns:
        Updated user record
    """
    query = """
        UPDATE users 
        SET message_credits = message_credits + %s, updated_at = NOW()
        WHERE telegram_id = %s
        RETURNING message_credits, telegram_id;
    """
    return execute_query(query, (credit_amount, telegram_id), fetch_one=True)


def update_user_stripe_customer(telegram_id: int, stripe_customer_id: str) -> None:
    """Link Stripe customer ID to user."""
    query = """
        UPDATE users 
        SET stripe_customer_id = %s, updated_at = NOW()
        WHERE telegram_id = %s;
    """
    execute_query(query, (stripe_customer_id, telegram_id))


def update_user_tier(telegram_id: int, tier_id: int) -> None:
    """Update user's tier."""
    query = """
        UPDATE users 
        SET tier_id = %s, updated_at = NOW()
        WHERE telegram_id = %s;
    """
    execute_query(query, (tier_id, telegram_id))


def update_user_time_access(user_id: int, expires_at: Any) -> bool:
    """
    Update user's time-based access expiration.

    Args:
        user_id: User's Telegram ID
        expires_at: DateTime when time access expires

    Returns:
        True if successful
    """
    query = """
        UPDATE users 
        SET 
            time_credits_expires_at = %s,
            updated_at = NOW()
        WHERE telegram_id = %s
    """

    try:
        execute_query(query, (expires_at, user_id))
        logger.info(f"✅ Updated time access for user {user_id} until {expires_at}")
        return True
    except Exception as e:
        logger.error(f"Failed to update time access for user {user_id}: {e}")
        return False


# =============================================================================
# CONVERSATION MANAGEMENT FUNCTIONS
# =============================================================================


def create_conversation_topic(
    user_id: int,
    admin_group_id: int,
    topic_id: int,
    pinned_message_id: Optional[int] = None,
) -> None:
    """Create new conversation topic for user."""
    query = """
        INSERT INTO conversations (user_id, admin_group_id, topic_id, pinned_message_id, last_user_message_at, created_at)
        VALUES (%s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT (user_id, admin_group_id) 
        DO UPDATE SET 
            topic_id = EXCLUDED.topic_id,
            pinned_message_id = EXCLUDED.pinned_message_id,
            last_user_message_at = NOW(),
            status = 'open';
    """
    execute_query(query, (user_id, admin_group_id, topic_id, pinned_message_id))


def delete_conversation_topic(user_id: int, admin_group_id: int) -> None:
    """Delete conversation topic record when topic is manually deleted."""
    query = """
        DELETE FROM conversations 
        WHERE user_id = %s AND admin_group_id = %s
    """
    execute_query(query, (user_id, admin_group_id))
    logger.info(f"Deleted conversation record for user {user_id}")


def get_user_id_from_topic(topic_id: int, admin_group_id: int) -> Optional[int]:
    """Get user ID associated with topic."""
    query = """
        SELECT user_id FROM conversations 
        WHERE topic_id = %s AND admin_group_id = %s AND status = 'open'
    """
    result = execute_query(query, (topic_id, admin_group_id), fetch_one=True)
    return result["user_id"] if result else None


def get_topic_id_from_user(user_id: int, admin_group_id: int) -> Optional[int]:
    """Get topic ID for user."""
    query = """
        SELECT topic_id FROM conversations 
        WHERE user_id = %s AND admin_group_id = %s AND status = 'open'
    """
    result = execute_query(query, (user_id, admin_group_id), fetch_one=True)
    return result["topic_id"] if result else None


def update_last_message_time(user_id: int, admin_group_id: int) -> None:
    """Update last message timestamp for user."""
    query = """
        UPDATE conversations 
        SET last_user_message_at = NOW()
        WHERE user_id = %s AND admin_group_id = %s AND status = 'open';
    """
    execute_query(query, (user_id, admin_group_id))


# =============================================================================
# TRANSACTION MANAGEMENT
# =============================================================================


def log_transaction(
    user_id: int,
    product_id: Optional[int],
    stripe_charge_id: Optional[str],
    stripe_session_id: Optional[str],
    idempotency_key: str,
    amount_cents: int,
    credits_granted: int = 0,
    time_granted_seconds: int = 0,
    status: str = "pending",
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Log transaction for business intelligence."""
    query = """
        INSERT INTO transactions 
        (user_id, product_id, stripe_charge_id, stripe_session_id, idempotency_key,
         amount_paid_usd_cents, credits_granted, time_granted_seconds, status, description, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        RETURNING id, created_at;
    """
    return execute_query(
        query,
        (
            user_id,
            product_id,
            stripe_charge_id,
            stripe_session_id,
            idempotency_key,
            amount_cents,
            credits_granted,
            time_granted_seconds,
            status,
            description,
        ),
        fetch_one=True,
    )


def update_transaction_status(
    transaction_id: str, status: str, stripe_charge_id: Optional[str] = None
) -> None:
    """Update transaction status."""
    if stripe_charge_id:
        query = """
            UPDATE transactions 
            SET status = %s, stripe_charge_id = %s
            WHERE id = %s;
        """
        execute_query(query, (status, stripe_charge_id, transaction_id))
    else:
        query = """
            UPDATE transactions 
            SET status = %s
            WHERE id = %s;
        """
        execute_query(query, (status, transaction_id))


def get_user_transactions(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get user's transaction history.

    Args:
        user_id: User's Telegram ID
        limit: Maximum number of transactions to return

    Returns:
        List of transaction dictionaries
    """
    query = """
        SELECT 
            id,
            user_id,
            product_id,
            stripe_charge_id,
            stripe_session_id,
            idempotency_key,
            amount_paid_usd_cents,
            credits_granted,
            time_granted_seconds,
            status,
            description,
            created_at
        FROM transactions 
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT %s
    """

    result = execute_query(query, (user_id, limit), fetch_all=True)
    return result if result else []


def get_user_payment_stats(user_id: int) -> Dict[str, Any]:
    """
    Get comprehensive payment statistics for a user.

    Args:
        user_id: User's Telegram ID

    Returns:
        Dictionary with payment statistics
    """
    query = """
        SELECT 
            COUNT(*) as total_transactions,
            COUNT(*) FILTER (WHERE status = 'completed') as successful_transactions,
            COUNT(*) FILTER (WHERE status = 'failed') as failed_transactions,
            COUNT(*) FILTER (WHERE status = 'pending') as pending_transactions,
            COALESCE(SUM(amount_paid_usd_cents) FILTER (WHERE status = 'completed'), 0) as total_spent_cents,
            COALESCE(SUM(credits_granted) FILTER (WHERE status = 'completed'), 0) as total_credits_purchased,
            MIN(created_at) FILTER (WHERE status = 'completed') as first_purchase_date,
            MAX(created_at) FILTER (WHERE status = 'completed') as last_purchase_date
        FROM transactions 
        WHERE user_id = %s
    """

    result = execute_query(query, (user_id,), fetch_one=True)
    return (
        result
        if result
        else {
            "total_transactions": 0,
            "successful_transactions": 0,
            "failed_transactions": 0,
            "pending_transactions": 0,
            "total_spent_cents": 0,
            "total_credits_purchased": 0,
            "first_purchase_date": None,
            "last_purchase_date": None,
        }
    )


def enable_auto_recharge(
    user_id: int, product_id: int, trigger_threshold: int = 5
) -> bool:
    """
    Enable auto-recharge for a user.

    Args:
        user_id: User's Telegram ID
        product_id: Product ID to auto-purchase
        trigger_threshold: Credit level that triggers auto-recharge

    Returns:
        True if successful
    """
    query = """
        UPDATE users 
        SET 
            auto_recharge_enabled = TRUE,
            auto_recharge_product_id = %s,
            auto_recharge_threshold = %s,
            updated_at = NOW()
        WHERE telegram_id = %s
    """

    try:
        execute_query(query, (product_id, trigger_threshold, user_id))
        logger.info(
            f"✅ Enabled auto-recharge for user {user_id}, product {product_id}, threshold {trigger_threshold}"
        )
        return True
    except Exception as e:
        logger.error(f"Failed to enable auto-recharge for user {user_id}: {e}")
        return False


def disable_auto_recharge(user_id: int) -> bool:
    """
    Disable auto-recharge for a user.

    Args:
        user_id: User's Telegram ID

    Returns:
        True if successful
    """
    query = """
        UPDATE users 
        SET 
            auto_recharge_enabled = FALSE,
            auto_recharge_product_id = NULL,
            auto_recharge_threshold = NULL,
            updated_at = NOW()
        WHERE telegram_id = %s
    """

    try:
        execute_query(query, (user_id,))
        logger.info(f"✅ Disabled auto-recharge for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to disable auto-recharge for user {user_id}: {e}")
        return False


def get_users_needing_auto_recharge() -> List[Dict[str, Any]]:
    """
    Get users who need auto-recharge triggered.

    Returns:
        List of users with auto-recharge enabled and low credits
    """
    query = """
        SELECT 
            u.telegram_id,
            u.message_credits,
            u.auto_recharge_product_id,
            u.auto_recharge_threshold,
            u.stripe_customer_id,
            p.stripe_price_id,
            p.name as product_name,
            p.price_usd_cents
        FROM users u
        JOIN products p ON u.auto_recharge_product_id = p.id
        WHERE 
            u.auto_recharge_enabled = TRUE
            AND u.message_credits <= COALESCE(u.auto_recharge_threshold, 5)
            AND u.stripe_customer_id IS NOT NULL
            AND p.is_active = TRUE
    """

    result = execute_query(query, fetch_all=True)
    return result if result else []


def check_failed_payments(user_id: int, days: int = 7) -> int:
    """
    Check how many payments have failed for a user in recent days.

    Args:
        user_id: User's Telegram ID
        days: Number of days to check back

    Returns:
        Number of failed payments
    """
    query = """
        SELECT COUNT(*) as failed_count
        FROM transactions 
        WHERE user_id = %s 
        AND status = 'failed'
        AND created_at >= NOW() - INTERVAL '%s days'
    """

    result = execute_query(query, (user_id, days), fetch_one=True)
    return result.get("failed_count", 0) if result else 0


# =============================================================================
# PRODUCT MANAGEMENT
# =============================================================================


def get_active_products() -> List[Dict[str, Any]]:
    """Get all active products."""
    query = """
        SELECT * FROM products 
        WHERE is_active = true 
        ORDER BY sort_order, product_type, price_usd_cents;
    """
    return execute_query(query, fetch_all=True)


def get_products_by_type(product_type: str) -> List[Dict[str, Any]]:
    """Get active products by type (credits or time)."""
    query = """
        SELECT * FROM products 
        WHERE is_active = true AND product_type = %s
        ORDER BY sort_order, price_usd_cents;
    """
    return execute_query(query, (product_type,), fetch_all=True)


def get_product_by_stripe_price_id(stripe_price_id: str) -> Optional[Dict[str, Any]]:
    """Get product by Stripe price ID."""
    query = "SELECT * FROM products WHERE stripe_price_id = %s AND is_active = true"
    return execute_query(query, (stripe_price_id,), fetch_one=True)


def get_product_by_credit_amount(credit_amount: int) -> Optional[Dict[str, Any]]:
    """
    Get a product by the number of credits it grants.

    Args:
        credit_amount: The number of credits.

    Returns:
        A dictionary representing the product, or None if not found.
    """
    query = """
        SELECT * FROM products
        WHERE credits_granted = %s AND product_type = 'credits'
        ORDER BY price_usd ASC
        LIMIT 1
    """
    return execute_query(query, (credit_amount,), fetch_one=True)


# =============================================================================
# BOT SETTINGS MANAGEMENT
# =============================================================================


def get_bot_setting(key: str) -> Optional[str]:
    """Get bot setting value."""
    query = "SELECT value FROM bot_settings WHERE key = %s"
    result = execute_query(query, (key,), fetch_one=True)
    return result["value"] if result else None


def set_bot_setting(key: str, value: str, updated_by: Optional[int] = None) -> None:
    """Set bot setting value."""
    query = """
        INSERT INTO bot_settings (key, value, updated_by, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (key) 
        DO UPDATE SET 
            value = EXCLUDED.value,
            updated_by = EXCLUDED.updated_by,
            updated_at = EXCLUDED.updated_at;
    """
    execute_query(query, (key, value, updated_by))


# =============================================================================
# ANALYTICS & BUSINESS INTELLIGENCE
# =============================================================================


def get_user_dashboard_data(user_id: int) -> Optional[Dict[str, Any]]:
    """Get comprehensive user data for admin dashboard."""
    query = "SELECT * FROM user_dashboard_view WHERE telegram_id = %s;"
    return execute_query(query, (user_id,), fetch_one=True)


def get_revenue_analytics(days: int = 30) -> List[Dict[str, Any]]:
    """Get revenue analytics for specified period."""
    query = """
        SELECT 
            DATE(created_at) as date,
            COUNT(*) as transactions,
            SUM(amount_paid_usd_cents) as revenue_cents,
            COUNT(DISTINCT user_id) as unique_users
        FROM transactions 
        WHERE status = 'completed' 
          AND created_at >= NOW() - INTERVAL '%s days'
        GROUP BY DATE(created_at)
        ORDER BY date DESC;
    """
    return execute_query(query, (days,), fetch_all=True)


def get_revenue_analytics() -> Dict[str, Any]:
    """Get detailed revenue analytics."""
    query = """
    SELECT
        (SELECT COALESCE(SUM(amount_paid_usd_cents), 0) FROM transactions WHERE status = 'completed') / 100.0 AS total_revenue,
        (SELECT COALESCE(SUM(amount_paid_usd_cents), 0) FROM transactions WHERE status = 'completed' AND created_at >= date_trunc('month', NOW())) / 100.0 AS current_month,
        (SELECT COALESCE(SUM(amount_paid_usd_cents), 0) FROM transactions WHERE status = 'completed' AND created_at >= date_trunc('month', NOW() - interval '1 month') AND created_at < date_trunc('month', NOW())) / 100.0 AS last_month,
        (SELECT COUNT(*) FROM transactions) AS total_transactions,
        (SELECT COUNT(*) FROM transactions WHERE status = 'completed') AS successful_payments,
        (SELECT COUNT(*) FROM transactions WHERE status = 'failed') AS failed_payments,
        (SELECT name FROM products ORDER BY (SELECT COUNT(*) FROM transactions WHERE product_id = products.id) DESC LIMIT 1) AS top_product,
        (SELECT COALESCE(AVG(amount_paid_usd_cents), 0) FROM transactions WHERE status = 'completed') / 100.0 AS avg_order_value,
        (SELECT COALESCE(SUM(credits_granted), 0) FROM transactions WHERE status = 'completed') AS total_credits_sold
    """
    return execute_query(query, fetch_one=True)

def get_user_analytics() -> Dict[str, Any]:
    """Get detailed user analytics."""
    query = """
    SELECT
        (SELECT COUNT(*) FROM users) AS total_users,
        (SELECT COUNT(*) FROM users WHERE created_at >= NOW() - interval '1 day') AS new_today,
        (SELECT COUNT(*) FROM users WHERE created_at >= NOW() - interval '7 day') AS new_week,
        (SELECT COUNT(*) FROM users WHERE created_at >= NOW() - interval '30 day') AS new_month,
        (SELECT COUNT(*) FROM users WHERE last_message_at >= NOW() - interval '1 day') AS active_24h,
        (SELECT COUNT(*) FROM users WHERE last_message_at >= NOW() - interval '7 day') AS active_7d,
        (SELECT COUNT(*) FROM users WHERE last_message_at >= NOW() - interval '30 day') AS active_30d,
        (SELECT COALESCE(AVG(total_messages_sent), 0) FROM users) AS avg_messages,
        (SELECT COALESCE(AVG(message_credits), 0) FROM users) AS avg_credits,
        (SELECT COUNT(*) FROM users WHERE total_messages_sent > 100) AS power_users,
        (SELECT COUNT(*) FROM users WHERE is_banned = TRUE) AS banned_users
    """
    return execute_query(query, fetch_one=True)


# =============================================================================
# ANALYTICS FUNCTIONS
# =============================================================================


def get_user_count() -> int:
    """Get total number of users."""
    query = "SELECT COUNT(*) as count FROM users"
    result = execute_query(query, fetch_one=True)
    return result["count"] if result else 0


def get_conversation_count() -> int:
    """Get total number of active conversations."""
    query = "SELECT COUNT(*) as count FROM conversations WHERE status = 'open'"
    result = execute_query(query, fetch_one=True)
    return result["count"] if result else 0


def get_all_products() -> List[Dict[str, Any]]:
    """Get all products."""
    query = """
        SELECT id, product_type, name, description, stripe_price_id, 
               amount, price_usd_cents, is_active, sort_order
        FROM products 
        ORDER BY sort_order ASC, created_at DESC
    """
    return execute_query(query, fetch_all=True)


# =============================================================================
# DATABASE MIGRATIONS
# =============================================================================


def apply_conversation_table_fix() -> None:
    """
    Apply critical fix for conversations table constraint issue.
    This addresses the ON CONFLICT deferrable constraint problem.
    """
    try:
        logger.info("🔧 Applying conversations table constraint fix...")

        # Step 1: Drop any existing problematic constraints
        drop_constraints_queries = [
            "ALTER TABLE conversations DROP CONSTRAINT IF EXISTS conversations_user_id_admin_group_id_status_key",
            "ALTER TABLE conversations DROP CONSTRAINT IF EXISTS conversations_user_id_admin_group_id_key",
            "DROP INDEX IF EXISTS idx_conversations_user_group_open",
        ]

        for query in drop_constraints_queries:
            try:
                execute_query(query)
                logger.info(f"Executed: {query}")
            except Exception as e:
                logger.warning(f"Could not execute {query}: {e}")

        # Step 2: Add the simple constraint we need
        add_constraint_query = """
            ALTER TABLE conversations 
            ADD CONSTRAINT conversations_user_admin_unique 
            UNIQUE (user_id, admin_group_id)
        """
        try:
            execute_query(add_constraint_query)
            logger.info("✅ Added conversations unique constraint")
        except Exception as e:
            if "already exists" in str(e):
                logger.info("✅ Conversations constraint already exists")
            else:
                logger.error(f"Failed to add constraint: {e}")

        # Step 3: Clean up any duplicate conversations (keep the latest)
        cleanup_query = """
            DELETE FROM conversations 
            WHERE id NOT IN (
                SELECT DISTINCT ON (user_id, admin_group_id) id
                FROM conversations 
                ORDER BY user_id, admin_group_id, created_at DESC
            )
        """
        try:
            execute_query(cleanup_query)
            logger.info("✅ Cleaned up duplicate conversations")
        except Exception as e:
            logger.warning(f"Could not clean up duplicates: {e}")

        logger.info("✅ Conversations table constraint fix completed")

    except Exception as e:
        logger.error(f"Failed to apply conversations table fix: {e}")
        # Don't raise - this is a migration, let the app continue


def fix_products_table_schema() -> None:
    """
    Ensure the products table has all required columns.
    This fixes schema mismatches from earlier deployments.
    """
    try:
        logger.info("🔧 Checking and fixing products table schema...")

        # Check what columns exist in products table
        check_columns_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'products' 
            ORDER BY ordinal_position
        """
        existing_columns = execute_query(check_columns_query, fetch_all=True)
        column_names = (
            [col["column_name"] for col in existing_columns] if existing_columns else []
        )

        logger.info(f"Existing products columns: {column_names}")

        # Define required columns and their definitions
        required_columns = {
            "stripe_price_id": "VARCHAR(255) NOT NULL",
            "product_type": "VARCHAR(50) NOT NULL DEFAULT 'credits'",
            "name": "VARCHAR(100) NOT NULL DEFAULT 'Unknown Product'",
            "description": "TEXT",
            "amount": "INT NOT NULL DEFAULT 1",
            "price_usd_cents": "INT NOT NULL DEFAULT 100",
            "sort_order": "INT DEFAULT 0",
            "is_active": "BOOLEAN DEFAULT TRUE",
        }

        # Add missing columns
        for column_name, column_def in required_columns.items():
            if column_name not in column_names:
                try:
                    alter_query = (
                        f"ALTER TABLE products ADD COLUMN {column_name} {column_def}"
                    )
                    execute_query(alter_query)
                    logger.info(f"✅ Added column: {column_name}")
                except Exception as e:
                    logger.error(f"Failed to add column {column_name}: {e}")

        # Ensure we have a unique constraint on stripe_price_id
        try:
            unique_constraint_query = """
                ALTER TABLE products 
                ADD CONSTRAINT products_stripe_price_id_unique 
                UNIQUE (stripe_price_id)
            """
            execute_query(unique_constraint_query)
            logger.info("✅ Added stripe_price_id unique constraint")
        except Exception as e:
            if "already exists" in str(e):
                logger.info("✅ stripe_price_id constraint already exists")
            else:
                logger.warning(f"Could not add stripe_price_id constraint: {e}")

        logger.info("✅ Products table schema check completed")

    except Exception as e:
        logger.error(f"Failed to fix products table schema: {e}")


def ensure_sample_products() -> None:
    """
    Ensure sample products exist in database for testing.
    Call this during app startup if no products found.
    """
    try:
        # First fix the schema
        fix_products_table_schema()

        # Check if products already exist
        existing_products = get_active_products()
        if existing_products:
            logger.info(
                f"Found {len(existing_products)} existing products, skipping sample creation"
            )
            return

        logger.info("No products found, creating sample products...")

        sample_products = [
            (
                "credits",
                "10 Credits Pack",
                "Perfect for light usage - 10 message credits",
                "price_10credits_test",
                10,
                500,
                1,
            ),
            (
                "credits",
                "25 Credits Pack",
                "Great value - 25 message credits",
                "price_25credits_test",
                25,
                1000,
                2,
            ),
            (
                "credits",
                "50 Credits Pack",
                "Best value - 50 message credits",
                "price_50credits_test",
                50,
                1800,
                3,
            ),
            (
                "time",
                "7 Days Access",
                "Unlimited messages for 7 days",
                "price_7days_test",
                7,
                1500,
                4,
            ),
            (
                "time",
                "30 Days Access",
                "Unlimited messages for 30 days",
                "price_30days_test",
                30,
                5000,
                5,
            ),
        ]

        query = """
            INSERT INTO products (product_type, name, description, stripe_price_id, 
                                amount, price_usd_cents, sort_order, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, true)
            ON CONFLICT (stripe_price_id) DO NOTHING
        """

        for product_data in sample_products:
            execute_query(query, product_data)

        logger.info(f"✅ Created {len(sample_products)} sample products")

    except Exception as e:
        logger.error(f"Failed to create sample products: {e}")


def apply_database_views_and_functions() -> None:
    """
    Apply database views and functions that are missing from initial deployment.
    This ensures the user_dashboard_view and other schema objects are created.
    """
    try:
        logger.info("🔧 Applying database views and functions...")

        # Create user_dashboard_view
        user_dashboard_view_sql = """
        CREATE OR REPLACE VIEW user_dashboard_view AS
        SELECT
            u.telegram_id,
            u.username,
            u.first_name,
            u.message_credits,
            u.time_credits_expires_at,
            t.name as tier_name,
            t.permissions as tier_permissions,
            u.created_at as user_since,
            u.auto_recharge_enabled,
            COALESCE(SUM(tr.amount_paid_usd_cents) FILTER (WHERE tr.status = 'completed'), 0) as total_spent_cents,
            COUNT(tr.id) FILTER (WHERE tr.status = 'completed') as total_purchases,
            c.topic_id,
            c.last_user_message_at,
            c.status as conversation_status
        FROM
            users u
        LEFT JOIN
            tiers t ON u.tier_id = t.id
        LEFT JOIN
            transactions tr ON u.telegram_id = tr.user_id
        LEFT JOIN
            conversations c ON u.telegram_id = c.user_id AND c.status = 'open'
        GROUP BY
            u.telegram_id, u.username, u.first_name, u.message_credits, 
            u.time_credits_expires_at, t.name, t.permissions, u.created_at,
            u.auto_recharge_enabled, c.topic_id, c.last_user_message_at, c.status;
        """

        execute_query(user_dashboard_view_sql)
        logger.info("✅ Created/updated user_dashboard_view")

        # Create revenue_analytics view
        revenue_analytics_view_sql = """
        CREATE OR REPLACE VIEW revenue_analytics AS
        SELECT
            DATE(tr.created_at) as date,
            COUNT(*) as transaction_count,
            SUM(tr.amount_paid_usd_cents) as revenue_cents,
            COUNT(DISTINCT tr.user_id) as unique_customers,
            AVG(tr.amount_paid_usd_cents) as avg_transaction_value
        FROM
            transactions tr
        WHERE
            tr.status = 'completed'
            AND tr.created_at >= NOW() - INTERVAL '90 days'
        GROUP BY
            DATE(tr.created_at)
        ORDER BY
            date DESC;
        """

        execute_query(revenue_analytics_view_sql)
        logger.info("✅ Created/updated revenue_analytics view")

        # Create bot settings functions
        get_bot_setting_function_sql = """
        CREATE OR REPLACE FUNCTION get_bot_setting(setting_key VARCHAR)
        RETURNS TEXT AS $$
        DECLARE
            setting_value TEXT;
        BEGIN
            SELECT value INTO setting_value 
            FROM bot_settings 
            WHERE key = setting_key;
            
            RETURN setting_value;
        END;
        $$ LANGUAGE plpgsql;
        """

        execute_query(get_bot_setting_function_sql)
        logger.info("✅ Created/updated get_bot_setting function")

        set_bot_setting_function_sql = """
        CREATE OR REPLACE FUNCTION set_bot_setting(setting_key VARCHAR, setting_value TEXT, updated_by_user BIGINT DEFAULT NULL)
        RETURNS VOID AS $$
        BEGIN
            INSERT INTO bot_settings (key, value, updated_by, updated_at)
            VALUES (setting_key, setting_value, updated_by_user, NOW())
            ON CONFLICT (key) 
            DO UPDATE SET 
                value = EXCLUDED.value,
                updated_by = EXCLUDED.updated_by,
                updated_at = EXCLUDED.updated_at;
        END;
        $$ LANGUAGE plpgsql;
        """

        execute_query(set_bot_setting_function_sql)
        logger.info("✅ Created/updated set_bot_setting function")

        logger.info("✅ Database views and functions applied successfully")

    except Exception as e:
        logger.error(f"Failed to apply database views and functions: {e}")
        # Don't raise - this is a migration, let the app continue


def apply_enhanced_ux_migration() -> None:
    """
    Apply database migration for enhanced UX features.
    Adds new columns and bot settings for tutorial, progress bars, and quick buy.
    """
    logger.info("🔧 Applying enhanced UX migration...")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:

                # STEP 1: Fix bot_settings table schema if needed
                try:
                    # Check if value_type column exists
                    cursor.execute(
                        """
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'bot_settings' AND column_name = 'value_type'
                    """
                    )
                    has_value_type = cursor.fetchone() is not None

                    if not has_value_type:
                        logger.info(
                            "Adding missing value_type column to bot_settings table..."
                        )
                        cursor.execute(
                            """
                            ALTER TABLE bot_settings 
                            ADD COLUMN value_type VARCHAR(50) DEFAULT 'string'
                        """
                        )
                        logger.info("✅ Added value_type column to bot_settings")

                    # Ensure updated_by column exists
                    cursor.execute(
                        """
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'bot_settings' AND column_name = 'updated_by'
                    """
                    )
                    has_updated_by = cursor.fetchone() is not None

                    if not has_updated_by:
                        cursor.execute(
                            """
                            ALTER TABLE bot_settings 
                            ADD COLUMN updated_by BIGINT
                        """
                        )
                        logger.info("✅ Added updated_by column to bot_settings")

                except Exception as e:
                    logger.error(f"Error fixing bot_settings schema: {e}")

                # STEP 2: Add new columns to users table (if they don't exist)
                new_columns = [
                    ("tutorial_completed", "BOOLEAN DEFAULT FALSE"),
                    ("tutorial_step", "INTEGER DEFAULT 0"),
                    ("is_new_user", "BOOLEAN DEFAULT TRUE"),
                    ("total_messages_sent", "INTEGER DEFAULT 0"),
                    ("last_low_credit_warning_at", "TIMESTAMPTZ"),
                ]

                for column_name, column_def in new_columns:
                    try:
                        # Check if column exists first
                        cursor.execute(
                            """
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name = 'users' AND column_name = %s
                        """,
                            (column_name,),
                        )

                        if not cursor.fetchone():
                            cursor.execute(
                                f"""
                                ALTER TABLE users 
                                ADD COLUMN {column_name} {column_def}
                            """
                            )
                            logger.info(f"✅ Added column: users.{column_name}")
                        else:
                            logger.info(f"✅ Column users.{column_name} already exists")
                    except Exception as e:
                        logger.warning(f"Error adding column {column_name}: {e}")

                # STEP 3: Add new bot settings (if they don't exist)
                new_settings = [
                    # Enhanced Welcome System
                    (
                        "new_user_free_credits",
                        "3",
                        "Free credits given to new users",
                        "integer",
                    ),
                    (
                        "welcome_message_new",
                        "Welcome, {first_name}! 🎉\n\nYou've received {free_credits} FREE credits to get started! 🎁\n\n✨ What can I help you with today?",
                        "Welcome message for new users",
                        "string",
                    ),
                    (
                        "welcome_message_returning",
                        "Welcome back, {first_name}! 👋\n\n💰 Your balance: {credits} credits",
                        "Welcome message for returning users",
                        "string",
                    ),
                    # Tutorial System
                    (
                        "tutorial_enabled",
                        "true",
                        "Enable interactive tutorial for new users",
                        "boolean",
                    ),
                    (
                        "tutorial_completion_bonus",
                        "2",
                        "Bonus credits for completing tutorial",
                        "integer",
                    ),
                    # Progress Bar Settings
                    (
                        "progress_bar_max_credits",
                        "100",
                        "Maximum credits for 100% progress bar display",
                        "integer",
                    ),
                    (
                        "balance_low_threshold",
                        "5",
                        "Credits threshold for low balance warning",
                        "integer",
                    ),
                    (
                        "balance_critical_threshold",
                        "2",
                        "Credits threshold for critical balance warning",
                        "integer",
                    ),
                    # Quick Buy Settings
                    (
                        "quick_buy_enabled",
                        "true",
                        "Enable quick buy buttons for low credit situations",
                        "boolean",
                    ),
                    (
                        "quick_buy_trigger_threshold",
                        "5",
                        "Show quick buy options when credits below this",
                        "integer",
                    ),
                    (
                        "low_credit_warning_message",
                        "Running low on credits! 💡 Quick top-up options below:",
                        "Message shown with quick buy buttons",
                        "string",
                    ),
                ]

                # Insert settings with proper error handling
                settings_added = 0
                for key, value, description, value_type in new_settings:
                    try:
                        cursor.execute(
                            """
                            INSERT INTO bot_settings (key, value, description, value_type)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (key) DO NOTHING
                        """,
                            (key, value, description, value_type),
                        )
                        if cursor.rowcount > 0:
                            settings_added += 1
                    except Exception:
                        # Try without value_type if it still doesn't exist
                        try:
                            cursor.execute(
                                """
                                INSERT INTO bot_settings (key, value, description)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (key) DO NOTHING
                            """,
                                (key, value, description),
                            )
                            if cursor.rowcount > 0:
                                settings_added += 1
                        except Exception as e2:
                            logger.warning(f"Could not add setting {key}: {e2}")

                logger.info(f"✅ Added {settings_added} bot settings")

                # STEP 4: Update existing users to have proper defaults (with error handling)
                try:
                    cursor.execute(
                        """
                        UPDATE users 
                        SET 
                            tutorial_completed = COALESCE(tutorial_completed, FALSE),
                            tutorial_step = COALESCE(tutorial_step, 0),
                            is_new_user = COALESCE(is_new_user, 
                                CASE 
                                    WHEN message_credits > 0 THEN FALSE 
                                    ELSE TRUE 
                                END),
                            total_messages_sent = COALESCE(total_messages_sent, 0)
                        WHERE tutorial_completed IS NULL 
                           OR tutorial_step IS NULL 
                           OR is_new_user IS NULL
                           OR total_messages_sent IS NULL
                    """
                    )

                    updated_users = cursor.rowcount
                    if updated_users > 0:
                        logger.info(
                            f"✅ Updated {updated_users} existing users with new defaults"
                        )

                except Exception as e:
                    logger.warning(f"Could not update existing users: {e}")

                # STEP 5: Commit all changes
                conn.commit()
                logger.info("✅ Enhanced UX migration completed successfully")

    except Exception as e:
        logger.error(f"❌ Enhanced UX migration failed: {e}")
        # Don't raise - let the app continue with whatever state it's in


# =============================================================================
# ENHANCED USER EXPERIENCE FUNCTIONS
# =============================================================================


def is_new_user(telegram_id: int) -> bool:
    """
    Check if user is a new user (hasn't received welcome credits yet).

    Args:
        telegram_id: User's Telegram ID

    Returns:
        True if user is new, False otherwise
    """
    try:
        query = """
            SELECT is_new_user, message_credits, total_messages_sent 
            FROM users 
            WHERE telegram_id = %s
        """
        result = execute_query(query, (telegram_id,), fetch_one=True)
    except Exception:
        # Fallback if columns don't exist yet
        query = """
            SELECT message_credits 
            FROM users 
            WHERE telegram_id = %s
        """
        result = execute_query(query, (telegram_id,), fetch_one=True)
        if not result:
            return True
        # Consider user new if they have no credits and haven't made purchases
        return result.get("message_credits", 0) == 0 and not has_user_made_purchases(
            telegram_id
        )

    if not result:
        return True  # User doesn't exist, definitely new

    # User is new if flagged as new and has no message history
    # and no purchased credits
    return (
        result.get("is_new_user", True)
        and result.get("total_messages_sent", 0) == 0
        and not has_user_made_purchases(telegram_id)
    )


def mark_user_as_not_new(telegram_id: int) -> None:
    """
    Mark user as no longer new (after welcome credits given).

    Args:
        telegram_id: User's Telegram ID
    """
    try:
        query = """
            UPDATE users 
            SET is_new_user = FALSE, updated_at = NOW()
            WHERE telegram_id = %s
        """
        execute_query(query, (telegram_id,))
    except Exception:
        # Column doesn't exist yet, skip this operation
        pass


def get_user_tutorial_state(telegram_id: int) -> Dict[str, Any]:
    """
    Get user's tutorial progress.

    Args:
        telegram_id: User's Telegram ID

    Returns:
        Dictionary with tutorial_completed, tutorial_step
    """
    try:
        query = """
            SELECT tutorial_completed, tutorial_step 
            FROM users 
            WHERE telegram_id = %s
        """
        result = execute_query(query, (telegram_id,), fetch_one=True)
    except Exception:
        # Fallback if columns don't exist yet
        return {"tutorial_completed": False, "tutorial_step": 0}

    if not result:
        return {"tutorial_completed": False, "tutorial_step": 0}

    return {
        "tutorial_completed": result.get("tutorial_completed", False),
        "tutorial_step": result.get("tutorial_step", 0),
    }


def update_user_tutorial_state(
    telegram_id: int, step: int = None, completed: bool = None
) -> None:
    """
    Update user's tutorial progress.

    Args:
        telegram_id: User's Telegram ID
        step: Tutorial step (optional)
        completed: Whether tutorial is completed (optional)
    """
    updates = []
    params = []

    if step is not None:
        updates.append("tutorial_step = %s")
        params.append(step)

    if completed is not None:
        updates.append("tutorial_completed = %s")
        params.append(completed)

    if not updates:
        return

    updates.append("updated_at = NOW()")
    params.append(telegram_id)

    query = f"""
        UPDATE users 
        SET {', '.join(updates)}
        WHERE telegram_id = %s
    """

    execute_query(query, params)


def increment_user_message_count(telegram_id: int) -> int:
    """
    Increment user's total message count and return new count.

    Args:
        telegram_id: User's Telegram ID

    Returns:
        New total message count
    """
    query = """
        UPDATE users 
        SET total_messages_sent = total_messages_sent + 1, updated_at = NOW()
        WHERE telegram_id = %s
        RETURNING total_messages_sent
    """
    result = execute_query(query, (telegram_id,), fetch_one=True)
    return result.get("total_messages_sent", 0) if result else 0


def should_show_quick_buy_warning(telegram_id: int) -> bool:
    """
    Check if user should see quick buy warning (low credits + not shown recently).

    Args:
        telegram_id: User's Telegram ID

    Returns:
        True if should show warning, False otherwise
    """
    try:
        # Try with new column first
        query = """
            SELECT 
                message_credits,
                last_low_credit_warning_at,
                EXTRACT(EPOCH FROM (NOW() - COALESCE(last_low_credit_warning_at, '2000-01-01'::timestamptz))) / 3600 as hours_since_warning
            FROM users 
            WHERE telegram_id = %s
        """
        result = execute_query(query, (telegram_id,), fetch_one=True)
    except Exception:
        # Fallback if column doesn't exist yet
        query = """
            SELECT 
                message_credits,
                NULL as last_low_credit_warning_at,
                24 as hours_since_warning
            FROM users 
            WHERE telegram_id = %s
        """
        result = execute_query(query, (telegram_id,), fetch_one=True)

    if not result:
        return False

    # Get threshold from settings
    threshold = int(get_bot_setting("quick_buy_trigger_threshold") or "5")

    # Show warning if credits are low and warning not shown in last 24 hours
    return (
        result.get("message_credits", 0) <= threshold
        and result.get("hours_since_warning", 25) >= 24  # 24+ hours since last warning
    )


def mark_low_credit_warning_shown(telegram_id: int) -> None:
    """
    Mark that low credit warning was shown to user.

    Args:
        telegram_id: User's Telegram ID
    """
    query = """
        UPDATE users 
        SET last_low_credit_warning_at = NOW(), updated_at = NOW()
        WHERE telegram_id = %s
    """
    execute_query(query, (telegram_id,))


def has_user_made_purchases(telegram_id: int) -> bool:
    """
    Check if user has made any purchases.

    Args:
        telegram_id: User's Telegram ID

    Returns:
        True if user has made purchases, False otherwise
    """
    query = """
        SELECT COUNT(*) as purchase_count
        FROM transactions 
        WHERE user_id = %s AND status = 'completed'
    """
    result = execute_query(query, (telegram_id,), fetch_one=True)
    return result.get("purchase_count", 0) > 0 if result else False


# =============================================================================
# BROADCAST AND MASS OPERATIONS FUNCTIONS
# =============================================================================


def get_all_user_ids() -> List[int]:
    """
    Get all user IDs for broadcasting.

    Returns:
        List of user Telegram IDs
    """
    query = "SELECT telegram_id FROM users ORDER BY created_at DESC"
    result = execute_query(query, fetch_all=True)
    return [row["telegram_id"] for row in result] if result else []


def get_active_user_ids(days: int = 7) -> List[int]:
    """
    Get IDs of users active within specified days.

    Args:
        days: Number of days to look back for activity

    Returns:
        List of active user Telegram IDs
    """
    query = """
        SELECT telegram_id 
        FROM users 
        WHERE last_message_at >= NOW() - INTERVAL '%s days'
        ORDER BY last_message_at DESC
    """
    result = execute_query(query, (days,), fetch_all=True)
    return [row["telegram_id"] for row in result] if result else []


def get_low_credit_user_ids(threshold: int = 5) -> List[int]:
    """
    Get IDs of users with low credits.

    Args:
        threshold: Credit threshold for "low" credits

    Returns:
        List of low credit user Telegram IDs
    """
    query = """
        SELECT telegram_id 
        FROM users 
        WHERE message_credits <= %s
        ORDER BY message_credits ASC
    """
    result = execute_query(query, (threshold,), fetch_all=True)
    return [row["telegram_id"] for row in result] if result else []


def get_new_user_ids(days: int = 7) -> List[int]:
    """
    Get IDs of new users within specified days.

    Args:
        days: Number of days to look back for new users

    Returns:
        List of new user Telegram IDs
    """
    query = """
        SELECT telegram_id 
        FROM users 
        WHERE created_at >= NOW() - INTERVAL '%s days'
        ORDER BY created_at DESC
    """
    result = execute_query(query, (days,), fetch_all=True)
    return [row["telegram_id"] for row in result] if result else []


def log_broadcast(
    admin_id: int,
    message_text: str,
    target_audience: str,
    user_count: int,
    status: str = "pending",
) -> Dict[str, Any]:
    """
    Log a broadcast operation.

    Args:
        admin_id: Admin user ID who initiated the broadcast
        message_text: The broadcast message content
        target_audience: Description of target audience
        user_count: Number of users targeted
        status: Broadcast status (pending, completed, failed)

    Returns:
        Broadcast log record
    """
    query = """
        INSERT INTO broadcast_logs 
        (admin_id, message_text, target_audience, user_count, status, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        RETURNING id, created_at
    """
    return execute_query(
        query,
        (admin_id, message_text, target_audience, user_count, status),
        fetch_one=True,
    )


def update_broadcast_status(
    broadcast_id: int, status: str, delivered_count: int = 0
) -> None:
    """
    Update broadcast status and delivery count.

    Args:
        broadcast_id: Broadcast log ID
        status: New status (completed, failed, partial)
        delivered_count: Number of messages successfully delivered
    """
    query = """
        UPDATE broadcast_logs 
        SET status = %s, delivered_count = %s, completed_at = NOW()
        WHERE id = %s
    """
    execute_query(query, (status, delivered_count, broadcast_id))


# =============================================================================
# Connection pool will be initialized when Flask app starts
# init_connection_pool() - moved to Flask app factory

# =============================================================================
# MISSING FUNCTIONS FOR MESSAGE ROUTING AND CONVERSATION MANAGEMENT
# =============================================================================


def update_user_last_message(telegram_id: int) -> None:
    """
    Update user's last message timestamp.

    Args:
        telegram_id: User's Telegram ID
    """
    query = """
        UPDATE users 
        SET last_message_at = NOW(), updated_at = NOW()
        WHERE telegram_id = %s
    """
    execute_query(query, (telegram_id,))


def store_message_reference(
    user_message_id: int, admin_message_id: int, user_id: int, topic_id: int
) -> None:
    """
    Store reference between user message and admin forwarded message.

    Args:
        user_message_id: Original user message ID
        admin_message_id: Forwarded message ID in admin group
        user_id: User's Telegram ID
        topic_id: Topic ID in admin group
    """
    query = """
        INSERT INTO message_references 
        (user_message_id, admin_message_id, user_id, topic_id, created_at)
        VALUES (%s, %s, %s, %s, NOW())
        ON CONFLICT (user_message_id, user_id) 
        DO UPDATE SET 
            admin_message_id = EXCLUDED.admin_message_id,
            topic_id = EXCLUDED.topic_id,
            created_at = EXCLUDED.created_at
    """
    execute_query(query, (user_message_id, admin_message_id, user_id, topic_id))


def get_topic_info(admin_group_id: int, topic_id: int) -> Optional[Dict[str, Any]]:
    """
    Get topic information by topic ID.

    Args:
        admin_group_id: Admin group ID
        topic_id: Topic ID

    Returns:
        Topic information dictionary
    """
    query = """
        SELECT 
            user_id,
            topic_id,
            last_user_message_at,
            status,
            created_at
        FROM conversations 
        WHERE admin_group_id = %s AND topic_id = %s
    """
    return execute_query(query, (admin_group_id, topic_id), fetch_one=True)


def archive_conversation(
    user_id: int, admin_group_id: int, reason: str = "User request"
) -> None:
    """
    Archive a conversation.

    Args:
        user_id: User's Telegram ID
        admin_group_id: Admin group ID
        reason: Reason for archiving
    """
    query = """
        UPDATE conversations 
        SET 
            status = 'archived',
            archived_at = NOW(),
            archive_reason = %s
        WHERE user_id = %s AND admin_group_id = %s
    """
    execute_query(query, (reason, user_id, admin_group_id))


def update_conversation_last_message(user_id: int, admin_group_id: int) -> None:
    """
    Update conversation's last message timestamp.

    Args:
        user_id: User's Telegram ID
        admin_group_id: Admin group ID
    """
    query = """
        UPDATE conversations 
        SET last_user_message_at = NOW()
        WHERE user_id = %s AND admin_group_id = %s AND status = 'open'
    """
    execute_query(query, (user_id, admin_group_id))


def update_conversation_unread_count(
    user_id: int, admin_group_id: int, increment: int = 1
) -> None:
    """
    Update unread message count for a conversation.

    Args:
        user_id: User's Telegram ID
        admin_group_id: Admin group ID
        increment: Number to increment unread count by (can be negative to decrement)
    """
    query = """
        UPDATE conversations 
        SET unread_count = GREATEST(0, COALESCE(unread_count, 0) + %s),
            updated_at = NOW()
        WHERE user_id = %s AND admin_group_id = %s
    """
    execute_query(query, (increment, user_id, admin_group_id))


def mark_conversation_as_read(user_id: int, admin_group_id: int) -> None:
    """
    Mark a conversation as read (reset unread count to 0).

    Args:
        user_id: User's Telegram ID
        admin_group_id: Admin group ID
    """
    query = """
        UPDATE conversations 
        SET unread_count = 0,
            last_read_at = NOW(),
            updated_at = NOW()
        WHERE user_id = %s AND admin_group_id = %s
    """
    execute_query(query, (user_id, admin_group_id))


def get_total_unread_count(admin_group_id: int) -> int:
    """
    Get total unread message count across all conversations.

    Args:
        admin_group_id: Admin group ID

    Returns:
        Total unread message count
    """
    query = """
        SELECT COALESCE(SUM(unread_count), 0) as total_unread
        FROM conversations 
        WHERE admin_group_id = %s AND status = 'open'
    """
    result = execute_query(query, (admin_group_id,), fetch_one=True)
    return result.get("total_unread", 0) if result else 0


def get_conversations_with_unread(
    admin_group_id: int, limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Get conversations that have unread messages.

    Args:
        admin_group_id: Admin group ID
        limit: Maximum number of conversations to return

    Returns:
        List of conversation dictionaries with unread counts
    """
    query = """
        SELECT 
            c.user_id,
            c.topic_id,
            c.unread_count,
            c.last_user_message_at,
            c.last_read_at,
            u.first_name,
            u.last_name,
            u.username
        FROM conversations c
        JOIN users u ON c.user_id = u.telegram_id
        WHERE c.admin_group_id = %s 
        AND c.status = 'open' 
        AND c.unread_count > 0
        ORDER BY c.last_user_message_at DESC
        LIMIT %s
    """
    result = execute_query(query, (admin_group_id, limit), fetch_all=True)
    return result if result else []


# =============================================================================
# ADMIN ANALYTICS FUNCTIONS
# =============================================================================


def get_admin_analytics_data() -> Dict[str, Any]:
    """
    Get comprehensive analytics data for admin dashboard.

    Returns:
        Dictionary with various analytics metrics
    """
    try:
        # User statistics
        user_stats_query = """
            SELECT 
                COUNT(*) as total_users,
                             COUNT(*) FILTER (
                 WHERE created_at >= NOW() - INTERVAL '7 days'
             ) as new_users_week,
             COUNT(*) FILTER (
                 WHERE created_at >= NOW() - INTERVAL '30 days'
             ) as new_users_month,
             COUNT(*) FILTER (
                 WHERE last_message_at >= NOW() - INTERVAL '7 days'
             ) as active_users_week,
             COUNT(*) FILTER (
                 WHERE last_message_at >= NOW() - INTERVAL '30 days'
             ) as active_users_month
            FROM users
        """
        user_stats = execute_query(user_stats_query, fetch_one=True)

        # Revenue statistics
        revenue_stats_query = """
            SELECT 
                COUNT(*) as total_transactions,
                COUNT(*) FILTER (WHERE status = 'completed') as successful_transactions,
                             COUNT(*) FILTER (
                 WHERE status = 'completed' AND 
                       created_at >= NOW() - INTERVAL '7 days'
             ) as transactions_week,
             COUNT(*) FILTER (
                 WHERE status = 'completed' AND 
                       created_at >= NOW() - INTERVAL '30 days'
             ) as transactions_month,
             COALESCE(SUM(amount_paid_usd_cents) FILTER (
                 WHERE status = 'completed'
             ), 0) as total_revenue_cents,
             COALESCE(SUM(amount_paid_usd_cents) FILTER (
                 WHERE status = 'completed' AND 
                       created_at >= NOW() - INTERVAL '7 days'
             ), 0) as revenue_week_cents,
             COALESCE(SUM(amount_paid_usd_cents) FILTER (
                 WHERE status = 'completed' AND 
                       created_at >= NOW() - INTERVAL '30 days'
             ), 0) as revenue_month_cents,
             COALESCE(AVG(amount_paid_usd_cents) FILTER (
                 WHERE status = 'completed'
             ), 0) as avg_transaction_value
            FROM transactions
        """
        revenue_stats = execute_query(revenue_stats_query, fetch_one=True)

        # Credit statistics
        credit_stats_query = """
            SELECT 
                COALESCE(SUM(message_credits), 0) as total_credits_in_circulation,
                COALESCE(AVG(message_credits), 0) as avg_user_credits,
                             COUNT(*) FILTER (
                 WHERE message_credits <= 5
             ) as users_low_credits,
             COUNT(*) FILTER (
                 WHERE message_credits = 0
             ) as users_no_credits
            FROM users
        """
        credit_stats = execute_query(credit_stats_query, fetch_one=True)

        # Conversation statistics
        conversation_stats_query = """
            SELECT 
                COUNT(*) as total_conversations,
                             COUNT(*) FILTER (
                 WHERE status = 'open'
             ) as active_conversations,
             COUNT(*) FILTER (
                 WHERE last_user_message_at >= NOW() - INTERVAL '24 hours'
             ) as recent_conversations
            FROM conversations
        """
        conversation_stats = execute_query(conversation_stats_query, fetch_one=True)

        # Product performance
        product_stats_query = """
            SELECT 
                p.name,
                p.product_type,
                COUNT(t.id) as sales_count,
                COALESCE(SUM(t.amount_paid_usd_cents), 0) as revenue_cents
            FROM products p
            LEFT JOIN transactions t ON 
             p.id = t.product_id AND t.status = 'completed'
            WHERE p.is_active = TRUE
            GROUP BY p.id, p.name, p.product_type
            ORDER BY revenue_cents DESC
        """
        product_stats = execute_query(product_stats_query, fetch_all=True)

        return {
            "user_stats": user_stats or {},
            "revenue_stats": revenue_stats or {},
            "credit_stats": credit_stats or {},
            "conversation_stats": conversation_stats or {},
            "product_stats": product_stats or [],
        }

    except Exception as e:
        logger.error(f"Error getting admin analytics data: {e}")
        return {
            "user_stats": {},
            "revenue_stats": {},
            "credit_stats": {},
            "conversation_stats": {},
            "product_stats": [],
        }


def get_daily_revenue_chart_data(days: int = 30) -> List[Dict[str, Any]]:
    """
    Get daily revenue data for charts.

    Args:
        days: Number of days to include

    Returns:
        List of daily revenue data
    """
    query = """
        WITH date_series AS (
            SELECT generate_series(
                (NOW() - INTERVAL '%s days')::date,
                NOW()::date,
                '1 day'::interval
            )::date as date
        )
        SELECT 
            ds.date,
            COALESCE(COUNT(t.id), 0) as transaction_count,
            COALESCE(SUM(t.amount_paid_usd_cents), 0) as revenue_cents,
            COALESCE(COUNT(DISTINCT t.user_id), 0) as unique_customers
        FROM date_series ds
        LEFT JOIN transactions t ON 
            DATE(t.created_at) = ds.date 
            AND t.status = 'completed'
        GROUP BY ds.date
        ORDER BY ds.date ASC
    """

    result = execute_query(query, (days,), fetch_all=True)
    return result if result else []


def get_user_growth_chart_data(days: int = 30) -> List[Dict[str, Any]]:
    """
    Get daily user growth data for charts.

    Args:
        days: Number of days to include

    Returns:
        List of daily user growth data
    """
    query = """
        WITH date_series AS (
            SELECT generate_series(
                (NOW() - INTERVAL '%s days')::date,
                NOW()::date,
                '1 day'::interval
            )::date as date
        )
        SELECT 
            ds.date,
            COALESCE(COUNT(u.id), 0) as new_users,
            (
                SELECT COUNT(*) 
                FROM users 
                WHERE DATE(created_at) <= ds.date
            ) as total_users
        FROM date_series ds
        LEFT JOIN users u ON DATE(u.created_at) = ds.date
        GROUP BY ds.date
        ORDER BY ds.date ASC
    """

    result = execute_query(query, (days,), fetch_all=True)
    return result if result else []


# =============================================================================
# ADMIN USER MANAGEMENT FUNCTIONS
# =============================================================================


def get_all_users(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Get all users with pagination.

    Args:
        limit: Maximum number of users to return
        offset: Number of users to skip

    Returns:
        List of user dictionaries
    """
    query = """
        SELECT 
            telegram_id,
            username,
            first_name,
            last_name,
            message_credits,
            created_at,
            last_message_at,
            auto_recharge_enabled,
            (
                SELECT COUNT(*) 
                FROM transactions 
                WHERE user_id = users.telegram_id AND status = 'completed'
            ) as total_purchases,
            (
                SELECT COALESCE(SUM(amount_paid_usd_cents), 0) 
                FROM transactions 
                WHERE user_id = users.telegram_id AND status = 'completed'
            ) as total_spent_cents
        FROM users
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """

    result = execute_query(query, (limit, offset), fetch_all=True)
    return result if result else []


def search_users(search_term: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Search users by username, first name, or last name.

    Args:
        search_term: Search term
        limit: Maximum number of results

    Returns:
        List of matching user dictionaries
    """
    search_pattern = f"%{search_term}%"

    query = """
        SELECT 
            telegram_id,
            username,
            first_name,
            last_name,
            message_credits,
            created_at,
            last_message_at
        FROM users
        WHERE 
            LOWER(username) LIKE LOWER(%s) OR
            LOWER(first_name) LIKE LOWER(%s) OR
            LOWER(last_name) LIKE LOWER(%s) OR
            CAST(telegram_id AS TEXT) LIKE %s
        ORDER BY 
            CASE 
                WHEN LOWER(username) = LOWER(%s) THEN 1
                WHEN LOWER(first_name) = LOWER(%s) THEN 2
                WHEN CAST(telegram_id AS TEXT) = %s THEN 3
                ELSE 4
            END,
            created_at DESC
        LIMIT %s
    """

    result = execute_query(
        query,
        (
            search_pattern,
            search_pattern,
            search_pattern,
            search_pattern,
            search_term,
            search_term,
            search_term,
            limit,
        ),
        fetch_all=True,
    )
    return result if result else []


def gift_credits_to_user(telegram_id: int, credits: int, gifted_by: int) -> bool:
    """
    Gift credits to a user (admin function).

    Args:
        telegram_id: User's Telegram ID
        credits: Number of credits to gift
        gifted_by: Admin user ID who gifted the credits

    Returns:
        True if successful
    """
    try:
        # Update user credits
        update_user_credits(telegram_id, credits)

        # Log the gift transaction
        query = """
            INSERT INTO transactions 
            (user_id, product_id, stripe_charge_id, stripe_session_id, idempotency_key,
             amount_paid_usd_cents, credits_granted, time_granted_seconds, status, description, created_at)
            VALUES (%s, NULL, NULL, NULL, %s, 0, %s, 0, 'completed', %s, NOW())
        """

        idempotency_key = str(uuid.uuid4())
        description = f"Admin gift: {credits} credits (gifted by admin {gifted_by})"

        execute_query(query, (telegram_id, idempotency_key, credits, description))

        logger.info(
            f"✅ Gifted {credits} credits to user {telegram_id} by admin {gifted_by}"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to gift credits to user {telegram_id}: {e}")
        return False


def ban_user(telegram_id: int, banned_by: int, reason: str = "Admin decision") -> bool:
    """
    Ban a user (admin function).

    Args:
        telegram_id: User's Telegram ID
        banned_by: Admin user ID who banned the user
        reason: Reason for banning

    Returns:
        True if successful
    """
    try:
        query = """
            UPDATE users 
            SET 
                is_banned = TRUE,
                banned_at = NOW(),
                banned_by = %s,
                ban_reason = %s,
                updated_at = NOW()
            WHERE telegram_id = %s
        """

        execute_query(query, (banned_by, reason, telegram_id))

        # Archive any active conversations
        archive_conversation(telegram_id, -1, f"User banned: {reason}")

        logger.info(
            f"✅ Banned user {telegram_id} by admin {banned_by}, " f"reason: {reason}"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to ban user {telegram_id}: {e}")
        return False


def unban_user(telegram_id: int, unbanned_by: int) -> bool:
    """
    Unban a user (admin function).

    Args:
        telegram_id: User's Telegram ID
        unbanned_by: Admin user ID who unbanned the user

    Returns:
        True if successful
    """
    try:
        query = """
            UPDATE users 
            SET 
                is_banned = FALSE,
                banned_at = NULL,
                banned_by = NULL,
                ban_reason = NULL,
                updated_at = NOW()
            WHERE telegram_id = %s
        """

        execute_query(query, (telegram_id,))

        logger.info(f"✅ Unbanned user {telegram_id} by admin {unbanned_by}")
        return True

    except Exception as e:
        logger.error(f"Failed to unban user {telegram_id}: {e}")
        return False


# Import uuid for idempotency keys


def apply_unread_tracking_migration() -> None:
    """
    Add unread message tracking columns to conversations table.
    """
    try:
        logger.info("🔧 Applying unread tracking migration...")

        # Check if columns already exist
        check_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'conversations' 
            AND column_name IN ('unread_count', 'last_read_at')
        """
        existing_columns = execute_query(check_query, fetch_all=True)
        existing_column_names = (
            [col["column_name"] for col in existing_columns] if existing_columns else []
        )

        migrations = []

        # Add unread_count column if it doesn't exist
        if "unread_count" not in existing_column_names:
            migrations.append(
                "ALTER TABLE conversations ADD COLUMN unread_count INTEGER DEFAULT 0 NOT NULL"
            )

        # Add last_read_at column if it doesn't exist
        if "last_read_at" not in existing_column_names:
            migrations.append(
                "ALTER TABLE conversations ADD COLUMN last_read_at TIMESTAMPTZ"
            )

        # Execute migrations
        for migration in migrations:
            try:
                execute_query(migration)
                logger.info(f"✅ Executed: {migration}")
            except Exception as e:
                logger.error(f"Failed to execute {migration}: {e}")

        # Add index for performance
        index_query = """
            CREATE INDEX IF NOT EXISTS idx_conversations_unread 
            ON conversations (admin_group_id, unread_count) 
            WHERE status = 'open' AND unread_count > 0
        """
        try:
            execute_query(index_query)
            logger.info("✅ Added unread tracking index")
        except Exception as e:
            logger.warning(f"Could not add index: {e}")

        logger.info("✅ Unread tracking migration completed")

    except Exception as e:
        logger.error(f"Failed to apply unread tracking migration: {e}")
        # Don't raise - this is a migration, let the app continue
