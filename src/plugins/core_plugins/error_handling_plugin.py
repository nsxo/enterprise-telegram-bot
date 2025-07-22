"""
Enterprise Telegram Bot - Error Handling Plugin

This plugin provides centralized error handling for the bot,
including logging and user-facing error messages.
"""

import logging
from typing import Dict, Any
from telegram.ext import ContextTypes, Application
from telegram.error import TelegramError

from src.plugins.base_plugin import BasePlugin, PluginMetadata
from src.services.error_service import ErrorService, ErrorType

logger = logging.getLogger(__name__)


class ErrorHandlingPlugin(BasePlugin):
    """Plugin for centralized error handling."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="ErrorHandling",
            version="1.0.0",
            description="Centralized error handling and user notifications",
            dependencies=[],
        )

    async def initialize(self, config: Dict[str, Any] = None) -> bool:
        logger.info("Initializing Error Handling Plugin...")
        return True

    def register_handlers(self, application: Application) -> None:
        application.add_error_handler(self.global_error_handler)

    def get_commands(self) -> Dict[str, str]:
        return {}

    async def global_error_handler(
        self, update: object, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Log the error and send a user-friendly message."""
        error = context.error

        if isinstance(error, TelegramError):
            await ErrorService.handle_error(update, context, ErrorType.API_ERROR, error)
        elif isinstance(error, (ValueError, TypeError)):
            await ErrorService.handle_error(
                update, context, ErrorType.USER_ERROR, error
            )
        else:
            await ErrorService.handle_error(
                update, context, ErrorType.SYSTEM_ERROR, error
            )
