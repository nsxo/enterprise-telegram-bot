
# 🔌 API Guide - Enterprise Telegram Bot

## 📋 Overview

This document provides comprehensive API documentation for the Enterprise Telegram Bot, including webhook endpoints, plugin architecture, and integration guidelines.

## 🌐 Webhook Endpoints

### **Telegram Webhook**
```
POST /telegram-webhook
```

**Purpose**: Receives and processes Telegram updates

**Headers Required**:
```
Content-Type: application/json
X-Telegram-Bot-Api-Secret-Token: {WEBHOOK_SECRET_TOKEN}
```

**Request Body**: Telegram Update object
```json
{
  "update_id": 123456789,
  "message": {
    "message_id": 123,
    "from": {
      "id": 123456789,
      "username": "user123"
    },
    "chat": {
      "id": 123456789,
      "type": "private"
    },
    "text": "/start"
  }
}
```

**Response**:
- `200 OK` - Update processed successfully
- `403 Forbidden` - Invalid webhook secret token
- `400 Bad Request` - Invalid request format
- `500 Internal Server Error` - Processing error

### **Stripe Webhook**
```
POST /stripe-webhook
```

**Purpose**: Processes Stripe payment events

**Headers Required**:
```
Content-Type: application/json
Stripe-Signature: {stripe_signature}
```

**Request Body**: Stripe Event object
```json
{
  "id": "evt_123456789",
  "object": "event",
  "type": "checkout.session.completed",
  "data": {
    "object": {
      "id": "cs_123456789",
      "amount_total": 2500,
      "currency": "usd",
      "customer": "cus_123456789"
    }
  }
}
```

**Response**:
- `200 OK` - Event processed successfully
- `403 Forbidden` - Invalid Stripe signature
- `400 Bad Request` - Invalid event format
- `500 Internal Server Error` - Processing error

### **Health Check**
```
GET /health
```

**Purpose**: System health monitoring

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "services": {
    "database": "connected",
    "telegram": "connected",
    "stripe": "connected"
  },
  "version": "1.0.0"
}
```

## 🔌 Plugin Architecture

### **Base Plugin Class**
```python
from abc import ABC, abstractmethod
from telegram import Update
from telegram.ext import ContextTypes

class BasePlugin(ABC):
    """Base class for all bot plugins"""
    
    @abstractmethod
    def name(self) -> str:
        """Return plugin name"""
        pass
    
    @abstractmethod
    def description(self) -> str:
        """Return plugin description"""
        pass
    
    @abstractmethod
    def register_handlers(self, application):
        """Register plugin handlers with the application"""
        pass
```

### **Plugin Categories**

#### **Core Plugins** (`src/plugins/core_plugins/`)
- **core_commands_plugin.py** - Essential user commands (/start, /balance, etc.)
- **error_handling_plugin.py** - Global error handling and logging
- **message_routing_plugin.py** - Message routing and conversation management

#### **Admin Plugins** (`src/plugins/admin_plugins/`)
- **analytics_plugin.py** - Revenue analytics and reporting
- **broadcast_plugin.py** - Mass messaging capabilities
- **user_management_plugin.py** - User management and admin controls

#### **User Plugins** (`src/plugins/user_plugins/`)
- **purchase_plugin.py** - Payment processing and credit management
- **tutorial_plugin.py** - User onboarding and tutorial system

### **Plugin Manager**
```python
class PluginManager:
    """Manages plugin registration and lifecycle"""
    
    def register_plugin(self, plugin: BasePlugin):
        """Register a plugin with the bot"""
        pass
    
    def get_plugin(self, name: str) -> BasePlugin:
        """Get plugin by name"""
        pass
    
    def list_plugins(self) -> List[BasePlugin]:
        """List all registered plugins"""
        pass
```

## 💾 Database API

### **Connection Management**
```python
from src.database import get_db_connection

# Use context manager for database connections
with get_db_connection() as conn:
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE telegram_id = %s", (user_id,))
        user = cursor.fetchone()
```

### **User Management**
```python
# Get user by Telegram ID
user = get_user_by_telegram_id(telegram_id: int)

# Create new user
user_id = create_user(telegram_id: int, username: str, credits: int = 0)

# Update user credits
update_user_credits(telegram_id: int, new_credits: int)

# Get user statistics
stats = get_user_statistics(telegram_id: int)
```

### **Transaction Management**
```python
# Create transaction record
transaction_id = create_transaction(
    user_id: int,
    amount: int,
    status: str,
    stripe_data: dict
)

# Update transaction status
update_transaction_status(transaction_id: int, status: str)

# Get transaction history
transactions = get_user_transactions(user_id: int, limit: int = 10)
```

## 💳 Stripe Integration

### **Payment Processing**
```python
from src.stripe_utils import create_checkout_session, process_webhook_event

# Create Stripe checkout session
session = create_checkout_session(
    user_id: int,
    product_id: int,
    success_url: str,
    cancel_url: str
)

# Process webhook event
result = process_webhook_event(event_data: dict, signature: str)
```

### **Product Management**
```python
# Get product by ID
product = get_product_by_id(product_id: int)

# List all products
products = get_all_products()

# Create new product
product_id = create_product(
    name: str,
    price: int,
    credits_granted: int,
    stripe_price_id: str
)
```

## 🔐 Security

### **Webhook Verification**
```python
# Telegram webhook verification
def verify_telegram_webhook(request):
    secret_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
    if secret_token != os.environ.get('WEBHOOK_SECRET_TOKEN'):
        return False
    return True

# Stripe webhook verification
def verify_stripe_webhook(request):
    signature = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(
            request.data,
            signature,
            os.environ.get('STRIPE_WEBHOOK_SECRET')
        )
        return event
    except Exception as e:
        return None
```

### **Admin Authorization**
```python
def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    admin_ids = [int(id) for id in os.environ.get('ADMIN_USER_IDS', '').split(',')]
    return user_id in admin_ids
```

## 📊 Error Handling

### **Error Categories**
- **ValidationError** - Invalid input data
- **DatabaseError** - Database operation failures
- **StripeError** - Payment processing errors
- **TelegramError** - Telegram API errors
- **WebhookError** - Webhook processing errors

### **Error Response Format**
```json
{
  "error": {
    "type": "ValidationError",
    "message": "Invalid user ID provided",
    "code": "INVALID_USER_ID",
    "timestamp": "2024-01-01T00:00:00Z"
  }
}
```

## 🚀 Deployment

### **Environment Variables**
```bash
# Required
BOT_TOKEN=your_telegram_bot_token
ADMIN_GROUP_ID=your_admin_group_id
DATABASE_URL=postgresql://...
STRIPE_API_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Optional
PORT=8000
GUNICORN_WORKERS=2
GUNICORN_THREADS=2
LOG_LEVEL=INFO
```

### **Docker Deployment**
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "src.webhook_server:app"]
```

## 📈 Monitoring

### **Health Check Endpoints**
- `/health` - Basic health check
- `/health/detailed` - Detailed system status
- `/health/database` - Database connectivity
- `/health/telegram` - Telegram API status

### **Logging**
```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Log levels
logger.debug("Debug information")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical error")
```

## 🔄 Rate Limiting

### **Telegram API Limits**
- Global: 30 messages per second
- Per chat: 1 message per second
- Implement exponential backoff for retries

### **Stripe API Limits**
- 100 requests per second (live mode)
- 25 requests per second (test mode)
- Use idempotency keys for POST requests

## 📚 Integration Examples

### **Custom Plugin Development**
```python
from src.plugins.base_plugin import BasePlugin
from telegram.ext import CommandHandler

class CustomPlugin(BasePlugin):
    def name(self) -> str:
        return "custom_plugin"
    
    def description(self) -> str:
        return "Custom functionality plugin"
    
    def register_handlers(self, application):
        application.add_handler(
            CommandHandler("custom", self.custom_command)
        )
    
    async def custom_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Custom command executed!")
```

### **Webhook Integration**
```python
import requests

# Send webhook to external service
def send_webhook(url: str, data: dict):
    try:
        response = requests.post(url, json=data, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Webhook failed: {e}")
        return None
```

---

**For more detailed information, see the project documentation and source code.**
