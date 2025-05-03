#!/usr/bin/env python3
"""
Newsletter configuration module for the ESG Newsletter System.
Handles newsletter-specific settings and configurations.
"""

from typing import Dict, Any
from .base import get_required_env_var, get_optional_env_var

# Newsletter Settings
NEWSLETTER_SETTINGS: Dict[str, Any] = {
    "title": "ESG Newsletter",
    "description": "Your daily digest of ESG-related news and insights",
    "language": "en",
    "timezone": "UTC",
    "max_articles_per_section": 5,
    "max_total_articles": 20,
    "min_article_length": 100,
    "max_article_length": 1000,
    "include_summaries": True,
    "include_keywords": True,
    "include_sources": True,
    "include_dates": True,
}

# Newsletter Schedule
SCHEDULE = {
    "frequency": "daily",
    "time": "08:00",  # UTC
    "timezone": "UTC",
    "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
}

# Newsletter Sections
SECTIONS = [
    "ESG Policy & Regulation",
    "Climate Change & Environment",
    "Social Impact & Governance",
    "Sustainable Finance",
    "Corporate Responsibility",
]

# Newsletter Templates
TEMPLATES = {
    "html": "templates/newsletter.html",
    "text": "templates/newsletter.txt",
    "subject": "templates/subject.txt",
}

# Newsletter Metadata
METADATA = {
    "version": "1.0.0",
    "generator": "ESG Newsletter System",
    "encoding": "UTF-8",
}

# Newsletter Filters
FILTERS = {
    "min_relevance_score": 0.7,
    "max_age_days": 7,
    "excluded_domains": [
        "spam.com",
        "advertisement.com",
    ],
    "required_keywords": [
        "ESG",
        "sustainability",
        "climate",
        "environment",
        "social",
        "governance",
    ],
} 