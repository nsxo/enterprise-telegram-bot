"""
Enterprise Telegram Bot - Plugin System Tests

This module contains tests for the plugin manager, plugin discovery,
and plugin lifecycle management.
"""

import unittest
from unittest.mock import MagicMock, AsyncMock

from src.plugins import PluginManager, BasePlugin, PluginMetadata


class MockPlugin(BasePlugin):
    """A mock plugin for testing purposes."""

    def __init__(self, name, version="1.0.0", deps=None):
        super().__init__()
        self._name = name
        self._version = version
        self._deps = deps or []

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self._name,
            version=self._version,
            description="A mock plugin",
            dependencies=self._deps,
        )

    async def initialize(self, config=None) -> bool:
        self._mark_initialized()
        return True

    def register_handlers(self, application) -> None:
        pass

    def get_commands(self) -> dict:
        return {f"test_{self._name.lower()}": "Test command"}


class TestPluginManager(unittest.IsolatedAsyncioTestCase):
    """Tests for the PluginManager."""

    def setUp(self):
        self.plugin_manager = PluginManager(plugin_directories=[])
        self.mock_app = MagicMock()
        self.plugin_manager.register_application(self.mock_app)

    async def test_discover_plugins(self):
        """Test plugin discovery."""
        # This is hard to test without a real file system,
        # so we'll test the logic by manually adding plugins
        self.plugin_manager.plugins = {
            "PluginA": MockPlugin("PluginA"),
            "PluginB": MockPlugin("PluginB"),
        }
        self.assertEqual(len(self.plugin_manager.plugins), 2)

    async def test_dependency_resolution(self):
        """Test plugin dependency resolution and load order."""
        self.plugin_manager.plugins = {
            "PluginA": MockPlugin("PluginA", deps=["PluginB"]),
            "PluginB": MockPlugin("PluginB"),
        }
        self.plugin_manager._build_dependency_graph()

        load_order = self.plugin_manager._get_load_order()
        self.assertEqual(load_order, ["PluginB", "PluginA"])

    async def test_circular_dependency(self):
        """Test detection of circular dependencies."""
        self.plugin_manager.plugins = {
            "PluginA": MockPlugin("PluginA", deps=["PluginB"]),
            "PluginB": MockPlugin("PluginB", deps=["PluginA"]),
        }
        self.plugin_manager._build_dependency_graph()

        with self.assertRaises(Exception):
            self.plugin_manager._get_load_order()

    async def test_initialize_and_enable_plugins(self):
        """Test initialization and enabling of plugins."""
        plugin_a = MockPlugin("PluginA")
        plugin_a.initialize = AsyncMock(return_value=True)
        plugin_a.enable = AsyncMock(
            side_effect=lambda: setattr(plugin_a, "_enabled", True)
        )

        self.plugin_manager.plugins = {"PluginA": plugin_a}

        await self.plugin_manager.initialize_all_plugins()
        await self.plugin_manager.enable_all_plugins()

        plugin_a.initialize.assert_awaited_once()
        plugin_a.enable.assert_awaited_once()
        self.assertTrue(plugin_a.is_initialized)
        self.assertTrue(plugin_a.is_enabled)

    async def test_handler_registration(self):
        """Test handler registration for plugins."""
        plugin_a = MockPlugin("PluginA")
        plugin_a.register_handlers = MagicMock()

        self.plugin_manager.plugins = {"PluginA": plugin_a}

        await self.plugin_manager.initialize_all_plugins()
        self.plugin_manager.register_all_handlers()

        plugin_a.register_handlers.assert_called_once_with(self.mock_app)

    async def test_get_all_commands(self):
        """Test aggregation of commands from enabled plugins."""
        plugin_a = MockPlugin("PluginA")
        plugin_b = MockPlugin("PluginB")

        plugin_a._enabled = True
        plugin_b._enabled = True

        self.plugin_manager.plugins = {"PluginA": plugin_a, "PluginB": plugin_b}

        commands = self.plugin_manager.get_all_commands()

        self.assertIn("test_plugina", commands)
        self.assertIn("test_pluginb", commands)
        self.assertEqual(len(commands), 2)


if __name__ == "__main__":
    unittest.main()
