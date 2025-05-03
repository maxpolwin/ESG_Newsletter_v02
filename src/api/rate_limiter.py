#!/usr/bin/env python3
"""
Rate limiter module for API calls in the ESG Newsletter System.
Provides rate limiting functionality for various API endpoints.
"""

import time
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self):
        self.requests: Dict[str, list] = {}
        self.limits: Dict[str, Dict[str, int]] = {}
        
    def add_limit(self, endpoint: str, requests_per_minute: int, requests_per_hour: int):
        """Add rate limits for an endpoint."""
        self.limits[endpoint] = {
            'per_minute': requests_per_minute,
            'per_hour': requests_per_hour
        }
        
    def can_make_request(self, endpoint: str) -> bool:
        """Check if a request can be made to the endpoint."""
        current_time = datetime.now()
        
        # Initialize request history if not exists
        if endpoint not in self.requests:
            self.requests[endpoint] = []
            
        # Clean up old requests
        self._cleanup_old_requests(endpoint, current_time)
        
        # Check limits
        if endpoint in self.limits:
            limits = self.limits[endpoint]
            
            # Check per-minute limit
            minute_ago = current_time - timedelta(minutes=1)
            requests_last_minute = len([t for t in self.requests[endpoint] if t > minute_ago])
            if requests_last_minute >= limits['per_minute']:
                logging.warning(f"Rate limit exceeded for {endpoint}: {requests_last_minute} requests in last minute")
                return False
                
            # Check per-hour limit
            hour_ago = current_time - timedelta(hours=1)
            requests_last_hour = len([t for t in self.requests[endpoint] if t > hour_ago])
            if requests_last_hour >= limits['per_hour']:
                logging.warning(f"Rate limit exceeded for {endpoint}: {requests_last_hour} requests in last hour")
                return False
                
        return True
        
    def record_request(self, endpoint: str):
        """Record a request to an endpoint."""
        if endpoint not in self.requests:
            self.requests[endpoint] = []
        self.requests[endpoint].append(datetime.now())
        
    def _cleanup_old_requests(self, endpoint: str, current_time: datetime):
        """Remove requests older than an hour."""
        hour_ago = current_time - timedelta(hours=1)
        self.requests[endpoint] = [t for t in self.requests[endpoint] if t > hour_ago]
        
    def get_wait_time(self, endpoint: str) -> Optional[float]:
        """Calculate how long to wait before making the next request."""
        if not self.can_make_request(endpoint):
            current_time = datetime.now()
            
            if endpoint in self.requests and self.requests[endpoint]:
                # Get the oldest request within the last minute
                minute_ago = current_time - timedelta(minutes=1)
                recent_requests = [t for t in self.requests[endpoint] if t > minute_ago]
                
                if recent_requests:
                    oldest_request = min(recent_requests)
                    wait_time = (minute_ago - oldest_request).total_seconds()
                    return max(0, wait_time)
                    
        return None 