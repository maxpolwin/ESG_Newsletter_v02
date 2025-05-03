#!/usr/bin/env python3
"""
API configuration module for the ESG Newsletter System.
Handles API keys and related configurations.
"""

from typing import Dict, Any
from .base import get_required_env_var, ConfigError

# API Keys
PERPLEXITY_API_KEY = get_required_env_var("PERPLEXITY_API_KEY")

# API Configuration
API_CONFIG: Dict[str, Any] = {
    "perplexity": {
        "base_url": "https://api.perplexity.ai",
        "model": "mixtral-8x7b-instruct",
        "max_tokens": 4096,
        "temperature": 0.7,
        "top_p": 0.9,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
    }
}

# API Rate Limits
RATE_LIMITS = {
    "perplexity": {
        "requests_per_minute": 60,
        "requests_per_hour": 1000,
    }
}

# API Error Messages
API_ERROR_MESSAGES = {
    "perplexity": {
        "invalid_key": "Invalid Perplexity API key. Please check your configuration.",
        "rate_limit": "Rate limit exceeded. Please try again later.",
        "server_error": "Server error occurred. Please try again later.",
    }
} 