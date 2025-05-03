#!/usr/bin/env python3
"""
Base configuration module for the ESG Newsletter System.
Handles core configuration functionality and environment variables.
"""

import os
from pathlib import Path
from typing import Optional

class ConfigError(Exception):
    """Custom exception for configuration errors."""
    pass

def get_required_env_var(var_name: str) -> str:
    """
    Get a required environment variable or raise an error.
    
    Args:
        var_name: Name of the environment variable
        
    Returns:
        The value of the environment variable
        
    Raises:
        ConfigError: If the environment variable is not set
    """
    value = os.getenv(var_name)
    if not value:
        raise ConfigError(f"Required environment variable '{var_name}' is not set")
    return value

def get_optional_env_var(var_name: str, default: str) -> str:
    """
    Get an optional environment variable with a default value.
    
    Args:
        var_name: Name of the environment variable
        default: Default value if the variable is not set
        
    Returns:
        The value of the environment variable or the default value
    """
    return os.getenv(var_name, default)

# Define base directory for all paths
# Can be overridden by setting the ESG_BASE_DIR environment variable
BASE_DIR = os.getenv('ESG_BASE_DIR', os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def load_env_vars():
    """Load environment variables from .env file manually."""
    env_path = os.path.join(BASE_DIR, '.env')
    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip().strip('"\'')
        print(f"Loaded environment variables from {env_path}")
    except FileNotFoundError:
        print(f"Warning: .env file not found at {env_path}. Using default values.")
    except Exception as e:
        print(f"Error loading .env file: {e}")

# Load environment variables
load_env_vars() 