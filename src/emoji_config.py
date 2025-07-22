"""
Emoji Configuration for Telegram Bot

This module centralizes emoji usage to allow easy theming and customization.
You can switch between different emoji sets by changing the EMOJI_THEME
variable.
"""

# Available emoji themes
EMOJI_THEMES = {
    "default": {
        # Status & Actions
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️",
        "loading": "⏳",
        "refresh": "🔄",
        # User Interface
        "back": "⬅️",
        "close": "❌",
        "menu": "📋",
        "settings": "⚙️",
        "search": "🔍",
        "help": "❓",
        # Commerce & Billing
        "shop": "🛒",
        "credit_card": "💳",
        "money": "💰",
        "diamond": "💎",
        "gift": "🎁",
        "billing": "🏦",
        "lightning": "⚡",
        # Admin & Management
        "admin": "🔧",
        "dashboard": "📊",
        "analytics": "📈",
        "users": "👥",
        "ban": "🚫",
        "conversation": "💬",
        "broadcast": "📢",
        # Time & Progress
        "clock": "⏰",
        "progress": "📊",
        "calendar": "📅",
        "hourglass": "⏳",
        # Account & Status
        "user": "👤",
        "tier": "⭐",
        "balance": "💰",
        "credits": "💎",
        "time_access": "⏰",
        "status_good": "🟢",
        "status_warning": "🟡",
        "status_bad": "🔴",
        # Communication
        "welcome": "👋",
        "robot": "🤖",
        "message": "💬",
        "support": "📞",
    },
    "professional": {
        # More professional/business-oriented emojis
        "success": "✓",
        "error": "✗",
        "warning": "!",
        "info": "i",
        "loading": "⏳",
        "refresh": "↻",
        "back": "←",
        "close": "✗",
        "menu": "≡",
        "settings": "⚙",
        "search": "🔍",
        "help": "?",
        "shop": "🏪",
        "credit_card": "💳",
        "money": "💵",
        "diamond": "◆",
        "gift": "🎁",
        "billing": "🏛",
        "lightning": "⚡",
        "admin": "⚙",
        "dashboard": "📈",
        "analytics": "📊",
        "users": "👥",
        "ban": "⊗",
        "conversation": "💬",
        "broadcast": "📢",
        "clock": "🕐",
        "progress": "▓",
        "calendar": "📅",
        "hourglass": "⏳",
        "user": "👤",
        "tier": "★",
        "balance": "💵",
        "credits": "◆",
        "time_access": "🕐",
        "status_good": "●",
        "status_warning": "●",
        "status_bad": "●",
        "welcome": "👋",
        "robot": "🤖",
        "message": "✉",
        "support": "📞",
    },
    "fun": {
        # More playful/colorful emojis
        "success": "🎉",
        "error": "💥",
        "warning": "🚨",
        "info": "💡",
        "loading": "🌀",
        "refresh": "🔄",
        "back": "🔙",
        "close": "🚪",
        "menu": "📜",
        "settings": "🔧",
        "search": "🔎",
        "help": "🆘",
        "shop": "🛍️",
        "credit_card": "💳",
        "money": "💰",
        "diamond": "💎",
        "gift": "🎁",
        "billing": "🏦",
        "lightning": "⚡",
        "admin": "👑",
        "dashboard": "📊",
        "analytics": "📈",
        "users": "👨‍👩‍👧‍👦",
        "ban": "🔨",
        "conversation": "💬",
        "broadcast": "📣",
        "clock": "🕒",
        "progress": "📊",
        "calendar": "📅",
        "hourglass": "⏳",
        "user": "🧑",
        "tier": "🌟",
        "balance": "💰",
        "credits": "🪙",
        "time_access": "⏰",
        "status_good": "🟢",
        "status_warning": "🟡",
        "status_bad": "🔴",
        "welcome": "👋",
        "robot": "🤖",
        "message": "💬",
        "support": "🆘",
    },
}

# Set your desired theme here
EMOJI_THEME = "default"  # Change to "professional" or "fun" to switch themes


# Get the current emoji set
def get_emoji(key: str) -> str:
    """
    Get emoji for a specific key from the current theme.

    Args:
        key: The emoji key (e.g., 'success', 'shop', 'admin')

    Returns:
        The emoji string for the current theme
    """
    return EMOJI_THEMES[EMOJI_THEME].get(key, EMOJI_THEMES["default"].get(key, "❓"))


# Convenience function to get multiple emojis
def get_emojis(*keys: str) -> tuple:
    """Get multiple emojis at once."""
    return tuple(get_emoji(key) for key in keys)


# Theme switcher function
def set_emoji_theme(theme_name: str) -> bool:
    """
    Switch to a different emoji theme.

    Args:
        theme_name: Name of the theme ('default', 'professional', 'fun')

    Returns:
        True if theme was changed, False if theme doesn't exist
    """
    global EMOJI_THEME
    if theme_name in EMOJI_THEMES:
        EMOJI_THEME = theme_name
        return True
    return False


# Get list of available themes
def get_available_themes() -> list:
    """Get list of available emoji themes."""
    return list(EMOJI_THEMES.keys())
