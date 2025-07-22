# 🤖 Enterprise Telegram Bot

A production-ready, enterprise-grade Telegram bot that transforms a Telegram channel into a comprehensive business and communication platform with advanced monetization, admin management, and business intelligence capabilities.

## 🚀 Features

### 💰 **Monetization Engine**
- **Smart Credit System** - Flexible credit-based access control
- **Time-Based Access** - Pay-per-minute access to premium content
- **Stripe Integration** - Secure payment processing with idempotency
- **Auto-Recharge** - Subscription management via Stripe Customer Portal
- **Business Intelligence** - Revenue analytics and transaction tracking

### 👥 **Admin Conversation Management**
- **Topic-Based System** - Each user gets a dedicated admin thread
- **Two-Stage Routing** - Robust message routing with fallback system
- **User Info Cards** - Pinned user profiles with quick admin actions
- **Deep Topic Linking** - Direct links to user conversations
- **Admin Dashboard** - Comprehensive user management in Telegram

### 🔒 **Enterprise Security**
- **Webhook Signature Verification** - Prevents fraudulent webhook attacks
- **Thread-Safe Database** - ThreadedConnectionPool for production load
- **Parameterized Queries** - SQL injection prevention
- **Environment Validation** - Startup configuration verification
- **Non-Root Containers** - Security-hardened Docker deployment

### 📊 **Business Intelligence**
- **User Analytics** - Comprehensive user dashboard views
- **Revenue Tracking** - Complete transaction lifecycle management
- **Performance Monitoring** - Health checks and error alerting
- **Caching Layer** - Optimized performance for high-traffic scenarios

### 🔌 **Plugin Architecture**
- **Modular Design** - Clean separation of concerns with plugin system
- **Core Plugins** - Essential bot functionality (commands, routing, error handling)
- **Admin Plugins** - Advanced admin features (analytics, broadcast, user management)
- **User Plugins** - User-facing features (purchases, tutorials)
- **Extensible Framework** - Easy to add new features and capabilities

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Telegram      │    │   Flask         │    │   PostgreSQL    │
│   Bot API       │◄──►│   Webhook       │◄──►│   Database      │
│                 │    │   Server        │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Stripe        │
                       │   Payments      │
                       └─────────────────┘
```

### **Core Components**
- **Flask Webhook Server** - Application factory pattern with security
- **Plugin Manager** - Modular architecture for extensible functionality
- **ThreadedConnectionPool** - Production-ready database connections
- **Arbitrary Callback Data** - Secure inline keyboard interactions
- **Comprehensive Error Handling** - Admin alerting and recovery
- **Multi-Stage Docker** - Optimized production deployment

## 🛠️ Tech Stack

- **Language:** Python 3.11+
- **Framework:** Flask (webhook server)
- **WSGI Server:** Gunicorn (production)
- **Telegram Library:** python-telegram-bot[ext] 21.x+
- **Database:** PostgreSQL with psycopg2-binary
- **Payments:** Stripe API with webhook verification
- **Deployment:** Docker multi-stage builds
- **Platform:** Railway/Heroku ready

## 📦 Installation

### **Prerequisites**
- Python 3.11+
- PostgreSQL database
- Telegram Bot Token (from @BotFather)
- Stripe account and API keys

### **Quick Start**

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/enterprise-telegram-bot.git
   cd enterprise-telegram-bot
   ```

2. **Set up environment**
   ```bash
   # Copy environment template
   cp env.template .env
   
   # Edit with your configuration
   nano .env
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize database**
   ```bash
   python scripts/setup_db.py
   ```

5. **Start the bot**
   ```bash
   # Development
   python src/webhook_server.py
   
   # Production
   gunicorn --bind 0.0.0.0:8000 --workers 4 src.webhook_server:app
   ```

## ⚙️ Configuration

### **Required Environment Variables**

```bash
# Telegram Bot
BOT_TOKEN=your_telegram_bot_token_here
ADMIN_GROUP_ID=-1001234567890
WEBHOOK_URL=https://your-app.railway.app

# Database
DATABASE_URL=postgresql://username:password@hostname:port/database_name

# Stripe Payments
STRIPE_API_KEY=sk_test_your_stripe_api_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here

# Security
SECRET_KEY=your_super_secret_key_here
WEBHOOK_SECRET_TOKEN=your_webhook_secret_token_here
```

### **Optional Configuration**
```bash
# Application
FLASK_DEBUG=false
LOG_LEVEL=INFO
PORT=8000

# Gunicorn (Production)
GUNICORN_WORKERS=4
GUNICORN_THREADS=2
GUNICORN_TIMEOUT=30

# Development
DEV_MODE=false
DEBUG_WEBHOOKS=false
```

## 🚀 Deployment

### **Railway (Recommended)**
1. Connect your GitHub repository to Railway
2. Set environment variables in Railway dashboard
3. Deploy automatically on push to main branch

### **Docker**
```bash
# Build and run
docker build -f deployment/Dockerfile -t enterprise-telegram-bot .
docker run -p 8000:8000 --env-file .env enterprise-telegram-bot
```

### **Manual Deployment**
```bash
# Install dependencies
pip install -r requirements.txt

# Set up database
python scripts/setup_db.py

# Start with Gunicorn
gunicorn --bind 0.0.0.0:8000 --workers 4 src.webhook_server:app
```

## 📚 Usage

### **User Commands**
- `/start` - Welcome message with product catalog
- `/balance` - Check credit balance with progress bar
- `/billing` - Access Stripe Customer Portal
- `/buy10`, `/buy25`, `/buy50`, `/buy100` - Quick purchase commands

### **Admin Features**
- **Topic Management** - Automatic user conversation threads
- **User Info Cards** - Pinned user profiles with admin actions
- **Credit Management** - Gift credits, ban users, upgrade tiers
- **Payment Monitoring** - Transaction tracking and dispute handling

### **Webhook Endpoints**
- `POST /telegram-webhook` - Telegram update processing
- `POST /stripe-webhook` - Stripe payment events (signature verified)
- `GET /health` - Health check for monitoring

## 🔧 Development

### **Plugin Architecture**
The bot uses a modular plugin system for clean separation of concerns:

```
src/plugins/
├── base_plugin.py          # Base plugin class
├── plugin_manager.py       # Plugin management system
├── core_plugins/           # Essential bot functionality
│   ├── core_commands_plugin.py
│   ├── error_handling_plugin.py
│   └── message_routing_plugin.py
├── admin_plugins/          # Admin features
│   ├── analytics_plugin.py
│   ├── broadcast_plugin.py
│   └── user_management_plugin.py
└── user_plugins/           # User-facing features
    ├── purchase_plugin.py
    └── tutorial_plugin.py
```

### **Code Quality**
```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run quality checks
pre-commit run --all-files
```

### **Testing**
```bash
# Run tests
pytest

# Check code coverage
pytest --cov=src
```

### **Database Management**
```bash
# Initialize database
python scripts/setup_db.py

# View database schema
cat project_documentation/docs/schema.sql
```

## 📊 Monitoring

### **Health Checks**
- Database connectivity monitoring
- Telegram bot API status
- Stripe API connectivity
- Application performance metrics

### **Error Handling**
- Comprehensive error logging
- Admin alerting for critical issues
- Automatic error categorization
- Recovery mechanisms

### **Business Intelligence**
- User engagement analytics
- Revenue tracking and reporting
- Transaction lifecycle monitoring
- Performance optimization insights

## 🔒 Security

### **Implemented Security Measures**
- ✅ Webhook signature verification
- ✅ SQL injection prevention
- ✅ Environment variable validation
- ✅ Non-root Docker containers
- ✅ Thread-safe database connections
- ✅ Secure payment processing
- ✅ Comprehensive error handling

### **Security Checklist**
- [ ] Set strong SECRET_KEY
- [ ] Use HTTPS in production
- [ ] Configure webhook secrets
- [ ] Enable admin notifications
- [ ] Monitor error logs
- [ ] Regular security updates

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### **Development Guidelines**
- Follow the `.cursorrules` guidelines
- Use pre-commit hooks for code quality
- Write comprehensive docstrings
- Include type hints for all functions
- Test thoroughly before submitting

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### **Documentation**
- [API Reference](project_documentation/docs/API_GUIDE.md)
- [Function Specifications](project_documentation/docs/FUNCTION_SPECS.md)
- [User Stories](project_documentation/docs/USER_STORIES.md)
- [Database Schema](project_documentation/docs/schema.sql)

### **Issues**
- Report bugs via [GitHub Issues](https://github.com/yourusername/enterprise-telegram-bot/issues)
- Request features through issue templates
- Check existing issues before creating new ones

### **Community**
- Join our [Telegram Support Group](https://t.me/your_support_group)
- Follow development updates
- Share your implementations

## 🎯 Roadmap

### **Planned Features**
- [ ] Advanced analytics dashboard
- [ ] Multi-language support
- [ ] Advanced admin permissions
- [ ] Automated testing suite
- [ ] Performance optimization
- [ ] Mobile admin app

### **Architecture Improvements**
- [ ] Redis caching integration
- [ ] Message queue system
- [ ] Microservices architecture
- [ ] Advanced monitoring
- [ ] Auto-scaling support

---

**Built with ❤️ for the Telegram community**

*Enterprise-grade Telegram bot architecture for modern businesses* 