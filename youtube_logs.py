#!/usr/bin/env python3
"""
YouTube API Logging Module

This module provides specialized logging functions for YouTube API operations.
It creates separate log files for different types of operations and ensures
logs are overwritten with each execution.
"""

import os
import logging
import datetime
from typing import Optional

# Log file paths
API_LOG_FILE = "youtube_api.log"
ERROR_LOG_FILE = "youtube_errors.log"
DEBUG_LOG_FILE = "youtube_debug.log"

def setup_logging():
    """Setup logging configuration for YouTube API operations."""
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Configure API logging
    api_logger = logging.getLogger('youtube_api')
    api_logger.setLevel(logging.INFO)
    api_handler = logging.FileHandler(f'logs/{API_LOG_FILE}', mode='w')
    api_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    api_logger.addHandler(api_handler)
    
    # Configure error logging
    error_logger = logging.getLogger('youtube_errors')
    error_logger.setLevel(logging.ERROR)
    error_handler = logging.FileHandler(f'logs/{ERROR_LOG_FILE}', mode='w')
    error_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s\n%(exc_info)s'
    ))
    error_logger.addHandler(error_handler)
    
    # Configure debug logging
    debug_logger = logging.getLogger('youtube_debug')
    debug_logger.setLevel(logging.DEBUG)
    debug_handler = logging.FileHandler(f'logs/{DEBUG_LOG_FILE}', mode='w')
    debug_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    debug_logger.addHandler(debug_handler)
    
    return api_logger, error_logger, debug_logger

def log_api_request(
    api_logger: logging.Logger,
    method: str,
    endpoint: str,
    params: dict,
    response_status: int,
    response_time: float
):
    """Log API request details."""
    api_logger.info(
        f"API Request: {method} {endpoint}\n"
        f"Params: {params}\n"
        f"Status: {response_status}\n"
        f"Response Time: {response_time:.2f}s"
    )

def log_api_error(
    error_logger: logging.Logger,
    error_type: str,
    error_message: str,
    request_details: Optional[dict] = None,
    exc_info: Optional[Exception] = None
):
    """Log API error details."""
    error_logger.error(
        f"API Error: {error_type}\n"
        f"Message: {error_message}\n"
        f"Request Details: {request_details}",
        exc_info=exc_info
    )

def log_api_rate_limit(
    error_logger: logging.Logger,
    quota_used: int,
    quota_remaining: int,
    reset_time: datetime.datetime
):
    """Log API rate limit information."""
    error_logger.warning(
        f"API Rate Limit:\n"
        f"Quota Used: {quota_used}\n"
        f"Quota Remaining: {quota_remaining}\n"
        f"Reset Time: {reset_time}"
    )

def log_api_success(
    api_logger: logging.Logger,
    operation: str,
    details: dict
):
    """Log successful API operation."""
    api_logger.info(
        f"API Success: {operation}\n"
        f"Details: {details}"
    )

def log_debug_info(
    debug_logger: logging.Logger,
    message: str,
    data: Optional[dict] = None
):
    """Log debug information."""
    if data:
        debug_logger.debug(f"{message}\nData: {data}")
    else:
        debug_logger.debug(message)

# Initialize loggers
api_logger, error_logger, debug_logger = setup_logging() 