#!/usr/bin/env python3
"""
Spotify Podcast Processor for ESG_Newsletter

This module searches for relevant podcasts using the Spotify API based on
configured keywords. It filters podcasts by language (English and German),
publication date (last 24 hours), and keyword relevance.

Features:
- Automatic token management with caching
- Rate limiting to respect API constraints
- Graceful error handling
- Parallel processing for performance
- Informative progress logging
- Seamless integration with ESG_Newsletter
"""

import os
import requests
import logging
import datetime
import time
import base64
import json
import threading
from typing import Dict, List, Tuple, Optional, Union, Any
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps

# Import configuration and utilities (matching ESG_Newsletter import pattern)
from config import KEYWORDS, NEGATIVE_KEYWORDS
from utils import normalize_text, generate_article_id

# Spotify API endpoints
TOKEN_URL = "https://accounts.spotify.com/api/token"
SEARCH_ENDPOINT = "https://api.spotify.com/v1/search"

# Constants for request handling
DEFAULT_TIMEOUT = 30
RETRY_ATTEMPTS = 5
BASE_DELAY = 1  # Initial delay for exponential backoff

# Language settings
SUPPORTED_LANGUAGES = ["en", "de"]
MARKET_LANGUAGE_MAP = {
    "US": "en",
    "GB": "en",
    "DE": "de",
    "AT": "de",
    "CH": "de"
}

# Define markets to search in for each language
LANGUAGE_MARKETS = {
    "en": ["US", "GB"],
    "de": ["DE", "AT", "CH"]
}

# Rate limiting settings
MAX_CALLS_PER_SECOND = 5  # Conservative rate limit for Spotify API
MIN_REQUEST_INTERVAL = 0.2  # 200ms minimum between requests

class SpotifyAuthError(Exception):
    """Exception raised for Spotify authentication errors."""
    pass

class SpotifyAPIError(Exception):
    """Exception raised for Spotify API errors."""
    pass

class PodcastProcessorError(Exception):
    """Base exception for podcast processor errors."""
    pass

class SpotifyRateLimiter:
    """Rate limiter for Spotify API to prevent hitting API limits."""
    
    def __init__(self, calls_per_second: int = MAX_CALLS_PER_SECOND):
        self.calls_per_second = calls_per_second
        self.call_timestamps = []
        self.lock = threading.RLock()
        self.min_interval = 1.0 / calls_per_second
        
    def wait_if_needed(self):
        """Wait if necessary to stay under rate limit."""
        with self.lock:
            now = time.time()
            # Remove old timestamps
            self.call_timestamps = [ts for ts in self.call_timestamps 
                                   if now - ts < 1.0]
            
            # Check if we need to wait
            if len(self.call_timestamps) >= self.calls_per_second:
                sleep_time = 1.0 - (now - self.call_timestamps[0])
                if sleep_time > 0:
                    logging.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
                    time.sleep(sleep_time)
            
            # Record this call
            self.call_timestamps.append(time.time())

# Global rate limiter instance
spotify_rate_limiter = SpotifyRateLimiter()

class SpotifyTokenManager:
    """Manages Spotify API tokens with automatic caching and refresh."""
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token: Optional[str] = None
        self.expiration_time: Optional[datetime.datetime] = None
        self.lock = threading.RLock()
        
    def get_valid_token(self) -> str:
        """Get a valid token, refreshing if necessary."""
        with self.lock:
            if not self.token or not self._is_token_valid():
                self._refresh_token()
            return self.token
    
    def _refresh_token(self) -> None:
        """Refresh the Spotify access token using client credentials flow."""
        try:
            # Prepare authentication
            auth_string = f"{self.client_id}:{self.client_secret}"
            auth_bytes = auth_string.encode("utf-8")
            auth_base64 = base64.b64encode(auth_bytes).decode("utf-8")
            
            headers = {
                "Authorization": f"Basic {auth_base64}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {"grant_type": "client_credentials"}
            
            # Rate limit the token request
            spotify_rate_limiter.wait_if_needed()
            
            logging.info("Requesting new Spotify API token...")
            response = requests.post(TOKEN_URL, headers=headers, data=data, timeout=DEFAULT_TIMEOUT)
            
            # Handle specific error cases
            if response.status_code == 400:
                error_data = response.json()
                error_msg = error_data.get("error_description", "Invalid request")
                logging.error(f"Spotify Auth Error: {error_msg}")
                raise SpotifyAuthError(f"Invalid authentication: {error_msg}")
            elif response.status_code == 401:
                logging.error("Invalid client credentials")
                raise SpotifyAuthError("Invalid client ID or secret")
            elif response.status_code == 403:
                logging.error("Forbidden access - check client status")
                raise SpotifyAuthError("Access forbidden - check client status")
            
            response.raise_for_status()
            
            # Parse token response
            auth_data = response.json()
            self.token = auth_data.get("access_token")
            if not self.token:
                raise SpotifyAuthError("No access token in response")
            
            # Calculate token expiration time
            expires_in = auth_data.get("expires_in", 3600)  # Default to 1 hour
            self.expiration_time = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)
            
            logging.info(f"Successfully obtained Spotify token, expires in {expires_in}s")
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to authenticate with Spotify API: {str(e)}")
            raise SpotifyAuthError(f"Authentication failed: {str(e)}")
    
    def _is_token_valid(self) -> bool:
        """Check if the token is still valid."""
        if not self.expiration_time:
            return False
        # Consider token invalid if it expires in less than 5 minutes
        buffer_time = datetime.timedelta(minutes=5)
        return datetime.datetime.now() < (self.expiration_time - buffer_time)

# Token manager singleton
_token_manager: Optional[SpotifyTokenManager] = None

def get_token_manager(client_id: str = None, client_secret: str = None) -> SpotifyTokenManager:
    """Get the global token manager instance."""
    global _token_manager
    
    if _token_manager is None:
        if not client_id or not client_secret:
            # Try to get from environment if not provided
            client_id = os.environ.get("SPOTIFY_CLIENT_ID")
            client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
            
            if not client_id or not client_secret:
                raise SpotifyAuthError("Spotify credentials not found in environment variables")
        
        _token_manager = SpotifyTokenManager(client_id, client_secret)
    
    return _token_manager

def with_spotify_auth(func):
    """Decorator to ensure Spotify API calls have valid authentication."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Check if the function expects a token parameter
        if "token" in kwargs:
            token_manager = get_token_manager()
            kwargs["token"] = token_manager.get_valid_token()
        elif len(args) > 0 and isinstance(args[0], str):
            # Assume first string argument is the token
            token_manager = get_token_manager()
            args = (token_manager.get_valid_token(),) + args[1:]
        
        return func(*args, **kwargs)
    return wrapper

@with_spotify_auth
def search_podcasts(
    token: str, 
    keyword: str,
    market: str,
    limit: int = 50,
    offset: int = 0,
    include_external: str = "audio"
) -> List[Dict]:
    """
    Search for podcast episodes using the Spotify API.
    The token parameter will be automatically populated by the decorator.
    """
    try:
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        params = {
            "q": keyword,
            "type": "episode",
            "market": market,
            "limit": limit,
            "offset": offset,
            "include_external": include_external
        }
        
        # Apply rate limiting
        spotify_rate_limiter.wait_if_needed()
        
        logging.debug(f"Searching Spotify: keyword='{keyword}', market={market}, limit={limit}")
        response = requests.get(SEARCH_ENDPOINT, headers=headers, params=params, timeout=DEFAULT_TIMEOUT)
        
        # Handle Spotify-specific error codes
        if response.status_code == 401:
            # Token might have expired, force refresh
            get_token_manager().get_valid_token()
            raise SpotifyAuthError("Token expired, please retry")
        elif response.status_code == 403:
            error_data = response.json()
            error_msg = error_data.get("error", {}).get("message", "Unknown error")
            raise SpotifyAPIError(f"Forbidden: {error_msg}")
        elif response.status_code == 429:
            # Rate limited - retry with exponential backoff
            retry_after = int(response.headers.get("Retry-After", 30))
            logging.warning(f"Rate limited by Spotify. Waiting {retry_after}s")
            time.sleep(retry_after)
            return []  # Return empty to continue without crashing
        
        response.raise_for_status()
        
        data = response.json()
        episodes = data.get("episodes", {}).get("items", [])
        
        logging.debug(f"Found {len(episodes)} episodes for keyword '{keyword}' in market {market}")
        return episodes
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to search podcasts: {str(e)}")
        raise SpotifyAPIError(f"API search failed: {str(e)}")

def filter_podcasts_by_date(podcasts: List[Dict], hours_ago: int = 24) -> List[Dict]: #72 hours = 3 days increased from 24 hours = 1 day
    """Filter podcasts by release date."""
    cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours_ago)
    filtered_podcasts = []
    
    for podcast in podcasts:
        if "release_date" not in podcast:
            continue
            
        try:
            # Spotify uses ISO 8601 date format (YYYY-MM-DD)
            release_date_str = podcast["release_date"]
            
            # Parse different date formats
            if "T" in release_date_str:
                release_date = datetime.datetime.fromisoformat(release_date_str.replace("Z", "+00:00"))
            else:
                # For date-only strings, assume it was released at 00:00
                release_date = datetime.datetime.strptime(release_date_str, "%Y-%m-%d")
            
            if release_date >= cutoff_time:
                filtered_podcasts.append(podcast)
                
        except (ValueError, TypeError):
            # Skip podcasts with invalid date format
            logging.debug(f"Invalid date format for podcast: {podcast.get('name', 'Unknown')}")
            continue
    
    return filtered_podcasts

def filter_podcasts_by_keywords(
    podcasts: List[Dict],
    keywords: List[str],
    negative_keywords: List[str] = None
) -> Tuple[List[Dict], Counter]:
    """Filter podcasts by keywords in title and description."""
    if negative_keywords is None:
        negative_keywords = []
        
    filtered_podcasts = []
    keyword_counts = Counter()
    
    for podcast in podcasts:
        # Combine title and description for keyword matching
        text = f"{podcast.get('name', '')} {podcast.get('description', '')}"
        text_normalized = normalize_text(text)
        
        # Add spaces for word boundary checks
        padded_text = f" {text_normalized} "
        
        # Check for matches
        matched_keywords = []
        for kw in keywords:
            kw_normalized = normalize_text(kw)
            
            # Follow ESG_Newsletter keyword matching pattern
            if kw.startswith(" ") or kw.endswith(" "):
                if kw_normalized in padded_text:
                    matched_keywords.append(kw)
            else:
                if kw_normalized in text_normalized:
                    matched_keywords.append(kw)
        
        # Check for negative keywords
        excluded = False
        for kw in negative_keywords:
            kw_normalized = normalize_text(kw)
            
            if kw.startswith(" ") or kw.endswith(" "):
                if kw_normalized in padded_text:
                    excluded = True
                    break
            else:
                if kw_normalized in text_normalized:
                    excluded = True
                    break
        
        # If we have matches and no exclusions, add the podcast
        if matched_keywords and not excluded:
            # Add matched keywords to the podcast object
            podcast["matched_keywords"] = matched_keywords
            
            # Count occurrences of each keyword
            for kw in matched_keywords:
                keyword_counts[kw] += 1
                
            filtered_podcasts.append(podcast)
    
    return filtered_podcasts, keyword_counts

def enrich_podcast_data(podcast: Dict, market: str) -> Dict:
    """Enrich podcast data with additional details needed for the newsletter format."""
    # Extract key information
    podcast_id = podcast.get("id", "")
    name = podcast.get("name", "")
    description = podcast.get("description", "")
    release_date = podcast.get("release_date", "")
    duration_ms = podcast.get("duration_ms", 0)
    language = MARKET_LANGUAGE_MAP.get(market, "unknown")
    external_urls = podcast.get("external_urls", {})
    
    # Get show information
    show = podcast.get("show", {})
    show_name = show.get("name", "")
    publisher = show.get("publisher", "")
    
    # Format duration
    minutes, seconds = divmod(duration_ms // 1000, 60)
    hours, minutes = divmod(minutes, 60)
    
    if hours > 0:
        duration_formatted = f"{hours}h {minutes}m"
    else:
        duration_formatted = f"{minutes}m {seconds}s"
    
    # Create snippet from description
    max_snippet_length = 300
    snippet = description[:max_snippet_length] + "..." if len(description) > max_snippet_length else description
    
    # Format in the standard article format expected by the HTML generator
    enriched_data = {
        "title": name,
        "snippet": snippet,
        "keywords": podcast.get("matched_keywords", []),
        "article_id": podcast_id,
        "source_type": "podcast",  # New source type for podcasts
        "source_info": {
            "title": show_name,
            "publisher": publisher,
            "domain": "spotify.com"
        },
        "link": external_urls.get("spotify", ""),
        "pub_date": release_date,
        "language": language,
        # Podcast-specific fields
        "show_name": show_name,
        "duration": duration_formatted,
        "spotify_url": external_urls.get("spotify", "")
    }
    
    return enriched_data

def with_graceful_failure(func):
    """Decorator to handle failures gracefully and continue processing."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logging.error(f"Error in {func.__name__}: {str(e)}")
            # Return empty results based on function signature
            if "get_token" in func.__name__ or "search" in func.__name__:
                return []
            else:
                return None
    return wrapper

def search_keyword_in_markets(keyword: str, markets: List[str]) -> List[Dict]:
    """Search for a keyword in multiple markets."""
    all_results = []
    
    for market in markets:
        try:
            results = search_podcasts(keyword=keyword, market=market)
            # Add market information to each podcast
            for podcast in results:
                podcast["market"] = market
            all_results.extend(results)
        except Exception as e:
            logging.error(f"Error searching keyword '{keyword}' in market {market}: {str(e)}")
            continue
    
    return all_results

def process_podcasts_parallel(keywords: List[str], languages: List[str]) -> List[Dict]:
    """Process podcasts in parallel for better performance."""
    all_results = []
    total_searches = 0
    successful_searches = 0
    
    # Calculate total searches for progress tracking
    for language in languages:
        total_searches += len(keywords) * len(LANGUAGE_MARKETS.get(language, []))
    
    if total_searches == 0:
        logging.warning("No searches to perform")
        return []
    
    logging.info(f"Starting parallel search for {total_searches} keyword/market combinations")
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for language in languages:
            markets = LANGUAGE_MARKETS.get(language, [])
            for keyword in keywords:
                future = executor.submit(search_keyword_in_markets, keyword, markets)
                futures.append((future, language, keyword))
        
        # Track progress
        completed = 0
        for future, language, keyword in futures:
            try:
                results = future.result()
                if results:
                    successful_searches += 1
                    all_results.extend(results)
                completed += 1
                
                # Progress logging
                progress = (completed / total_searches) * 100
                if progress % 20 == 0 or completed == total_searches:
                    logging.info(f"Search progress: {progress:.0f}% ({completed}/{total_searches})")
                    print(f"Podcast search progress: {progress:.0f}% ({completed}/{total_searches})")
                
            except Exception as e:
                logging.error(f"Error processing future for keyword '{keyword}': {str(e)}")
                completed += 1
    
    logging.info(f"Parallel search complete: {successful_searches}/{total_searches} successful searches")
    return all_results

def process_podcasts(
    client_id: str = None,
    client_secret: str = None,
    keywords: List[str] = None,
    negative_keywords: List[str] = None,
    languages: List[str] = None,
    hours_ago: int = 24,
    use_parallel: bool = True
) -> Tuple[List[Dict], Counter]:
    """
    Main function to process podcasts using the Spotify API.
    
    This function gracefully handles all errors and provides detailed logging.
    """
    # Log configuration
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*60}")
    print(f"SPOTIFY PODCAST PROCESSOR - {timestamp}")
    print(f"{'='*60}")
    
    # Try to get credentials from environment if not provided
    if not client_id or not client_secret:
        client_id = os.environ.get("SPOTIFY_CLIENT_ID")
        client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    
    # Check credentials
    if not client_id or not client_secret:
        logging.warning("Spotify API credentials not found. Podcast processing will be skipped.")
        print("Spotify API credentials not found. Podcast processing will be skipped.")
        return [], Counter()
    
    # Use imported keywords if none are provided
    if keywords is None:
        keywords = KEYWORDS
    
    if negative_keywords is None:
        negative_keywords = NEGATIVE_KEYWORDS
        
    if languages is None:
        languages = SUPPORTED_LANGUAGES
    
    # Validate languages
    languages = [lang for lang in languages if lang in SUPPORTED_LANGUAGES]
    
    # Early validation
    if not keywords:
        logging.warning("No keywords provided. No podcasts will be returned.")
        print("Warning: No keywords provided. No podcasts will be returned.")
        return [], Counter()
    
    if not languages:
        logging.warning("No valid languages provided. No podcasts will be returned.")
        print("Warning: No valid languages provided. No podcasts will be returned.")
        return [], Counter()
    
    # Initialize token manager
    try:
        token_manager = get_token_manager(client_id, client_secret)
        logging.info("Spotify token manager initialized successfully")
        print("Spotify token manager initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize Spotify token manager: {str(e)}")
        print(f"Error: Failed to initialize Spotify token manager: {str(e)}")
        return [], Counter()
    
    # Search for podcasts
    try:
        print(f"\nSearching for podcasts with {len(keywords)} keywords in {len(languages)} languages")
        print(f"Time range: Last {hours_ago} hours")
        
        if use_parallel:
            all_podcasts = process_podcasts_parallel(keywords, languages)
        else:
            # Fallback to sequential processing
            all_podcasts = []
            for language in languages:
                markets = LANGUAGE_MARKETS.get(language, [])
                for market in markets:
                    for keyword in keywords:
                        results = search_podcasts(keyword=keyword, market=market)
                        for podcast in results:
                            podcast["market"] = market
                        all_podcasts.extend(results)
        
        print(f"Initial search results: {len(all_podcasts)} episodes")
        
        # Remove duplicates based on podcast ID
        seen_ids = set()
        unique_podcasts = []
        
        for podcast in all_podcasts:
            podcast_id = podcast.get("id")
            if podcast_id and podcast_id not in seen_ids:
                seen_ids.add(podcast_id)
                unique_podcasts.append(podcast)
        
        print(f"After deduplication: {len(unique_podcasts)} unique episodes")
        
        # Filter by date
        print(f"Filtering for episodes from last {hours_ago} hours...")
        recent_podcasts = filter_podcasts_by_date(unique_podcasts, hours_ago)
        print(f"Recent episodes: {len(recent_podcasts)}")
        
        # Filter by keywords
        print("Filtering by keywords...")
        filtered_podcasts, keyword_counts = filter_podcasts_by_keywords(
            recent_podcasts, 
            keywords,
            negative_keywords
        )
        print(f"Keyword-matching episodes: {len(filtered_podcasts)}")
        
        # Enrich podcast data
        enriched_podcasts = []
        for podcast in filtered_podcasts:
            market = podcast.get("market", "US")
            enriched_podcast = enrich_podcast_data(podcast, market)
            enriched_podcasts.append(enriched_podcast)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"PODCAST PROCESSING SUMMARY")
        print(f"{'='*60}")
        print(f"Total episodes found: {len(enriched_podcasts)}")
        
        if keyword_counts:
            print("\nTop matching keywords:")
            for keyword, count in keyword_counts.most_common(5):
                print(f"  - {keyword}: {count}")
        
        if filtered_podcasts:
            print("\nFirst 3 podcast titles:")
            for i, podcast in enumerate(enriched_podcasts[:3]):
                print(f"  {i+1}. {podcast['title']}")
        
        print(f"\n{'='*60}\n")
        
        logging.info(f"Successfully processed {len(enriched_podcasts)} podcast episodes")
        return enriched_podcasts, keyword_counts
        
    except Exception as e:
        logging.error(f"Error processing podcasts: {str(e)}", exc_info=True)
        print(f"Error processing podcasts: {str(e)}")
        return [], Counter()

if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("podcast_processor.log"),
            logging.StreamHandler()
        ]
    )
    
    # Test the module
    podcasts, counts = process_podcasts()
    
    # Print results
    print(f"\nTest Results:")
    print(f"Found {len(podcasts)} relevant podcasts")
    if counts:
        print("Top keyword matches:")
        for keyword, count in counts.most_common(10):
            print(f"  {keyword}: {count}")