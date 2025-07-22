# Deployment Reference for Enterprise Telegram Bot

## 🔗 **Essential Deployment Documentation Links**
- **Docker Documentation**: https://docs.docker.com/
- **Gunicorn Documentation**: https://docs.gunicorn.org/
- **Railway Deployment**: https://docs.railway.app/
- **Environment Variables**: https://12factor.net/config
- **Production Security**: https://docs.python.org/3/howto/security.html

## 🐳 **Docker Configuration**

### **1. Multi-Stage Dockerfile (Optimized for Production)**
```dockerfile
# deployment/Dockerfile
# Multi-stage build for optimized production image

# --- Stage 1: Build Stage ---
FROM python:3.11-slim as builder

WORKDIR /app

# Install build-time dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install dependencies into a wheelhouse
RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt

# --- Stage 2: Final Production Stage ---
FROM python:3.11-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Install runtime dependencies only
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --system --create-home --no-log-init appuser

# Copy the pre-built wheels from the builder stage
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

# Install dependencies from the local wheels without hitting the network
RUN pip install --no-cache /wheels/* \
    && rm -rf /wheels

# Copy application source code
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser scripts/ ./scripts/
COPY --chown=appuser:appuser docs/ ./docs/

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Expose port (Railway provides PORT environment variable)
EXPOSE ${PORT:-8000}

# Command to run the application using Gunicorn production server
# Use environment variables for configuration
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8000} --workers ${GUNICORN_WORKERS:-4} --timeout ${GUNICORN_TIMEOUT:-30} --worker-class ${GUNICORN_WORKER_CLASS:-sync} src.webhook_server:app"]
```

### **2. Docker Compose (Development)**
```yaml
# docker-compose.yml
version: '3.8'

services:
  telegram-bot:
    build:
      context: .
      dockerfile: deployment/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/telegram_bot
      - BOT_TOKEN=${BOT_TOKEN}
      - ADMIN_GROUP_ID=${ADMIN_GROUP_ID}
      - STRIPE_API_KEY=${STRIPE_API_KEY}
      - STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET}
    depends_on:
      - db
    volumes:
      - ./logs:/app/logs

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=telegram_bot
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docs/schema.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"

volumes:
  postgres_data:
```

## 🔧 **Environment Configuration**

### **1. Required Environment Variables**
```bash
# .env (Development) - DO NOT COMMIT
BOT_TOKEN=your_telegram_bot_token_here
ADMIN_GROUP_ID=-1001234567890
DATABASE_URL=postgresql://user:password@localhost:5432/telegram_bot
STRIPE_API_KEY=sk_test_your_stripe_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here

# Optional
FLASK_DEBUG=false
LOG_LEVEL=INFO
MAX_DB_CONNECTIONS=10
```

### **2. Production Environment Template**
```bash
# Production Environment Variables
BOT_TOKEN=              # Required: Your production Telegram bot token
ADMIN_GROUP_ID=         # Required: Admin group/channel ID (negative number)
DATABASE_URL=           # Required: PostgreSQL connection string
STRIPE_API_KEY=         # Required: Production Stripe API key (sk_live_...)
STRIPE_WEBHOOK_SECRET=  # Required: Stripe webhook endpoint secret

# Optional Configuration
FLASK_DEBUG=false
LOG_LEVEL=INFO
MAX_DB_CONNECTIONS=10
WEBHOOK_URL=           # Your public webhook URL
PORT=8000              # Port for Flask server
```

### **3. Configuration Validation**
```python
# src/config.py
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Required environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_GROUP_ID = os.getenv('ADMIN_GROUP_ID')
DATABASE_URL = os.getenv('DATABASE_URL')
STRIPE_API_KEY = os.getenv('STRIPE_API_KEY')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

# Optional environment variables
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
MAX_DB_CONNECTIONS = int(os.getenv('MAX_DB_CONNECTIONS', '10'))
PORT = int(os.getenv('PORT', '8000'))

def validate_config():
    """Validate required configuration on startup"""
    required_vars = {
        'BOT_TOKEN': BOT_TOKEN,
        'ADMIN_GROUP_ID': ADMIN_GROUP_ID,
        'DATABASE_URL': DATABASE_URL,
        'STRIPE_API_KEY': STRIPE_API_KEY,
        'STRIPE_WEBHOOK_SECRET': STRIPE_WEBHOOK_SECRET,
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    # Validate ADMIN_GROUP_ID format
    try:
        admin_group_id = int(ADMIN_GROUP_ID)
        if admin_group_id >= 0:
            raise ValueError("ADMIN_GROUP_ID should be negative for groups/channels")
    except ValueError as e:
        raise ValueError(f"Invalid ADMIN_GROUP_ID: {e}")
    
    print("✅ Configuration validation passed")

# Validate on import
validate_config()
```

## 🚀 **Production Deployment**

### **1. Railway Deployment**
```toml
# railway.toml
[build]
builder = "dockerfile"
dockerfilePath = "deployment/Dockerfile"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3

[env]
PORT = "8000"
```

### **2. Gunicorn Configuration**
```python
# gunicorn.conf.py
import multiprocessing

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 10

# Restart workers
max_requests = 1000
max_requests_jitter = 100
preload_app = True

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'telegram_bot_webhook_server'

# Server mechanics
daemon = False
pidfile = '/tmp/gunicorn.pid'
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
keyfile = None
certfile = None
```

### **3. Database Setup Script**
```python
# scripts/deploy_setup.py
import os
import psycopg2
from src.config import DATABASE_URL

def setup_production_database():
    """Setup database for production deployment"""
    try:
        print("🔧 Setting up production database...")
        
        # Connect to database
        connection = psycopg2.connect(DATABASE_URL)
        cursor = connection.cursor()
        
        # Read and execute schema
        schema_path = os.path.join(os.path.dirname(__file__), '..', 'docs', 'schema.sql')
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        cursor.execute(schema_sql)
        
        # Create initial products (example)
        products_sql = """
            INSERT INTO products (product_type, name, description, stripe_price_id, amount, price_usd_cents)
            VALUES 
                ('credits', '10 Credits', '10 message credits', 'price_10_credits', 10, 999),
                ('credits', '50 Credits', '50 message credits', 'price_50_credits', 50, 4999),
                ('time', '30 Day Access', '30 days premium access', 'price_30_days', 30, 2999)
            ON CONFLICT (stripe_price_id) DO NOTHING;
        """
        cursor.execute(products_sql)
        
        connection.commit()
        print("✅ Database setup completed successfully")
        
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        if connection:
            connection.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

if __name__ == "__main__":
    setup_production_database()
```

## 🛡️ **Security & Monitoring**

### **1. Security Checklist**
```bash
# Production Security Checklist

# ✅ Environment Variables
# - All secrets in environment variables
# - No hardcoded credentials
# - Strong random webhook secrets

# ✅ Database Security
# - Connection pooling enabled
# - Parameterized queries only
# - Regular backups configured

# ✅ API Security
# - Webhook signature verification
# - Rate limiting implemented
# - HTTPS only in production

# ✅ Container Security
# - Non-root user
# - Minimal base image
# - Health checks configured
```

### **2. Monitoring Setup**
```python
# src/monitoring.py
import logging
import time
from functools import wraps

def log_performance(func):
    """Decorator to log function performance"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logging.info(f"{func.__name__} executed in {execution_time:.3f}s")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logging.error(f"{func.__name__} failed after {execution_time:.3f}s: {e}")
            raise
    return wrapper

def setup_logging():
    """Setup production logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('/app/logs/app.log') if os.path.exists('/app/logs') else logging.NullHandler()
        ]
    )
```

### **3. Health Check Implementation**
```python
# Enhanced health check
@app.route('/health', methods=['GET'])
def health_check():
    """Comprehensive health check for production monitoring"""
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'services': {},
        'version': '1.0.0'
    }
    
    try:
        # Test database
        test_db_query = "SELECT 1;"
        execute_query(test_db_query)
        health_status['services']['database'] = 'ok'
    except Exception as e:
        health_status['services']['database'] = f'error: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    try:
        # Test Telegram API
        bot = telegram.Bot(token=BOT_TOKEN)
        bot.get_me()
        health_status['services']['telegram'] = 'ok'
    except Exception as e:
        health_status['services']['telegram'] = f'error: {str(e)}'
        health_status['status'] = 'degraded'
    
    status_code = 200 if health_status['status'] in ['healthy', 'degraded'] else 503
    return jsonify(health_status), status_code
```

## 🔄 **Deployment Workflow**

### **1. Deployment Steps**
```bash
# 1. Build and test locally
docker build -f deployment/Dockerfile -t telegram-bot .
docker run --env-file .env -p 8000:8000 telegram-bot

# 2. Test health endpoint
curl http://localhost:8000/health

# 3. Deploy to production
# (Railway will automatically build and deploy from repository)

# 4. Run database setup (first time only)
python scripts/deploy_setup.py

# 5. Set webhook URL
python scripts/set_webhook.py
```

### **2. Webhook Setup Script**
```python
# scripts/set_webhook.py
import telegram
from src.config import BOT_TOKEN

def set_webhook(webhook_url):
    """Set Telegram webhook URL"""
    bot = telegram.Bot(token=BOT_TOKEN)
    
    try:
        result = bot.set_webhook(
            url=f"{webhook_url}/telegram-webhook",
            allowed_updates=["message", "callback_query", "chat_member"]
        )
        
        if result:
            print(f"✅ Webhook set successfully to: {webhook_url}/telegram-webhook")
        else:
            print("❌ Failed to set webhook")
            
    except Exception as e:
        print(f"❌ Error setting webhook: {e}")

if __name__ == "__main__":
    webhook_url = input("Enter your webhook URL (https://your-app.railway.app): ")
    set_webhook(webhook_url)
```

This deployment reference covers all production deployment requirements for your Enterprise Telegram Bot project. 