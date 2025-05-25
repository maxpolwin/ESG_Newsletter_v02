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
- Limited to 30 keywords per day from dedicated YouTube keyword set
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
from config import DEDUPLICATION_ENABLED

# Import configuration and utilities
from keywords_config import get_keywords
from utils import normalize_text, generate_article_id
from youtube_logs import (
    api_logger, error_logger, debug_logger,
    log_api_request, log_api_error, log_api_rate_limit,
    log_api_success, log_debug_info
)

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
_, _, YOUTUBE_KEYWORDS, YOUTUBE_NEGATIVE_KEYWORDS = get_keywords()

# YouTube API endpoints
SEARCH_ENDPOINT = "https://www.googleapis.com/youtube/v3/search"
VIDEO_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"

# Constants for request handling
DEFAULT_TIMEOUT = 30
RETRY_ATTEMPTS = 2
BASE_DELAY = 1  # Initial delay for exponential backoff

# Rate limiting settings
DAILY_QUOTA = 10000  # YouTube API daily quota
SEARCH_COST = 100    # Cost per search request
VIDEO_COST = 1       # Cost per video details request
SAFE_QUOTA_LIMIT = 0.8  # Use only 80% of daily quota to be safe
MAX_KEYWORDS_PER_DAY = 30  # Maximum number of keywords to process per day

# Calculate safe request limits
MAX_SEARCHES_PER_HOUR = int((DAILY_QUOTA * SAFE_QUOTA_LIMIT) / (24 * SEARCH_COST))
MIN_REQUEST_INTERVAL = 5 / MAX_SEARCHES_PER_HOUR  # Minimum seconds between requests

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
        
        logging.info(f"Verifying YouTube API key with request to {SEARCH_ENDPOINT}")
        logging.debug(f"Request params: {params}")
        
        response = requests.get(
            SEARCH_ENDPOINT,
            params=params,
            timeout=DEFAULT_TIMEOUT
        )
        
        logging.info(f"API key verification response status: {response.status_code}")
        
        if response.status_code == 200:
            logging.info("API key verification successful")
            return True
            
        error_data = response.json()
        error_message = error_data.get('error', {}).get('message', 'Unknown error')
        error_code = error_data.get('error', {}).get('code', response.status_code)
        error_reason = error_data.get('error', {}).get('errors', [{}])[0].get('reason', 'unknown')
        
        logging.error(f"API Key Verification Failed:")
        logging.error(f"Error Code: {error_code}")
        logging.error(f"Error Message: {error_message}")
        logging.error(f"Error Reason: {error_reason}")
        
        if error_reason == 'quotaExceeded':
            logging.error("The API key has exceeded its quota. Please try again later or use a different API key.")
        elif error_reason == 'invalid':
            logging.error("The API key is invalid. Please check your API key in the .env file.")
        elif error_reason == 'forbidden':
            logging.error("The API key doesn't have access to the YouTube Data API v3.")
            logging.error("Please enable the YouTube Data API v3 in your Google Cloud Console:")
            logging.error("1. Go to https://console.cloud.google.com")
            logging.error("2. Select your project")
            logging.error("3. Go to 'APIs & Services' > 'Library'")
            logging.error("4. Search for 'YouTube Data API v3'")
            logging.error("5. Click 'Enable'")
        
        return False
        
    except Exception as e:
        logging.error(f"Error verifying API key: {str(e)}", exc_info=True)
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
    params = None  # Initialize at the top
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
        
        if published_after:
            params["publishedAfter"] = published_after.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        start_time = time.time()
        log_api_request(
            api_logger,
            "GET",
            SEARCH_ENDPOINT,
            params,
            0,  # Status will be updated after request
            0   # Response time will be updated after request
        )
        
        response = requests.get(
            SEARCH_ENDPOINT,
            params=params,
            timeout=DEFAULT_TIMEOUT
        )
        
        response_time = time.time() - start_time
        
        if response.status_code != 200:
            error_data = response.json()
            error_message = error_data.get('error', {}).get('message', 'Unknown error')
            error_code = error_data.get('error', {}).get('code', response.status_code)
            error_reason = error_data.get('error', {}).get('errors', [{}])[0].get('reason', 'unknown')
            
            log_api_error(
                error_logger,
                f"YouTube API Error {error_code}",
                error_message,
                {"params": params, "reason": error_reason},
                None
            )
            
            if error_reason == 'quotaExceeded':
                log_api_rate_limit(
                    error_logger,
                    quota_used=10000,  # This should be updated with actual quota info if available
                    quota_remaining=0,
                    reset_time=datetime.datetime.now() + datetime.timedelta(days=1)
                )
            
            raise YouTubeAPIError(f"API Error {error_code}: {error_message} (Reason: {error_reason})")
        
        data = response.json()
        items = data.get("items", [])
        
        log_api_success(
            api_logger,
            "Video Search",
            {
                "keyword": keyword,
                "videos_found": len(items),
                "response_time": response_time
            }
        )
        
        return items
        
    except requests.exceptions.RequestException as e:
        log_api_error(
            error_logger,
            "Request Exception",
            str(e),
            {"endpoint": SEARCH_ENDPOINT, "params": params} if params else {"endpoint": SEARCH_ENDPOINT},
            e
        )
        raise YouTubeAPIError(f"API request failed: {str(e)}")
    except Exception as e:
        if 'quotaExceeded' in str(e):
            print("Quota exceeded. Stopping further API calls.")
            return []  # Return empty list instead of break
        log_api_error(
            error_logger,
            "Unexpected Error",
            str(e),
            {"endpoint": SEARCH_ENDPOINT, "params": params} if params else {"endpoint": SEARCH_ENDPOINT},
            e
        )
        raise

def filter_videos_by_keywords(
    videos: List[Dict],
    positive_keywords: List[str],
    negative_keywords: List[str]
) -> Tuple[List[Dict], Counter]:
    """
    Filter videos based on positive and negative keywords.
    
    Args:
        videos (List[Dict]): List of video dictionaries to filter
        positive_keywords (List[str]): Keywords that should be present
        negative_keywords (List[str]): Keywords that should not be present
        
    Returns:
        Tuple[List[Dict], Counter]: Filtered videos and keyword frequency counter
    """
    filtered_videos = []
    keyword_counts = Counter()
    
    for video in videos:
        # Get video title and description
        title = video.get('snippet', {}).get('title', '').lower()
        description = video.get('snippet', {}).get('description', '').lower()
        
        # Check for negative keywords first
        has_negative_keyword = any(
            keyword.lower() in title or keyword.lower() in description
            for keyword in negative_keywords
        )
        
        if has_negative_keyword:
            continue
            
        # Check for positive keywords
        matched_keywords = []
        for keyword in positive_keywords:
            if keyword.lower() in title or keyword.lower() in description:
                matched_keywords.append(keyword)
                keyword_counts[keyword] += 1
        
        # Only include videos that match at least one positive keyword
        if matched_keywords:
            filtered_videos.append(video)
    
    return filtered_videos, keyword_counts

def enrich_video_data(video: Dict, keywords: list = None) -> Optional[Dict]:
    """
    Enrich video data with additional formatted information.
    Args:
        video (Dict): Raw video data from YouTube API
        keywords (list, optional): List of matched keywords
    Returns:
        Optional[Dict]: Enriched video data or None if enrichment fails
    """
    try:
        snippet = video.get('snippet', {})
        enriched = {
            'video_id': video.get('id', {}).get('videoId'),
            'title': snippet.get('title', ''),
            'description': snippet.get('description', ''),
            'snippet': snippet.get('description', ''),  # For HTML generator compatibility
            'channel_title': snippet.get('channelTitle', ''),
            'channel_id': snippet.get('channelId', ''),
            'pub_date': snippet.get('publishedAt', ''),
            'thumbnail_url': snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
            'link': f"https://www.youtube.com/watch?v={video.get('id', {}).get('videoId')}",
            'keywords': keywords or [],
            'duration': '',
            'view_count': 0
        }
        # Try to get additional video details if available
        if 'contentDetails' in video:
            duration = video['contentDetails'].get('duration', '')
            if duration:
                hours = 0
                minutes = 0
                seconds = 0
                if 'H' in duration:
                    hours = int(duration.split('H')[0].replace('PT', ''))
                if 'M' in duration:
                    minutes = int(duration.split('M')[0].split('H')[-1])
                if 'S' in duration:
                    seconds = int(duration.split('S')[0].split('M')[-1])
                if hours > 0:
                    enriched['duration'] = f"{hours}:{minutes:02d}:{seconds:02d}"
                else:
                    enriched['duration'] = f"{minutes}:{seconds:02d}"
        if 'statistics' in video:
            enriched['view_count'] = int(video['statistics'].get('viewCount', 0))
        if enriched['pub_date']:
            try:
                pub_date = datetime.datetime.fromisoformat(
                    enriched['pub_date'].replace('Z', '+00:00')
                )
                enriched['pub_date'] = pub_date.strftime('%Y-%m-%d %H:%M:%S UTC')
            except (ValueError, TypeError):
                pass
        content_to_store = {
            'id': video.get('id', {}).get('videoId'),
            'source_type': 'youtube',
            'title': snippet.get('title', ''),
            'content': snippet.get('description', ''),
            'url': f"https://www.youtube.com/watch?v={video.get('id', {}).get('videoId')}",
            'date_published': snippet.get('publishedAt', ''),
            'source_info': {
                'title': snippet.get('channelTitle', ''),  # Set title for source_info
                'channel_title': snippet.get('channelTitle', ''),
                'channel_id': snippet.get('channelId', ''),
                'domain': 'youtube.com'
            },
            'keywords': keywords or [],
            'metadata': {
                'duration': enriched.get('duration', ''),
                'view_count': enriched.get('view_count', 0),
                'thumbnail_url': enriched.get('thumbnail_url', ''),
                'channel_title': snippet.get('channelTitle', ''),
                'channel_id': snippet.get('channelId', '')
            }
        }
        from content_storage import store_content
        store_content(content_to_store)
        return enriched
    except Exception as e:
        logging.error(f"Error enriching video data: {str(e)}")
        return None

def process_videos(
    keywords: List[str] = None,
    negative_keywords: List[str] = None,
    hours_ago: int = 24,
    use_parallel: bool = True,
    process_all: bool = False,
    keyword_limit: int = MAX_KEYWORDS_PER_DAY
) -> Tuple[List[Dict], Counter]:
    """
    Process videos from YouTube API.
    
    Args:
        keywords (List[str], optional): List of keywords to search for. If None, uses YOUTUBE_KEYWORDS
        negative_keywords (List[str], optional): List of negative keywords to exclude. If None, uses YOUTUBE_NEGATIVE_KEYWORDS
        hours_ago (int, optional): Number of hours to look back. Defaults to 24
        use_parallel (bool, optional): Whether to use parallel processing. Defaults to True
        process_all (bool, optional): If True, process all keywords. If False, limit to keyword_limit. Defaults to False
        keyword_limit (int, optional): Maximum number of keywords to process. Defaults to MAX_KEYWORDS_PER_DAY
        
    Returns:
        Tuple[List[Dict], Counter]: List of enriched videos and keyword frequency counter
        Even if processing fails, returns empty list and counter to allow main.py to continue
    """
    try:
        # Use current date and time
        current_time = datetime.datetime.now(datetime.timezone.utc)
        
        # Log configuration
        timestamp = current_time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{'='*60}")
        print(f"YOUTUBE VIDEO PROCESSOR - {timestamp}")
        print(f"{'='*60}")
        
        # Use YouTube-specific keywords if none are provided
        if keywords is None:
            keywords = list(YOUTUBE_KEYWORDS)
        
        if negative_keywords is None:
            negative_keywords = list(YOUTUBE_NEGATIVE_KEYWORDS)
        
        # Convert sets to lists if necessary
        if isinstance(keywords, set):
            keywords = list(keywords)
        if isinstance(negative_keywords, set):
            negative_keywords = list(negative_keywords)
        
        # Randomly select keywords if not processing all
        if not process_all:
            original_keyword_count = len(keywords)
            # Set random seed for reproducibility based on current date
            random.seed(int(current_time.date().strftime("%Y%m%d")))
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
        
        print(f"\nSearching for videos with {len(keywords)} keywords")
        print(f"Time range: Last {hours_ago} hours")
        
        # Search for videos
        all_videos = []
        failed_keywords = []
        
        # Implement parallel processing for video searches
        if use_parallel:
            with ThreadPoolExecutor(max_workers=min(10, len(keywords))) as executor:
                # Create future tasks for each keyword
                future_to_keyword = {
                    executor.submit(search_videos, keyword=keyword, published_after=cutoff_time): keyword 
                    for keyword in keywords
                }
                
                # Process results as they complete
                for future in as_completed(future_to_keyword):
                    keyword = future_to_keyword[future]
                    try:
                        results = future.result()
                        if results:
                            all_videos.extend(results)
                            print(f"Found {len(results)} videos for keyword: {keyword}")
                    except Exception as e:
                        if 'quotaExceeded' in str(e):
                            print("Quota exceeded. Stopping further API calls.")
                            break
                        failed_keywords.append(keyword)
                        logging.error(f"Error processing keyword '{keyword}': {str(e)}")
                        print(f"Error processing keyword '{keyword}': {str(e)}")
                        continue
        else:
            # Existing sequential processing code
            for keyword in keywords:
                try:
                    print(f"\nProcessing keyword: {keyword}")
                    results = search_videos(
                        keyword=keyword,
                        published_after=cutoff_time
                    )
                    if results:
                        all_videos.extend(results)
                        print(f"Found {len(results)} videos for keyword: {keyword}")
                    else:
                        print(f"No videos found for keyword: {keyword}")
                except Exception as e:
                    if 'quotaExceeded' in str(e):
                        print("Quota exceeded. Stopping further API calls.")
                        break
                    failed_keywords.append(keyword)
                    logging.error(f"Error processing keyword '{keyword}': {str(e)}")
                    print(f"Error processing keyword '{keyword}': {str(e)}")
                    continue  # Continue with next keyword
        
        if failed_keywords:
            print(f"\nFailed to process {len(failed_keywords)} keywords: {', '.join(failed_keywords)}")
            logging.warning(f"Failed to process {len(failed_keywords)} keywords: {', '.join(failed_keywords)}")
        
        print(f"Initial search results: {len(all_videos)} videos")
        
        # Remove duplicates based on video ID
        seen_ids = set()
        unique_videos = []
        if DEDUPLICATION_ENABLED:
            for video in all_videos:
                video_id = video["id"]["videoId"]
                if video_id not in seen_ids:
                    seen_ids.add(video_id)
                    unique_videos.append(video)
        else:
            unique_videos = all_videos  # No deduplication, keep all
        
        print(f"After deduplication: {len(unique_videos)} unique videos")
        
        # Filter by date (double-check)
        recent_videos = unique_videos  # Since filtering already happened in search_videos
        print(f"Recent videos: {len(recent_videos)}")
        
        # Filter by keywords
        print("Filtering by keywords...")
        filtered_videos, keyword_counts = filter_videos_by_keywords(
            recent_videos,
            keywords,
            negative_keywords
        )
        print(f"Keyword-matching videos: {len(filtered_videos)}")
        
        # Enrich video data and attach matched keywords
        enriched_videos = []
        for video in filtered_videos:
            title = video.get('snippet', {}).get('title', '').lower()
            description = video.get('snippet', {}).get('description', '').lower()
            matched_keywords = [kw for kw in keywords if kw.lower() in title or kw.lower() in description]
            enriched_video = enrich_video_data(video, keywords=matched_keywords)
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
        logging.error(f"Critical error in process_videos: {str(e)}", exc_info=True)
        print(f"Critical error in process_videos: {str(e)}")
        return [], Counter()  # Return empty results to allow main.py to continue

if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',  # Simplified format
        handlers=[
            logging.FileHandler("youtube_processor.log"),
            logging.StreamHandler(sys.stdout)  # Explicitly use stdout
        ]
    )
    
    # Set root logger level to INFO
    logging.getLogger().setLevel(logging.INFO)
    
    # Default values
    process_all = False  # Changed default to False to use random selection
    keyword_limit = MAX_KEYWORDS_PER_DAY  # Set to MAX_KEYWORDS_PER_DAY
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
                keyword_limit = min(int(sys.argv[1]), MAX_KEYWORDS_PER_DAY)  # Cap at MAX_KEYWORDS_PER_DAY
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
        keywords=YOUTUBE_KEYWORDS,
        negative_keywords=YOUTUBE_NEGATIVE_KEYWORDS,
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