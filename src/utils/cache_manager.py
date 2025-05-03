#!/usr/bin/env python3
"""
Cache manager for API responses.
Handles caching and retrieval of API responses with expiration.
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path
import logging

class CacheManager:
    def __init__(self, cache_dir: str = "cache", expiration_hours: int = 12):
        """
        Initialize the cache manager.
        
        Args:
            cache_dir: Directory to store cache files
            expiration_hours: Number of hours before cache expires (default: 12)
        """
        self.cache_dir = Path(cache_dir)
        self.expiration_hours = expiration_hours
        self._ensure_cache_dir()
        
    def _ensure_cache_dir(self) -> None:
        """Ensure the cache directory exists."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def _get_cache_file_path(self, key: str) -> Path:
        """Get the path for a cache file."""
        # Create a safe filename from the key
        safe_key = "".join(c for c in key if c.isalnum() or c in ('-', '_')).rstrip()
        return self.cache_dir / f"{safe_key}.json"
        
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached data if it exists and hasn't expired.
        
        Args:
            key: Unique identifier for the cached data
            
        Returns:
            Cached data if valid, None otherwise
        """
        cache_file = self._get_cache_file_path(key)
        
        if not cache_file.exists():
            return None
            
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                
            # Check if cache has expired
            cache_time = datetime.fromisoformat(cache_data['timestamp'])
            if datetime.now() - cache_time > timedelta(hours=self.expiration_hours):
                logging.info(f"Cache expired for key: {key}")
                return None
                
            return cache_data['data']
            
        except Exception as e:
            logging.error(f"Error reading cache for key {key}: {e}")
            return None
            
    def set(self, key: str, data: Dict[str, Any]) -> None:
        """
        Store data in the cache.
        
        Args:
            key: Unique identifier for the cached data
            data: Data to cache
        """
        cache_file = self._get_cache_file_path(key)
        
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'data': data
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
                
            logging.info(f"Cached data for key: {key}")
            
        except Exception as e:
            logging.error(f"Error caching data for key {key}: {e}")
            
    def clear_expired(self) -> None:
        """Remove all expired cache files."""
        try:
            current_time = datetime.now()
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                        cache_time = datetime.fromisoformat(cache_data['timestamp'])
                        
                    if current_time - cache_time > timedelta(hours=self.expiration_hours):
                        cache_file.unlink()
                        logging.info(f"Removed expired cache file: {cache_file}")
                        
                except Exception as e:
                    logging.error(f"Error processing cache file {cache_file}: {e}")
                    continue
                    
        except Exception as e:
            logging.error(f"Error clearing expired cache: {e}")
            
    def clear_all(self) -> None:
        """Remove all cache files."""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            logging.info("Cleared all cache files")
        except Exception as e:
            logging.error(f"Error clearing all cache: {e}") 