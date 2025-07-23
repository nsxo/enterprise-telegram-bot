"""
Enterprise Telegram Bot - Circuit Breaker Service

This module implements the circuit breaker pattern for external API calls
to handle failures gracefully and prevent cascading failures.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, blocking calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5      # Failures before opening
    recovery_timeout: int = 60      # Seconds before trying half-open
    success_threshold: int = 3      # Successes to close from half-open
    timeout: int = 30               # Request timeout in seconds


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """
    Circuit breaker implementation for external API calls.
    
    Implements the circuit breaker pattern to:
    - Prevent cascading failures
    - Provide fast failure when service is down
    - Allow graceful recovery testing
    """

    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        """
        Initialize circuit breaker.

        Args:
            name: Unique name for this circuit breaker
            config: Configuration object
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_success_time = None

    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset from open to half-open."""
        if self.state != CircuitState.OPEN:
            return False
        
        if not self.last_failure_time:
            return False
        
        time_since_failure = time.time() - self.last_failure_time
        return time_since_failure >= self.config.recovery_timeout

    def _record_success(self) -> None:
        """Record a successful call."""
        self.last_success_time = time.time()
        self.failure_count = 0
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.success_count = 0
                logger.info(f"Circuit breaker '{self.name}' closed - service recovered")
        
        logger.debug(f"Circuit breaker '{self.name}' recorded success")

    def _record_failure(self) -> None:
        """Record a failed call."""
        self.last_failure_time = time.time()
        self.failure_count += 1
        self.success_count = 0
        
        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker '{self.name}' opened - "
                    f"{self.failure_count} consecutive failures"
                )
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker '{self.name}' reopened - test call failed")
        
        logger.debug(f"Circuit breaker '{self.name}' recorded failure")

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.

        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            CircuitBreakerError: When circuit is open
            Exception: Original exception from function
        """
        # Check if we should attempt reset
        if self._should_attempt_reset():
            self.state = CircuitState.HALF_OPEN
            logger.info(f"Circuit breaker '{self.name}' half-open - testing service")

        # Block calls if circuit is open
        if self.state == CircuitState.OPEN:
            raise CircuitBreakerError(
                f"Circuit breaker '{self.name}' is open - service unavailable"
            )

        try:
            # Execute function with timeout
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(
                    func(*args, **kwargs), 
                    timeout=self.config.timeout
                )
            else:
                result = func(*args, **kwargs)
            
            self._record_success()
            return result

        except asyncio.TimeoutError:
            logger.warning(f"Circuit breaker '{self.name}' - call timed out")
            self._record_failure()
            raise
        except Exception as e:
            logger.warning(f"Circuit breaker '{self.name}' - call failed: {e}")
            self._record_failure()
            raise

    def get_state(self) -> Dict[str, Any]:
        """
        Get current circuit breaker state information.

        Returns:
            Dictionary with state information
        """
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout,
            }
        }

    def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        logger.info(f"Circuit breaker '{self.name}' manually reset")


class CircuitBreakerManager:
    """
    Manages multiple circuit breakers for different services.
    """

    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

    def get_breaker(self, name: str, config: CircuitBreakerConfig = None) -> CircuitBreaker:
        """
        Get or create circuit breaker for service.

        Args:
            name: Service name
            config: Optional configuration

        Returns:
            Circuit breaker instance
        """
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(name, config)
        return self.circuit_breakers[name]

    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get state information for all circuit breakers."""
        return {
            name: breaker.get_state() 
            for name, breaker in self.circuit_breakers.items()
        }

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self.circuit_breakers.values():
            breaker.reset()


# Global circuit breaker manager
circuit_manager = CircuitBreakerManager()


# Convenience functions for common services
def get_telegram_circuit_breaker() -> CircuitBreaker:
    """Get circuit breaker for Telegram API calls."""
    config = CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=30,
        success_threshold=2,
        timeout=15
    )
    return circuit_manager.get_breaker("telegram_api", config)


def get_stripe_circuit_breaker() -> CircuitBreaker:
    """Get circuit breaker for Stripe API calls."""
    config = CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=60,
        success_threshold=3,
        timeout=30
    )
    return circuit_manager.get_breaker("stripe_api", config)


def get_database_circuit_breaker() -> CircuitBreaker:
    """Get circuit breaker for database calls."""
    config = CircuitBreakerConfig(
        failure_threshold=10,
        recovery_timeout=30,
        success_threshold=5,
        timeout=20
    )
    return circuit_manager.get_breaker("database", config)


async def with_circuit_breaker(
    service_name: str, 
    func: Callable, 
    *args, 
    config: CircuitBreakerConfig = None,
    **kwargs
) -> Any:
    """
    Convenience function to execute function with circuit breaker.

    Args:
        service_name: Name of the service
        func: Function to execute
        *args: Function arguments
        config: Optional circuit breaker configuration
        **kwargs: Function keyword arguments

    Returns:
        Function result

    Raises:
        CircuitBreakerError: When circuit is open
        Exception: Original exception from function
    """
    breaker = circuit_manager.get_breaker(service_name, config)
    return await breaker.call(func, *args, **kwargs) 