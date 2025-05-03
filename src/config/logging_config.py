#!/usr/bin/env python3
"""
Logging configuration module for the ESG Newsletter System.
Handles logging setup and configuration.
"""

import logging
import sys
from .paths import LOG_DIR

def setup_logging():
    """Configure logging with secure defaults."""
    log_file = os.path.join(LOG_DIR, "app.log")
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Create logger
    logger = logging.getLogger(__name__)
    
    # Add security warning if running in debug mode
    if logging.getLogger().getEffectiveLevel() == logging.DEBUG:
        logger.warning("Debug mode is enabled. This may expose sensitive information in logs.")
    
    return logger

# Initialize logger
logger = setup_logging() 