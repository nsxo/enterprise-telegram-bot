"""
Enterprise Telegram Bot - Retry Service

This module implements retry logic with exponential backoff and jitter
for handling transient failures in external API calls and database operations.
"""

import asyncio
import logging
import random
import time
from typing import Any, Callable, Dict, List, Optional, Type, Union
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategy types."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    jitter: bool = True
    exponential_base: float = 2.0
    retryable_exceptions: tuple = (Exception,)


class RetryError(Exception):
    """Raised when all retry attempts are exhausted."""
    
    def __init__(self, message: str, last_exception: Exception, attempts: int):
        super().__init__(message)
        self.last_exception = last_exception
        self.attempts = attempts


class RetryService:
    """
    Service for executing functions with retry logic and exponential backoff.
    
    Supports multiple retry strategies:
    - Exponential backoff with jitter
    - Linear backoff
    - Fixed delay
    """

    def __init__(self, config: RetryConfig = None):
        """
        Initialize retry service.

        Args:
            config: Retry configuration
        """
        self.config = config or RetryConfig()

    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for the given attempt number.

        Args:
            attempt: Current attempt number (1-based)

        Returns:
            Delay in seconds
        """
        if self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.config.base_delay * (
                self.config.exponential_base ** (attempt - 1)
            )
        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.base_delay * attempt
        else:  # FIXED_DELAY
            delay = self.config.base_delay

        # Apply maximum delay limit
        delay = min(delay, self.config.max_delay)

        # Add jitter if enabled (±25% random variation)
        if self.config.jitter:
            jitter_amount = delay * 0.25
            delay += random.uniform(-jitter_amount, jitter_amount)
            delay = max(0, delay)  # Ensure non-negative delay

        return delay

    def _is_retryable_exception(self, exception: Exception) -> bool:
        """
        Check if exception is retryable based on configuration.

        Args:
            exception: Exception to check

        Returns:
            True if exception should trigger retry
        """
        return isinstance(exception, self.config.retryable_exceptions)

    async def execute_async(
        self, 
        func: Callable, 
        *args, 
        **kwargs
    ) -> Any:
        """
        Execute async function with retry logic.

        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            RetryError: When all attempts are exhausted
        """
        last_exception = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                logger.debug(f"Retry attempt {attempt}/{self.config.max_attempts}")
                result = await func(*args, **kwargs)
                
                if attempt > 1:
                    logger.info(f"Function succeeded on attempt {attempt}")
                
                return result

            except Exception as e:
                last_exception = e
                
                if not self._is_retryable_exception(e):
                    logger.debug(f"Non-retryable exception: {type(e).__name__}")
                    raise
                
                if attempt == self.config.max_attempts:
                    logger.error(
                        f"All {self.config.max_attempts} retry attempts failed. "
                        f"Last error: {e}"
                    )
                    break
                
                delay = self._calculate_delay(attempt)
                logger.warning(
                    f"Attempt {attempt} failed with {type(e).__name__}: {e}. "
                    f"Retrying in {delay:.2f}s"
                )
                
                await asyncio.sleep(delay)

        # All attempts exhausted
        raise RetryError(
            f"Function failed after {self.config.max_attempts} attempts",
            last_exception,
            self.config.max_attempts
        )

    def execute_sync(
        self, 
        func: Callable, 
        *args, 
        **kwargs
    ) -> Any:
        """
        Execute synchronous function with retry logic.

        Args:
            func: Synchronous function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            RetryError: When all attempts are exhausted
        """
        last_exception = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                logger.debug(f"Retry attempt {attempt}/{self.config.max_attempts}")
                result = func(*args, **kwargs)
                
                if attempt > 1:
                    logger.info(f"Function succeeded on attempt {attempt}")
                
                return result

            except Exception as e:
                last_exception = e
                
                if not self._is_retryable_exception(e):
                    logger.debug(f"Non-retryable exception: {type(e).__name__}")
                    raise
                
                if attempt == self.config.max_attempts:
                    logger.error(
                        f"All {self.config.max_attempts} retry attempts failed. "
                        f"Last error: {e}"
                    )
                    break
                
                delay = self._calculate_delay(attempt)
                logger.warning(
                    f"Attempt {attempt} failed with {type(e).__name__}: {e}. "
                    f"Retrying in {delay:.2f}s"
                )
                
                time.sleep(delay)

        # All attempts exhausted
        raise RetryError(
            f"Function failed after {self.config.max_attempts} attempts",
            last_exception,
            self.config.max_attempts
        )


# Pre-configured retry services for common scenarios
def get_database_retry_service() -> RetryService:
    """Get retry service configured for database operations."""
    config = RetryConfig(
        max_attempts=3,
        base_delay=0.5,
        max_delay=5.0,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        jitter=True,
        retryable_exceptions=(
            # Database connection errors, timeouts, etc.
            ConnectionError,
            TimeoutError,
            OSError,
        )
    )
    return RetryService(config)


def get_api_retry_service() -> RetryService:
    """Get retry service configured for API calls."""
    config = RetryConfig(
        max_attempts=4,
        base_delay=1.0,
        max_delay=30.0,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        jitter=True,
        retryable_exceptions=(
            # Network errors, timeouts, rate limits
            ConnectionError,
            TimeoutError,
            OSError,
        )
    )
    return RetryService(config)


def get_telegram_retry_service() -> RetryService:
    """Get retry service configured for Telegram API calls."""
    config = RetryConfig(
        max_attempts=3,
        base_delay=2.0,
        max_delay=20.0,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        jitter=True,
        retryable_exceptions=(
            # Telegram API specific errors
            ConnectionError,
            TimeoutError,
            OSError,
        )
    )
    return RetryService(config)


def get_stripe_retry_service() -> RetryService:
    """Get retry service configured for Stripe API calls."""
    config = RetryConfig(
        max_attempts=4,
        base_delay=1.0,
        max_delay=30.0,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        jitter=True,
        retryable_exceptions=(
            # Stripe specific retryable errors
            ConnectionError,
            TimeoutError,
            OSError,
        )
    )
    return RetryService(config)


# Decorator functions for easy usage
def retry_async(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    retryable_exceptions: tuple = (Exception,)
):
    """
    Decorator for adding retry logic to async functions.

    Args:
        max_attempts: Maximum number of attempts
        base_delay: Base delay in seconds
        strategy: Retry strategy to use
        retryable_exceptions: Tuple of retryable exception types

    Returns:
        Decorated function
    """
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_attempts=max_attempts,
                base_delay=base_delay,
                strategy=strategy,
                retryable_exceptions=retryable_exceptions
            )
            retry_service = RetryService(config)
            return await retry_service.execute_async(func, *args, **kwargs)
        return wrapper
    return decorator


def retry_sync(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    retryable_exceptions: tuple = (Exception,)
):
    """
    Decorator for adding retry logic to synchronous functions.

    Args:
        max_attempts: Maximum number of attempts
        base_delay: Base delay in seconds
        strategy: Retry strategy to use
        retryable_exceptions: Tuple of retryable exception types

    Returns:
        Decorated function
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_attempts=max_attempts,
                base_delay=base_delay,
                strategy=strategy,
                retryable_exceptions=retryable_exceptions
            )
            retry_service = RetryService(config)
            return retry_service.execute_sync(func, *args, **kwargs)
        return wrapper
    return decorator


# Convenience functions for common patterns
async def retry_with_exponential_backoff(
    func: Callable,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    *args,
    **kwargs
) -> Any:
    """
    Convenience function for executing a function with exponential backoff.

    Args:
        func: Function to execute
        max_attempts: Maximum number of attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Function result

    Raises:
        RetryError: When all attempts are exhausted
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        jitter=True
    )
    retry_service = RetryService(config)
    
    if asyncio.iscoroutinefunction(func):
        return await retry_service.execute_async(func, *args, **kwargs)
    else:
        return retry_service.execute_sync(func, *args, **kwargs) 