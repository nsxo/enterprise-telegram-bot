
# Function Specifications

This document provides detailed specifications for key functions in the project.

---

### File: `src/database.py`

#### Function: `get_or_create_user`
- **Description:** Retrieves a user by their Telegram ID. If the user does not exist, it creates a new entry and returns the new user data. This is an "upsert" operation.
- **Parameters:**
    - `telegram_id` (int): The user's unique Telegram ID.
    - `username` (str): The user's current username. Can be `None`.
    - `first_name` (str): The user's first name.
- **Returns:** A dictionary representing the user row from the `users` table.
- **Behavior:**
    1.  Use an `INSERT ... ON CONFLICT (telegram_id) DO UPDATE` statement to perform the upsert in a single, atomic database query.
    2.  Update the `username` and `first_name` fields if the user already exists.
    3.  The `RETURNING *` clause should be used to get the complete user row back.
- **Error Handling:** Should be handled by the master `execute_query` function.

#### Function: `get_user_id_from_topic`
- **Description:** Finds the `user_id` associated with a given `topic_id` in the admin group.
- **Parameters:**
    - `topic_id` (int): The ID of the message thread (topic).
- **Returns:** An integer `user_id` if found, otherwise `None`.
- **Behavior:**
    1.  Execute a `SELECT user_id FROM conversations WHERE topic_id = %s`.
    2.  Return the result.

---

### File: `src/bot.py`

#### Function: `create_progress_bar`
- **Description:** A helper function that generates a text-based progress bar.
- **Parameters:**
    - `current_value` (int): The user's current credit count.
    - `max_value` (int): The maximum credits a user typically buys (e.g., 100). If `current_value` exceeds `max_value`, the bar should show as 100% full.
    - `length` (int): The number of characters for the bar itself (default to 10).
- **Returns:** A formatted string, e.g., `[█████░░░░░] 50%`.
- **Behavior:**
    1.  Calculate the percentage, capping it at 100%.
    2.  Calculate how many "filled" characters (`█`) and "empty" characters (`░`) to display.
    3.  Combine the bar and the percentage text into a single string.

#### Function: `get_or_create_user_topic`
- **Description:** The core of the conversation bridge. It finds an existing topic for a user in the admin group or creates a new one if none exists.
- **Parameters:**
    - `context` (`ContextTypes.DEFAULT_TYPE`): The `python-telegram-bot` context object.
    - `user` (`telegram.User`): The user object from the update.
- **Returns:** The integer `topic_id` for the user's conversation thread.
- **Behavior:**
    1.  Query the `conversations` table for the `user.id`.
    2.  If a `topic_id` exists, return it immediately.
    3.  If not, call `context.bot.create_forum_topic` in the `ADMIN_GROUP_ID` group. The topic name should be `f"👤 {user.first_name} (@{user.username}) - {user.id}"`.
    4.  Save the new `topic_id` and `user.id` to the `conversations` table.
    5.  Call `send_user_info_card` to pin the context message in the new topic.
    6.  Return the new `topic_id`.
