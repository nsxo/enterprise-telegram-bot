"""
Enterprise Telegram Bot - Flask Webhook Server

This module implements the webhook server using Flask application factory pattern
with proper security, error handling, and monitoring for production deployment.
"""

import logging
import json
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
    
    # Initialize Telegram application
    global telegram_app
    telegram_app = create_application()
    
    # Register routes
    register_routes(app)
    register_error_handlers(app)
    
    logger.info("✅ Flask webhook server initialized")
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
            
            # Test database connectivity
            try:
                from src.database import connection_pool, execute_query
                if connection_pool:
                    # Simple query to test database
                    execute_query("SELECT 1", fetch_one=True)
                    health_status['components']['database'] = 'healthy'
                else:
                    health_status['components']['database'] = 'not_initialized'
                    health_status['status'] = 'degraded'
            except Exception as e:
                logger.error(f"Database health check failed: {e}")
                health_status['components']['database'] = 'unhealthy'
                health_status['status'] = 'unhealthy'
            
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
            
            # Test Stripe connection
            try:
                import stripe
                stripe.Product.list(limit=1)
                health_status['components']['stripe'] = 'healthy'
            except Exception as e:
                logger.error(f"Stripe health check failed: {e}")
                health_status['components']['stripe'] = 'unhealthy'
                health_status['status'] = 'unhealthy'
            
            # Return appropriate status code
            if health_status['status'] == 'healthy':
                return jsonify(health_status), 200
            elif health_status['status'] == 'degraded':
                return jsonify(health_status), 200  # Still return 200 for degraded
            else:
                return jsonify(health_status), 503  # Service Unavailable
                
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
            # Initialize the application
            telegram_app.initialize()
            logger.info("✅ Telegram application initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Telegram application: {e}")
            raise


def shutdown_telegram_application() -> None:
    """
    Shutdown the Telegram application gracefully.
    Should be called when the Flask app shuts down.
    """
    global telegram_app
    if telegram_app:
        try:
            telegram_app.shutdown()
            logger.info("✅ Telegram application shutdown complete")
        except Exception as e:
            logger.error(f"Error shutting down Telegram application: {e}")


# Create Flask application instance
app = create_flask_app()


# Application lifecycle management
@app.before_first_request
def before_first_request():
    """Initialize services before handling first request."""
    try:
        start_telegram_application()
        logger.info("✅ Webhook server ready to handle requests")
    except Exception as e:
        logger.error(f"Failed to start services: {e}")
        raise


# Graceful shutdown
import atexit
atexit.register(shutdown_telegram_application)


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