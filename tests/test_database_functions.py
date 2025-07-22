"""
Database function tests for Enterprise Telegram Bot.

These tests verify database operations work correctly.
"""

import unittest
import sys
import os
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDatabaseFunctions(unittest.TestCase):
    """Test database functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_user_id = 12345
        self.test_username = "testuser"
        self.test_first_name = "Test"
        self.test_last_name = "User"

    @patch("src.database.execute_query")
    def test_get_or_create_user(self, mock_execute):
        """Test user creation/retrieval."""
        from src import database as db

        # Mock successful user creation
        mock_execute.return_value = {
            "telegram_id": self.test_user_id,
            "username": self.test_username,
            "first_name": self.test_first_name,
            "last_name": self.test_last_name,
            "message_credits": 3,
            "is_banned": False,
        }

        result = db.get_or_create_user(
            telegram_id=self.test_user_id,
            username=self.test_username,
            first_name=self.test_first_name,
            last_name=self.test_last_name,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["telegram_id"], self.test_user_id)
        mock_execute.assert_called_once()

    @patch("src.database.execute_query")
    def test_update_user_credits(self, mock_execute):
        """Test credit update functionality."""
        from src import database as db

        # Mock successful credit update
        mock_execute.return_value = {
            "message_credits": 25,
            "telegram_id": self.test_user_id,
        }

        result = db.update_user_credits(self.test_user_id, 25)

        self.assertIsNotNone(result)
        self.assertEqual(result["message_credits"], 25)
        mock_execute.assert_called_once()

    @patch("src.database.execute_query")
    def test_get_user_dashboard_data(self, mock_execute):
        """Test dashboard data retrieval."""
        from src import database as db

        # Mock dashboard data
        mock_execute.return_value = {
            "telegram_id": self.test_user_id,
            "message_credits": 15,
            "tier_name": "standard",
            "total_spent_cents": 1000,
            "total_purchases": 2,
        }

        result = db.get_user_dashboard_data(self.test_user_id)

        self.assertIsNotNone(result)
        self.assertEqual(result["message_credits"], 15)
        self.assertEqual(result["tier_name"], "standard")
        mock_execute.assert_called_once()

    @patch("src.database.execute_query")
    def test_get_all_products(self, mock_execute):
        """Test product retrieval."""
        from src import database as db

        # Mock product data
        mock_execute.return_value = [
            {
                "id": 1,
                "name": "10 Credits",
                "credits": 10,
                "price_cents": 500,
                "stripe_price_id": "price_test123",
            }
        ]

        result = db.get_all_products()

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["credits"], 10)
        mock_execute.assert_called_once()

    def test_database_connection_context_manager(self):
        """Test that database connection context manager exists."""
        from src import database as db

        # Verify the context manager exists
        self.assertTrue(hasattr(db, "get_db_connection"))
        self.assertTrue(callable(db.get_db_connection))


class TestDatabaseUtilities(unittest.TestCase):
    """Test database utility functions."""

    def test_bot_settings_functions_exist(self):
        """Test that bot settings functions exist."""
        from src import database as db

        self.assertTrue(hasattr(db, "get_bot_setting"))
        self.assertTrue(hasattr(db, "set_bot_setting"))

    def test_conversation_functions_exist(self):
        """Test that conversation management functions exist."""
        from src import database as db

        self.assertTrue(hasattr(db, "create_conversation_topic"))
        self.assertTrue(hasattr(db, "get_user_id_from_topic"))


if __name__ == "__main__":
    unittest.main()
