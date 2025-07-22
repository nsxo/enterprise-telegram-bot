"""
Enterprise Telegram Bot - Configuration Module

This module handles environment variable loading, validation, and configuration
management for the Enterprise Telegram Bot application.
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""

    pass


def get_env_var(
    var_name: str, required: bool = True, default: Optional[str] = None
) -> Optional[str]:
    """
    Get environment variable with optional default and validation.

    Args:
        var_name: Name of the environment variable
        required: Whether the variable is required
        default: Default value if not required and not found

    Returns:
        The environment variable value or default

    Raises:
        ConfigurationError: If required variable is missing
    """
    value = os.getenv(var_name, default)
    if required and not value:
        raise ConfigurationError(
            f"Required environment variable {var_name} is not set"
        )
    return value


def get_env_int(
    var_name: str, required: bool = True, default: Optional[int] = None
) -> Optional[int]:
    """
    Get environment variable as integer.

    Args:
        var_name: Name of the environment variable
        required: Whether the variable is required
        default: Default value if not required and not found

    Returns:
        The environment variable value as integer or default

    Raises:
        ConfigurationError: If required variable is missing or invalid
    """
    value = get_env_var(var_name, required, str(default) if default is not None else None)
    if value is None:
        return default

    try:
        return int(value)
    except ValueError as e:
        raise ConfigurationError(f"Environment variable {var_name} must be an integer, got: {value}") from e


def get_env_bool(var_name: str, required: bool = True, default: Optional[bool] = None) -> Optional[bool]:
    """
    Get environment variable as boolean.

    Args:
        var_name: Name of the environment variable
        required: Whether the variable is required
        default: Default value if not required and not found

    Returns:
        The environment variable value as boolean or default

    Raises:
        ConfigurationError: If required variable is missing
    """
    value = get_env_var(var_name, required, str(default).lower() if default is not None else None)
    if value is None:
        return default

    return value.lower() in ("true", "1", "yes", "on")


# =============================================================================
# TELEGRAM BOT CONFIGURATION (REQUIRED)
# =============================================================================

BOT_TOKEN = get_env_var("BOT_TOKEN")
ADMIN_GROUP_ID = get_env_int("ADMIN_GROUP_ID")
WEBHOOK_URL = get_env_var("WEBHOOK_URL", required=False)

# =============================================================================
# DATABASE CONFIGURATION (REQUIRED)
# =============================================================================

DATABASE_URL = get_env_var("DATABASE_URL")
DB_POOL_MIN_CONN = get_env_int("DB_POOL_MIN_CONN", required=False, default=2)
DB_POOL_MAX_CONN = get_env_int("DB_POOL_MAX_CONN", required=False, default=10)

# =============================================================================
# STRIPE PAYMENT CONFIGURATION (REQUIRED)
# =============================================================================

STRIPE_API_KEY = get_env_var("STRIPE_API_KEY")
STRIPE_WEBHOOK_SECRET = get_env_var("STRIPE_WEBHOOK_SECRET")

# =============================================================================
# APPLICATION CONFIGURATION (OPTIONAL)
# =============================================================================

FLASK_DEBUG = get_env_bool("FLASK_DEBUG", required=False, default=False)
LOG_LEVEL = get_env_var("LOG_LEVEL", required=False, default="INFO")
PORT = get_env_int("PORT", required=False, default=8000)

# =============================================================================
# GUNICORN CONFIGURATION (PRODUCTION)
# =============================================================================

GUNICORN_WORKERS = get_env_int("GUNICORN_WORKERS", required=False, default=4)
GUNICORN_THREADS = get_env_int("GUNICORN_THREADS", required=False, default=2)
GUNICORN_TIMEOUT = get_env_int("GUNICORN_TIMEOUT", required=False, default=30)
GUNICORN_WORKER_CLASS = get_env_var("GUNICORN_WORKER_CLASS", required=False, default="sync")

# =============================================================================
# SECURITY CONFIGURATION
# =============================================================================

SECRET_KEY = get_env_var("SECRET_KEY")
WEBHOOK_SECRET_TOKEN = get_env_var("WEBHOOK_SECRET_TOKEN", required=False)

# =============================================================================
# DEVELOPMENT SETTINGS
# =============================================================================

DEV_MODE = get_env_bool("DEV_MODE", required=False, default=False)
DEBUG_WEBHOOKS = get_env_bool("DEBUG_WEBHOOKS", required=False, default=False)


def validate_config() -> None:
    """
    Validate required configuration on startup.

    Raises:
        ConfigurationError: If configuration validation fails
    """
    logger.info("Validating configuration...")

    # Validate ADMIN_GROUP_ID format (must be negative for groups/channels)
    if ADMIN_GROUP_ID and ADMIN_GROUP_ID >= 0:
        raise ConfigurationError(
            f"ADMIN_GROUP_ID should be negative for groups/channels, got: {ADMIN_GROUP_ID}"
        )

    # Validate Stripe API key format
    if STRIPE_API_KEY and not (STRIPE_API_KEY.startswith("sk_test_") or STRIPE_API_KEY.startswith("sk_live_")):
        raise ConfigurationError("STRIPE_API_KEY must start with 'sk_test_' or 'sk_live_'")

    # Validate Stripe webhook secret format
    if STRIPE_WEBHOOK_SECRET and not STRIPE_WEBHOOK_SECRET.startswith("whsec_"):
        raise ConfigurationError("STRIPE_WEBHOOK_SECRET must start with 'whsec_'")

    # Validate database pool configuration
    if DB_POOL_MIN_CONN and DB_POOL_MAX_CONN and DB_POOL_MIN_CONN > DB_POOL_MAX_CONN:
        raise ConfigurationError(
            f"DB_POOL_MIN_CONN ({DB_POOL_MIN_CONN}) cannot be greater than DB_POOL_MAX_CONN ({DB_POOL_MAX_CONN})"
        )

    # Production safety checks
    if not DEV_MODE:
        if FLASK_DEBUG:
            logger.warning("FLASK_DEBUG is enabled in production mode - this is not recommended")
        if DEBUG_WEBHOOKS:
            logger.warning("DEBUG_WEBHOOKS is enabled in production mode - this is not recommended")

    logger.info("✅ Configuration validation passed")


def get_db_pool_size() -> int:
    """
    Calculate optimal database pool size based on Gunicorn configuration.

    Returns:
        Recommended maximum pool size

    Note:
        Uses formula: pool_size >= (gunicorn_workers * gunicorn_threads)
        as recommended in the architectural review.
    """
    recommended_size = GUNICORN_WORKERS * GUNICORN_THREADS
    configured_size = DB_POOL_MAX_CONN

    if configured_size < recommended_size:
        logger.warning(
            f"DB_POOL_MAX_CONN ({configured_size}) is smaller than recommended "
            f"size ({recommended_size}) for {GUNICORN_WORKERS} workers with "
            f"{GUNICORN_THREADS} threads each"
        )

    return max(configured_size, recommended_size)


# Validate configuration on import
try:
    validate_config()
except ConfigurationError as e:
    logger.error(f"Configuration validation failed: {e}")
    raise


# Log configuration summary (without sensitive data)
if DEV_MODE:
    logger.info("Configuration summary:")
    logger.info(f"  - BOT_TOKEN: {'***' + BOT_TOKEN[-8:] if BOT_TOKEN else 'Not set'}")
    logger.info(f"  - ADMIN_GROUP_ID: {ADMIN_GROUP_ID}")
    logger.info(f"  - DATABASE_URL: {'***' + DATABASE_URL[-20:] if DATABASE_URL else 'Not set'}")
    logger.info(f"  - STRIPE_API_KEY: {'***' + STRIPE_API_KEY[-8:] if STRIPE_API_KEY else 'Not set'}")
    logger.info(f"  - DB_POOL_MAX_CONN: {DB_POOL_MAX_CONN}")
    logger.info(f"  - Recommended pool size: {get_db_pool_size()}")
    logger.info(f"  - DEV_MODE: {DEV_MODE}")
    logger.info(f"  - FLASK_DEBUG: {FLASK_DEBUG}") 