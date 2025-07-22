# Gemini Workspace Context

## Project Overview

This project is a sophisticated, enterprise-grade Telegram bot built with Python. It features a credit-based messaging system, a comprehensive 12-category admin control center, and deep integration with Stripe for payments. The system is designed for production deployment on Railway using Docker and Gunicorn.

## Core Technologies

-   **Backend**: Python 3.11+
-   **Bot Framework**: `python-telegram-bot`
-   **Web Server**: Flask & Gunicorn
-   **Database**: PostgreSQL
-   **Payments**: Stripe API
-   **Code Quality**: `pre-commit` with `black`, `ruff`, and `gitleaks`.

## Key Files & Directories

-   `src/bot.py`: Contains the core bot logic, including command handlers and user interaction flows.
-   `src/webhook_server.py`: The Flask application entry point that handles webhooks from Telegram and Stripe. This is the main entry point for the production application.
-   `src/handlers/`: Contains the core bot logic, broken down by functionality.
    -   `message_router.py`: The central dispatcher for all incoming messages, routing them to user or admin handlers.
    -   `admin.py`, `purchases.py`, `user_interactions.py`: Specific handlers for different bot features.
-   `src/stripe_utils.py`: Handles all interactions with the Stripe API, including creating checkout sessions and processing webhooks.
-   `src/database.py`: Manages the connection to the PostgreSQL database and all database operations.
-   `src/config.py`: Loads and manages configuration from environment variables.
-   `deployment/Dockerfile`: A multi-stage Dockerfile that defines the container for production deployment.
-   `Procfile`: Defines the process for the Railway deployment, starting the `gunicorn` server.
-   `.pre-commit-config.yaml`: Defines the pre-commit hooks used to maintain code quality.

## Development Workflow

### Setup

1.  Ensure you have Python 3.11 or higher installed.
2.  Create a virtual environment: `python -m venv venv`
3.  Activate it: `source venv/bin/activate`
4.  Install dependencies: `pip install -r requirements.txt`
5.  Set up environment variables by copying `env.template` to `.env` and filling in the required values (like `BOT_TOKEN`, `DATABASE_URL`, and `STRIPE_API_KEY`).

### Running Locally

The production application runs as a web server to handle webhooks. To run it locally, use `gunicorn`:

```bash
gunicorn --bind 0.0.0.0:8000 --workers 2 --timeout 30 src.webhook_server:app
```

For development that doesn't require webhooks (e.g., testing commands), you may be able to run the bot in polling mode:

```bash
python src/bot.py
```

### Code Style & Linting

This project uses `pre-commit` to enforce code style with tools like `black`, `ruff`, and `gitleaks`. Before committing, run the checks:

```bash
pre-commit run --all-files
```

### Testing

The project is set up to use `pytest`. To run the tests, use the following command:

```bash
pytest
```

## Deployment

Deployment is handled automatically by Railway. Pushing to the `main` branch will trigger a new deployment based on the `Procfile` and `deployment/Dockerfile`. The `Procfile` specifies that the `gunicorn` web server should be started.