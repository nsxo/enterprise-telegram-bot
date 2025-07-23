"""
Enterprise Telegram Bot - Flask Webhook Server

This module implements the webhook server using Flask application factory pattern
with proper security, error handling, and monitoring for production deployment.
"""

import logging
import json
import threading
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application

from src.config import WEBHOOK_SECRET_TOKEN, DEBUG_WEBHOOKS
from src.stripe_utils import (
    verify_webhook_signature,
    process_webhook_event,
    StripeError,
)
from src.bot_factory import create_application
from src import database as db

# Graceful shutdown
import atexit

logger = logging.getLogger(__name__)

# Global variables for application instances
telegram_app: Application = None


class WebhookServerError(Exception):
    """Raised when webhook server operations fail."""

    pass


class AsyncLoopManager:
    """
    Manages async event loops to prevent memory leaks and multiple loop creation.
    Implements singleton pattern for centralized loop management.
    """
    _instance = None
    _loop = None
    _thread = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_or_create_loop(self):
        """Get existing loop or create new one if needed."""
        if self._loop is None or self._loop.is_closed():
            import asyncio
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop
    
    def close_loop(self):
        """Safely close the managed loop."""
        if self._loop and not self._loop.is_closed():
            self._loop.close()
            self._loop = None

# Global loop manager instance
loop_manager = AsyncLoopManager()

# Migration coordination to prevent concurrent execution across workers
_migrations_completed = False


def _run_migrations_once() -> None:
    """
    Run database migrations only once, even with multiple Gunicorn workers.
    Uses a database-based lock to prevent race conditions across processes.
    """
    global _migrations_completed
    
    if _migrations_completed:
        logger.info("📋 Migrations already completed by this worker")
        return
    
    try:
        # Use database-based lock for cross-process coordination
        migration_lock_acquired = False
        
        try:
            # Try to acquire a migration lock in the database
            with db.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Check if migrations are already running or completed
                    cursor.execute("""
                        SELECT value FROM bot_settings 
                        WHERE key = 'migration_status' 
                        FOR UPDATE NOWAIT
                    """)
                    result = cursor.fetchone()
                    
                    current_status = result['value'] if result else 'not_started'
                    
                    if current_status == 'completed':
                        logger.info("📋 Migrations already completed by another worker")
                        _migrations_completed = True
                        return
                    elif current_status == 'running':
                        logger.info(
                            "📋 Migrations currently running in another worker, waiting..."
                        )
                        # Wait for completion and return
                        return
                     
                    # Set migration status to running
                    cursor.execute("""
                        INSERT INTO bot_settings (key, value, description, updated_at)
                        VALUES ('migration_status', 'running', 
                               'Database migration coordination flag', NOW())
                        ON CONFLICT (key) 
                        DO UPDATE SET value = 'running', updated_at = NOW()
                    """)
                    conn.commit()
                    migration_lock_acquired = True
                    
        except Exception as lock_error:
            if "could not obtain lock" in str(lock_error).lower():
                logger.info("📋 Another worker is running migrations, skipping...")
                return
            else:
                logger.warning(f"Could not acquire migration lock: {lock_error}")
                # Continue anyway, but with caution
                
        logger.info("🔧 Running database migrations (process-safe)...")
        
        try:
            # Apply database migrations with better error handling
            logger.info("📝 Applying conversation table fix...")
            db.apply_conversation_table_fix()
            
            # Apply enhanced UX migration
            logger.info("📝 Applying enhanced UX migration...")
            db.apply_enhanced_ux_migration()
            
            # Apply unread tracking migration
            logger.info("📝 Applying unread tracking migration...")
            db.apply_unread_tracking_migration()
            
            # Apply conversations updated_at fix
            logger.info("📝 Applying conversations updated_at fix...")
            db.apply_conversations_updated_at_fix()
            
            # Apply database views and functions
            logger.info("📝 Applying database views and functions...")
            db.apply_database_views_and_functions()
            
            # Clean up any problematic indexes first
            logger.info("📝 Cleaning problematic indexes...")
            db.clean_problematic_indexes()
            
            # Apply performance indexes migration
            logger.info("📝 Applying performance indexes migration...")
            db.apply_performance_indexes_migration()
            
            # Apply message references table migration
            logger.info("📝 Applying message references table migration...")
            db.apply_message_references_table_migration()
            
            # Mark migrations as completed
            if migration_lock_acquired:
                try:
                    with db.get_db_connection() as conn:
                        with conn.cursor() as cursor:
                            cursor.execute("""
                                UPDATE bot_settings 
                                SET value = 'completed', updated_at = NOW()
                                WHERE key = 'migration_status'
                            """)
                            conn.commit()
                except Exception as e:
                    logger.warning(f"Could not update migration status: {e}")
            
            _migrations_completed = True
            logger.info("✅ All database migrations completed successfully")
            
        except Exception as migration_error:
            logger.error(f"❌ Migration failed: {migration_error}")
            
            # Reset migration status on failure
            if migration_lock_acquired:
                try:
                    with db.get_db_connection() as conn:
                        with conn.cursor() as cursor:
                            cursor.execute("""
                                UPDATE bot_settings 
                                SET value = 'failed', updated_at = NOW()
                                WHERE key = 'migration_status'
                            """)
                            conn.commit()
                except Exception:
                    pass  # Don't fail on cleanup failure
            
            # Re-raise to prevent app from starting with broken state
            raise
            
    except Exception as e:
        logger.error(f"❌ Migration coordination failed: {e}")
        # Don't prevent app startup for coordination failures
        if "migration" in str(e).lower():
            raise


def create_flask_app() -> Flask:
    """
    Create Flask application using factory pattern.

    Returns:
        Configured Flask application
    """
    app = Flask(__name__)

    # Configure logging for production
    if not app.debug:
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
        )

    # Initialize database connection pool
    from src.database import init_connection_pool

    init_connection_pool()

    # Apply database migrations with lock to prevent concurrent execution
    _run_migrations_once()

    # Ensure we have sample products for testing
    logger.info("🛍️ Ensuring sample products exist...")
    db.ensure_sample_products()
    logger.info("✅ Product setup completed")

    # Initialize and START Telegram application immediately
    global telegram_app
    
    # Create and initialize the Telegram application using managed loop
    def initialize_telegram_app():
        loop = loop_manager.get_or_create_loop()
        telegram_app = loop.run_until_complete(create_application())
        return telegram_app
    
    telegram_app = initialize_telegram_app()
    start_telegram_application()

    # Register routes
    register_routes(app)
    register_error_handlers(app)

    logger.info("✅ Flask webhook server initialized with Telegram app running")
    return app


def register_routes(app: Flask) -> None:
    """
    Register all webhook routes.

    Args:
        app: Flask application instance
    """

    @app.route("/telegram-webhook", methods=["POST"])
    def telegram_webhook():
        """
        Handle incoming Telegram webhook updates.

        Returns:
            JSON response with status
        """
        try:
            # Telegram app is already started in create_flask_app()
            global telegram_app
            if not telegram_app or not hasattr(telegram_app, "bot"):
                logger.error("Telegram app not initialized")
                return jsonify({"error": "Telegram service unavailable"}), 503

            # Verify webhook secret token if configured
            if WEBHOOK_SECRET_TOKEN:
                auth_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
                if auth_header != WEBHOOK_SECRET_TOKEN:
                    logger.warning(
                        f"Invalid webhook secret token from {request.remote_addr}"
                    )
                    return jsonify({"error": "Unauthorized"}), 403

            # Get raw JSON data
            try:
                update_dict = request.get_json(force=True)
                if not update_dict:
                    logger.error("Empty webhook payload received")
                    return jsonify({"error": "Empty payload"}), 400
            except Exception as e:
                logger.error(f"Failed to parse webhook JSON: {e}")
                return jsonify({"error": "Invalid JSON"}), 400

            # Debug logging if enabled
            if DEBUG_WEBHOOKS:
                logger.debug(
                    f"Telegram webhook data: {json.dumps(update_dict, indent=2)}"
                )

            # Create Update object
            try:
                update = Update.de_json(update_dict, telegram_app.bot)
                if not update:
                    logger.error("Failed to create Update object")
                    return jsonify({"error": "Invalid update format"}), 400
            except Exception as e:
                logger.error(f"Failed to deserialize update: {e}")
                return jsonify({"error": "Update deserialization failed"}), 400

            # Process update asynchronously
            try:
                telegram_app.update_queue.put_nowait(update)
                logger.info(f"✅ Telegram update queued: {update.update_id}")
            except Exception as e:
                logger.error(f"Failed to queue update: {e}")
                return jsonify({"error": "Update processing failed"}), 500

            return jsonify({"status": "ok"}), 200

        except Exception as e:
            logger.error(f"Telegram webhook error: {e}")
            return jsonify({"error": "Internal server error"}), 500

    @app.route("/stripe-webhook", methods=["POST"])
    def stripe_webhook():
        """
        Handle incoming Stripe webhook events.
        SECURITY CRITICAL: Verifies signature before processing.

        Returns:
            JSON response with status
        """
        try:
            # Get raw payload and signature
            payload = request.get_data()
            signature = request.headers.get("Stripe-Signature")

            if not payload:
                logger.error("Empty Stripe webhook payload")
                return jsonify({"error": "Empty payload"}), 400

            if not signature:
                logger.error("Missing Stripe signature header")
                return jsonify({"error": "Missing signature"}), 400

            # CRITICAL: Verify webhook signature first
            try:
                event = verify_webhook_signature(payload, signature)
                logger.info(
                    f"✅ Stripe webhook verified: {event['type']} - {event['id']}"
                )
            except StripeError as e:
                logger.error(f"Stripe signature verification failed: {e}")
                if "Invalid signature" in str(e):
                    return jsonify({"error": "Invalid signature"}), 403
                else:
                    return jsonify({"error": "Signature verification failed"}), 400

            # Debug logging if enabled
            if DEBUG_WEBHOOKS:
                logger.debug(
                    f"Stripe webhook event: {json.dumps(event, indent=2, default=str)}"
                )

            # Process the verified event
            try:
                success = process_webhook_event(event)
                if success:
                    logger.info(f"✅ Stripe event processed: {event['type']}")
                    return jsonify({"status": "success"}), 200
                else:
                    logger.error(f"Failed to process Stripe event: {event['type']}")
                    return jsonify({"error": "Event processing failed"}), 500

            except Exception as e:
                logger.error(f"Error processing Stripe event {event['type']}: {e}")
                return jsonify({"error": "Event processing error"}), 500

        except Exception as e:
            logger.error(f"Stripe webhook error: {e}")
            return jsonify({"error": "Internal server error"}), 500

    @app.route("/", methods=["GET"])
    def root():
        """Simple root endpoint for basic connectivity test."""
        return jsonify({"status": "ok", "service": "Enterprise Telegram Bot"})

    @app.route("/health", methods=["GET"])
    def health_check():
        """
        Health check endpoint for monitoring.
        Tests database connectivity and basic service health.

        Returns:
            JSON response with health status
        """
        try:
            health_status = {
                "status": "healthy",
                "service": "Enterprise Telegram Bot",
                "components": {},
            }

            # Test database connectivity (non-blocking)
            try:
                from src.database import connection_pool

                if connection_pool:
                    health_status["components"]["database"] = "initialized"
                else:
                    health_status["components"]["database"] = "not_initialized"
            except Exception as e:
                logger.error(f"Database health check failed: {e}")
                health_status["components"]["database"] = "error"

            # Test Telegram bot connection
            try:
                if telegram_app and telegram_app.bot:
                    health_status["components"]["telegram_bot"] = "healthy"
                else:
                    health_status["components"]["telegram_bot"] = "not_initialized"
                    health_status["status"] = "degraded"
            except Exception as e:
                logger.error(f"Telegram bot health check failed: {e}")
                health_status["components"]["telegram_bot"] = "unhealthy"
                health_status["status"] = "unhealthy"

            # Test Stripe connection (non-blocking)
            try:
                from src.config import STRIPE_API_KEY

                if STRIPE_API_KEY:
                    health_status["components"]["stripe"] = "configured"
                else:
                    health_status["components"]["stripe"] = "not_configured"
            except Exception as e:
                logger.error(f"Stripe health check failed: {e}")
                health_status["components"]["stripe"] = "error"

            # Always return 200 for basic health check
            return jsonify(health_status), 200

        except Exception as e:
            logger.error(f"Health check error: {e}")
            return jsonify({"status": "unhealthy", "error": "Health check failed"}), 503

    @app.route("/success")
    def payment_success():
        """
        Payment success page.
        Shown after successful Stripe checkout.
        """
        session_id = request.args.get("session_id")
        logger.info(f"Payment success page accessed with session: {session_id}")

        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Payment Successful</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                .success { color: #28a745; font-size: 24px; margin-bottom: 20px; }
                .message { font-size: 18px; margin-bottom: 30px; }
                .button { 
                    background-color: #007bff; 
                    color: white; 
                    padding: 12px 24px; 
                    text-decoration: none; 
                    border-radius: 5px;
                    display: inline-block;
                }
            </style>
        </head>
        <body>
            <div class="success">✅ Payment Successful!</div>
            <div class="message">
                Your purchase has been completed successfully.<br>
                Your credits have been added to your account.
            </div>
            <a href="https://t.me/your_bot_username" class="button">Return to Bot</a>
        </body>
        </html>
        """

    @app.route("/cancel")
    def payment_cancel():
        """
        Payment cancellation page.
        Shown when user cancels Stripe checkout.
        """
        logger.info("Payment cancel page accessed")

        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Payment Cancelled</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                .cancel { color: #dc3545; font-size: 24px; margin-bottom: 20px; }
                .message { font-size: 18px; margin-bottom: 30px; }
                .button { 
                    background-color: #007bff; 
                    color: white; 
                    padding: 12px 24px; 
                    text-decoration: none; 
                    border-radius: 5px;
                    display: inline-block;
                }
            </style>
        </head>
        <body>
            <div class="cancel">❌ Payment Cancelled</div>
            <div class="message">
                Your payment was cancelled.<br>
                No charges have been made to your account.
            </div>
            <a href="https://t.me/your_bot_username" class="button">Return to Bot</a>
        </body>
        </html>
        """

    @app.route("/billing-complete")
    def billing_complete():
        """
        Billing management complete page.
        Shown after user completes billing portal session.
        """
        logger.info("Billing complete page accessed")

        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Billing Updated</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                .success { color: #28a745; font-size: 24px; margin-bottom: 20px; }
                .message { font-size: 18px; margin-bottom: 30px; }
                .button { 
                    background-color: #007bff; 
                    color: white; 
                    padding: 12px 24px; 
                    text-decoration: none; 
                    border-radius: 5px;
                    display: inline-block;
                }
            </style>
        </head>
        <body>
            <div class="success">✅ Billing Settings Updated</div>
            <div class="message">
                Your billing information has been updated successfully.<br>
                You can now return to the bot to continue.
            </div>
            <a href="https://t.me/your_bot_username" class="button">Return to Bot</a>
        </body>
        </html>
        """


def register_error_handlers(app: Flask) -> None:
    """
    Register Flask error handlers.

    Args:
        app: Flask application instance
    """

    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        logger.warning(f"404 Not Found: {request.url}")
        return jsonify({"error": "Endpoint not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        """Handle 405 Method Not Allowed errors."""
        logger.warning(f"405 Method Not Allowed: {request.method} {request.url}")
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 Internal Server Error."""
        logger.error(f"500 Internal Server Error: {error}")
        return jsonify({"error": "Internal server error"}), 500

    @app.errorhandler(Exception)
    def handle_exception(e):
        """Handle all unhandled exceptions."""
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred"}), 500


# =============================================================================
# APPLICATION STARTUP
# =============================================================================


def start_telegram_application() -> None:
    """
    Start the Telegram application for processing updates.
    Should be called when the Flask app starts.
    """
    global telegram_app
    if telegram_app:
        try:
            # Create a background task to process the update queue  
            def run_telegram_app():
                import asyncio

                loop = loop_manager.get_or_create_loop()
                
                async def process_updates():
                    await telegram_app.initialize()
                    await telegram_app.start()
                    logger.info(
                        "✅ Telegram application started and processing updates"
                    )

                    # Process updates from the queue continuously
                    while True:
                        try:
                            # Get update from queue with timeout
                            update = await asyncio.wait_for(
                                telegram_app.update_queue.get(), timeout=1.0
                            )

                            # Process the update
                            await telegram_app.process_update(update)

                        except asyncio.TimeoutError:
                            # No update received, continue loop
                            continue
                        except Exception as e:
                            logger.error(f"Error processing update: {e}")
                            continue

                try:
                    loop.run_until_complete(process_updates())
                except Exception as e:
                    logger.error(f"Telegram app error: {e}")

            # Start in background thread
            telegram_thread = threading.Thread(target=run_telegram_app, daemon=True)
            telegram_thread.start()

        except Exception as e:
            logger.error(f"Failed to start Telegram application: {e}")
            raise


def shutdown_telegram_application() -> None:
    """
    Shutdown the Telegram application gracefully.
    Should be called when the Flask app shuts down.
    """
    global telegram_app
    if telegram_app:
        try:
            loop = loop_manager.get_or_create_loop()

            # Run async shutdown operations
            loop.run_until_complete(telegram_app.stop())
            loop.run_until_complete(telegram_app.shutdown())
            
            # Close the managed loop
            loop_manager.close_loop()

            logger.info("✅ Telegram application shutdown complete")
        except Exception as e:
            logger.error(f"Error shutting down Telegram application: {e}")


# Graceful shutdown
atexit.register(shutdown_telegram_application)

# Create the Flask app for Gunicorn to import
app = create_flask_app()

# Telegram application is already started
logger.info("✅ Webhook server ready - Telegram app is running")

if __name__ == "__main__":
    """
    Development server entry point.
    For production, use Gunicorn instead.
    """
    from src.config import PORT, FLASK_DEBUG

    logger.info("🚀 Starting Enterprise Telegram Bot Webhook Server")
    logger.info(f"Debug mode: {FLASK_DEBUG}")
    logger.info(f"Port: {PORT}")

    # Warning for development mode
    if FLASK_DEBUG:
        logger.warning("⚠️ Running in DEBUG mode - not suitable for production!")

    try:
        app.run(
            host="0.0.0.0",
            port=PORT,
            debug=FLASK_DEBUG,
            use_reloader=False,  # Disable reloader to prevent issues with Telegram app
        )
    except Exception as e:
        logger.error(f"Failed to start webhook server: {e}")
        raise
