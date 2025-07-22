#!/usr/bin/env python3
"""
Enterprise Telegram Bot - Stripe Webhook Setup Script

This script provides multiple methods to create and manage Stripe webhooks:
1. Using Stripe CLI for development/testing
2. Using Stripe API for production deployment
3. Validating existing webhook configurations

Usage:
    python scripts/setup_stripe_webhooks.py --help
"""

import os
import sys
import argparse
import subprocess
from typing import List, Dict, Any, Optional

# Add src to path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import stripe
    from src.config import STRIPE_API_KEY, WEBHOOK_URL
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you have installed requirements.txt and set up your .env")
    sys.exit(1)

# Configure Stripe
stripe.api_key = STRIPE_API_KEY


class StripeWebhookManager:
    """Manages Stripe webhook endpoints via CLI and API."""

    # Events that your application handles
    WEBHOOK_EVENTS = [
        "checkout.session.completed",
        "payment_intent.payment_failed",
        "payment_intent.succeeded",
        "charge.dispute.created",
        "customer.subscription.deleted",
        "invoice.payment_failed",
        "payment_method.attached",
    ]

    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize webhook manager.

        Args:
            webhook_url: Your webhook endpoint URL
        """
        self.webhook_url = webhook_url or WEBHOOK_URL
        if not self.webhook_url:
            raise ValueError(
                "WEBHOOK_URL must be set in environment or provided as argument"
            )

        # Ensure webhook URL ends with /stripe-webhook
        if not self.webhook_url.endswith("/stripe-webhook"):
            if self.webhook_url.endswith("/"):
                self.webhook_url += "stripe-webhook"
            else:
                self.webhook_url += "/stripe-webhook"

    def check_stripe_cli(self) -> bool:
        """Check if Stripe CLI is installed and authenticated."""
        try:
            result = subprocess.run(
                ["stripe", "--version"], capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"✅ Stripe CLI installed: {result.stdout.strip()}")

                # Check authentication
                auth_result = subprocess.run(
                    ["stripe", "config", "--list"], capture_output=True, text=True
                )
                if (
                    "test_mode_api_key" in auth_result.stdout
                    or "live_mode_api_key" in auth_result.stdout
                ):
                    print("✅ Stripe CLI is authenticated")
                    return True
                else:
                    print("❌ Stripe CLI not authenticated. Run: stripe login")
                    return False
            else:
                return False
        except FileNotFoundError:
            print("❌ Stripe CLI not found")
            return False

    def install_stripe_cli_instructions(self):
        """Print instructions for installing Stripe CLI."""
        print("\n📦 To install Stripe CLI:")
        print("macOS: brew install stripe/stripe-cli/stripe")
        print("Windows: Download from https://github.com/stripe/stripe-cli/releases")
        print("Linux: https://stripe.com/docs/stripe-cli#install")
        print("\nAfter installation, authenticate with: stripe login")

    def create_webhook_via_cli(self, local_port: int = 8000) -> None:
        """
        Create webhook for local development using Stripe CLI.

        Args:
            local_port: Local port where your Flask app is running
        """
        if not self.check_stripe_cli():
            self.install_stripe_cli_instructions()
            return

        print(f"\n🔧 Creating webhook for local development on port {local_port}")

        # Format events for CLI
        events_str = ",".join(self.WEBHOOK_EVENTS)

        # Start listening (this will run in foreground)
        cmd = [
            "stripe",
            "listen",
            "--forward-to",
            f"localhost:{local_port}/stripe-webhook",
            "--events",
            events_str,
        ]

        print(f"Running: {' '.join(cmd)}")
        print(
            "📝 This will display the webhook signing secret - copy it to your .env file as STRIPE_WEBHOOK_SECRET"
        )
        print("🚀 Keep this running while developing. Press Ctrl+C to stop.\n")

        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            print("\n✅ Webhook listener stopped")

    def create_webhook_via_api(self, description: str = None) -> Dict[str, Any]:
        """
        Create webhook endpoint via Stripe API for production.

        Args:
            description: Optional description for the webhook

        Returns:
            Created webhook endpoint data
        """
        if not description:
            description = f"Enterprise Telegram Bot - {self.webhook_url}"

        print(f"\n🌐 Creating webhook endpoint via API: {self.webhook_url}")

        try:
            webhook_endpoint = stripe.WebhookEndpoint.create(
                url=self.webhook_url,
                enabled_events=self.WEBHOOK_EVENTS,
                description=description,
                api_version="2023-10-16",  # Use latest stable API version
            )

            print("✅ Webhook created successfully!")
            print(f"📋 Webhook ID: {webhook_endpoint.id}")
            print(f"🔑 Webhook Secret: {webhook_endpoint.secret}")
            print(f"🌐 URL: {webhook_endpoint.url}")
            print(f"📝 Events: {', '.join(webhook_endpoint.enabled_events)}")

            print("\n⚠️  IMPORTANT: Add this to your .env file:")
            print(f"STRIPE_WEBHOOK_SECRET={webhook_endpoint.secret}")

            return webhook_endpoint

        except stripe.error.StripeError as e:
            print(f"❌ Failed to create webhook: {e}")
            raise

    def list_webhooks(self) -> List[Dict[str, Any]]:
        """List all existing webhook endpoints."""
        print("\n📋 Listing existing webhook endpoints:")

        try:
            webhooks = stripe.WebhookEndpoint.list(limit=100)

            if not webhooks.data:
                print("No webhook endpoints found")
                return []

            for i, webhook in enumerate(webhooks.data, 1):
                status = "🟢 Active" if webhook.status == "enabled" else "🔴 Disabled"
                print(f"\n{i}. {webhook.id}")
                print(f"   URL: {webhook.url}")
                print(f"   Status: {status}")
                print(f"   Description: {webhook.description or 'No description'}")
                print(f"   Events: {len(webhook.enabled_events)} events")
                print(f"   Created: {webhook.created}")

            return webhooks.data

        except stripe.error.StripeError as e:
            print(f"❌ Failed to list webhooks: {e}")
            return []

    def test_webhook(self, webhook_id: str = None) -> None:
        """
        Send a test webhook event.

        Args:
            webhook_id: Specific webhook to test (optional)
        """
        print("\n🧪 Testing webhook...")

        if not self.check_stripe_cli():
            print("❌ Stripe CLI required for testing webhooks")
            return

        try:
            # Send a test checkout.session.completed event
            cmd = ["stripe", "events", "resend", "evt_test_webhook"]
            if webhook_id:
                cmd.extend(["--webhook-endpoint", webhook_id])

            subprocess.run(cmd, check=True)
            print("✅ Test event sent!")

        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to send test event: {e}")

            # Alternative: create a test event
            print("🔄 Trying alternative test method...")
            try:
                cmd = ["stripe", "trigger", "checkout.session.completed"]
                subprocess.run(cmd, check=True)
                print("✅ Test event triggered!")
            except subprocess.CalledProcessError:
                print("❌ Could not send test event. Check Stripe CLI setup.")

    def delete_webhook(self, webhook_id: str) -> None:
        """
        Delete a webhook endpoint.

        Args:
            webhook_id: ID of webhook to delete
        """
        print(f"\n🗑️  Deleting webhook: {webhook_id}")

        try:
            stripe.WebhookEndpoint.delete(webhook_id)
            print(f"✅ Webhook {webhook_id} deleted successfully")

        except stripe.error.StripeError as e:
            print(f"❌ Failed to delete webhook: {e}")

    def validate_current_setup(self) -> bool:
        """Validate current webhook configuration."""
        print("\n🔍 Validating current webhook setup...")

        # Check environment variables
        webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        if not webhook_secret:
            print("❌ STRIPE_WEBHOOK_SECRET not set in environment")
            return False

        if not webhook_secret.startswith("whsec_"):
            print("❌ STRIPE_WEBHOOK_SECRET should start with 'whsec_'")
            return False

        print("✅ STRIPE_WEBHOOK_SECRET properly configured")

        # Check if webhook URL is accessible (basic check)
        if not self.webhook_url.startswith("https://"):
            print("⚠️  Warning: Webhook URL should use HTTPS in production")

        print(f"✅ Webhook URL configured: {self.webhook_url}")

        # List matching webhooks
        webhooks = self.list_webhooks()
        matching_webhooks = [w for w in webhooks if w.url == self.webhook_url]

        if matching_webhooks:
            print(f"✅ Found {len(matching_webhooks)} matching webhook(s)")
            for webhook in matching_webhooks:
                missing_events = set(self.WEBHOOK_EVENTS) - set(webhook.enabled_events)
                if missing_events:
                    print(f"⚠️  Missing events: {', '.join(missing_events)}")
                else:
                    print("✅ All required events configured")
        else:
            print("⚠️  No webhooks found matching your webhook URL")

        return True


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Stripe Webhook Management for Enterprise Telegram Bot"
    )

    parser.add_argument(
        "action",
        choices=["create-dev", "create-prod", "list", "test", "delete", "validate"],
        help="Action to perform",
    )

    parser.add_argument(
        "--webhook-url", help="Webhook URL (defaults to WEBHOOK_URL from config)"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Local port for development webhook (default: 8000)",
    )

    parser.add_argument("--webhook-id", help="Webhook ID for delete/test operations")

    parser.add_argument("--description", help="Description for production webhook")

    args = parser.parse_args()

    try:
        manager = StripeWebhookManager(webhook_url=args.webhook_url)

        if args.action == "create-dev":
            manager.create_webhook_via_cli(local_port=args.port)

        elif args.action == "create-prod":
            manager.create_webhook_via_api(description=args.description)

        elif args.action == "list":
            manager.list_webhooks()

        elif args.action == "test":
            manager.test_webhook(webhook_id=args.webhook_id)

        elif args.action == "delete":
            if not args.webhook_id:
                print("❌ --webhook-id required for delete action")
                sys.exit(1)
            manager.delete_webhook(args.webhook_id)

        elif args.action == "validate":
            manager.validate_current_setup()

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
