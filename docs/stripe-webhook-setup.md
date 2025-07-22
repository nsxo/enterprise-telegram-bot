# Stripe Webhook Setup Guide

## 🎯 **Quick Start: Creating Stripe Webhooks via Terminal**

Your application is already configured to handle Stripe webhooks at `/stripe-webhook`. Here are multiple ways to create them:

## 🔧 **Method 1: Using Our Custom Script (Recommended)**

We've created a comprehensive webhook management script:

### **Development Webhooks (Local Testing)**
```bash
# Install and setup Stripe CLI first
brew install stripe/stripe-cli/stripe
stripe login

# Create development webhook
python scripts/setup_stripe_webhooks.py create-dev --port 8000
```

### **Production Webhooks (Live Deployment)**
```bash
# Create production webhook
python scripts/setup_stripe_webhooks.py create-prod \
  --webhook-url https://your-app.railway.app

# Or with custom description
python scripts/setup_stripe_webhooks.py create-prod \
  --description "My Bot Production Webhook"
```

### **Webhook Management**
```bash
# List all existing webhooks
python scripts/setup_stripe_webhooks.py list

# Test webhook functionality
python scripts/setup_stripe_webhooks.py test

# Validate current configuration
python scripts/setup_stripe_webhooks.py validate

# Delete specific webhook
python scripts/setup_stripe_webhooks.py delete --webhook-id we_xxx

# Get help
python scripts/setup_stripe_webhooks.py --help
```

---

## 🌐 **Method 2: Direct Stripe CLI Commands**

### **Installation**
```bash
# macOS
brew install stripe/stripe-cli/stripe

# Windows (via winget)
winget install stripe.cli

# Or download from: https://github.com/stripe/stripe-cli/releases
```

### **Authentication**
```bash
stripe login
```

### **Development Webhook**
```bash
# Forward webhook events to local development server
stripe listen --forward-to localhost:8000/stripe-webhook \
  --events checkout.session.completed,payment_intent.payment_failed,charge.dispute.created

# This will output a webhook secret like: whsec_xxx
# Copy this to your .env file as STRIPE_WEBHOOK_SECRET
```

### **Production Webhook Creation**
```bash
# Create webhook endpoint for production
stripe webhook_endpoints create \
  --url https://your-app.railway.app/stripe-webhook \
  --enabled-events checkout.session.completed \
  --enabled-events payment_intent.payment_failed \
  --enabled-events charge.dispute.created \
  --enabled-events customer.subscription.deleted \
  --enabled-events payment_method.attached

# List existing webhooks
stripe webhook_endpoints list

# Get webhook details (including secret)
stripe webhook_endpoints retrieve we_xxxxx
```

---

## 🐍 **Method 3: Python Script (Direct API)**

Create a simple script to manage webhooks programmatically:

```python
#!/usr/bin/env python3
import stripe
import os

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_API_KEY')

def create_production_webhook(webhook_url):
    """Create webhook endpoint for production."""
    
    events = [
        'checkout.session.completed',
        'payment_intent.payment_failed',
        'charge.dispute.created',
        'customer.subscription.deleted',
        'payment_method.attached',
    ]
    
    webhook = stripe.WebhookEndpoint.create(
        url=f"{webhook_url}/stripe-webhook",
        enabled_events=events,
        description="Enterprise Telegram Bot Webhook"
    )
    
    print(f"✅ Webhook created: {webhook.id}")
    print(f"🔑 Secret: {webhook.secret}")
    print(f"Add to .env: STRIPE_WEBHOOK_SECRET={webhook.secret}")
    
    return webhook

# Usage
if __name__ == '__main__':
    webhook_url = "https://your-app.railway.app"
    create_production_webhook(webhook_url)
```

---

## ⚙️ **Configuration Requirements**

### **Environment Variables**
Your `.env` file needs:
```bash
# Stripe Configuration
STRIPE_API_KEY=sk_test_xxxxx  # or sk_live_xxxxx for production
STRIPE_WEBHOOK_SECRET=whsec_xxxxx  # From webhook creation

# Webhook URL (production)
WEBHOOK_URL=https://your-app.railway.app
```

### **Webhook Events Handled**
Your application automatically handles these events:
- ✅ `checkout.session.completed` - Grant credits after purchase
- ✅ `payment_intent.payment_failed` - Handle payment failures
- ✅ `charge.dispute.created` - Handle chargebacks/disputes
- ✅ `customer.subscription.deleted` - Handle cancellations
- ✅ `payment_method.attached` - Payment method updates

---

## 🧪 **Testing Webhooks**

### **Using Stripe CLI**
```bash
# Send test events
stripe trigger checkout.session.completed
stripe trigger payment_intent.payment_failed

# Forward live events to local development
stripe listen --forward-to localhost:8000/stripe-webhook
```

### **Using Dashboard**
1. Go to Stripe Dashboard → Webhooks
2. Click on your webhook endpoint
3. Click "Send test webhook"
4. Select event type and send

### **Manual Testing**
```bash
# Test with curl (for development)
curl -X POST http://localhost:8000/stripe-webhook \
  -H "Content-Type: application/json" \
  -H "Stripe-Signature: your_signature" \
  -d '{"type": "checkout.session.completed", "data": {...}}'
```

---

## 🔒 **Security Checklist**

- ✅ **Signature Verification**: Your app verifies `Stripe-Signature` header
- ✅ **HTTPS Required**: Production webhooks must use HTTPS
- ✅ **Secret Management**: Store `STRIPE_WEBHOOK_SECRET` securely
- ✅ **Event Validation**: Only process expected event types
- ✅ **Idempotency**: Handle duplicate events gracefully

---

## 🚨 **Troubleshooting**

### **Common Issues**

1. **Webhook Secret Not Working**
   ```bash
   # Verify secret format
   echo $STRIPE_WEBHOOK_SECRET
   # Should start with whsec_
   ```

2. **Events Not Received**
   ```bash
   # Check webhook status
   python scripts/setup_stripe_webhooks.py validate
   ```

3. **Signature Verification Failed**
   - Ensure raw request body is used for verification
   - Check that secret matches the webhook endpoint
   - Verify timezone/timestamp issues

4. **Development Testing**
   ```bash
   # Use ngrok for external webhook testing
   ngrok http 8000
   # Use the ngrok URL for webhook creation
   ```

### **Monitoring**
- Monitor webhook deliveries in Stripe Dashboard
- Check application logs for webhook processing
- Use health endpoint: `GET /health` to verify service status

---

## 📚 **Additional Resources**

- [Stripe Webhooks Guide](https://stripe.com/docs/webhooks)
- [Stripe CLI Documentation](https://stripe.com/docs/stripe-cli)
- [Your Application's Webhook Handler](../src/webhook_server.py)
- [Stripe Integration Utils](../src/stripe_utils.py)

This guide covers all the methods to create and manage Stripe webhooks for your Enterprise Telegram Bot! 