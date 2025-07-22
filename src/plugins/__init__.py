"""
Enterprise Telegram Bot - Plugin System

This package contains the modular plugin architecture for the bot,
allowing features to be organized into focused, reusable components.
"""

from .base_plugin import BasePlugin, PluginMetadata
from .plugin_manager import PluginManager

__all__ = ["BasePlugin", "PluginMetadata", "PluginManager"]
