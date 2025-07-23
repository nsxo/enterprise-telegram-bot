# 🔧 Bot Fix Deployment Guide

## Issues Fixed

### ✅ 1. Database Schema Issue
**Problem**: Missing `updated_at` column in conversations table
**Solution**: Added `apply_conversations_updated_at_fix()` migration that will run on next deployment

### ✅ 2. Billing Portal Issue  
**Problem**: Using Telegram user ID instead of Stripe customer ID
**Solution**: Fixed billing command to use proper `stripe_customer_id` from database

### ⏳ 3. Stripe Products Issue
**Problem**: Using test price IDs that don't exist in your Stripe account
**Solution**: Need to create real Stripe products

## Deployment Steps

### Step 1: Deploy the Fixes
```bash
git add .
git commit -m "Fix database schema and billing portal issues"
git push origin main
```

The bot will automatically restart and apply the database migration.

### Step 2: Set Up Real Stripe Products
Since the local script can't connect to Railway's database, you have two options:

#### Option A: Use Stripe Dashboard (Recommended)
1. Go to your [Stripe Dashboard](https://dashboard.stripe.com)
2. Navigate to **Products** → **Add Product**
3. Create these products:

| Product Name | Price | Description |
|--------------|-------|-------------|
| 10 Credits Pack | $5.00 | Perfect for light usage - 10 message credits |
| 25 Credits Pack | $10.00 | Great value - 25 message credits |
| 50 Credits Pack | $18.00 | Best value - 50 message credits |
| 7 Days Access | $15.00 | Unlimited messages for 7 days |
| 30 Days Access | $50.00 | Unlimited messages for 30 days |

4. Copy the **Price IDs** (they look like `price_xxxxxxxxxx`)

#### Option B: Railway CLI Script
1. Install Railway CLI: `npm install -g @railway/cli`
2. Login: `railway login`
3. Connect to your project: `railway link`
4. Run the script: `railway run python scripts/setup_stripe_products.py`

### Step 3: Update Database with Real Price IDs
You'll need to update the database to replace the test price IDs with real ones.

**Connect to your Railway database** and run these queries:
```sql
UPDATE products SET stripe_price_id = 'your_real_price_id_here' WHERE stripe_price_id = 'price_10credits_test';
UPDATE products SET stripe_price_id = 'your_real_price_id_here' WHERE stripe_price_id = 'price_25credits_test';
UPDATE products SET stripe_price_id = 'your_real_price_id_here' WHERE stripe_price_id = 'price_50credits_test';
UPDATE products SET stripe_price_id = 'your_real_price_id_here' WHERE stripe_price_id = 'price_7days_test';
UPDATE products SET stripe_price_id = 'your_real_price_id_here' WHERE stripe_price_id = 'price_30days_test';
```

### Step 4: Test the Bot
1. Try `/start` command - should work without database errors
2. Try `/buy` command - should show products with working payment links
3. Try `/billing` command - should work after making a purchase

## Expected Results

✅ **User commands work** without database errors  
✅ **Admin commands work** without crashes  
✅ **Purchase flow works** with real Stripe checkout  
✅ **Billing portal works** for existing customers  

## If Issues Persist

1. Check Railway logs for any remaining errors
2. Verify all environment variables are set correctly
3. Ensure Stripe webhook endpoints are configured
4. Test with a small purchase to verify the complete flow

---

## Quick Deployment Commands

```bash
# Deploy the fixes
git add .
git commit -m "Fix critical bot issues: database schema, billing portal, error handling"
git push origin main

# Monitor deployment
railway logs --follow
```

The bot should be working properly after these fixes are deployed! 🚀 