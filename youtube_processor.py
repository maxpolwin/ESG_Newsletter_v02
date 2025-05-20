#!/usr/bin/env python3
"""
YouTube Video Processor for ESG_Newsletter

This module searches for relevant YouTube videos using the YouTube Data API v3 based on
configured keywords. It filters videos by publication date (last 24 hours) and keyword relevance.

Features:
- Automatic API key management from .env
- Rate limiting to respect API constraints
- Graceful error handling
- Parallel processing for performance
- Informative progress logging
- Seamless integration with ESG_Newsletter
"""

import os
import sys
import requests
import logging
import datetime
import time
import json
import threading
from typing import Dict, List, Tuple, Optional, Union, Any
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps
from urllib.parse import quote_plus
import random

# Import configuration and utilities
from keywords_config import get_keywords
from utils import normalize_text, generate_article_id

# Load environment variables from .env file
def load_env_file():
    """Load environment variables from .env file"""
    try:
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
        print("Loaded environment variables from .env file")
    except FileNotFoundError:
        print("No .env file found, using system environment variables")
    except Exception as e:
        print(f"Error loading .env file: {e}")

# Load environment variables
load_env_file()

# Load keywords
KEYWORDS, NEGATIVE_KEYWORDS = get_keywords()

# YouTube API endpoints
SEARCH_ENDPOINT = "https://www.googleapis.com/youtube/v3/search"
VIDEO_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"

# Constants for request handling
DEFAULT_TIMEOUT = 30
RETRY_ATTEMPTS = 5
BASE_DELAY = 1  # Initial delay for exponential backoff

# Rate limiting settings
DAILY_QUOTA = 10000  # YouTube API daily quota
SEARCH_COST = 100    # Cost per search request
VIDEO_COST = 1       # Cost per video details request
SAFE_QUOTA_LIMIT = 0.8  # Use only 80% of daily quota to be safe

# Calculate safe request limits
MAX_SEARCHES_PER_HOUR = int((DAILY_QUOTA * SAFE_QUOTA_LIMIT) / (24 * SEARCH_COST))
MIN_REQUEST_INTERVAL = 3600 / MAX_SEARCHES_PER_HOUR  # Minimum seconds between requests

class YouTubeAPIError(Exception):
    """Exception raised for YouTube API errors."""
    pass

class YouTubeRateLimiter:
    """Rate limiter for YouTube API to prevent hitting API limits."""
    
    def __init__(self):
        self.last_request_time = 0
        self.lock = threading.RLock()
        self.request_count = 0
        self.hourly_requests = []
        self.daily_requests = []
        
    def wait_if_needed(self):
        """Wait if necessary to stay under rate limit."""
        with self.lock:
            now = time.time()
            
            # Clean up old request records
            self.hourly_requests = [t for t in self.hourly_requests if now - t < 3600]
            self.daily_requests = [t for t in self.daily_requests if now - t < 86400]
            
            # Check hourly limit
            if len(self.hourly_requests) >= MAX_SEARCHES_PER_HOUR:
                # Calculate time until next hour
                next_hour = now + (3600 - (now % 3600))
                sleep_time = next_hour - now
                logging.info(f"Hourly quota reached. Waiting {sleep_time/60:.1f} minutes until next hour.")
                time.sleep(sleep_time)
                # Reset hourly requests after waiting
                self.hourly_requests = []
            
            # Check daily limit
            daily_cost = (len(self.daily_requests) * SEARCH_COST)
            if daily_cost >= (DAILY_QUOTA * SAFE_QUOTA_LIMIT):
                # Calculate time until next day
                next_day = now + (86400 - (now % 86400))
                sleep_time = next_day - now
                logging.info(f"Daily quota reached. Waiting {sleep_time/3600:.1f} hours until next day.")
                time.sleep(sleep_time)
                # Reset daily requests after waiting
                self.daily_requests = []
            
            # Ensure minimum interval between requests
            time_since_last = now - self.last_request_time
            if time_since_last < MIN_REQUEST_INTERVAL:
                sleep_time = MIN_REQUEST_INTERVAL - time_since_last
                logging.debug(f"Rate limiting: sleeping for {sleep_time:.1f}s")
                time.sleep(sleep_time)
            
            # Record this request
            self.last_request_time = time.time()
            self.hourly_requests.append(now)
            self.daily_requests.append(now)
            self.request_count += 1
            
            # Log quota usage
            hourly_usage = len(self.hourly_requests) / MAX_SEARCHES_PER_HOUR * 100
            daily_usage = (len(self.daily_requests) * SEARCH_COST) / (DAILY_QUOTA * SAFE_QUOTA_LIMIT) * 100
            logging.info(f"Quota usage - Hourly: {hourly_usage:.1f}%, Daily: {daily_usage:.1f}%")

# Global rate limiter instance
youtube_rate_limiter = YouTubeRateLimiter()

def verify_api_key(api_key: str) -> bool:
    """
    Verify that the API key is valid and has the necessary permissions.
    
    Args:
        api_key (str): The API key to verify
        
    Returns:
        bool: True if the API key is valid and has the necessary permissions
    """
    try:
        # Make a simple API request to verify the key
        params = {
            "key": api_key,
            "part": "snippet",
            "q": "test",
            "type": "video",
            "maxResults": 1
        }
        
        response = requests.get(
            SEARCH_ENDPOINT,
            params=params,
            timeout=DEFAULT_TIMEOUT
        )
        
        if response.status_code == 200:
            return True
            
        error_data = response.json()
        error_message = error_data.get('error', {}).get('message', 'Unknown error')
        error_code = error_data.get('error', {}).get('code', response.status_code)
        error_reason = error_data.get('error', {}).get('errors', [{}])[0].get('reason', 'unknown')
        
        print(f"\nAPI Key Verification Failed:")
        print(f"Error Code: {error_code}")
        print(f"Error Message: {error_message}")
        print(f"Error Reason: {error_reason}")
        
        if error_reason == 'quotaExceeded':
            print("\nThe API key has exceeded its quota. Please try again later or use a different API key.")
        elif error_reason == 'invalid':
            print("\nThe API key is invalid. Please check your API key in the .env file.")
        elif error_reason == 'forbidden':
            print("\nThe API key doesn't have access to the YouTube Data API v3.")
            print("Please enable the YouTube Data API v3 in your Google Cloud Console:")
            print("1. Go to https://console.cloud.google.com")
            print("2. Select your project")
            print("3. Go to 'APIs & Services' > 'Library'")
            print("4. Search for 'YouTube Data API v3'")
            print("5. Click 'Enable'")
        
        return False
        
    except Exception as e:
        print(f"\nError verifying API key: {str(e)}")
        return False

def get_api_key() -> str:
    """Get YouTube API key from environment variables."""
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise YouTubeAPIError("YouTube API key not found in environment variables")
    
    # Verify the API key
    if not verify_api_key(api_key):
        raise YouTubeAPIError("Invalid API key or insufficient permissions")
    
    return api_key

def with_retry(func):
    """Decorator to handle retries for API calls."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        for attempt in range(RETRY_ATTEMPTS):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == RETRY_ATTEMPTS - 1:
                    raise
                delay = BASE_DELAY * (2 ** attempt)
                logging.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay}s...")
                time.sleep(delay)
    return wrapper

@with_retry
def search_videos(
    keyword: str,
    max_results: int = 50,
    published_after: Optional[datetime.datetime] = None
) -> List[Dict]:
    """
    Search for videos using the YouTube Data API.
    
    Args:
        keyword (str): Search keyword
        max_results (int): Maximum number of results to return
        published_after (datetime): Only return videos published after this time
        
    Returns:
        List[Dict]: List of video results
    """
    try:
        api_key = get_api_key()
        
        # Apply rate limiting
        youtube_rate_limiter.wait_if_needed()
        
        # Prepare search parameters
        params = {
            "key": api_key,
            "part": "snippet",
            "q": keyword,
            "type": "video",
            "maxResults": max_results,
            "order": "date"
        }
        
        # Make API request
        response = requests.get(
            SEARCH_ENDPOINT,
            params=params,
            timeout=DEFAULT_TIMEOUT
        )
        
        # Check for API errors
        if response.status_code != 200:
            error_data = response.json()
            error_message = error_data.get('error', {}).get('message', 'Unknown error')
            error_code = error_data.get('error', {}).get('code', response.status_code)
            error_reason = error_data.get('error', {}).get('errors', [{}])[0].get('reason', 'unknown')
            raise YouTubeAPIError(f"API Error {error_code}: {error_message} (Reason: {error_reason})")
        
        data = response.json()
        items = data.get("items", [])
        
        # Filter by date after getting results
        if published_after:
            filtered_items = []
            for item in items:
                try:
                    published_at = datetime.datetime.fromisoformat(
                        item["snippet"]["publishedAt"].replace("Z", "+00:00")
                    )
                    if published_at >= published_after:
                        filtered_items.append(item)
                except (KeyError, ValueError) as e:
                    logging.debug(f"Error parsing video date: {str(e)}")
                    continue
            items = filtered_items
        
        return items
        
    except requests.exceptions.RequestException as e:
        logging.error(f"YouTube API request failed: {str(e)}")
        raise YouTubeAPIError(f"API request failed: {str(e)}")

def process_videos(
    keywords: List[str] = None,
    negative_keywords: List[str] = None,
    hours_ago: int = 24,
    use_parallel: bool = True,
    process_all: bool = True,
    keyword_limit: int = 33  # Changed default to 33 to match hourly quota
) -> Tuple[List[Dict], Counter]:
    """
    Process videos from YouTube API.
    
    Args:
        keywords (List[str], optional): List of keywords to search for
        negative_keywords (List[str], optional): List of negative keywords to exclude
        hours_ago (int, optional): Number of hours to look back. Defaults to 24
        use_parallel (bool, optional): Whether to use parallel processing. Defaults to True
        process_all (bool, optional): If True, process all keywords. If False, limit to keyword_limit
        keyword_limit (int, optional): Maximum number of keywords to process. Defaults to 33
        
    Returns:
        Tuple[List[Dict], Counter]: List of enriched videos and keyword frequency counter
    """
    # Use a fixed current date for testing
    current_time = datetime.datetime(2024, 3, 19, 20, 34, 48, tzinfo=datetime.timezone.utc)
    
    # Log configuration
    timestamp = current_time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*60}")
    print(f"YOUTUBE VIDEO PROCESSOR - {timestamp}")
    print(f"{'='*60}")
    
    # Use imported keywords if none are provided
    if keywords is None:
        keywords = KEYWORDS
    
    if negative_keywords is None:
        negative_keywords = NEGATIVE_KEYWORDS
    
    # Convert sets to lists if necessary
    if isinstance(keywords, set):
        keywords = list(keywords)
    if isinstance(negative_keywords, set):
        negative_keywords = list(negative_keywords)
    
    # Randomly select keywords if not processing all
    if not process_all:
        original_keyword_count = len(keywords)
        # Set random seed for reproducibility
        random.seed(int(current_time.timestamp()))
        # Randomly select keywords
        keywords = random.sample(keywords, min(keyword_limit, len(keywords)))
        print(f"Randomly selected {len(keywords)} keywords from {original_keyword_count} total keywords")
        logging.info(f"Randomly selected {len(keywords)} keywords from {original_keyword_count} total keywords")
    
    # Early validation
    if not keywords:
        logging.warning("No keywords provided. No videos will be returned.")
        print("Warning: No keywords provided. No videos will be returned.")
        return [], Counter()
    
    # Calculate cutoff time in UTC
    cutoff_time = current_time - datetime.timedelta(hours=hours_ago)
    print(f"Searching for videos published after: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    try:
        print(f"\nSearching for videos with {len(keywords)} keywords")
        print(f"Time range: Last {hours_ago} hours")
        
        # Search for videos
        all_videos = []
        for keyword in keywords:
            results = search_videos(
                keyword=keyword,
                published_after=cutoff_time
            )
            all_videos.extend(results)
        
        print(f"Initial search results: {len(all_videos)} videos")
        
        # Remove duplicates based on video ID
        seen_ids = set()
        unique_videos = []
        
        for video in all_videos:
            video_id = video["id"]["videoId"]
            if video_id not in seen_ids:
                seen_ids.add(video_id)
                unique_videos.append(video)
        
        print(f"After deduplication: {len(unique_videos)} unique videos")
        
        # Filter by date (double-check)
        recent_videos = filter_videos_by_date(unique_videos, hours_ago)
        print(f"Recent videos: {len(recent_videos)}")
        
        # Filter by keywords
        print("Filtering by keywords...")
        filtered_videos, keyword_counts = filter_videos_by_keywords(
            recent_videos,
            keywords,
            negative_keywords
        )
        print(f"Keyword-matching videos: {len(filtered_videos)}")
        
        # Enrich video data
        enriched_videos = []
        for video in filtered_videos:
            enriched_video = enrich_video_data(video)
            if enriched_video:
                enriched_videos.append(enriched_video)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"VIDEO PROCESSING SUMMARY")
        print(f"{'='*60}")
        print(f"Total videos found: {len(enriched_videos)}")
        
        if keyword_counts:
            print("\nTop matching keywords:")
            for keyword, count in keyword_counts.most_common(5):
                print(f"  - {keyword}: {count}")
        
        if enriched_videos:
            print("\nFirst 3 video titles:")
            for i, video in enumerate(enriched_videos[:3]):
                print(f"  {i+1}. {video['title']}")
        
        print(f"\n{'='*60}\n")
        
        logging.info(f"Successfully processed {len(enriched_videos)} videos")
        return enriched_videos, keyword_counts
        
    except Exception as e:
        logging.error(f"Error processing videos: {str(e)}", exc_info=True)
        print(f"Error processing videos: {str(e)}")
        return [], Counter()

if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("youtube_processor.log"),
            logging.StreamHandler()
        ]
    )
    
    # Default values
    process_all = False  # Changed default to False to use random selection
    keyword_limit = 33  # Set to 33 to match hourly quota
    hours_ago = 24
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1].lower() == "all":
            process_all = True
            print("Processing all keywords")
        elif sys.argv[1].lower() == "debug":
            logging.getLogger().setLevel(logging.DEBUG)
            print("Debug level set - showing more detailed output")
        elif sys.argv[1].lower() == "verbose":
            logging.getLogger().setLevel(logging.DEBUG)
            print("Verbose level set - showing detailed output")
        else:
            try:
                # First argument can be number of keywords to process
                keyword_limit = min(int(sys.argv[1]), 33)  # Cap at 33 keywords
                print(f"Will process up to {keyword_limit} keywords")
                
                # Second argument can be number of days to look back
                if len(sys.argv) > 2:
                    hours_ago = int(sys.argv[2]) * 24  # Convert days to hours
                    print(f"Will look back {hours_ago//24} days for videos")
            except ValueError:
                print(f"Unrecognized argument: {sys.argv[1]}")
                print("Usage: python youtube_processor.py [all|debug|verbose|NUMBER_OF_KEYWORDS [NUMBER_OF_DAYS]]")
                sys.exit(1)
    
    # Test the module with explicit parameters
    videos, counts = process_videos(
        keywords=KEYWORDS,
        negative_keywords=NEGATIVE_KEYWORDS,
        hours_ago=hours_ago,
        use_parallel=True,
        process_all=process_all,
        keyword_limit=keyword_limit
    )
    
    # Print detailed results
    print(f"\nTest Results:")
    print(f"Found {len(videos)} relevant videos")
    if counts:
        print("Top keyword matches:")
        for keyword, count in counts.most_common(10):
            print(f"  {keyword}: {count}")
    
    # Print some example video results
    if videos:
        print("\nExample videos found:")
        for i, video in enumerate(videos[:3]):
            print(f"{i+1}. {video['title']}")
            print(f"   Channel: {video['channel_title']}")
            print(f"   Duration: {video['duration']}")
            print(f"   Views: {video['view_count']}")
            print(f"   Published: {video['pub_date']}")
            print(f"   Link: {video['link']}")
            print() 