# Telegram API Documentation Library

This directory contains essential Telegram Bot API documentation for the Enterprise Telegram Bot project.

## 📚 **Available Documentation**

### **1. Core Telegram Bot API** (`bot-api.html`)
- **Source**: https://core.telegram.org/bots/api
- **Content**: Complete Telegram Bot API reference
- **Key Sections**: 
  - Available Methods (sendMessage, forwardMessage, etc.)
  - Available Types (Update, Message, User, etc.)
  - Inline mode and keyboards
  - File handling and media
  - Payments API

### **2. Python-Telegram-Bot Library** (`python-telegram-bot-docs.html`)
- **Source**: https://docs.python-telegram-bot.org/en/stable/
- **Content**: Official python-telegram-bot library documentation
- **Key Features**:
  - Handler patterns (CommandHandler, MessageHandler, CallbackQueryHandler)
  - Application and Bot classes
  - Context and update handling
  - Persistence and conversation handling

### **3. Webhooks Guide** (`webhooks-guide.html`)
- **Source**: https://core.telegram.org/bots/webhooks
- **Content**: Comprehensive webhook setup and management
- **Critical Topics**:
  - Setting up webhooks vs long polling
  - HTTPS requirements and certificate handling
  - Webhook URL security and validation
  - Error handling and retry logic

### **4. Forum Topics & Groups** (`forum-topics.html`)
- **Source**: https://core.telegram.org/bots/features#topics-in-groups
- **Content**: Forum topics functionality for group management
- **Project Relevance**:
  - `createForumTopic` method for admin conversation system
  - Topic message handling and routing
  - Message threading and organization
  - Admin group management

## 🎯 **Project-Specific Reference Guide**

### **For Bot Handlers** (`src/bot.py`)
- **Commands**: Refer to `bot-api.html` → Available Methods → sendMessage, editMessageText
- **Inline Keyboards**: `bot-api.html` → InlineKeyboardMarkup and InlineKeyboardButton
- **Message Handling**: `python-telegram-bot-docs.html` → Handlers and Context

### **For Webhook Server** (`src/webhook_server.py`)
- **Webhook Setup**: `webhooks-guide.html` → Setting a Webhook
- **Update Processing**: `bot-api.html` → Update object structure
- **Error Handling**: `webhooks-guide.html` → Testing your webhook

### **For Admin Conversation System**
- **Forum Topics**: `forum-topics.html` → Topic creation and management
- **Message Forwarding**: `bot-api.html` → forwardMessage method
- **Group Administration**: `bot-api.html` → Chat administration methods

### **For Payment Integration**
- **Payments API**: `bot-api.html` → Telegram Payments API
- **Invoice Creation**: sendInvoice and related methods
- **Payment Processing**: Pre-checkout and successful payment handling

## 🔧 **Quick Reference Commands**

### **Essential Methods for This Project**
```python
# Topic Management
context.bot.create_forum_topic(chat_id=ADMIN_GROUP_ID, name="User Topic")
context.bot.edit_forum_topic(chat_id, message_thread_id, name)

# Message Operations  
context.bot.send_message(chat_id, text, reply_markup=keyboard)
context.bot.forward_message(chat_id, from_chat_id, message_id, message_thread_id)
context.bot.set_message_reaction(chat_id, message_id, reaction)

# Webhook Management
context.bot.set_webhook(url=webhook_url, secret_token=secret)
context.bot.delete_webhook()
```

## 📖 **Integration with Cursor AI**

This documentation is now available locally for Cursor AI to reference when:
- Implementing Telegram Bot API methods
- Troubleshooting webhook issues  
- Setting up forum topic management
- Handling payment flows
- Debugging API errors and responses

The local documentation ensures accurate, up-to-date implementation guidance without requiring internet access during development. 