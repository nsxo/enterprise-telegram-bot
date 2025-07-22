
-- docs/schema.sql
-- Enhanced Database Schema for Enterprise Telegram Bot
-- Based on architectural review recommendations

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Define ENUM types for better data integrity
CREATE TYPE product_type AS ENUM ('credits', 'time', 'premium_content');
CREATE TYPE transaction_status AS ENUM ('pending', 'completed', 'failed', 'refunded');
CREATE TYPE conversation_status AS ENUM ('open', 'closed', 'archived');

-- User Tiers Table: Dynamic tier management
CREATE TABLE tiers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    permissions JSONB DEFAULT '{}',
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default tiers
INSERT INTO tiers (name, description) VALUES
    ('standard', 'Standard user with basic access'),
    ('premium', 'Premium user with enhanced features'),
    ('vip', 'VIP user with full access');

-- Core Table for Users: Stores all user-specific data and state
CREATE TABLE users (
    telegram_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    message_credits INT DEFAULT 0 CHECK (message_credits >= 0),
    time_credits_expires_at TIMESTAMPTZ,
    tier_id INT NOT NULL DEFAULT 1 REFERENCES tiers(id),
    is_banned BOOLEAN DEFAULT FALSE,
    auto_recharge_enabled BOOLEAN DEFAULT FALSE,
    auto_recharge_product_id INT REFERENCES products(id),
    auto_recharge_threshold INT DEFAULT 5,
    stripe_customer_id VARCHAR(255) UNIQUE,
    tutorial_completed BOOLEAN DEFAULT FALSE,
    tutorial_step INTEGER DEFAULT 0,
    is_new_user BOOLEAN DEFAULT TRUE,
    total_messages_sent INTEGER DEFAULT 0,
    last_low_credit_warning_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Core Table for Products: Defines what you sell (credit packs, time passes, etc.)
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    product_type product_type NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    stripe_price_id VARCHAR(255) NOT NULL UNIQUE,
    amount INT NOT NULL, -- e.g., number of credits, or days of access
    price_usd_cents INT NOT NULL CHECK (price_usd_cents > 0),
    sort_order INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Foreign key constraints
ALTER TABLE users ADD CONSTRAINT fk_auto_recharge_product
FOREIGN KEY (auto_recharge_product_id) REFERENCES products(id);

-- Enhanced Conversations Table: More robust design for future expansion
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    admin_group_id BIGINT NOT NULL,
    topic_id INT NOT NULL,
    pinned_message_id BIGINT,
    status conversation_status DEFAULT 'open',
    last_user_message_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    notes TEXT,
    -- Ensure one open topic per user per admin group (simplified constraint)
    UNIQUE (user_id, admin_group_id)
);

-- Enhanced Transactions Table: Complete financial audit trail
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT NOT NULL REFERENCES users(telegram_id),
    product_id INT REFERENCES products(id),
    stripe_charge_id VARCHAR(255) UNIQUE,
    stripe_session_id VARCHAR(255),
    idempotency_key VARCHAR(255) UNIQUE, -- For safe retries
    amount_paid_usd_cents INT NOT NULL CHECK (amount_paid_usd_cents >= 0),
    credits_granted INT DEFAULT 0 CHECK (credits_granted >= 0),
    time_granted_seconds INT DEFAULT 0 CHECK (time_granted_seconds >= 0),
    status transaction_status NOT NULL DEFAULT 'pending',
    description TEXT,
    metadata JSONB DEFAULT '{}', -- For additional transaction data
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Message References Table: Links user messages to admin group messages
CREATE TABLE message_references (
    id SERIAL PRIMARY KEY,
    user_message_id BIGINT NOT NULL,
    admin_message_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    topic_id INT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    -- Ensure one reference per user message
    UNIQUE (user_message_id, user_id)
);

-- Add missing columns to users table (these will be added by migration)
-- Note: These columns are already in the application's migration function
-- last_message_at TIMESTAMPTZ,
-- banned_at TIMESTAMPTZ,
-- banned_by BIGINT,
-- ban_reason TEXT,
-- archive_reason TEXT,
-- archived_at TIMESTAMPTZ,

-- Bot Settings Table: Key-value store for configuration
CREATE TABLE bot_settings (
    key VARCHAR(255) PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    value_type VARCHAR(50) DEFAULT 'string',
    updated_by BIGINT REFERENCES users(telegram_id),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Default bot settings
INSERT INTO bot_settings (key, value, description, value_type) VALUES
    ('new_user_free_credits', '3', 'Free credits given to new users', 'integer'),
    ('welcome_message_new', 'Welcome, {first_name}! 🎉\n\nYou''ve received {free_credits} FREE credits to get started! 🎁\n\n✨ What can I help you with today?', 'Welcome message for new users', 'string'),
    ('welcome_message_returning', 'Welcome back, {first_name}! 👋\n\n💰 Your balance: {credits} credits', 'Welcome message for returning users', 'string'),
    ('tutorial_enabled', 'true', 'Enable interactive tutorial for new users', 'boolean'),
    ('tutorial_completion_bonus', '2', 'Bonus credits for completing tutorial', 'integer'),
    ('progress_bar_max_credits', '100', 'Maximum credits for 100% progress bar display', 'integer'),
    ('balance_low_threshold', '5', 'Credits threshold for low balance warning', 'integer'),
    ('balance_critical_threshold', '2', 'Credits threshold for critical balance warning', 'integer'),
    ('quick_buy_enabled', 'true', 'Enable quick buy buttons for low credit situations', 'boolean'),
    ('quick_buy_trigger_threshold', '5', 'Show quick buy options when credits below this', 'integer'),
    ('low_credit_warning_message', 'Running low on credits! 💡 Quick top-up options below:', 'Message shown with quick buy buttons', 'string');

-- Performance Indexes: Optimized for common query patterns
CREATE INDEX idx_users_tier_id ON users(tier_id);
CREATE INDEX idx_users_stripe_customer_id ON users(stripe_customer_id);
CREATE INDEX idx_users_created_at ON users(created_at);

CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_conversations_topic_id ON conversations(topic_id);
CREATE INDEX idx_conversations_status ON conversations(status);
CREATE INDEX idx_conversations_last_message ON conversations(last_user_message_at);

CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_transactions_status ON transactions(status);
CREATE INDEX idx_transactions_created_at ON transactions(created_at);
CREATE INDEX idx_transactions_stripe_charge_id ON transactions(stripe_charge_id);

CREATE INDEX idx_products_type ON products(product_type);
CREATE INDEX idx_products_active ON products(is_active);
CREATE INDEX idx_products_sort_order ON products(sort_order);

-- Analytics and Reporting Views
CREATE OR REPLACE VIEW user_dashboard_view AS
SELECT
    u.telegram_id,
    u.username,
    u.first_name,
    u.last_name,
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
    u.telegram_id, u.username, u.first_name, u.last_name, u.message_credits, 
    u.time_credits_expires_at, t.name, t.permissions, u.created_at,
    u.auto_recharge_enabled, c.topic_id, c.last_user_message_at, c.status;

-- Revenue Analytics View
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

-- Trigger Functions
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE OR REPLACE FUNCTION update_bot_settings_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers
CREATE TRIGGER update_users_modtime
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_bot_settings_modtime
    BEFORE UPDATE ON bot_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_bot_settings_timestamp();

-- Functions for common operations
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
