"""
Enterprise Telegram Bot - Caching Module

This module provides caching functionality for frequently accessed data
to improve performance and reduce database load.
"""

import logging
import time
from typing import Any, Optional, Dict
from threading import RLock

logger = logging.getLogger(__name__)


class SimpleCache:
    """
    Thread-safe in-memory cache with TTL (Time To Live) support.
    
    This is a simple implementation for basic caching needs.
    For production scale, consider using Redis.
    """
    
    def __init__(self, default_ttl: int = 300):
        """
        Initialize cache.
        
        Args:
            default_ttl: Default time to live in seconds (5 minutes)
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = RLock()
        self.default_ttl = default_ttl
        logger.info("Simple cache initialized")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found or expired
        """
        with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            
            # Check if expired
            if time.time() > entry['expires_at']:
                del self._cache[key]
                logger.debug(f"Cache key '{key}' expired and removed")
                return None
            
            logger.debug(f"Cache hit for key '{key}'")
            return entry['value']
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if None)
        """
        ttl = ttl or self.default_ttl
        expires_at = time.time() + ttl
        
        with self._lock:
            self._cache[key] = {
                'value': value,
                'expires_at': expires_at,
                'created_at': time.time()
            }
            logger.debug(f"Cache set for key '{key}' with TTL {ttl}s")
    
    def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if key was deleted, False if not found
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache key '{key}' deleted")
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            cache_size = len(self._cache)
            self._cache.clear()
            logger.info(f"Cache cleared ({cache_size} entries removed)")
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.
        
        Returns:
            Number of entries removed
        """
        current_time = time.time()
        expired_keys = []
        
        with self._lock:
            for key, entry in self._cache.items():
                if current_time > entry['expires_at']:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
        
        if expired_keys:
            logger.info(f"Removed {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    
    def stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        with self._lock:
            current_time = time.time()
            active_count = 0
            expired_count = 0
            
            for entry in self._cache.values():
                if current_time > entry['expires_at']:
                    expired_count += 1
                else:
                    active_count += 1
            
            return {
                'total_entries': len(self._cache),
                'active_entries': active_count,
                'expired_entries': expired_count,
                'default_ttl': self.default_ttl
            }


# Global cache instance
cache = SimpleCache()


# Convenience functions for bot settings
def get_bot_setting_cached(key: str) -> Optional[str]:
    """
    Get bot setting from cache or database.
    
    Args:
        key: Setting key
        
    Returns:
        Setting value or None
    """
    cache_key = f"bot_setting:{key}"
    
    # Try cache first
    value = cache.get(cache_key)
    if value is not None:
        return value
    
    # Fallback to database
    try:
        from src.database import get_bot_setting
        value = get_bot_setting(key)
        
        if value is not None:
            # Cache for 5 minutes
            cache.set(cache_key, value, ttl=300)
        
        return value
    except Exception as e:
        logger.error(f"Failed to get bot setting '{key}': {e}")
        return None


def invalidate_bot_setting(key: str) -> None:
    """
    Invalidate cached bot setting.
    
    Args:
        key: Setting key to invalidate
    """
    cache_key = f"bot_setting:{key}"
    cache.delete(cache_key)
    logger.debug(f"Invalidated bot setting cache for '{key}'")


def get_user_cached(user_id: int, ttl: int = 60) -> Optional[Dict[str, Any]]:
    """
    Get user data from cache or database.
    
    Args:
        user_id: User's Telegram ID
        ttl: Cache TTL in seconds (default 1 minute)
        
    Returns:
        User data or None
    """
    cache_key = f"user:{user_id}"
    
    # Try cache first
    value = cache.get(cache_key)
    if value is not None:
        return value
    
    # Fallback to database
    try:
        from src.database import get_user
        user_data = get_user(user_id)
        
        if user_data:
            # Cache user data
            cache.set(cache_key, user_data, ttl=ttl)
        
        return user_data
    except Exception as e:
        logger.error(f"Failed to get user data for {user_id}: {e}")
        return None


def invalidate_user_cache(user_id: int) -> None:
    """
    Invalidate cached user data.
    
    Args:
        user_id: User's Telegram ID
    """
    cache_key = f"user:{user_id}"
    cache.delete(cache_key)
    logger.debug(f"Invalidated user cache for {user_id}")


# Periodic cleanup (could be called from a scheduled task)
def periodic_cache_cleanup() -> None:
    """Perform periodic cache maintenance."""
    try:
        expired_count = cache.cleanup_expired()
        stats = cache.stats()
        
        logger.info(
            f"Cache cleanup completed: {expired_count} expired entries removed, "
            f"{stats['active_entries']} active entries remaining"
        )
    except Exception as e:
        logger.error(f"Cache cleanup failed: {e}")


logger.info("Cache module initialized") 