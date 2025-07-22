
# Project Blueprint: Enterprise Telegram Bot

## 1. Project Vision & Core Purpose

- **Goal:** To build an enterprise-grade Telegram bot that transforms a Telegram channel into a comprehensive business and communication platform.
- **Key Functions:**
    - **Monetization Engine:** A sophisticated system for selling services via Stripe, including a smart credit system, time-based access, pay-to-unlock premium content, and auto-recharge subscriptions.
    - **Admin Conversation Management:** A topic-based system in a private admin group that gives each user a dedicated, persistent thread for organized, context-rich communication.
    - **Business Intelligence:** Advanced analytics on revenue, user engagement, and content performance.
- **Core Principles:** The architecture must be **scalable**, **reliable**, **modular**, and **secure**. All real-time interactions must be **webhook-based**, not long-polling, for maximum efficiency.

---

## 2. Tech Stack & Key Libraries

- **Language:** Python 3.11+
- **Framework (for Webhooks):** Flask
- **WSGI Server:** Gunicorn
- **Telegram Library:** `python-telegram-bot[ext]` (Version 21.x or higher is preferred)
- **Database:** PostgreSQL
- **Database Driver:** `psycopg2-binary`
- **Payments:** `stripe`
- **Environment Management:** `python-dotenv`
- **Deployment:** Docker, Railway

---

## 3. Project Folder Structure

This structure separates concerns and makes the project maintainable. All new files should be created in their respective directories as defined below.

```
telegram_bot/
├── 📁 src/                # Core application logic
│   ├── __init__.py
│   ├── bot.py             # Main bot handlers and logic
│   ├── database.py        # Database connection and query functions
│   ├── config.py          # Environment variable loading and validation
│   ├── error_handler.py   # Global error handling module
│   ├── cache.py           # Caching layer for frequently accessed data
│   ├── webhook_server.py  # Flask/Gunicorn server for webhooks
│   └── stripe_utils.py    # Functions for interacting with the Stripe API
├── 📁 scripts/             # One-off, manually run scripts
│   └── setup_db.py        # Script to initialize the database schema
├── 📁 deployment/          # Deployment configurations
│   └── Dockerfile
├── 📁 docs/                # Project documentation and static assets
│   ├── PROJECT_BLUEPRINT.md # This file
│   └── schema.sql         # The authoritative database schema
├── .env                   # Local environment variables (DO NOT COMMIT)
├── .gitignore             # Specifies intentionally untracked files
└── requirements.txt       # Project dependencies
```

---

## 4. Step-by-Step Build Plan

This project will be built iteratively in phases.

### Phase 1: Initial Project & Environment Setup
1.  **Initialize Git:** Set up the Git repository.
2.  **Create `.gitignore`:** Create the file with standard Python entries (`__pycache__/`, `*.pyc`), virtual environment folders (`venv/`, `.venv/`), and sensitive files (`.env`, `*.env`).
3.  **Create Folder Structure:** Create all directories as defined in Section 3.
4.  **Create `requirements.txt`:** Populate it with the libraries listed in the Tech Stack (Section 2).

### Phase 2: Database and Configuration
1.  **Create `docs/schema.sql`:** Create this file and populate it with the complete, pre-defined SQL schema for all tables (`users`, `products`, `conversations`, `transactions`, etc.), including indexes and views.
2.  **Create `src/config.py`:**
    -   Use `python-dotenv` and `os` to load all necessary environment variables: `BOT_TOKEN`, `ADMIN_GROUP_ID`, `DATABASE_URL`, `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET`.
    -   Variables should be validated (e.g., cast to `int` where necessary) and exposed as constants.
3.  **Create `src/database.py`:**
    -   **CRITICAL:** Implement a `psycopg2.pool.SimpleConnectionPool` to manage database connections efficiently.
    -   Create a master `execute_query` function that acquires a connection from the pool, executes a query, and releases the connection back to the pool in a `finally` block.
    -   Implement specific, modular functions for all required database operations (e.g., `get_user(user_id)`, `update_user_credits(user_id, amount)`, `create_conversation_topic(user_id, topic_id)`, `get_user_id_from_topic(topic_id)`).
4.  **Create `scripts/setup_db.py`:**
    -   This script should connect to the database using the `DATABASE_URL` from `src/config.py`.
    -   It must read the contents of `docs/schema.sql` and execute them to create the database schema.

### Phase 3: Core Bot Logic & User Experience
1.  **Create `src/bot.py`:** This will contain all `python-telegram-bot` handlers.
2.  **Implement User-Facing Commands:**
    -   `/start`: Handler sends a welcome message with a single "▶️ Start" `InlineKeyboardButton`. A `CallbackQueryHandler` must listen for its `callback_data` to then display the product list.
    -   `/balance`: Handler fetches user's balance from the DB and displays it using a visual progress bar helper function (e.g., `[████░░░░░░] 40%`).
    -   `/billing`: Handler uses `stripe_utils.py` to create and send a Stripe Customer Portal session link.
    -   Quick-buy commands (e.g., `/buy10`): A single handler for multiple commands that parses the amount from the command text and initiates a purchase.
3.  **Implement Topic-Based Conversation Bridge:**
    -   Create a `master_message_handler` that is the primary message router.
    -   **Logic:**
        -   **IF** message is from a user in a private chat:
            1.  Call `get_or_create_user_topic` helper function. This function checks the DB for an existing topic; if none, it uses `context.bot.create_forum_topic` to make one in the `ADMIN_GROUP_ID` group and saves the new `topic_id` to the DB.
            2.  Forward the user's message to that `topic_id`.
        -   **IF** message is a reply from an admin inside a topic (`update.message.is_topic_message` is `True`):
            1.  Look up the `user_id` from the `topic_id` in the database.
            2.  If a user is found, copy the admin's message to that `user_id`.
            3.  React to the admin's message with a '✅' emoji to confirm it was sent.
4.  **Implement Admin User Info Card:**
    -   Create a `send_user_info_card` function that fetches user details from the DB.
    -   It should format this data into a message and send it to the user's topic with quick-action buttons (`Ban`, `Gift Credits`).
    -   This message should be pinned in the topic using `context.bot.pin_chat_message`.

### Phase 4: Webhook Server & Payment Processing
1.  **Create `src/stripe_utils.py`:**
    -   Centralize all Stripe API interactions here.
    -   Include functions like `create_checkout_session(user_id, price_id)` and `create_billing_portal_session(customer_id)`.
2.  **Create `src/webhook_server.py`:**
    -   Set up a basic Flask application.
    -   Create a `/telegram-webhook` endpoint. It receives the JSON update from Telegram, passes it to the `python-telegram-bot` `Application` object for processing, and returns a `200 OK` response.
    -   Create a `/stripe-webhook` endpoint.
        -   **CRITICAL:** It must protect against CSRF by verifying the `Stripe-Signature` header against the `STRIPE_WEBHOOK_SECRET`.
        -   Handle the `checkout.session.completed` event to grant credits/time to the user.
        -   Handle other events like `payment_intent.payment_failed` and `charge.dispute.created` to notify the admin.
    -   Create a `/health` endpoint that returns `{"status": "healthy"}`.

### Phase 5: Production Deployment
1.  **Create `deployment/Dockerfile`:**
    -   Use an official `python:3.11-slim` base image.
    -   Set up the working directory, copy `requirements.txt`, and install dependencies.
    -   Copy the `src/` and `scripts/` directories.
    -   The final `CMD` must use `gunicorn` to run the Flask app from `src/webhook_server.py`. Example: `CMD ["gunicorn", "--bind", "0.0.0.0:8000", "src.webhook_server:app"]`.
