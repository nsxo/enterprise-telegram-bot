# 🚀 Deployment Notes for Enterprise Telegram Bot

## **Automatic Deployment Process**

The bot now includes **automatic setup** that runs during startup to ensure all necessary components are in place.

### **What Happens Automatically:**

1. ✅ **Database Migrations** - All schema updates applied
2. ✅ **Product Creation** - Sample products created if none exist
3. ✅ **Command Registration** - All user commands including `/balance` and `/time`
4. ✅ **Health Checks** - Verification that everything is working

### **Using the Deploy Script:**

```bash
# Automated deployment to Railway
./deploy.sh
```

This script will:
- Commit and push your changes
- Trigger Railway deployment
- Wait for deployment completion
- Check health endpoints
- Verify the bot is ready

---

## **Manual Setup (If Needed)**

If automatic setup fails or you need to run setup manually:

### **Option 1: Railway CLI**
```bash
# Run comprehensive setup
railway run python scripts/deploy_setup.py

# Or just ensure products exist
railway run python scripts/ensure_products.py
```

### **Option 2: Local Development**
```bash
# For local testing (requires local database)
python scripts/deploy_setup.py
python scripts/ensure_products.py
```

---

## **Post-Deployment Verification**

### **1. Health Check**
```bash
curl https://your-railway-app.up.railway.app/health
```

### **2. Test Bot Commands**
- `/start` - Should show welcome with tutorial options
- `/balance` - Should display credit balance with progress bar
- `/buy` - Should show product catalog (not empty)
- `/buy10` - Should work without system errors
- `/help` - Should list all available commands
- `/time` - Should show current time

### **3. Check Logs**
```bash
railway logs
```

Look for these success messages:
- `✅ Product setup completed`
- `🎉 Successfully ensured X products exist`
- `✅ All plugins loaded and handlers registered successfully`

---

## **Troubleshooting**

### **If Products Are Still Missing:**

1. **Check startup logs** for product creation errors
2. **Run manual setup:**
   ```bash
   railway run python scripts/deploy_setup.py
   ```
3. **Verify database connection** and permissions

### **If Commands Don't Work:**

1. **Check that all plugins loaded successfully** in logs
2. **Verify no database connection errors**
3. **Test with `/help` to see available commands**

### **If Purchase Flow Fails:**

1. **Ensure products exist** (run `scripts/ensure_products.py`)
2. **Check Stripe configuration** and webhook endpoints
3. **Verify database schema** is up to date

---

## **What's Fixed in This Deployment**

✅ **Database Errors Fixed:**
- Column name mismatches (`price_usd` → `price_usd_cents`)
- Data type issues (`character varying = integer`)

✅ **Missing Commands Added:**
- `/balance` command with visual progress bars
- `/time` command for utility
- Enhanced `/status` command

✅ **Purchase System Fixed:**
- Correct product ID handling
- Proper Stripe price ID usage
- Error handling improvements

✅ **Automatic Setup:**
- Products created on startup
- Database migrations applied automatically
- Health checks included

---

## **Production Readiness Checklist**

- [ ] Environment variables configured
- [ ] Stripe webhook endpoints set up
- [ ] Admin group ID configured
- [ ] Health endpoint responding
- [ ] All commands working
- [ ] Products visible in `/buy`
- [ ] Purchase flow completing successfully

**Your bot is now ready for production use! 🎉** 