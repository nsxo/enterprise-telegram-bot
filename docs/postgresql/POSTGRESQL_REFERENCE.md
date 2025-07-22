# PostgreSQL Reference for Enterprise Telegram Bot

## 🔗 **Essential PostgreSQL Documentation Links**
- **PostgreSQL Documentation**: https://www.postgresql.org/docs/current/
- **Connection Pooling**: https://www.postgresql.org/docs/current/runtime-config-connection.html
- **Performance Tuning**: https://www.postgresql.org/docs/current/performance-tips.html
- **psycopg2 Documentation**: https://www.psycopg.org/docs/
- **UUID Functions**: https://www.postgresql.org/docs/current/uuid-ossp.html

## 🗄️ **Database Connection Management**

### **1. Connection Pool Implementation (CRITICAL)**
```python
# src/database.py
import psycopg2
from psycopg2 import pool
import logging
from src.config import DATABASE_URL

# Global connection pool
connection_pool = None

def init_connection_pool(min_conn=1, max_conn=10):
    """
    Initialize PostgreSQL connection pool
    CRITICAL: Uses ThreadedConnectionPool for multi-threaded Gunicorn environment
    """
    global connection_pool
    try:
        # MUST use ThreadedConnectionPool for production with Gunicorn workers
        # SimpleConnectionPool is NOT thread-safe and will cause race conditions
        connection_pool = psycopg2.pool.ThreadedConnectionPool(
            min_conn, max_conn,
            DATABASE_URL,
            cursor_factory=psycopg2.extras.RealDictCursor  # Return dict-like results
        )
        logging.info(f"ThreadedConnectionPool created with {min_conn}-{max_conn} connections")
    except Exception as e:
        logging.error(f"Error creating connection pool: {e}")
        raise

def get_connection():
    """Get connection from pool"""
    global connection_pool
    if connection_pool:
        return connection_pool.getconn()
    else:
        raise Exception("Connection pool not initialized")

def return_connection(connection):
    """Return connection to pool"""
    global connection_pool
    if connection_pool:
        connection_pool.putconn(connection)

def close_all_connections():
    """Close all connections in pool"""
    global connection_pool
    if connection_pool:
        connection_pool.closeall()
```

### **2. Master Query Execution Function**
```python
def execute_query(query, params=None, fetch_one=False, fetch_all=False):
    """
    Master function for all database operations
    Handles connection acquisition, execution, and cleanup
    """
    connection = None
    cursor = None
    try:
        # Get connection from pool
        connection = get_connection()
        cursor = connection.cursor()
        
        # Execute query
        cursor.execute(query, params)
        
        # Handle different return types
        if fetch_one:
            result = cursor.fetchone()
        elif fetch_all:
            result = cursor.fetchall()
        else:
            result = cursor.rowcount
            
        # Commit transaction
        connection.commit()
        return result
        
    except Exception as e:
        if connection:
            connection.rollback()
        logging.error(f"Database error: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            return_connection(connection)
```

## 👤 **User Management Functions**

### **1. Upsert User (Get or Create)**
```python
def get_or_create_user(telegram_id, username, first_name, last_name=None):
    """
    Get existing user or create new one (upsert operation)
    Uses INSERT ... ON CONFLICT for atomic operation
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
        query, 
        (telegram_id, username, first_name, last_name),
        fetch_one=True
    )

def get_user(telegram_id):
    """Get user by Telegram ID"""
    query = "SELECT * FROM users WHERE telegram_id = %s"
    return execute_query(query, (telegram_id,), fetch_one=True)

def update_user_credits(telegram_id, credit_amount):
    """Add credits to user account"""
    query = """
        UPDATE users 
        SET message_credits = message_credits + %s, updated_at = NOW()
        WHERE telegram_id = %s
        RETURNING message_credits;
    """
    return execute_query(query, (credit_amount, telegram_id), fetch_one=True)

def update_user_stripe_customer(telegram_id, stripe_customer_id):
    """Link Stripe customer ID to user"""
    query = """
        UPDATE users 
        SET stripe_customer_id = %s, updated_at = NOW()
        WHERE telegram_id = %s;
    """
    return execute_query(query, (stripe_customer_id, telegram_id))
```

## 💬 **Conversation Management Functions**

### **1. Topic Management**
```python
def create_conversation_topic(user_id, topic_id, pinned_message_id=None):
    """Create new conversation topic for user"""
    query = """
        INSERT INTO conversations (user_id, topic_id, pinned_message_id, last_user_message_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (user_id) 
        DO UPDATE SET 
            topic_id = EXCLUDED.topic_id,
            pinned_message_id = EXCLUDED.pinned_message_id,
            last_user_message_at = NOW();
    """
    return execute_query(query, (user_id, topic_id, pinned_message_id))

def get_user_id_from_topic(topic_id):
    """Get user ID associated with topic"""
    query = "SELECT user_id FROM conversations WHERE topic_id = %s"
    result = execute_query(query, (topic_id,), fetch_one=True)
    return result['user_id'] if result else None

def get_topic_id_from_user(user_id):
    """Get topic ID for user"""
    query = "SELECT topic_id FROM conversations WHERE user_id = %s"
    result = execute_query(query, (user_id,), fetch_one=True)
    return result['topic_id'] if result else None

def update_last_message_time(user_id):
    """Update last message timestamp for user"""
    query = """
        UPDATE conversations 
        SET last_user_message_at = NOW()
        WHERE user_id = %s;
    """
    return execute_query(query, (user_id,))
```

## 💳 **Transaction Management**

### **1. Transaction Logging**
```python
def log_transaction(user_id, product_id, stripe_charge_id, amount_cents, status, description=None):
    """Log transaction for business intelligence"""
    query = """
        INSERT INTO transactions 
        (user_id, product_id, stripe_charge_id, amount_paid_usd_cents, status, description, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        RETURNING id;
    """
    return execute_query(
        query, 
        (user_id, product_id, stripe_charge_id, amount_cents, status, description),
        fetch_one=True
    )

def get_user_transactions(user_id, limit=10):
    """Get user's transaction history"""
    query = """
        SELECT t.*, p.name as product_name, p.product_type
        FROM transactions t
        LEFT JOIN products p ON t.product_id = p.id
        WHERE t.user_id = %s
        ORDER BY t.created_at DESC
        LIMIT %s;
    """
    return execute_query(query, (user_id, limit), fetch_all=True)
```

## 🛍️ **Product Management**

### **1. Product Operations**
```python
def get_active_products():
    """Get all active products"""
    query = """
        SELECT * FROM products 
        WHERE is_active = true 
        ORDER BY product_type, price_usd_cents;
    """
    return execute_query(query, fetch_all=True)

def get_product_by_stripe_price_id(stripe_price_id):
    """Get product by Stripe price ID"""
    query = "SELECT * FROM products WHERE stripe_price_id = %s AND is_active = true"
    return execute_query(query, (stripe_price_id,), fetch_one=True)

def create_product(product_type, name, description, stripe_price_id, amount, price_cents):
    """Create new product"""
    query = """
        INSERT INTO products (product_type, name, description, stripe_price_id, amount, price_usd_cents, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        RETURNING id;
    """
    return execute_query(
        query, 
        (product_type, name, description, stripe_price_id, amount, price_cents),
        fetch_one=True
    )
```

## 📊 **Analytics & Business Intelligence**

### **1. Dashboard Queries**
```python
def get_user_dashboard_data(user_id):
    """Get comprehensive user data for admin dashboard"""
    query = """
        SELECT * FROM user_dashboard_view 
        WHERE telegram_id = %s;
    """
    return execute_query(query, (user_id,), fetch_one=True)

def get_revenue_analytics(days=30):
    """Get revenue analytics for specified period"""
    query = """
        SELECT 
            DATE(created_at) as date,
            COUNT(*) as transactions,
            SUM(amount_paid_usd_cents) as revenue_cents,
            COUNT(DISTINCT user_id) as unique_users
        FROM transactions 
        WHERE status = 'succeeded' 
          AND created_at >= NOW() - INTERVAL '%s days'
        GROUP BY DATE(created_at)
        ORDER BY date DESC;
    """
    return execute_query(query, (days,), fetch_all=True)

def get_top_users_by_spending(limit=10):
    """Get top users by total spending"""
    query = """
        SELECT 
            u.telegram_id,
            u.username,
            u.first_name,
            SUM(t.amount_paid_usd_cents) as total_spent_cents,
            COUNT(t.id) as transaction_count
        FROM users u
        JOIN transactions t ON u.telegram_id = t.user_id
        WHERE t.status = 'succeeded'
        GROUP BY u.telegram_id, u.username, u.first_name
        ORDER BY total_spent_cents DESC
        LIMIT %s;
    """
    return execute_query(query, (limit,), fetch_all=True)
```

## 🔧 **Database Setup & Maintenance**

### **1. Database Initialization**
```python
# scripts/setup_db.py
import psycopg2
from src.config import DATABASE_URL

def setup_database():
    """Initialize database with schema"""
    try:
        # Read schema file
        with open('docs/schema.sql', 'r') as f:
            schema_sql = f.read()
        
        # Connect to database
        connection = psycopg2.connect(DATABASE_URL)
        cursor = connection.cursor()
        
        # Execute schema
        cursor.execute(schema_sql)
        connection.commit()
        
        print("Database schema created successfully")
        
    except Exception as e:
        print(f"Error setting up database: {e}")
        if connection:
            connection.rollback()
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

if __name__ == "__main__":
    setup_database()
```

### **2. Performance Optimization**
```python
def create_indexes():
    """Create additional indexes for performance"""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);",
        "CREATE INDEX IF NOT EXISTS idx_conversations_last_message ON conversations(last_user_message_at);",
    ]
    
    for index_sql in indexes:
        try:
            execute_query(index_sql)
            print(f"Created index: {index_sql}")
        except Exception as e:
            print(f"Error creating index: {e}")
```

## 🛡️ **Security & Best Practices**

### **1. Query Safety**
```python
# ALWAYS use parameterized queries
# GOOD:
execute_query("SELECT * FROM users WHERE telegram_id = %s", (user_id,))

# BAD - SQL Injection vulnerability:
# execute_query(f"SELECT * FROM users WHERE telegram_id = {user_id}")
```

### **2. Connection Management**
```python
# ALWAYS use connection pooling in production
# ALWAYS return connections to pool in finally blocks
# NEVER leave connections open
# ALWAYS handle exceptions and rollback on errors
```

### **3. Data Validation**
```python
def validate_telegram_id(telegram_id):
    """Validate Telegram ID format"""
    if not isinstance(telegram_id, int) or telegram_id <= 0:
        raise ValueError("Invalid Telegram ID")
    return telegram_id

def validate_credit_amount(amount):
    """Validate credit amount"""
    if not isinstance(amount, int) or amount < 0:
        raise ValueError("Invalid credit amount")
    return amount
```

This PostgreSQL reference covers all database requirements for your Enterprise Telegram Bot project. 