# Flask Reference for Enterprise Telegram Bot Webhook Server

## 🔗 **Essential Flask Documentation Links**
- **Flask Documentation**: https://flask.palletsprojects.com/en/3.0.x/
- **Application Factories**: https://flask.palletsprojects.com/en/3.0.x/patterns/appfactories/
- **Request Handling**: https://flask.palletsprojects.com/en/3.0.x/api/#incoming-request-data
- **Error Handling**: https://flask.palletsprojects.com/en/3.0.x/errorhandling/
- **Deployment**: https://flask.palletsprojects.com/en/3.0.x/deploying/

## 🌐 **Flask Webhook Server Implementation**

### **1. Application Factory Pattern (Required)**
```python
# src/webhook_server.py
from flask import Flask, request, jsonify
import logging

def create_app():
    """Create Flask application using factory pattern"""
    app = Flask(__name__)
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Register routes
    register_routes(app)
    register_error_handlers(app)
    
    return app

def register_routes(app):
    """Register all webhook routes"""
    
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint for hosting providers"""
        return jsonify({'status': 'healthy'}), 200
    
    @app.route('/telegram-webhook', methods=['POST'])
    def telegram_webhook():
        """Handle Telegram bot updates"""
        try:
            # Get JSON payload
            update_data = request.get_json()
            
            if not update_data:
                return jsonify({'error': 'No JSON payload'}), 400
            
            # Process with python-telegram-bot
            # This should be processed by your bot application
            process_telegram_update(update_data)
            
            return jsonify({'status': 'ok'}), 200
            
        except Exception as e:
            app.logger.error(f"Telegram webhook error: {e}")
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/stripe-webhook', methods=['POST'])
    def stripe_webhook():
        """Handle Stripe webhook events"""
        try:
            payload = request.get_data()
            sig_header = request.headers.get('Stripe-Signature')
            
            if not sig_header:
                return jsonify({'error': 'Missing signature'}), 400
            
            # Verify signature and process
            result = process_stripe_webhook(payload, sig_header)
            
            return jsonify({'status': 'success'}), 200
            
        except ValueError as e:
            return jsonify({'error': 'Invalid payload'}), 400
        except Exception as e:
            app.logger.error(f"Stripe webhook error: {e}")
            return jsonify({'error': 'Internal server error'}), 500

def register_error_handlers(app):
    """Register global error handlers"""
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Endpoint not found'}), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({'error': 'Method not allowed'}), 405
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500

# Application instance for Gunicorn
app = create_app()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8000)
```

### **2. Request Handling Patterns**

#### **Getting JSON Data**
```python
# For Telegram webhooks
@app.route('/telegram-webhook', methods=['POST'])
def telegram_webhook():
    # Always use get_json() for JSON payloads
    data = request.get_json()
    
    # Check if JSON was provided
    if not data:
        return jsonify({'error': 'JSON required'}), 400
```

#### **Getting Raw Data (For Stripe Signatures)**
```python
# For Stripe webhook signature verification
@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    # Use get_data() for raw payload (needed for signature verification)
    payload = request.get_data()
    signature = request.headers.get('Stripe-Signature')
```

#### **Getting Headers**
```python
# Access request headers
content_type = request.headers.get('Content-Type')
user_agent = request.headers.get('User-Agent')
custom_header = request.headers.get('X-Custom-Header')
```

### **3. Response Patterns**

#### **JSON Responses**
```python
from flask import jsonify

# Success response
return jsonify({'status': 'success', 'data': result}), 200

# Error response
return jsonify({'error': 'Invalid request'}), 400

# Custom status codes
return jsonify({'message': 'Created'}), 201
```

#### **Quick Responses (Critical for Telegram)**
```python
@app.route('/telegram-webhook', methods=['POST'])
def telegram_webhook():
    # Process update quickly to avoid Telegram timeout
    update_data = request.get_json()
    
    # Queue for background processing or process synchronously but quickly
    # Telegram expects response within ~60 seconds
    
    return jsonify({'status': 'ok'}), 200  # Respond immediately
```

## 🔧 **Production Configuration**

### **1. Gunicorn Configuration**
```python
# gunicorn_config.py
bind = "0.0.0.0:8000"
workers = 4  # Adjust based on your server
worker_class = "sync"
timeout = 30
keepalive = 10
max_requests = 1000
max_requests_jitter = 100
```

### **2. Docker Integration**
```dockerfile
# In Dockerfile
CMD ["gunicorn", "--config", "gunicorn_config.py", "src.webhook_server:app"]
```

### **3. Environment Variables**
```python
# src/config.py integration
import os
from flask import Flask

def create_app():
    app = Flask(__name__)
    
    # Load configuration from environment
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['DEBUG'] = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    return app
```

## 🛡️ **Security & Error Handling**

### **1. Request Validation**
```python
@app.route('/telegram-webhook', methods=['POST'])
def telegram_webhook():
    # Validate content type
    if request.content_type != 'application/json':
        return jsonify({'error': 'Content-Type must be application/json'}), 400
    
    # Validate JSON structure
    try:
        data = request.get_json()
        if not isinstance(data, dict):
            raise ValueError("Invalid JSON structure")
    except Exception:
        return jsonify({'error': 'Invalid JSON'}), 400
```

### **2. Rate Limiting Protection**
```python
from functools import wraps
import time

# Simple rate limiting decorator
def rate_limit(max_requests=100, per_seconds=60):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Implement rate limiting logic
            # (In production, use Redis or similar)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/telegram-webhook', methods=['POST'])
@rate_limit(max_requests=100, per_seconds=60)
def telegram_webhook():
    # Your webhook logic
    pass
```

### **3. Logging Configuration**
```python
import logging
from logging.handlers import RotatingFileHandler

def configure_logging(app):
    if not app.debug:
        # File logging
        file_handler = RotatingFileHandler(
            'webhook.log', maxBytes=10240, backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('Webhook server startup')
```

## 🔄 **Integration with python-telegram-bot**

### **Webhook Integration Pattern**
```python
from telegram import Update
from telegram.ext import Application

# Initialize bot application
bot_application = Application.builder().token(BOT_TOKEN).build()

def process_telegram_update(update_data):
    """Process Telegram update through python-telegram-bot"""
    try:
        # Convert dict to Update object
        update = Update.de_json(update_data, bot_application.bot)
        
        # Process through application
        asyncio.run(bot_application.process_update(update))
        
    except Exception as e:
        logging.error(f"Error processing update: {e}")
        raise
```

## 📊 **Monitoring & Health Checks**

### **Health Check Implementation**
```python
@app.route('/health', methods=['GET'])
def health_check():
    """Comprehensive health check"""
    try:
        # Test database connection
        test_database_connection()
        
        # Test external services
        test_telegram_api()
        test_stripe_api()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'services': {
                'database': 'ok',
                'telegram': 'ok',
                'stripe': 'ok'
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503
```

This Flask reference covers all webhook server requirements for your Enterprise Telegram Bot project. 