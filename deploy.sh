#!/bin/bash

# Enterprise Telegram Bot - Quick Deploy Script
# Ensures Railway always runs the latest version

set -e

echo "🚀 ENTERPRISE TELEGRAM BOT - QUICK DEPLOY"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if git is clean
if [[ -n $(git status --porcelain) ]]; then
    echo -e "${RED}❌ You have uncommitted changes. Please commit them first.${NC}"
    git status --short
    exit 1
fi

# Get current commit
COMMIT=$(git rev-parse --short HEAD)
BRANCH=$(git branch --show-current)

echo -e "${BLUE}📊 Current status:${NC}"
echo -e "  Branch: ${BRANCH}"
echo -e "  Commit: ${COMMIT}"

# Confirm deployment
echo ""
read -p "🚀 Deploy commit ${COMMIT} to Railway? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}⏹️  Deployment cancelled${NC}"
    exit 0
fi

echo -e "${BLUE}🔄 Triggering Railway deployment...${NC}"

# Create deployment trigger with timestamp
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
cat > .railway-trigger << EOF
🚀 Manual Deployment Trigger
=========================
Timestamp: ${TIMESTAMP}
Commit: ${COMMIT}
Branch: ${BRANCH}
Deployed by: $(whoami)
Host: $(hostname)

This file triggers Railway to deploy the latest code.
EOF

# Commit and push the trigger
git add .railway-trigger
git commit -m "🚀 Deploy: ${TIMESTAMP} (${COMMIT})"

echo -e "${BLUE}📤 Pushing to GitHub...${NC}"
git push origin main

echo -e "${GREEN}✅ Deployment triggered!${NC}"
echo ""
echo -e "${BLUE}📋 Next steps:${NC}"
echo "  1. Railway will automatically deploy the latest code"
echo "  2. Check deployment status: railway logs"
echo "  3. Verify health: curl https://independent-art-production-51fb.up.railway.app/health"
echo "  4. Test bot: Send /start to your bot in Telegram"
echo ""
echo -e "${YELLOW}⏳ Deployment usually takes 2-3 minutes${NC}"

# Optional: Wait and check health
read -p "🔍 Wait for deployment and check health? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}⏳ Waiting 90 seconds for deployment...${NC}"
    sleep 90
    
    echo -e "${BLUE}🏥 Checking health endpoint...${NC}"
    HEALTH_URL="https://independent-art-production-51fb.up.railway.app/health"
    
    if curl -s "$HEALTH_URL" | grep -q "healthy"; then
        echo -e "${GREEN}✅ Deployment successful! Bot is healthy${NC}"
    else
        echo -e "${YELLOW}⚠️  Health check inconclusive. Check Railway logs:${NC}"
        echo "  railway logs"
    fi
fi

echo ""
echo -e "${GREEN}🎉 Deployment process complete!${NC}" 