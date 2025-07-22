"""
Enterprise Telegram Bot - Flask Webhook Server

This module implements the webhook server using Flask application factory pattern
with proper security, error handling, and monitoring for production deployment.
"""

import logging
import json
import threading
from typing import Dict, Any
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application

from src.config import BOT_TOKEN, WEBHOOK_SECRET_TOKEN, DEBUG_WEBHOOKS
from src.stripe_utils import verify_webhook_signature, process_webhook_event, StripeError
from src.bot import create_application

logger = logging.getLogger(__name__)

# Global variables for application instances
telegram_app: Application = None


class WebhookServerError(Exception):
    """Raised when webhook server operations fail."""
    pass


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
            level=logging.INFO,
            format='%(asctime)s %(levelname)s %(name)s: %(message)s'
        )
    
    # Initialize database connection pool
    from src.database import init_connection_pool
    init_connection_pool()
    
    # Initialize and START Telegram application immediately
    global telegram_app
    telegram_app = create_application()
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
    
    @app.route('/telegram-webhook', methods=['POST'])
    def telegram_webhook():
        """
        Handle incoming Telegram webhook updates.
        
        Returns:
            JSON response with status
        """
        try:
            # Telegram app is already started in create_flask_app()
            global telegram_app
            if not telegram_app or not hasattr(telegram_app, 'bot'):
                logger.error("Telegram app not initialized")
                return jsonify({'error': 'Telegram service unavailable'}), 503
            
            # Verify webhook secret token if configured
            if WEBHOOK_SECRET_TOKEN:
                auth_header = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
                if auth_header != WEBHOOK_SECRET_TOKEN:
                    logger.warning(f"Invalid webhook secret token from {request.remote_addr}")
                    return jsonify({'error': 'Unauthorized'}), 403
            
            # Get raw JSON data
            try:
                update_dict = request.get_json(force=True)
                if not update_dict:
                    logger.error("Empty webhook payload received")
                    return jsonify({'error': 'Empty payload'}), 400
            except Exception as e:
                logger.error(f"Failed to parse webhook JSON: {e}")
                return jsonify({'error': 'Invalid JSON'}), 400
            
            # Debug logging if enabled
            if DEBUG_WEBHOOKS:
                logger.debug(f"Telegram webhook data: {json.dumps(update_dict, indent=2)}")
            
            # Create Update object
            try:
                update = Update.de_json(update_dict, telegram_app.bot)
                if not update:
                    logger.error("Failed to create Update object")
                    return jsonify({'error': 'Invalid update format'}), 400
            except Exception as e:
                logger.error(f"Failed to deserialize update: {e}")
                return jsonify({'error': 'Update deserialization failed'}), 400
            
            # Process update asynchronously
            try:
                telegram_app.update_queue.put_nowait(update)
                logger.info(f"✅ Telegram update queued: {update.update_id}")
            except Exception as e:
                logger.error(f"Failed to queue update: {e}")
                return jsonify({'error': 'Update processing failed'}), 500
            
            return jsonify({'status': 'ok'}), 200
            
        except Exception as e:
            logger.error(f"Telegram webhook error: {e}")
            return jsonify({'error': 'Internal server error'}), 500
    
    
    @app.route('/stripe-webhook', methods=['POST'])
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
            signature = request.headers.get('Stripe-Signature')
            
            if not payload:
                logger.error("Empty Stripe webhook payload")
                return jsonify({'error': 'Empty payload'}), 400
            
            if not signature:
                logger.error("Missing Stripe signature header")
                return jsonify({'error': 'Missing signature'}), 400
            
            # CRITICAL: Verify webhook signature first
            try:
                event = verify_webhook_signature(payload, signature)
                logger.info(f"✅ Stripe webhook verified: {event['type']} - {event['id']}")
            except StripeError as e:
                logger.error(f"Stripe signature verification failed: {e}")
                if "Invalid signature" in str(e):
                    return jsonify({'error': 'Invalid signature'}), 403
                else:
                    return jsonify({'error': 'Signature verification failed'}), 400
            
            # Debug logging if enabled
            if DEBUG_WEBHOOKS:
                logger.debug(f"Stripe webhook event: {json.dumps(event, indent=2, default=str)}")
            
            # Process the verified event
            try:
                success = process_webhook_event(event)
                if success:
                    logger.info(f"✅ Stripe event processed: {event['type']}")
                    return jsonify({'status': 'success'}), 200
                else:
                    logger.error(f"Failed to process Stripe event: {event['type']}")
                    return jsonify({'error': 'Event processing failed'}), 500
                    
            except Exception as e:
                logger.error(f"Error processing Stripe event {event['type']}: {e}")
                return jsonify({'error': 'Event processing error'}), 500
            
        except Exception as e:
            logger.error(f"Stripe webhook error: {e}")
            return jsonify({'error': 'Internal server error'}), 500
    
    
    @app.route('/', methods=['GET'])
    def root():
        """Simple root endpoint for basic connectivity test."""
        return jsonify({'status': 'ok', 'service': 'Enterprise Telegram Bot'})
    
    @app.route('/health', methods=['GET'])
    def health_check():
        """
        Health check endpoint for monitoring.
        Tests database connectivity and basic service health.
        
        Returns:
            JSON response with health status
        """
        try:
            health_status = {
                'status': 'healthy',
                'service': 'Enterprise Telegram Bot',
                'components': {}
            }
            
            # Test database connectivity (non-blocking)
            try:
                from src.database import connection_pool
                if connection_pool:
                    health_status['components']['database'] = 'initialized'
                else:
                    health_status['components']['database'] = 'not_initialized'
            except Exception as e:
                logger.error(f"Database health check failed: {e}")
                health_status['components']['database'] = 'error'
            
            # Test Telegram bot connection
            try:
                if telegram_app and telegram_app.bot:
                    health_status['components']['telegram_bot'] = 'healthy'
                else:
                    health_status['components']['telegram_bot'] = 'not_initialized'
                    health_status['status'] = 'degraded'
            except Exception as e:
                logger.error(f"Telegram bot health check failed: {e}")
                health_status['components']['telegram_bot'] = 'unhealthy'
                health_status['status'] = 'unhealthy'
            
            # Test Stripe connection (non-blocking)
            try:
                from src.config import STRIPE_API_KEY
                if STRIPE_API_KEY:
                    health_status['components']['stripe'] = 'configured'
                else:
                    health_status['components']['stripe'] = 'not_configured'
            except Exception as e:
                logger.error(f"Stripe health check failed: {e}")
                health_status['components']['stripe'] = 'error'
            
            # Always return 200 for basic health check
            return jsonify(health_status), 200
                
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': 'Health check failed'
            }), 503
    
    
    @app.route('/success')
    def payment_success():
        """
        Payment success page.
        Shown after successful Stripe checkout.
        """
        session_id = request.args.get('session_id')
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
    
    
    @app.route('/cancel')
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
    
    
    @app.route('/billing-complete')
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
        return jsonify({'error': 'Endpoint not found'}), 404
    
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        """Handle 405 Method Not Allowed errors."""
        logger.warning(f"405 Method Not Allowed: {request.method} {request.url}")
        return jsonify({'error': 'Method not allowed'}), 405
    
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 Internal Server Error."""
        logger.error(f"500 Internal Server Error: {error}")
        return jsonify({'error': 'Internal server error'}), 500
    
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        """Handle all unhandled exceptions."""
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        return jsonify({'error': 'An unexpected error occurred'}), 500


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
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    async def process_updates():
                        await telegram_app.initialize()
                        await telegram_app.start()
                        logger.info("✅ Telegram application started and processing updates")
                        
                        # Process updates from the queue continuously
                        while True:
                            try:
                                # Get update from queue with timeout
                                update = await asyncio.wait_for(
                                    telegram_app.update_queue.get(), 
                                    timeout=1.0
                                )
                                
                                # Process the update
                                await telegram_app.process_update(update)
                                
                            except asyncio.TimeoutError:
                                # No update received, continue loop
                                continue
                            except Exception as e:
                                logger.error(f"Error processing update: {e}")
                                continue
                    
                    loop.run_until_complete(process_updates())
                    
                except Exception as e:
                    logger.error(f"Telegram app error: {e}")
                finally:
                    loop.close()

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
            import asyncio
            
            # Get current event loop or create new one
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Run async shutdown operations
            loop.run_until_complete(telegram_app.stop())
            loop.run_until_complete(telegram_app.shutdown())
            
            logger.info("✅ Telegram application shutdown complete")
        except Exception as e:
            logger.error(f"Error shutting down Telegram application: {e}")


# Graceful shutdown
import atexit
atexit.register(shutdown_telegram_application)

# Create the Flask app for Gunicorn to import
app = create_flask_app()

# Telegram application is already started
logger.info("✅ Webhook server ready - Telegram app is running")

if __name__ == '__main__':
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
            host='0.0.0.0',
            port=PORT,
            debug=FLASK_DEBUG,
            use_reloader=False  # Disable reloader to prevent issues with Telegram app
        )
    except Exception as e:
        logger.error(f"Failed to start webhook server: {e}")
        raise 