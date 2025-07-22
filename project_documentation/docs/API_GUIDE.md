
# API Guide

This document specifies the behavior of the application's API endpoints.

---

### Endpoint: `POST /telegram-webhook`

- **Description:** The primary endpoint that receives all updates from the Telegram API.
- **Request Body:** A JSON object representing a Telegram `Update`. The structure is defined by the Telegram Bot API.
- **Security:** Access is secured by a secret token in the webhook URL, which should be a long, randomly generated string.
- **Behavior:**
    1.  The endpoint receives the raw request body.
    2.  The JSON body is deserialized into a `telegram.Update` object.
    3.  The update object is passed to the `python-telegram-bot` `Application` instance for processing by the appropriate handlers.
    4.  The endpoint must respond quickly to Telegram to avoid timeouts.
- **Responses:**
    - **`200 OK`**: Always returned immediately after successfully queuing the update for processing.

---

### Endpoint: `POST /stripe-webhook`

- **Description:** Handles all incoming webhook events from the Stripe API to manage payments, subscriptions, and other financial events.
- **Request Body:** A JSON object representing a Stripe `Event`.
- **Security:**
    - **CRITICAL:** The endpoint MUST verify the `Stripe-Signature` header from the incoming request.
    - The signature is checked against the payload and the `STRIPE_WEBHOOK_SECRET`.
    - Any request failing signature verification MUST be rejected immediately.
- **Behavior:**
    1.  Verify the signature.
    2.  Parse the JSON payload to get the event `type` (e.g., `checkout.session.completed`).
    3.  Based on the event `type`, trigger the appropriate business logic (e.g., call a database function to add credits to a user's account).
- **Responses:**
    - **`200 OK`**: Returned if the event was received and successfully processed (or queued for processing).
    - **`400 Bad Request`**: Returned if the payload is malformed or the signature is missing.
    - **`403 Forbidden`**: Returned if signature verification fails.
    - **`500 Internal Server Error`**: Returned if an unexpected error occurs during processing. Stripe will attempt to resend the webhook.

---

### Endpoint: `GET /health`

- **Description:** A simple health check endpoint used by the hosting provider (e.g., Railway) to verify that the application is running.
- **Request Body:** None.
- **Security:** None needed. This is a public endpoint.
- **Responses:**
    - **`200 OK`**: With a JSON body of `{"status": "healthy"}`.
