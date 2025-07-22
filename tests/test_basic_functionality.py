"""
Basic functionality tests for Enterprise Telegram Bot.

These tests verify that core components can be imported and initialized
without errors, and that the new plugin system is functioning correctly.
"""

import unittest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.plugins import PluginManager


class TestBasicFunctionality(unittest.IsolatedAsyncioTestCase):
    """Test basic functionality and imports."""

    def test_config_import(self):
        """Test that config module can be imported."""
        try:
            from src import config

            self.assertTrue(hasattr(config, "BOT_TOKEN"))
            self.assertTrue(hasattr(config, "DATABASE_URL"))
        except ImportError as e:
            self.fail(f"Config import failed: {e}")

    def test_database_import(self):
        """Test that database module can be imported."""
        try:
            from src import database

            self.assertTrue(hasattr(database, "init_connection_pool"))
        except ImportError as e:
            self.fail(f"Database import failed: {e}")

    async def test_plugin_discovery_and_initialization(self):
        """Test that plugins are discovered and can be initialized."""
        try:
            plugin_manager = PluginManager()
            await plugin_manager.discover_plugins()
            self.assertGreater(
                len(plugin_manager.plugins), 0, "No plugins were discovered."
            )

            # Test initialization of a single plugin
            # This assumes at least one plugin exists.
            # A more robust test would mock the plugins.
            a_plugin_name = list(plugin_manager.plugins.keys())[0]
            initialization_result = await plugin_manager._initialize_plugin(
                a_plugin_name
            )
            self.assertTrue(
                initialization_result, f"Plugin {a_plugin_name} failed to initialize."
            )

        except Exception as e:
            self.fail(f"Plugin discovery and initialization failed: {e}")

    def test_bot_factory_import(self):
        """Test that bot factory can be imported."""
        try:
            from src import bot_factory

            self.assertTrue(hasattr(bot_factory, "create_application"))
        except ImportError as e:
            self.fail(f"Bot factory import failed: {e}")


class TestScripts(unittest.TestCase):
    """Test that scripts can be imported and have main functions."""

    def test_validate_script(self):
        """Test validate script can be imported."""
        try:
            # Add scripts to path
            scripts_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"
            )
            sys.path.insert(0, scripts_path)

            import validate

            self.assertTrue(hasattr(validate, "main") or callable(validate))
        except ImportError as e:
            self.fail(f"Validate script import failed: {e}")

    def test_setup_db_script(self):
        """Test setup_db script can be imported."""
        try:
            scripts_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"
            )
            sys.path.insert(0, scripts_path)

            import setup_db

            # Check it has some setup functions
            self.assertTrue(hasattr(setup_db, "main") or len(dir(setup_db)) > 10)
        except ImportError as e:
            self.fail(f"Setup DB script import failed: {e}")


if __name__ == "__main__":
    unittest.main()
