"""
Enterprise Telegram Bot - Plugin Manager

Manages plugin discovery, loading, initialization, and lifecycle.
Provides isolation and error handling for plugin operations.
"""

import logging
import importlib
import inspect
import os
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
from telegram.ext import Application

from .base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class PluginLoadError(Exception):
    """Exception raised when a plugin fails to load."""

    pass


class PluginDependencyError(Exception):
    """Exception raised when plugin dependencies cannot be resolved."""

    pass


class PluginManager:
    """
    Manages the plugin system for the Telegram bot.

    Handles plugin discovery, dependency resolution, initialization,
    and lifecycle management with proper error isolation.
    """

    def __init__(self, plugin_directories: List[str] = None):
        """
        Initialize the plugin manager.

        Args:
            plugin_directories: List of directories to search for plugins
        """
        self.plugins: Dict[str, BasePlugin] = {}
        self.plugin_configs: Dict[str, Dict[str, Any]] = {}
        self.failed_plugins: Dict[str, str] = {}
        self.application: Optional[Application] = None

        # Default plugin directories
        if plugin_directories is None:
            plugin_base = Path(__file__).parent
            plugin_directories = [
                str(plugin_base / "admin_plugins"),
                str(plugin_base / "user_plugins"),
                str(plugin_base / "core_plugins"),
            ]

        self.plugin_directories = plugin_directories
        self._dependency_graph: Dict[str, Set[str]] = {}

    def register_application(self, application: Application) -> None:
        """Register the Telegram application for handler registration."""
        self.application = application

    async def discover_plugins(self) -> None:
        """Discover all available plugins in the plugin directories."""
        logger.info("🔍 Discovering plugins...")

        discovered_count = 0

        for directory in self.plugin_directories:
            if not os.path.exists(directory):
                logger.warning(f"Plugin directory does not exist: {directory}")
                continue

            try:
                discovered_count += await self._discover_plugins_in_directory(directory)
            except Exception as e:
                logger.error(f"Error discovering plugins in {directory}: {e}")

        logger.info(f"📦 Discovered {discovered_count} plugins")

        # Build dependency graph
        self._build_dependency_graph()

    async def _discover_plugins_in_directory(self, directory: str) -> int:
        """Discover plugins in a specific directory."""
        discovered = 0
        directory_path = Path(directory)

        # Look for Python files that might contain plugins
        for python_file in directory_path.glob("*.py"):
            if python_file.name.startswith("__"):
                continue

            module_name = python_file.stem
            try:
                # Import the module using the correct module path
                # Construct the proper module path with src prefix
                if "admin_plugins" in str(python_file):
                    module_path = f"src.plugins.admin_plugins.{module_name}"
                elif "user_plugins" in str(python_file):
                    module_path = f"src.plugins.user_plugins.{module_name}"
                elif "core_plugins" in str(python_file):
                    module_path = f"src.plugins.core_plugins.{module_name}"
                else:
                    # Fallback for other plugin directories
                    relative_path = python_file.relative_to(
                        Path(__file__).parent.parent.parent
                    )
                    module_path = str(relative_path).replace('/', '.').replace('\\', '.')
                    module_path = module_path.replace('.py', '')
                
                module = importlib.import_module(module_path)

                # Find plugin classes in the module
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (
                        issubclass(obj, BasePlugin)
                        and obj != BasePlugin
                        and not inspect.isabstract(obj)
                    ):

                        try:
                            plugin_instance = obj()
                            plugin_name = plugin_instance.name

                            if plugin_name in self.plugins:
                                logger.warning(
                                    f"Plugin {plugin_name} already exists, skipping"
                                )
                                continue

                            self.plugins[plugin_name] = plugin_instance
                            discovered += 1
                            logger.info(
                                f"✅ Discovered plugin: {plugin_name} "
                                f"v{plugin_instance.version}"
                            )

                        except Exception as e:
                            logger.error(
                                f"Failed to instantiate plugin {name}: {e}"
                            )
                            self.failed_plugins[name] = str(e)

            except Exception as e:
                logger.error(f"Failed to import module {module_name}: {e}")

        return discovered

    def _build_dependency_graph(self) -> None:
        """Build the plugin dependency graph."""
        self._dependency_graph.clear()

        for plugin_name, plugin in self.plugins.items():
            dependencies = set(plugin.metadata.dependencies)
            self._dependency_graph[plugin_name] = dependencies

            # Validate dependencies exist
            for dep in dependencies:
                if dep not in self.plugins:
                    logger.error(f"Plugin {plugin_name} has missing dependency: {dep}")

    def _get_load_order(self) -> List[str]:
        """
        Calculate the correct plugin load order based on dependencies.

        Returns:
            List of plugin names in load order

        Raises:
            PluginDependencyError: If circular dependencies are detected
        """
        # Topological sort to resolve dependencies
        in_degree = {name: 0 for name in self.plugins}

        # Calculate in-degrees
        for plugin_name, dependencies in self._dependency_graph.items():
            for dep in dependencies:
                if dep in in_degree:
                    in_degree[plugin_name] += 1

        # Find plugins with no dependencies
        queue = [name for name, degree in in_degree.items() if degree == 0]
        load_order = []

        while queue:
            current = queue.pop(0)
            load_order.append(current)

            # Update in-degrees for dependent plugins
            for plugin_name, dependencies in self._dependency_graph.items():
                if current in dependencies:
                    in_degree[plugin_name] -= 1
                    if in_degree[plugin_name] == 0:
                        queue.append(plugin_name)

        # Check for circular dependencies
        if len(load_order) != len(self.plugins):
            remaining = [name for name in self.plugins if name not in load_order]
            raise PluginDependencyError(f"Circular dependencies detected: {remaining}")

        return load_order

    async def initialize_all_plugins(self) -> None:
        """Initialize all discovered plugins in dependency order."""
        if not self.plugins:
            logger.info("No plugins to initialize")
            return

        try:
            load_order = self._get_load_order()
            logger.info(f"🚀 Initializing plugins in order: {load_order}")

            for plugin_name in load_order:
                await self._initialize_plugin(plugin_name)

        except PluginDependencyError as e:
            logger.error(f"Plugin dependency error: {e}")
            raise

    async def _initialize_plugin(self, plugin_name: str) -> bool:
        """Initialize a single plugin."""
        plugin = self.plugins.get(plugin_name)
        if not plugin:
            logger.error(f"Plugin {plugin_name} not found")
            return False

        try:
            # Get plugin configuration
            config = self.plugin_configs.get(plugin_name, {})
            plugin.set_config(config)

            # Initialize the plugin
            success = await plugin.initialize(config)
            if success:
                plugin._mark_initialized()
                logger.info(f"✅ Initialized plugin: {plugin_name}")
                return True
            else:
                logger.error(f"Plugin {plugin_name} initialization returned False")
                return False

        except Exception as e:
            logger.error(f"Failed to initialize plugin {plugin_name}: {e}")
            self.failed_plugins[plugin_name] = str(e)
            return False

    def register_all_handlers(self) -> None:
        """Register handlers for all initialized plugins."""
        if not self.application:
            logger.error("No application registered for handler registration")
            return

        registered_count = 0

        for plugin_name, plugin in self.plugins.items():
            if not plugin.is_initialized:
                logger.warning(
                    f"Skipping handler registration for uninitialized plugin: {plugin_name}"
                )
                continue

            try:
                plugin.register_handlers(self.application)
                registered_count += 1
                logger.info(f"📝 Registered handlers for plugin: {plugin_name}")

            except Exception as e:
                logger.error(
                    f"Failed to register handlers for plugin {plugin_name}: {e}"
                )
                self.failed_plugins[plugin_name] = str(e)

        logger.info(f"📋 Registered handlers for {registered_count} plugins")

    async def enable_all_plugins(self) -> None:
        """Enable all initialized plugins."""
        enabled_count = 0

        for plugin_name, plugin in self.plugins.items():
            if not plugin.is_initialized:
                continue

            try:
                success = await plugin.enable()
                if success:
                    enabled_count += 1

            except Exception as e:
                logger.error(f"Failed to enable plugin {plugin_name}: {e}")
                self.failed_plugins[plugin_name] = str(e)

        logger.info(f"🟢 Enabled {enabled_count} plugins")

    async def shutdown_all_plugins(self) -> None:
        """Shutdown all plugins gracefully."""
        logger.info("🔄 Shutting down all plugins...")

        for plugin_name, plugin in self.plugins.items():
            try:
                await plugin.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down plugin {plugin_name}: {e}")

        logger.info("✅ All plugins shut down")

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """Get a plugin by name."""
        return self.plugins.get(name)

    def get_all_commands(self) -> Dict[str, str]:
        """Get all commands from all enabled plugins."""
        all_commands = {}

        for plugin in self.plugins.values():
            if plugin.is_enabled:
                try:
                    commands = plugin.get_commands()
                    all_commands.update(commands)
                except Exception as e:
                    logger.error(
                        f"Error getting commands from plugin {plugin.name}: {e}"
                    )

        return all_commands

    def get_plugin_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status information for all plugins."""
        status = {}

        for plugin_name, plugin in self.plugins.items():
            status[plugin_name] = {
                "version": plugin.version,
                "initialized": plugin.is_initialized,
                "enabled": plugin.is_enabled,
                "description": plugin.metadata.description,
                "dependencies": plugin.metadata.dependencies,
            }

        # Add failed plugins
        for plugin_name, error in self.failed_plugins.items():
            if plugin_name not in status:
                status[plugin_name] = {
                    "version": "unknown",
                    "initialized": False,
                    "enabled": False,
                    "description": "Failed to load",
                    "error": error,
                }

        return status

    def set_plugin_config(self, plugin_name: str, config: Dict[str, Any]) -> None:
        """Set configuration for a specific plugin."""
        self.plugin_configs[plugin_name] = config

        # If plugin is already loaded, update its config
        plugin = self.plugins.get(plugin_name)
        if plugin:
            plugin.set_config(config)
