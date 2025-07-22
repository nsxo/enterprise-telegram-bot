"""
Enterprise Telegram Bot - Base Plugin

Abstract base class that all plugins must inherit from.
Provides the interface and common functionality for the plugin system.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from telegram.ext import Application

logger = logging.getLogger(__name__)


class PluginMetadata:
    """Metadata for a plugin containing version and dependency information."""

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        author: str = "Enterprise Bot Team",
        dependencies: Optional[List[str]] = None,
        min_bot_version: str = "1.0.0",
    ):
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.dependencies = dependencies or []
        self.min_bot_version = min_bot_version


class BasePlugin(ABC):
    """
    Abstract base class for all bot plugins.

    Plugins provide modular functionality that can be loaded, unloaded,
    and managed independently. Each plugin should focus on a specific
    feature set or domain.
    """

    def __init__(self):
        self._initialized = False
        self._enabled = False
        self._config = {}
        self._handlers = []

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata including name, version, and dependencies."""
        pass

    @property
    def name(self) -> str:
        """Get the plugin name."""
        return self.metadata.name

    @property
    def version(self) -> str:
        """Get the plugin version."""
        return self.metadata.version

    @property
    def is_initialized(self) -> bool:
        """Check if the plugin has been initialized."""
        return self._initialized

    @property
    def is_enabled(self) -> bool:
        """Check if the plugin is currently enabled."""
        return self._enabled

    @abstractmethod
    async def initialize(self, config: Dict[str, Any] = None) -> bool:
        """
        Initialize the plugin with configuration.

        Args:
            config: Plugin-specific configuration dictionary

        Returns:
            True if initialization successful, False otherwise
        """
        pass

    @abstractmethod
    def register_handlers(self, application: Application) -> None:
        """
        Register all handlers with the Telegram application.

        Args:
            application: The Telegram bot application instance
        """
        pass

    @abstractmethod
    def get_commands(self) -> Dict[str, str]:
        """
        Get a dictionary of commands this plugin provides.

        Returns:
            Dictionary mapping command names to descriptions
        """
        pass

    async def enable(self) -> bool:
        """
        Enable the plugin.

        Returns:
            True if enabled successfully, False otherwise
        """
        try:
            if not self._initialized:
                logger.error(f"Cannot enable plugin {self.name}: not initialized")
                return False

            await self._on_enable()
            self._enabled = True
            logger.info(f"✅ Plugin {self.name} enabled")
            return True

        except Exception as e:
            logger.error(f"Failed to enable plugin {self.name}: {e}")
            return False

    async def disable(self) -> bool:
        """
        Disable the plugin.

        Returns:
            True if disabled successfully, False otherwise
        """
        try:
            await self._on_disable()
            self._enabled = False
            logger.info(f"🔴 Plugin {self.name} disabled")
            return True

        except Exception as e:
            logger.error(f"Failed to disable plugin {self.name}: {e}")
            return False

    async def shutdown(self) -> None:
        """Clean up plugin resources before shutdown."""
        try:
            if self._enabled:
                await self.disable()
            await self._on_shutdown()
            self._initialized = False
            logger.info(f"🔄 Plugin {self.name} shut down")

        except Exception as e:
            logger.error(f"Error during plugin {self.name} shutdown: {e}")

    def set_config(self, config: Dict[str, Any]) -> None:
        """Set plugin configuration."""
        self._config = config or {}

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config.get(key, default)

    async def _on_enable(self) -> None:
        """Hook called when plugin is enabled. Override in subclasses."""
        pass

    async def _on_disable(self) -> None:
        """Hook called when plugin is disabled. Override in subclasses."""
        pass

    async def _on_shutdown(self) -> None:
        """Hook called during plugin shutdown. Override in subclasses."""
        pass

    def _mark_initialized(self) -> None:
        """Mark the plugin as initialized (internal use only)."""
        self._initialized = True

    def __str__(self) -> str:
        """String representation of the plugin."""
        return f"{self.name} v{self.version}"

    def __repr__(self) -> str:
        """Detailed string representation of the plugin."""
        return f"<{self.__class__.__name__}: {self.name} v{self.version}>"
