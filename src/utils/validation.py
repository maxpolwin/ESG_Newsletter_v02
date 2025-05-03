#!/usr/bin/env python3
"""
Validation utilities for the ESG Newsletter System.
Handles validation of various data types and formats.
"""

import re
from typing import List, Optional
from datetime import datetime

def validate_email(email: str) -> bool:
    """Validate email address format."""
    if not email:
        return False
        
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_url(url: str) -> bool:
    """Validate URL format."""
    if not url:
        return False
        
    pattern = r'^https?://(?:[\w-]+\.)+[\w-]+(?:/[\w-./?%&=]*)?$'
    return bool(re.match(pattern, url))

def validate_date(date_str: str) -> bool:
    """Validate date string format (YYYY-MM-DD)."""
    if not date_str:
        return False
        
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def validate_keywords(keywords: List[str]) -> bool:
    """Validate list of keywords."""
    if not keywords:
        return False
        
    # Check each keyword
    for keyword in keywords:
        if not keyword or not isinstance(keyword, str):
            return False
        if len(keyword) > 50:  # Reasonable length limit
            return False
            
    return True

def validate_article(article: dict) -> bool:
    """Validate article data structure."""
    required_fields = ['title', 'content', 'source']
    
    # Check required fields
    for field in required_fields:
        if field not in article or not article[field]:
            return False
            
    # Validate title length
    if len(article['title']) > 200:
        return False
        
    # Validate content length
    if len(article['content']) < 50:  # Minimum content length
        return False
        
    # Validate source if it's a URL
    if article['source'].startswith(('http://', 'https://')):
        if not validate_url(article['source']):
            return False
            
    return True

def validate_config(config: dict) -> bool:
    """Validate configuration dictionary."""
    required_fields = [
        'title',
        'description',
        'max_articles',
        'min_relevance_score'
    ]
    
    # Check required fields
    for field in required_fields:
        if field not in config:
            return False
            
    # Validate specific fields
    if not isinstance(config['max_articles'], int) or config['max_articles'] < 1:
        return False
        
    if not isinstance(config['min_relevance_score'], float):
        return False
        
    if not 0 <= config['min_relevance_score'] <= 1:
        return False
        
    return True

def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent XSS and other security issues."""
    if not text:
        return ""
        
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove potentially dangerous characters
    text = re.sub(r'[<>]', '', text)
    
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip() 