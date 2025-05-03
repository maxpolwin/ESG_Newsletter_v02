#!/usr/bin/env python3
"""
Paths configuration module for the ESG Newsletter System.
Handles all directory and file path configurations.
"""

import os
from .base import BASE_DIR

# Output directory setup
OUTPUT_DIR = os.path.join(BASE_DIR, "latest_articles")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Directory for newsletter attachments
ATTACHMENTS_DIR = os.path.join(OUTPUT_DIR, "newsletter_attachments")
os.makedirs(ATTACHMENTS_DIR, exist_ok=True)

# Directory for CSS files
CSS_DIR = os.path.join(BASE_DIR, "css")
os.makedirs(CSS_DIR, exist_ok=True)

# Directory for logs
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Keywords configuration path
KEYWORDS_PATH = os.path.join(BASE_DIR, 'keywords_config_v01.py')

# Main color scheme - centralized for easy theming
COLORS = {
    "primary": "#00827C",
    "primary_dark": "#00635F",
    "primary_light": "#BDD7D6",
    "secondary": "#3B8589",
    "background": "#e3f1ee",
    "background_light": "#F8F8FF",
    "background_alt": "#FFFFFF",
    "text_dark": "#333333",
    "text_medium": "#444444",
    "text_light": "#666666",
    "accent": "#5E9E9A",
} 