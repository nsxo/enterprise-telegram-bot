"""
Enterprise Telegram Bot - Database Module

This module handles all database connections and operations using ThreadedConnectionPool
for thread-safe operations in a Gunicorn multi-worker environment.
"""

import logging
import contextlib
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
            cursor_factory=RealDictCursor  # Return dict-like results
        )
        logger.info(f"ThreadedConnectionPool created with {min_conn}-{max_conn} connections")
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
    fetch_all: bool = False
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

def get_or_create_user(telegram_id: int, username: Optional[str], first_name: str, last_name: Optional[str] = None) -> Dict[str, Any]:
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
    return execute_query(query, (telegram_id, username, first_name, last_name), fetch_one=True)


def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Get user by Telegram ID."""
    query = "SELECT * FROM users WHERE telegram_id = %s"
    return execute_query(query, (telegram_id,), fetch_one=True)


def update_user_credits(telegram_id: int, credit_amount: int) -> Optional[Dict[str, Any]]:
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


# =============================================================================
# CONVERSATION MANAGEMENT FUNCTIONS
# =============================================================================

def create_conversation_topic(user_id: int, admin_group_id: int, topic_id: int, pinned_message_id: Optional[int] = None) -> None:
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
    return result['user_id'] if result else None


def get_topic_id_from_user(user_id: int, admin_group_id: int) -> Optional[int]:
    """Get topic ID for user."""
    query = """
        SELECT topic_id FROM conversations 
        WHERE user_id = %s AND admin_group_id = %s AND status = 'open'
    """
    result = execute_query(query, (user_id, admin_group_id), fetch_one=True)
    return result['topic_id'] if result else None


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
    status: str = 'pending',
    description: Optional[str] = None
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
        (user_id, product_id, stripe_charge_id, stripe_session_id, idempotency_key,
         amount_cents, credits_granted, time_granted_seconds, status, description),
        fetch_one=True
    )


def update_transaction_status(transaction_id: str, status: str, stripe_charge_id: Optional[str] = None) -> None:
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
    """Get user's transaction history."""
    query = """
        SELECT t.*, p.name as product_name, p.product_type
        FROM transactions t
        LEFT JOIN products p ON t.product_id = p.id
        WHERE t.user_id = %s
        ORDER BY t.created_at DESC
        LIMIT %s;
    """
    return execute_query(query, (user_id, limit), fetch_all=True)


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


def get_product_by_stripe_price_id(stripe_price_id: str) -> Optional[Dict[str, Any]]:
    """Get product by Stripe price ID."""
    query = "SELECT * FROM products WHERE stripe_price_id = %s AND is_active = true"
    return execute_query(query, (stripe_price_id,), fetch_one=True)


# =============================================================================
# BOT SETTINGS MANAGEMENT
# =============================================================================

def get_bot_setting(key: str) -> Optional[str]:
    """Get bot setting value."""
    query = "SELECT value FROM bot_settings WHERE key = %s"
    result = execute_query(query, (key,), fetch_one=True)
    return result['value'] if result else None


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


# =============================================================================
# ANALYTICS FUNCTIONS
# =============================================================================

def get_user_count() -> int:
    """Get total number of users."""
    query = "SELECT COUNT(*) as count FROM users"
    result = execute_query(query, fetch_one=True)
    return result['count'] if result else 0


def get_conversation_count() -> int:
    """Get total number of active conversations."""
    query = "SELECT COUNT(*) as count FROM conversations WHERE status = 'open'"
    result = execute_query(query, fetch_one=True)
    return result['count'] if result else 0


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
            "DROP INDEX IF EXISTS idx_conversations_user_group_open"
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
        column_names = [col['column_name'] for col in existing_columns] if existing_columns else []
        
        logger.info(f"Existing products columns: {column_names}")
        
        # Define required columns and their definitions
        required_columns = {
            'stripe_price_id': 'VARCHAR(255) NOT NULL',
            'product_type': 'VARCHAR(50) NOT NULL DEFAULT \'credits\'',
            'name': 'VARCHAR(100) NOT NULL DEFAULT \'Unknown Product\'',
            'description': 'TEXT',
            'amount': 'INT NOT NULL DEFAULT 1',
            'price_usd_cents': 'INT NOT NULL DEFAULT 100',
            'sort_order': 'INT DEFAULT 0',
            'is_active': 'BOOLEAN DEFAULT TRUE'
        }
        
        # Add missing columns
        for column_name, column_def in required_columns.items():
            if column_name not in column_names:
                try:
                    alter_query = f"ALTER TABLE products ADD COLUMN {column_name} {column_def}"
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
            logger.info(f"Found {len(existing_products)} existing products, skipping sample creation")
            return
        
        logger.info("No products found, creating sample products...")
        
        sample_products = [
            ('credits', '10 Credits Pack', 'Perfect for light usage - 10 message credits', 
             'price_10credits_test', 10, 500, 1),
            ('credits', '25 Credits Pack', 'Great value - 25 message credits',
             'price_25credits_test', 25, 1000, 2),
            ('credits', '50 Credits Pack', 'Best value - 50 message credits',
             'price_50credits_test', 50, 1800, 3),
            ('time', '7 Days Access', 'Unlimited messages for 7 days',
             'price_7days_test', 7, 1500, 4),
            ('time', '30 Days Access', 'Unlimited messages for 30 days',
             'price_30days_test', 30, 5000, 5)
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


# =============================================================================
# Connection pool will be initialized when Flask app starts
# init_connection_pool() - moved to Flask app factory 