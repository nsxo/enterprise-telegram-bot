#!/usr/bin/env python3
"""
Deployment Setup Script for Enterprise Telegram Bot

This script performs all necessary setup tasks for a fresh deployment:
- Database migrations
- Product creation
- Health checks
- Configuration validation
"""

import sys
import os
import asyncio
import logging

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import (
    init_connection_pool,
    ensure_sample_products,
    apply_conversation_table_fix,
    apply_database_views_and_functions,
    apply_enhanced_ux_migration,
    apply_unread_tracking_migration,
    get_active_products,
    get_user_count,
)
from src.config import validate_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_database_migrations():
    """Run all database migrations."""
    logger.info("🔧 Running database migrations...")
    
    try:
        # Apply conversation table fix
        logger.info("📊 Applying conversation table fixes...")
        apply_conversation_table_fix()
        
        # Apply enhanced UX migration
        logger.info("✨ Applying enhanced UX migration...")
        apply_enhanced_ux_migration()
        
        # Apply unread tracking migration
        logger.info("📬 Applying unread tracking migration...")
        apply_unread_tracking_migration()
        
        # Apply database views and functions
        logger.info("🔍 Applying database views and functions...")
        apply_database_views_and_functions()
        
        logger.info("✅ All database migrations completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database migration failed: {e}")
        return False


def setup_products():
    """Ensure products exist in the database."""
    logger.info("🛍️ Setting up products...")
    
    try:
        # Ensure sample products exist
        ensure_sample_products()
        
        # Verify products were created
        products = get_active_products()
        if len(products) == 0:
            logger.error("❌ No products found after setup!")
            return False
            
        logger.info(f"✅ Successfully set up {len(products)} products")
        return True
        
    except Exception as e:
        logger.error(f"❌ Product setup failed: {e}")
        return False


def run_health_checks():
    """Run comprehensive health checks."""
    logger.info("🔍 Running health checks...")
    
    try:
        # Check database connection
        user_count = get_user_count()
        logger.info(f"📊 Database connection OK - {user_count} users in system")
        
        # Check products
        products = get_active_products()
        logger.info(f"🛍️ Products OK - {len(products)} active products")
        
        # List products for verification
        for product in products:
            logger.info(f"  • {product['name']} - ${product['price_usd_cents']/100:.2f}")
        
        logger.info("✅ All health checks passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return False


def main():
    """Main deployment setup function."""
    logger.info("🚀 Starting deployment setup...")
    
    try:
        # Validate configuration
        logger.info("⚙️ Validating configuration...")
        validate_config()
        logger.info("✅ Configuration validation passed")
        
        # Initialize database connection pool
        logger.info("🔗 Initializing database connection...")
        init_connection_pool()
        logger.info("✅ Database connection initialized")
        
        # Run database migrations
        if not run_database_migrations():
            logger.error("❌ Migration failed, aborting setup")
            sys.exit(1)
        
        # Setup products
        if not setup_products():
            logger.error("❌ Product setup failed, aborting setup")
            sys.exit(1)
        
        # Run health checks
        if not run_health_checks():
            logger.error("❌ Health checks failed, aborting setup")
            sys.exit(1)
        
        logger.info("🎉 Deployment setup completed successfully!")
        logger.info("")
        logger.info("📋 Setup Summary:")
        logger.info("  ✅ Database migrations applied")
        logger.info("  ✅ Products configured")
        logger.info("  ✅ Health checks passed")
        logger.info("")
        logger.info("🚀 Your bot is ready for production!")
        
    except Exception as e:
        logger.error(f"❌ Deployment setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 