#!/usr/bin/env python3
"""
Semantic Scholar API client with caching support.
"""

import os
import time
import logging
from typing import List, Dict, Any, Optional
import requests
from ..utils.cache_manager import CacheManager
from ..utils.rate_limiter import RateLimiter

class SemanticScholarAPI:
    def __init__(self, cache_dir: str = "cache"):
        """
        Initialize the Semantic Scholar API client.
        
        Args:
            cache_dir: Directory to store cache files
        """
        self.base_url = "https://api.semanticscholar.org/v1"
        self.cache_manager = CacheManager(cache_dir=cache_dir)
        self.rate_limiter = RateLimiter(calls_per_second=5)  # Semantic Scholar's rate limit
        
    def _get_cache_key(self, keyword: str, days_ago: int) -> str:
        """Generate a cache key for a search query."""
        return f"semantic_scholar_{keyword}_{days_ago}"
        
    def search_papers(self, keyword: str, days_ago: int = 1) -> List[Dict[str, Any]]:
        """
        Search for papers using a keyword, with caching support.
        
        Args:
            keyword: Search keyword
            days_ago: Look back period in days
            
        Returns:
            List of paper data
        """
        # Check cache first
        cache_key = self._get_cache_key(keyword, days_ago)
        cached_data = self.cache_manager.get(cache_key)
        
        if cached_data:
            logging.info(f"Using cached data for keyword: {keyword}")
            return cached_data
            
        # If not in cache, make API call
        self.rate_limiter.wait()
        
        try:
            # Calculate the date range
            end_date = int(time.time())
            start_date = end_date - (days_ago * 24 * 60 * 60)
            
            # Prepare the search query
            params = {
                'query': keyword,
                'offset': 0,
                'limit': 100,
                'fields': 'paperId,title,abstract,authors,year,venue,url,citationCount,references',
                'openAccessPdf': True,
                'sort': 'relevance',
                'sortOrder': 'desc',
                'dateRange': f"{start_date}-{end_date}"
            }
            
            # Make the API request
            response = requests.get(
                f"{self.base_url}/paper/search",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                papers = data.get('data', [])
                
                # Cache the results
                self.cache_manager.set(cache_key, papers)
                
                return papers
            else:
                logging.error(f"API request failed with status {response.status_code}")
                return []
                
        except Exception as e:
            logging.error(f"Error searching papers for keyword '{keyword}': {e}")
            return []
            
    def get_paper_details(self, paper_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific paper.
        
        Args:
            paper_id: Semantic Scholar paper ID
            
        Returns:
            Paper details if found, None otherwise
        """
        # Check cache first
        cache_key = f"paper_details_{paper_id}"
        cached_data = self.cache_manager.get(cache_key)
        
        if cached_data:
            logging.info(f"Using cached data for paper ID: {paper_id}")
            return cached_data
            
        # If not in cache, make API call
        self.rate_limiter.wait()
        
        try:
            response = requests.get(
                f"{self.base_url}/paper/{paper_id}",
                params={'fields': 'paperId,title,abstract,authors,year,venue,url,citationCount,references'},
                timeout=30
            )
            
            if response.status_code == 200:
                paper_data = response.json()
                
                # Cache the results
                self.cache_manager.set(cache_key, paper_data)
                
                return paper_data
            else:
                logging.error(f"API request failed with status {response.status_code}")
                return None
                
        except Exception as e:
            logging.error(f"Error getting paper details for ID '{paper_id}': {e}")
            return None
            
    def clear_cache(self) -> None:
        """Clear all cached data."""
        self.cache_manager.clear_all()
        
    def clear_expired_cache(self) -> None:
        """Clear only expired cache entries."""
        self.cache_manager.clear_expired() 