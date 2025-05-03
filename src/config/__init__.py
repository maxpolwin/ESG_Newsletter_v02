#!/usr/bin/env python3
"""
Configuration package for the ESG Newsletter System.
Exposes all configuration modules and their contents.
"""

from .base import (
    ConfigError,
    get_required_env_var,
    get_optional_env_var,
    BASE_DIR,
    load_env_vars,
)

from .email_config import (
    validate_email,
    get_recipient_emails,
    EMAIL_HOST,
    EMAIL_USER,
    EMAIL_PASSWORD,
    EMAIL_RECIPIENTS,
    TRUSTED_SENDERS,
)

from .paths import (
    OUTPUT_DIR,
    ATTACHMENTS_DIR,
    CSS_DIR,
    LOG_DIR,
    KEYWORDS_PATH,
    COLORS,
)

from .logging_config import setup_logging, logger

from .feeds import (
    RSS_FEEDS,
    TIME_THRESHOLD,
    CLEANUP_THRESHOLD,
)

from .api_config import (
    PERPLEXITY_API_KEY,
    API_CONFIG,
    RATE_LIMITS,
    API_ERROR_MESSAGES,
)

from .newsletter_config import (
    NEWSLETTER_SETTINGS,
    SCHEDULE,
    SECTIONS,
    TEMPLATES,
    METADATA,
    FILTERS,
)

__all__ = [
    # Base
    'ConfigError',
    'get_required_env_var',
    'get_optional_env_var',
    'BASE_DIR',
    'load_env_vars',
    
    # Email
    'validate_email',
    'get_recipient_emails',
    'EMAIL_HOST',
    'EMAIL_USER',
    'EMAIL_PASSWORD',
    'EMAIL_RECIPIENTS',
    'TRUSTED_SENDERS',
    
    # Paths
    'OUTPUT_DIR',
    'ATTACHMENTS_DIR',
    'CSS_DIR',
    'LOG_DIR',
    'KEYWORDS_PATH',
    'COLORS',
    
    # Logging
    'setup_logging',
    'logger',
    
    # Feeds
    'RSS_FEEDS',
    'TIME_THRESHOLD',
    'CLEANUP_THRESHOLD',
    
    # API
    'PERPLEXITY_API_KEY',
    'API_CONFIG',
    'RATE_LIMITS',
    'API_ERROR_MESSAGES',
    
    # Newsletter
    'NEWSLETTER_SETTINGS',
    'SCHEDULE',
    'SECTIONS',
    'TEMPLATES',
    'METADATA',
    'FILTERS',
] 