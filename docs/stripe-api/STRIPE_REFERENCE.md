# Stripe API Reference for Enterprise Telegram Bot

## 🔗 **Essential Stripe Documentation Links**
- **Main API Reference**: https://stripe.com/docs/api
- **Webhooks Guide**: https://stripe.com/docs/webhooks
- **Checkout Sessions**: https://stripe.com/docs/api/checkout/sessions
- **Customer Portal**: https://stripe.com/docs/api/customer_portal/sessions
- **Payment Intents**: https://stripe.com/docs/api/payment_intents

## 💳 **Critical Stripe Integration for Your Bot**

### **1. Environment Variables Required**
```python
# In src/config.py
STRIPE_API_KEY = os.getenv('STRIPE_API_KEY')           # sk_test_... or sk_live_...
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')  # whsec_...
```

### **2. Webhook Signature Verification (CRITICAL)**
```python
import stripe
import hmac
import hashlib

def verify_stripe_signature(payload, sig_header, webhook_secret):
    """Verify Stripe webhook signature - SECURITY CRITICAL"""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        return event
    except ValueError:
        # Invalid payload
        raise ValueError("Invalid payload")
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        raise stripe.error.SignatureVerificationError("Invalid signature")
```

### **3. Create Checkout Session (For Credit Purchases)**
```python
def create_checkout_session(user_id, price_id):
    """Create Stripe checkout session for credit purchases"""
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,  # From products table: stripe_price_id
                'quantity': 1,
            }],
            mode='payment',  # One-time payment
            success_url='https://yourbot.com/success',
            cancel_url='https://yourbot.com/cancel',
            metadata={
                'user_id': str(user_id),  # Link to your users table
                'product_type': 'credits'
            },
            customer_email=None,  # Optional: if you have user email
        )
        return session.url
    except stripe.error.StripeError as e:
        # Handle Stripe errors
        raise e
```

### **4. Create Customer Portal Session (For /billing command)**
```python
def create_billing_portal_session(customer_id):
    """Create Stripe Customer Portal session for account management"""
    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,  # From users.stripe_customer_id
            return_url='https://yourbot.com/account',
        )
        return session.url
    except stripe.error.StripeError as e:
        raise e
```

### **5. Handle Webhook Events (In webhook_server.py)**
```python
def handle_stripe_webhook(request):
    """Handle Stripe webhook events"""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = verify_stripe_signature(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    
    # Handle specific events
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session['metadata']['user_id']
        
        # Grant credits to user based on purchased product
        # Update database: users.message_credits += amount
        
    elif event['type'] == 'payment_intent.payment_failed':
        # Handle failed payment
        # Notify admin group about payment failure
        
    elif event['type'] == 'invoice.payment_failed':
        # Handle subscription payment failure
        # Notify user and admin
        
    return jsonify({'status': 'success'}), 200
```

## 🏗️ **Database Integration Patterns**

### **Products Table Setup**
```sql
-- Your products should have Stripe price IDs
INSERT INTO products (product_type, name, stripe_price_id, amount, price_usd_cents) VALUES
('credits', '10 Credits Pack', 'price_1234567890', 10, 999),  -- $9.99
('credits', '50 Credits Pack', 'price_0987654321', 50, 4999), -- $49.99
('time', '30 Days Access', 'price_1122334455', 30, 2999);    -- $29.99
```

### **Customer Management**
```python
def get_or_create_stripe_customer(user):
    """Get or create Stripe customer for user"""
    if user['stripe_customer_id']:
        return user['stripe_customer_id']
    
    # Create new Stripe customer
    customer = stripe.Customer.create(
        metadata={'telegram_user_id': user['telegram_id']},
        name=user['first_name'],
    )
    
    # Update database with customer ID
    update_user_stripe_customer(user['telegram_id'], customer.id)
    return customer.id
```

## ⚠️ **Security & Error Handling**

### **Always Verify Webhooks**
```python
# NEVER trust webhook data without signature verification
# ALWAYS use the webhook secret to verify authenticity
# NEVER expose webhook endpoints without verification
```

### **Handle Stripe Errors**
```python
try:
    # Stripe API call
    result = stripe.SomeResource.create(...)
except stripe.error.CardError as e:
    # Card was declined
    pass
except stripe.error.RateLimitError as e:
    # Too many requests
    pass
except stripe.error.InvalidRequestError as e:
    # Invalid parameters
    pass
except stripe.error.AuthenticationError as e:
    # Authentication failed
    pass
except stripe.error.APIConnectionError as e:
    # Network communication failed
    pass
except stripe.error.StripeError as e:
    # Generic Stripe error
    pass
```

## 🔧 **Testing & Development**

### **Use Test Mode**
```python
# Test API keys start with sk_test_
# Test webhook endpoints with Stripe CLI:
# stripe listen --forward-to localhost:5000/stripe-webhook
```

### **Key Events to Handle**
- `checkout.session.completed` - Grant credits/access
- `payment_intent.succeeded` - Payment confirmed
- `payment_intent.payment_failed` - Payment failed
- `customer.subscription.deleted` - Subscription cancelled
- `invoice.payment_failed` - Subscription payment failed

## 📊 **Monitoring & Analytics**

### **Transaction Logging**
```python
def log_transaction(user_id, stripe_charge_id, amount, status):
    """Log all transactions for business intelligence"""
    execute_query(
        "INSERT INTO transactions (user_id, stripe_charge_id, amount_paid_usd_cents, status) VALUES (%s, %s, %s, %s)",
        (user_id, stripe_charge_id, amount, status)
    )
```

This reference covers all Stripe integration requirements for your Enterprise Telegram Bot project. 