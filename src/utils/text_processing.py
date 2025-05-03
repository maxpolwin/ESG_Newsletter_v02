#!/usr/bin/env python3
"""
Text processing utilities for the ESG Newsletter System.
Handles text normalization, cleaning, and processing.
"""

import re
import unicodedata
from typing import List, Optional
from html import unescape

def normalize_text(text: str) -> str:
    """Normalize text to remove inconsistencies in encoding and case."""
    if not text:
        return ""
    if isinstance(text, bytes):
        text = text.decode('utf-8', errors='ignore')
    return unicodedata.normalize("NFKD", unescape(text)).lower()

def clean_text(text: str) -> str:
    """Clean text by removing extra whitespace and special characters."""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove special characters but keep basic punctuation
    text = re.sub(r'[^\w\s.,!?-]', '', text)
    return text.strip()

def extract_links(text: str) -> List[str]:
    """Extract URLs from text."""
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    return re.findall(url_pattern, text)

def truncate_text(text: str, max_length: int = 200) -> str:
    """Truncate text to a maximum length while preserving words."""
    if len(text) <= max_length:
        return text
    return text[:max_length].rsplit(' ', 1)[0] + '...'

def sanitize_filename(filename: str) -> str:
    """Create a safe filename from a string."""
    # Remove invalid filename characters
    safe_name = re.sub(r'[\\/*?:"<>|]', "", filename)
    # Replace spaces, commas, etc. with underscores
    safe_name = re.sub(r'[\s,;]+', "_", safe_name)
    # Remove other problematic characters
    safe_name = re.sub(r'[^\w\-.]', "", safe_name)
    # Limit length but try to keep full words
    if len(safe_name) > 100:
        safe_name = safe_name[:100]
    # Ensure the filename isn't empty
    if not safe_name:
        safe_name = "newsletter"
    return safe_name

def extract_keywords(text: str, keywords: List[str]) -> List[str]:
    """Extract keywords from text."""
    found_keywords = []
    normalized_text = normalize_text(text)
    
    for keyword in keywords:
        if keyword.lower() in normalized_text:
            found_keywords.append(keyword)
            
    return found_keywords

def calculate_relevance(text: str, keywords: List[str]) -> float:
    """Calculate text relevance based on keyword occurrences."""
    if not keywords:
        return 0.0
        
    normalized_text = normalize_text(text)
    keyword_counts = {}
    
    for keyword in keywords:
        count = len(re.findall(r'\b' + re.escape(keyword.lower()) + r'\b', normalized_text))
        keyword_counts[keyword] = count
        
    total_occurrences = sum(keyword_counts.values())
    max_possible = len(keywords) * 3  # Assume 3 occurrences per keyword is maximum
    
    return min(1.0, total_occurrences / max_possible) 