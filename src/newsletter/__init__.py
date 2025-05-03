#!/usr/bin/env python3
"""
Newsletter package for the ESG Newsletter System.
Exposes newsletter-related functionality.
"""

from .generator import NewsletterGenerator
from .content_processor import ContentProcessor
from .templates import TemplateManager

__all__ = [
    'NewsletterGenerator',
    'ContentProcessor',
    'TemplateManager'
] 