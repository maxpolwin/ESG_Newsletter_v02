#!/usr/bin/env python3
"""
Retry utility for handling API retries with exponential backoff and jitter.
"""

import time
import random
import logging
from typing import Callable, Any, Optional, Dict, Type, Union
from datetime import datetime, timedelta
import requests
import threading
from enum import Enum

class ErrorSeverity(Enum):
    """Severity levels for different types of errors."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3

class RetryableError(Exception):
    """Base class for retryable errors."""
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM):
        super().__init__(message)
        self.severity = severity
        self.timestamp = datetime.now()

class RateLimitError(RetryableError):
    """Raised when rate limit is exceeded."""
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message, ErrorSeverity.HIGH)
        self.retry_after = retry_after

class NetworkError(RetryableError):
    """Raised for network-related errors."""
    def __init__(self, message: str):
        super().__init__(message, ErrorSeverity.LOW)

class ServerError(RetryableError):
    """Raised for server errors (5xx)."""
    def __init__(self, message: str, status_code: int):
        super().__init__(message, ErrorSeverity.HIGH)
        self.status_code = status_code

class ClientError(RetryableError):
    """Raised for client errors (4xx)."""
    def __init__(self, message: str, status_code: int):
        super().__init__(message, ErrorSeverity.MEDIUM)
        self.status_code = status_code

class RetryManager:
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        timeout_minutes: int = 60,
        jitter: bool = True,
        jitter_factor: float = 0.1
    ):
        """
        Initialize the retry manager.
        
        Args:
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
            backoff_factor: Factor to multiply delay by after each retry
            timeout_minutes: Total timeout period in minutes
            jitter: Whether to add random jitter to delays
            jitter_factor: Maximum jitter as a fraction of the delay
        """
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if initial_delay < 0:
            raise ValueError("initial_delay must be non-negative")
        if max_delay < initial_delay:
            raise ValueError("max_delay must be greater than or equal to initial_delay")
        if backoff_factor <= 0:
            raise ValueError("backoff_factor must be positive")
        if timeout_minutes < 0:
            raise ValueError("timeout_minutes must be non-negative")
        if jitter_factor < 0 or jitter_factor > 1:
            raise ValueError("jitter_factor must be between 0 and 1")

        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.timeout_minutes = timeout_minutes
        self.jitter = jitter
        self.jitter_factor = jitter_factor
        self.start_time = datetime.now()
        self._lock = threading.Lock()
        self._is_cancelled = False
        
        # Error classification mapping
        self.error_classifiers: Dict[Type[Exception], Type[RetryableError]] = {
            requests.exceptions.Timeout: NetworkError,
            requests.exceptions.ConnectionError: NetworkError,
            requests.exceptions.RequestException: NetworkError,
            requests.exceptions.HTTPError: self._classify_http_error
        }
        
    def _classify_http_error(self, error: requests.exceptions.HTTPError) -> RetryableError:
        """Classify HTTP errors based on status code and headers."""
        if not hasattr(error, 'response') or error.response is None:
            return NetworkError(str(error))
            
        status_code = error.response.status_code
        headers = error.response.headers
        
        # Handle rate limiting
        if status_code == 429:
            retry_after = None
            if 'Retry-After' in headers:
                try:
                    retry_after = int(headers['Retry-After'])
                except ValueError:
                    pass
            return RateLimitError(
                f"Rate limit exceeded (status: {status_code})",
                retry_after=retry_after
            )
            
        # Handle server errors
        if 500 <= status_code < 600:
            return ServerError(
                f"Server error (status: {status_code})",
                status_code=status_code
            )
            
        # Handle client errors
        if 400 <= status_code < 500:
            return ClientError(
                f"Client error (status: {status_code})",
                status_code=status_code
            )
            
        return RetryableError(f"HTTP error (status: {status_code})")
        
    def should_continue(self) -> bool:
        """Check if we should continue retrying based on timeout."""
        with self._lock:
            elapsed = datetime.now() - self.start_time
            return elapsed < timedelta(minutes=self.timeout_minutes)
            
    def cancel(self) -> None:
        """Cancel ongoing retries."""
        with self._lock:
            self._is_cancelled = True
            
    def _add_jitter(self, delay: float) -> float:
        """Add random jitter to the delay."""
        if not self.jitter:
            return delay
            
        jitter_amount = delay * self.jitter_factor
        return max(0.1, delay + random.uniform(-jitter_amount, jitter_amount))
        
    def _get_retry_delay(self, error: RetryableError, attempt: int) -> float:
        """Get the appropriate retry delay based on error type and attempt."""
        if attempt < 1:
            raise ValueError("Attempt number must be positive")
            
        # Handle rate limit retry-after
        if isinstance(error, RateLimitError) and error.retry_after is not None:
            return float(error.retry_after)
            
        # Calculate base delay with overflow protection
        try:
            delay = self.initial_delay * (self.backoff_factor ** (attempt - 1))
        except OverflowError:
            delay = self.max_delay
        else:
            delay = min(delay, self.max_delay)
            
        # Adjust delay based on error severity
        if error.severity == ErrorSeverity.HIGH:
            delay = min(delay * 1.5, self.max_delay)
        elif error.severity == ErrorSeverity.LOW:
            delay = min(delay * 0.8, self.max_delay)
            
        return max(0.1, delay)  # Ensure minimum delay
        
    def _classify_error(self, error: Exception) -> RetryableError:
        """Classify the error and return appropriate RetryableError."""
        for error_type, classifier in self.error_classifiers.items():
            if isinstance(error, error_type):
                if callable(classifier):
                    return classifier(error)
                return classifier()
        return RetryableError(str(error))
        
    def execute_with_retry(
        self,
        func: Callable,
        *args,
        error_callback: Optional[Callable] = None,
        cleanup_callback: Optional[Callable] = None,
        **kwargs
    ) -> Any:
        """
        Execute a function with retry logic.
        
        Args:
            func: Function to execute
            *args: Positional arguments for the function
            error_callback: Optional callback function to handle errors
            cleanup_callback: Optional callback function to clean up resources
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of the function execution
        """
        attempt = 0
        last_error = None
        
        while attempt < self.max_retries:
            if not self.should_continue():
                logging.warning("Retry timeout reached, stopping retries")
                break
                
            if self._is_cancelled:
                logging.warning("Retry operation cancelled")
                break
                
            try:
                result = func(*args, **kwargs)
                if cleanup_callback:
                    cleanup_callback()
                return result
            except Exception as e:
                attempt += 1
                classified_error = self._classify_error(e)
                last_error = classified_error
                
                if error_callback:
                    error_callback(classified_error, attempt)
                    
                if cleanup_callback:
                    try:
                        cleanup_callback()
                    except Exception as cleanup_error:
                        logging.error(f"Error during cleanup: {str(cleanup_error)}")
                    
                if attempt < self.max_retries:
                    delay = self._get_retry_delay(classified_error, attempt)
                    jittered_delay = self._add_jitter(delay)
                    
                    logging.warning(
                        f"Attempt {attempt} failed with {classified_error.__class__.__name__}: "
                        f"{str(classified_error)}. Retrying in {jittered_delay:.2f} seconds..."
                    )
                    time.sleep(jittered_delay)
                else:
                    logging.error(
                        f"All {self.max_retries} attempts failed with "
                        f"{classified_error.__class__.__name__}: {str(classified_error)}"
                    )
                    
        # If we get here, all retries failed or timeout was reached
        if last_error:
            raise last_error
        return None 