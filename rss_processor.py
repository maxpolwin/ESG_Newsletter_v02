#!/usr/bin/env python3
"""
Newsletter System v08 - Enhanced RSS Feed Processor

Handles fetching, parsing, and filtering of RSS feeds with advanced features.
Extracts relevant articles based on configured keywords with improved robustness.

Based on v07 by Max Polwin
Enhanced with anti-blocking, full content extraction, and stability improvements
"""

import feedparser
import time
import logging
import requests
from bs4 import BeautifulSoup
from collections import Counter
import random
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
import chardet
import os
import json
import hashlib
import tempfile
from datetime import datetime, timedelta
import socket
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import ssl
from urllib3.exceptions import InsecureRequestWarning
import gzip
import traceback
import threading
from keywords_config import get_keywords
from utils import normalize_text, generate_article_id, get_domain_from_url

# For PDF processing
try:
    import PyPDF2
    from PyPDF2 import PdfReader
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    logging.warning("PyPDF2 not installed. PDF processing will be disabled.")


# For browser automation (optional)
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    SELENIUM_SUPPORT = True
except ImportError:
    SELENIUM_SUPPORT = False
    logging.warning("Selenium not installed. Browser automation for difficult feeds will be disabled.")

# Import configuration and utilities
from config import RSS_FEEDS, KEYWORDS, NEGATIVE_KEYWORDS, TIME_THRESHOLD
from utils import normalize_text, generate_article_id, get_domain_from_url

# Suppress only the insecure request warning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Constants for request handling
DEFAULT_TIMEOUT = 30
EXTENDED_TIMEOUT = 120  # Increased default timeout for all feeds
RETRY_ATTEMPTS = 5  # Increased retry attempts for all feeds
BASE_DELAY = 5  # Increased base delay for all feeds
POOL_CONNECTIONS = 2
POOL_MAXSIZE = 3

# Rate limiting settings
RATE_LIMIT_REQUESTS = 10  # Number of requests allowed per window
RATE_LIMIT_WINDOW = 60  # Time window in seconds
MIN_REQUEST_INTERVAL = 0.5  # Minimum time between requests to the same domain

# Feed health monitoring settings
FEED_HEALTH_WINDOW = 24 * 60 * 60  # 24 hours in seconds
MIN_SUCCESS_RATE = 0.7  # Minimum success rate for a feed to be considered healthy
MAX_CONSECUTIVE_FAILURES = 3000  # Maximum number of consecutive failures before marking feed as unhealthy

# New settings for enhanced functionality
EXTRACT_FULL_CONTENT = True  # Whether to extract full article content
MAX_CONTENT_SIZE = 5 * 1024 * 1024  # 5MB max for full content extraction
FETCH_IMAGES = True  # Whether to fetch and store images
PROCESS_ATTACHMENTS = True  # Whether to process attachments like PDFs
USE_BROWSER_AUTOMATION = True if SELENIUM_SUPPORT else False  # Use browser automation for difficult feeds
BROWSER_TIMEOUT = 30  # Timeout for browser automation in seconds
MAX_BROWSER_INSTANCES = 2  # Maximum number of concurrent browser instances
USE_PROXIES = False  # Whether to use proxy rotation (requires proxy configuration)
PROXY_LIST = []  # List of proxies to use if USE_PROXIES is True
VERIFY_SSL = True  # Whether to verify SSL certificates

# Browser automation pool
browser_pool_semaphore = threading.Semaphore(MAX_BROWSER_INSTANCES)
browser_pool = {}  # Keep track of browser instances per thread

# Dictionary to track problematic feeds
problematic_feeds = {}

# Circuit breaker settings
CIRCUIT_BREAKER_ERROR_THRESHOLD = 5  # Number of errors before tripping the circuit breaker
CIRCUIT_BREAKER_TIMEOUT = 3600  # Time to keep circuit breaker tripped (1 hour)
circuit_breakers = {}  # Dictionary to store circuit breaker states

# Thread-local storage for browser instances
thread_local = threading.local()

class CircuitBreaker:
    """Implements the circuit breaker pattern for feed fetching."""

    def __init__(self):
        self.circuit_breakers = {}
        self.lock = threading.RLock()

    def can_execute(self, feed_url):
        """Check if a feed can be fetched based on its circuit breaker state."""
        with self.lock:
            if feed_url not in self.circuit_breakers:
                return True

            breaker = self.circuit_breakers[feed_url]
            if breaker['state'] == 'open':
                # Check if timeout has passed
                if time.time() - breaker['last_trip_time'] > CIRCUIT_BREAKER_TIMEOUT:
                    # Reset to half-open state
                    breaker['state'] = 'half-open'
                    return True
                return False
            return True

    def record_success(self, feed_url):
        """Record a successful feed fetch."""
        with self.lock:
            if feed_url in self.circuit_breakers:
                breaker = self.circuit_breakers[feed_url]
                if breaker['state'] == 'half-open':
                    # Reset the circuit breaker on successful half-open state
                    breaker['state'] = 'closed'
                    breaker['failure_count'] = 0
                else:
                    # Just reset the failure count
                    breaker['failure_count'] = 0
            else:
                # Initialize the circuit breaker if it doesn't exist
                self.circuit_breakers[feed_url] = {
                    'state': 'closed',
                    'failure_count': 0,
                    'last_trip_time': 0
                }

    def record_failure(self, feed_url):
        """Record a failed feed fetch."""
        with self.lock:
            if feed_url not in self.circuit_breakers:
                self.circuit_breakers[feed_url] = {
                    'state': 'closed',
                    'failure_count': 1,
                    'last_trip_time': 0
                }
            else:
                breaker = self.circuit_breakers[feed_url]
                if breaker['state'] == 'half-open':
                    # Trip the circuit breaker again
                    breaker['state'] = 'open'
                    breaker['last_trip_time'] = time.time()
                elif breaker['state'] == 'closed':
                    # Increment failure count
                    breaker['failure_count'] += 1
                    if breaker['failure_count'] >= CIRCUIT_BREAKER_ERROR_THRESHOLD:
                        # Trip the circuit breaker
                        breaker['state'] = 'open'
                        breaker['last_trip_time'] = time.time()
                        logging.warning(f"Circuit breaker tripped for feed: {feed_url}")

# Create a global circuit breaker
circuit_breaker = CircuitBreaker()

class FeedHealthMonitor:
    def __init__(self):
        self.feed_stats = {}
        self.last_check = {}
        self.stats_file = 'feed_health_stats.json'
        self.lock = threading.RLock()
        self._load_stats()

    def _load_stats(self):
        """Load feed health statistics from file."""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    self.feed_stats = json.load(f)
                    # Ensure response_times field exists for all feeds
                    for feed_url in self.feed_stats:
                        if 'response_times' not in self.feed_stats[feed_url]:
                            self.feed_stats[feed_url]['response_times'] = []
        except Exception as e:
            logging.error(f"Error loading feed health stats: {e}")

    def _save_stats(self):
        """Save feed health statistics to file."""
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.feed_stats, f)
        except Exception as e:
            logging.error(f"Error saving feed health stats: {e}")

    def record_fetch(self, feed_url, success, error=None):
        """Record the result of a feed fetch attempt."""
        with self.lock:
            current_time = time.time()

            if feed_url not in self.feed_stats:
                self.feed_stats[feed_url] = {
                    'total_attempts': 0,
                    'successful_attempts': 0,
                    'consecutive_failures': 0,
                    'last_success': None,
                    'last_failure': None,
                    'errors': [],
                    'response_times': []  # New: track response times
                }

            stats = self.feed_stats[feed_url]
            stats['total_attempts'] += 1

            if success:
                stats['successful_attempts'] += 1
                stats['consecutive_failures'] = 0
                stats['last_success'] = current_time
            else:
                stats['consecutive_failures'] += 1
                stats['last_failure'] = current_time
                if error:
                    stats['errors'].append((current_time, str(error)))
                    # Keep only last 10 errors
                    stats['errors'] = stats['errors'][-10:]

            # Periodically save stats to avoid excessive disk I/O
            if stats['total_attempts'] % 10 == 0:
                self._save_stats()

    def record_response_time(self, feed_url, response_time):
        """Record the response time for a feed."""
        with self.lock:
            if feed_url in self.feed_stats:
                self.feed_stats[feed_url]['response_times'].append((time.time(), response_time))
                # Keep only last 10 response times
                self.feed_stats[feed_url]['response_times'] = self.feed_stats[feed_url]['response_times'][-10:]

    def is_healthy(self, feed_url):
        """Check if a feed is healthy based on its history."""
        with self.lock:
            if feed_url not in self.feed_stats:
                return True  # New feeds are considered healthy by default

            stats = self.feed_stats[feed_url]

            # Check success rate over the health window
            recent_attempts = sum(1 for t in stats['errors'] if time.time() - t[0] <= FEED_HEALTH_WINDOW)
            success_rate = (stats['successful_attempts'] / max(1, stats['total_attempts']))

            # Check consecutive failures
            if stats['consecutive_failures'] >= MAX_CONSECUTIVE_FAILURES:
                return False

            # Check overall success rate
            if success_rate < MIN_SUCCESS_RATE and stats['total_attempts'] > 5:
                return False

            return True

    def get_feed_status(self, feed_url):
        """Get detailed status information for a feed."""
        with self.lock:
            if feed_url not in self.feed_stats:
                return {
                    'status': 'unknown',
                    'success_rate': 0,
                    'consecutive_failures': 0,
                    'last_success': None,
                    'last_failure': None,
                    'recent_errors': [],
                    'avg_response_time': None
                }

            stats = self.feed_stats[feed_url]
            success_rate = (stats['successful_attempts'] / max(1, stats['total_attempts']))

            # Calculate average response time from the last 10 measurements
            avg_response_time = None
            if 'response_times' in stats and stats['response_times']:
                response_times = [rt[1] for rt in stats['response_times']]
                if response_times:
                    avg_response_time = sum(response_times) / len(response_times)

            return {
                'status': 'healthy' if self.is_healthy(feed_url) else 'unhealthy',
                'success_rate': success_rate,
                'consecutive_failures': stats['consecutive_failures'],
                'last_success': stats['last_success'],
                'last_failure': stats['last_failure'],
                'recent_errors': stats['errors'],
                'avg_response_time': avg_response_time
            }

class RateLimiter:
    def __init__(self):
        self.requests = {}
        self.last_request = {}
        self.lock = threading.RLock()

    def can_make_request(self, domain):
        """Check if a request can be made to the given domain."""
        with self.lock:
            current_time = time.time()

            # Check minimum interval between requests
            if domain in self.last_request:
                time_since_last = current_time - self.last_request[domain]
                if time_since_last < MIN_REQUEST_INTERVAL:
                    return False

            # Check rate limit window
            if domain in self.requests:
                window_start = current_time - RATE_LIMIT_WINDOW
                self.requests[domain] = [t for t in self.requests[domain] if t > window_start]
                if len(self.requests[domain]) >= RATE_LIMIT_REQUESTS:
                    return False

            return True

    def record_request(self, domain):
        """Record a request to the given domain."""
        with self.lock:
            current_time = time.time()
            if domain not in self.requests:
                self.requests[domain] = []
            self.requests[domain].append(current_time)
            self.last_request[domain] = current_time

# Create a global feed health monitor
feed_monitor = FeedHealthMonitor()

# Create a global rate limiter
rate_limiter = RateLimiter()

def get_random_proxy():
    """Get a random proxy from the proxy list."""
    if not PROXY_LIST:
        return None
    return random.choice(PROXY_LIST)

def get_browser(headless=True):
    """Get or create a browser instance for this thread."""
    # Use thread-local storage to keep browser instances separate
    if not hasattr(thread_local, 'browser'):
        # Acquire semaphore to limit concurrent browser instances
        browser_pool_semaphore.acquire()
        try:
            chrome_options = Options()
            if headless:
                chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")

            # Add random user agent
            user_agent = get_random_user_agent()
            chrome_options.add_argument(f"--user-agent={user_agent}")

            # Add language setting
            chrome_options.add_argument("--lang=en-US,en;q=0.9")

            # Disable automation flags
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            # Disable images to speed up loading
            chrome_options.add_experimental_option("prefs", {
                "profile.managed_default_content_settings.images": 2
            })

            browser = webdriver.Chrome(options=chrome_options)
            thread_local.browser = browser

            # Register this browser in the pool
            thread_id = threading.get_ident()
            browser_pool[thread_id] = browser

            return browser
        except Exception as e:
            browser_pool_semaphore.release()
            logging.error(f"Failed to create browser instance: {e}")
            raise

    return thread_local.browser

def close_browser():
    """Close the browser instance for this thread if it exists."""
    thread_id = threading.get_ident()
    if thread_id in browser_pool:
        try:
            if hasattr(thread_local, 'browser'):
                thread_local.browser.quit()
                delattr(thread_local, 'browser')
        except Exception as e:
            logging.error(f"Error closing browser: {e}")
        finally:
            # Remove from pool and release semaphore
            del browser_pool[thread_id]
            browser_pool_semaphore.release()

def create_session():
    """Create a requests session with appropriate settings."""
    session = requests.Session()

    # Configure retry strategy
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        backoff_factor=1
    )

    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=POOL_CONNECTIONS,
        pool_maxsize=POOL_MAXSIZE
    )

    session.mount('https://', adapter)
    session.mount('http://', adapter)

    # Set default timeout
    session.timeout = DEFAULT_TIMEOUT

    return session

def get_random_user_agent():
    """Get a random user agent string."""
    user_agents = [
        # Chrome on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",

        # Chrome on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",

        # Firefox on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:92.0) Gecko/20100101 Firefox/92.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:113.0) Gecko/20100101 Firefox/113.0",

        # Firefox on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:90.0) Gecko/20100101 Firefox/90.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:91.0) Gecko/20100101 Firefox/91.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:92.0) Gecko/20100101 Firefox/92.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:113.0) Gecko/20100101 Firefox/113.0",

        # Safari on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.2 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.3 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",

        # Edge on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36 Edg/92.0.902.78",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36 Edg/93.0.961.38",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36 Edg/94.0.992.47",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    ]
    return random.choice(user_agents)

def get_custom_headers(feed_url):
    """Generate appropriate headers based on the feed URL."""
    # Get random user agent
    user_agent = get_random_user_agent()

    # Base headers that work for most sites
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1"
    }

    # Add referer for specific domains that need it
    domain = urlparse(feed_url).netloc
    if "euractiv.com" in domain:
        headers.update({
            "Referer": "https://www.euractiv.com/",
            "Origin": "https://www.euractiv.com"
        })
    elif "ilo.org" in domain:
        headers.update({
            "Referer": "https://www.ilo.org/",
            "Origin": "https://www.ilo.org"
        })
    elif "reuters.com" in domain:
        headers.update({
            "Referer": "https://www.reuters.com/",
            "Origin": "https://www.reuters.com"
        })
    elif "bloomberg.com" in domain:
        headers.update({
            "Referer": "https://www.bloomberg.com/",
            "Origin": "https://www.bloomberg.com"
        })
    elif "ft.com" in domain:
        headers.update({
            "Referer": "https://www.ft.com/",
            "Origin": "https://www.ft.com"
        })
    elif "sueddeutsche.de" in domain or "sz.de" in domain:
        headers.update({
            "Referer": "https://www.sueddeutsche.de/",
            "Origin": "https://www.sueddeutsche.de"
        })
    elif "zeit.de" in domain:
        headers.update({
            "Referer": "https://www.zeit.de/",
            "Origin": "https://www.zeit.de"
        })
    elif "handelsblatt.com" in domain:
        headers.update({
            "Referer": "https://www.handelsblatt.com/",
            "Origin": "https://www.handelsblatt.com"
        })
    elif "nytimes.com" in domain:
        headers.update({
            "Referer": "https://www.nytimes.com/",
            "Origin": "https://www.nytimes.com"
        })
    elif "europa.eu" in domain or "ec.europa.eu" in domain or "europarl.europa.eu" in domain:
        headers.update({
            "Referer": "https://europa.eu/",
            "Origin": "https://europa.eu"
        })
    elif "nature.com" in domain:
        headers.update({
            "Referer": "https://www.nature.com/",
            "Origin": "https://www.nature.com"
        })
    elif "sciencedirect.com" in domain:
        headers.update({
            "Referer": "https://www.sciencedirect.com/",
            "Origin": "https://www.sciencedirect.com"
        })
    elif "wiley.com" in domain or "onlinelibrary.wiley.com" in domain:
        headers.update({
            "Referer": "https://onlinelibrary.wiley.com/",
            "Origin": "https://onlinelibrary.wiley.com"
        })
    elif "tandfonline.com" in domain:
        headers.update({
            "Referer": "https://www.tandfonline.com/",
            "Origin": "https://www.tandfonline.com"
        })
    elif "springer.com" in domain or "link.springer.com" in domain:
        headers.update({
            "Referer": "https://link.springer.com/",
            "Origin": "https://link.springer.com"
        })
    elif "cepr.org" in domain:
        headers.update({
            "Referer": "https://cepr.org/",
            "Origin": "https://cepr.org"
        })
    elif "arxiv.org" in domain:
        headers.update({
            "Referer": "https://arxiv.org/",
            "Origin": "https://arxiv.org"
        })
    elif "dw.com" in domain:
        headers.update({
            "Referer": "https://www.dw.com/",
            "Origin": "https://www.dw.com"
        })
    elif "climate.gov" in domain:
        headers.update({
            "Referer": "https://www.climate.gov/",
            "Origin": "https://www.climate.gov"
        })
    elif "bafin.de" in domain:
        headers.update({
            "Referer": "https://www.bafin.de/",
            "Origin": "https://www.bafin.de"
        })
    elif "hoganlovells.com" in domain:
        headers.update({
            "Referer": "https://www.hoganlovells.com/",
            "Origin": "https://www.hoganlovells.com"
        })
    elif "bundesbank.de" in domain:
        headers.update({
            "Referer": "https://www.bundesbank.de/",
            "Origin": "https://www.bundesbank.de"
        })
    elif "finma.ch" in domain:
        headers.update({
            "Referer": "https://www.finma.ch/",
            "Origin": "https://www.finma.ch"
        })
    elif "snb.ch" in domain:
        headers.update({
            "Referer": "https://www.snb.ch/",
            "Origin": "https://www.snb.ch"
        })
    elif "sec.gov" in domain:
        headers.update({
            "Referer": "https://www.sec.gov/",
            "Origin": "https://www.sec.gov"
        })
    elif "fca.org.uk" in domain:
        headers.update({
            "Referer": "https://www.fca.org.uk/",
            "Origin": "https://www.fca.org.uk"
        })
    elif "esma.europa.eu" in domain:
        headers.update({
            "Referer": "https://www.esma.europa.eu/",
            "Origin": "https://www.esma.europa.eu"
        })
    elif "ecb.europa.eu" in domain:
        headers.update({
            "Referer": "https://www.ecb.europa.eu/",
            "Origin": "https://www.ecb.europa.eu"
        })
    elif "esrb.europa.eu" in domain:
        headers.update({
            "Referer": "https://www.esrb.europa.eu/",
            "Origin": "https://www.esrb.europa.eu"
        })
    elif "eba.europa.eu" in domain:
        headers.update({
            "Referer": "https://www.eba.europa.eu/",
            "Origin": "https://www.eba.europa.eu"
        })
    elif "imf.org" in domain:
        headers.update({
            "Referer": "https://www.imf.org/",
            "Origin": "https://www.imf.org"
        })
    elif "panda.org" in domain:
        headers.update({
            "Referer": "https://www.panda.org/",
            "Origin": "https://www.panda.org"
        })
    elif "eurostat" in domain or "ec.europa.eu/eurostat" in domain:
        headers.update({
            "Referer": "https://ec.europa.eu/eurostat/",
            "Origin": "https://ec.europa.eu/eurostat"
        })

    # Some feeds require specific accept headers
    if feed_url.endswith('.xml') or '/rss/' in feed_url or '/feed/' in feed_url or 'atom' in feed_url:
        headers.update({
            "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.7"
        })

    return headers

def validate_feed_content(content):
    """Validate and sanitize feed content before parsing."""
    try:
        # Check content length
        if len(content) < 100:  # Minimum reasonable size for a feed
            logging.error("Feed content too short")
            return None

        # Check if content might be JSON Feed
        if content.strip().startswith(b'{'):
            import json
            try:
                json_data = json.loads(content)
                # Check if it's a JSON Feed
                if 'version' in json_data and json_data.get('version', '').startswith('https://jsonfeed.org/version/'):
                    logging.info("Detected JSON Feed format")
                    return content  # Valid JSON feed
            except json.JSONDecodeError:
                pass  # Not valid JSON, continue with XML validation

        # Check for gzipped content
        try:
            if content.startswith(b'\x1f\x8b\x08'):
                content = gzip.decompress(content)
                logging.info("Decompressed gzipped content")
        except Exception as e:
            logging.warning(f"Failed to decompress content: {e}")

        # Check for HTML with embedded RSS
        if b'<html' in content.lower() and (b'application/rss+xml' in content.lower() or b'application/atom+xml' in content.lower()):
            logging.warning("Received HTML page with embedded feed link instead of direct feed")
            # Parse HTML to find feed URL
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')
                feed_link = soup.find('link', type=lambda t: t and ('rss+xml' in t or 'atom+xml' in t))
                if feed_link and feed_link.get('href'):
                    logging.info(f"Found embedded feed link: {feed_link['href']}")
            except Exception as e:
                logging.error(f"Error parsing HTML for feed link: {e}")
            return None  # Return None to indicate need to fetch the actual feed URL

        # Detect encoding
        encoding_result = chardet.detect(content)
        encoding = encoding_result['encoding']
        if not encoding:
            logging.warning("Could not detect encoding, trying UTF-8")
            encoding = 'utf-8'

        try:
            content_str = content.decode(encoding)
        except UnicodeDecodeError:
            logging.warning(f"Failed to decode with {encoding}, trying UTF-8 with ignore")
            content_str = content.decode('utf-8', errors='ignore')

        # Basic XML validation
        try:
            root = ET.fromstring(content_str)
        except ET.ParseError as e:
            logging.error(f"Invalid XML content in feed: {e}")

            # Try cleaning the XML
            try:
                # Remove problematic characters
                cleaned_content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', content_str)
                # Try parsing again
                root = ET.fromstring(cleaned_content)
                content_str = cleaned_content
                logging.info("Successfully cleaned and parsed XML content")
            except ET.ParseError:
                # Still failed, return None
                return None

        # Check for common feed formats
        if root.tag.endswith('rss') or root.tag.endswith('feed') or root.tag.endswith('RDF') or 'RDF' in root.tag or root.tag.endswith('opml'):
            # RSS 2.0 format
            if root.tag.endswith('rss'):
                channel = root.find('channel')
                if channel is None:
                    logging.error("RSS feed missing channel element")
                    return None
                if channel.find('title') is None:
                    logging.error("RSS feed missing title element")
                    return None

                # Check for Media RSS extensions
                media_ns = '{http://search.yahoo.com/mrss/}'
                if any(media_ns in elem.tag for elem in root.iter()):
                    logging.info("Detected Media RSS extensions")

                logging.info("Validated RSS 2.0 format")
                return content_str

            # RDF-based RSS 1.0
            elif 'RDF' in root.tag:
                # Find channel element with various namespace possibilities
                namespaces = [
                    '{http://purl.org/rss/1.0/}',
                    '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}',
                    ''  # No namespace
                ]

                channel_found = False
                for ns in namespaces:
                    channel = root.find(f'.//{ns}channel')
                    if channel is not None:
                        channel_found = True
                        break

                if not channel_found:
                    logging.warning("RDF feed with unusual structure, proceeding anyway")

                logging.info("Validated RDF-based RSS 1.0 format")
                return content_str

            # OPML format
            elif root.tag.endswith('opml'):
                # Basic OPML validation
                head = root.find('head')
                body = root.find('body')
                if body is None:
                    logging.error("OPML feed missing body element")
                    return None
                logging.info("Detected OPML format")
                return content_str

            # Atom feed
            else:
                if root.find('title') is None and root.find('.//{http://www.w3.org/2005/Atom}title') is None:
                    logging.error("Atom feed missing title element")
                    return None

                logging.info("Validated Atom feed format")
                return content_str
        else:
            logging.error(f"Feed is not in a recognized format. Root tag: {root.tag}")
            return None

    except Exception as e:
        logging.error(f"Error validating feed content: {e}")
        return None

def sanitize_feed_url(url):
    """Sanitize and validate feed URL."""
    try:
        parsed = urlparse(url)
        if not parsed.scheme:
            url = 'https://' + url
        parsed = urlparse(url)  # Re-parse with possibly added scheme
        if not parsed.netloc:
            logging.error(f"Invalid feed URL: {url}")
            return None
        return url
    except Exception as e:
        logging.error(f"Error sanitizing feed URL {url}: {e}")
        return None

def fetch_with_browser(url, timeout=BROWSER_TIMEOUT):
    """Fetch content using browser automation."""
    if not SELENIUM_SUPPORT:
        logging.error("Selenium not installed. Cannot use browser automation.")
        return None

    try:
        browser = get_browser()
        browser.set_page_load_timeout(timeout)

        logging.info(f"Fetching {url} with browser automation")
        browser.get(url)

        # Wait for page to load
        WebDriverWait(browser, timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Check for RSS/Atom content
        content_type = browser.execute_script("return document.contentType")
        if content_type and ('xml' in content_type or 'rss' in content_type or 'atom' in content_type):
            return browser.page_source

        # Check for RSS link in HTML
        feed_links = browser.find_elements(By.XPATH, "//link[@type='application/rss+xml' or @type='application/atom+xml']")
        if feed_links:
            feed_url = feed_links[0].get_attribute('href')
            logging.info(f"Found feed URL in HTML: {feed_url}")

            # Navigate to the feed URL
            browser.get(feed_url)
            return browser.page_source

        # If we got HTML but no feed links, just return the HTML
        return browser.page_source

    except TimeoutException:
        logging.error(f"Timeout while fetching {url} with browser")
        return None
    except WebDriverException as e:
        logging.error(f"WebDriver error while fetching {url}: {e}")
        return None
    except Exception as e:
        logging.error(f"Error fetching {url} with browser: {e}")
        return None

def bypass_cloudflare(url):
    """Attempt to bypass Cloudflare protection."""
    if not SELENIUM_SUPPORT:
        logging.error("Selenium not installed. Cannot bypass Cloudflare.")
        return None

    try:
        browser = get_browser(headless=False)  # Sometimes headless mode is detected
        browser.set_page_load_timeout(BROWSER_TIMEOUT * 2)  # Longer timeout for Cloudflare challenges

        logging.info(f"Attempting to bypass Cloudflare for {url}")
        browser.get(url)

        # Wait for Cloudflare challenge to pass (if present)
        try:
            WebDriverWait(browser, 10).until(
                EC.presence_of_element_located((By.ID, "challenge-running"))
            )
            logging.info("Cloudflare challenge detected, waiting for it to complete")

            # Wait longer for the challenge to complete
            WebDriverWait(browser, 30).until_not(
                EC.presence_of_element_located((By.ID, "challenge-running"))
            )
        except TimeoutException:
            # No challenge or it passed quickly
            pass

        # Wait for the page to fully load
        WebDriverWait(browser, BROWSER_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Get cookies to use with requests
        cookies = {cookie['name']: cookie['value'] for cookie in browser.get_cookies()}

        # Get page source
        content = browser.page_source

        # Return both content and cookies for future requests
        return {
            'content': content,
            'cookies': cookies
        }

    except Exception as e:
        logging.error(f"Error bypassing Cloudflare for {url}: {e}")
        return None

def fetch_feed_with_retry(feed_url):
    """Fetch a single RSS feed with retry logic."""
    # Sanitize URL first
    feed_url = sanitize_feed_url(feed_url)
    if not feed_url:
        feed_monitor.record_fetch(feed_url, False, "Invalid URL")
        return None

    # Check circuit breaker
    if not circuit_breaker.can_execute(feed_url):
        logging.warning(f"Circuit breaker open for feed: {feed_url}")
        feed_monitor.record_fetch(feed_url, False, "Circuit breaker open")
        return None

    # Get domain for rate limiting
    domain = urlparse(feed_url).netloc

    # Check rate limit
    while not rate_limiter.can_make_request(domain):
        time.sleep(1)  # Wait until we can make a request

    # Record the request
    rate_limiter.record_request(domain)

    # Check feed health
    if not feed_monitor.is_healthy(feed_url):
        logging.warning(f"Skipping unhealthy feed: {feed_url}")
        return None

    # Check if this feed has been problematic recently
    if feed_url in problematic_feeds:
        last_failure, failure_count = problematic_feeds[feed_url]
        current_time = time.time()

        # If feed has failed repeatedly and recently, skip it
        if failure_count >= 3 and (current_time - last_failure) < 3600:  # 1 hour cooling period
            logging.warning(f"Skipping recently problematic feed: {feed_url} (failed {failure_count} times)")
            feed_monitor.record_fetch(feed_url, False, f"Multiple failures ({failure_count})")
            return None

    # Create a session for better connection handling
    session = create_session()

    # Try different header combinations if we get 403
    header_combinations = [
        lambda: get_custom_headers(feed_url),  # Original headers
        lambda: {**get_custom_headers(feed_url), "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8"},  # RSS-specific accept
        lambda: {**get_custom_headers(feed_url), "Accept": "*/*"},  # Accept anything
        lambda: {**get_custom_headers(feed_url), "Accept": "application/xml,application/xhtml+xml,text/xml;q=0.9,*/*;q=0.8"},  # XML-specific accept
        lambda: {**get_custom_headers(feed_url), "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "X-Requested-With": "XMLHttpRequest"},  # AJAX-like request
    ]

    # Track if we've already tried browser automation
    browser_tried = False
    cloudflare_tried = False
    cloudflare_cookies = None

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            # If we've had multiple failures, try browser automation
            if attempt > 2 and USE_BROWSER_AUTOMATION and not browser_tried:
                browser_tried = True
                logging.info(f"Trying browser automation for feed: {feed_url}")
                content = fetch_with_browser(feed_url)
                if content:
                    # Validate feed content
                    processed_content = validate_feed_content(content.encode('utf-8') if isinstance(content, str) else content)
                    if processed_content:
                        circuit_breaker.record_success(feed_url)
                        feed_monitor.record_fetch(feed_url, True)
                        # If feed was previously problematic but now succeeded, reset its status
                        if feed_url in problematic_feeds:
                            del problematic_feeds[feed_url]
                        return processed_content

            # If we suspect Cloudflare protection and haven't tried bypassing it yet
            if attempt > 3 and USE_BROWSER_AUTOMATION and not cloudflare_tried and ('cloudflare' in feed_url.lower() or any('cloudflare' in str(e).lower() for e in problematic_feeds.get(feed_url, []))):
                cloudflare_tried = True
                logging.info(f"Trying to bypass Cloudflare protection for feed: {feed_url}")
                cf_result = bypass_cloudflare(feed_url)
                if cf_result:
                    cloudflare_cookies = cf_result['cookies']
                    content = cf_result['content']
                    processed_content = validate_feed_content(content.encode('utf-8') if isinstance(content, str) else content)
                    if processed_content:
                        circuit_breaker.record_success(feed_url)
                        feed_monitor.record_fetch(feed_url, True)
                        if feed_url in problematic_feeds:
                            del problematic_feeds[feed_url]
                        return processed_content

            # Try each header combination
            for header_func in header_combinations:
                try:
                    headers = header_func()

                    # Add Cloudflare cookies if we have them
                    cookies = None
                    if cloudflare_cookies:
                        cookies = cloudflare_cookies

                    # Get proxy if enabled
                    proxies = None
                    if USE_PROXIES:
                        proxy = get_random_proxy()
                        if proxy:
                            proxies = {
                                "http": proxy,
                                "https": proxy
                            }

                    logging.info(f"Fetching feed (attempt {attempt}/{RETRY_ATTEMPTS}) with headers: {headers}")
                    print(f"Fetching feed (attempt {attempt}/{RETRY_ATTEMPTS})")

                    # Measure response time
                    start_time = time.time()

                    response = session.get(
                        feed_url,
                        headers=headers,
                        timeout=EXTENDED_TIMEOUT,
                        verify=VERIFY_SSL,
                        cookies=cookies,
                        proxies=proxies,
                        allow_redirects=True
                    )

                    # Calculate response time
                    response_time = time.time() - start_time
                    feed_monitor.record_response_time(feed_url, response_time)

                    response.raise_for_status()

                    # Log response info
                    logging.info(f"Response status: {response.status_code}, Content-Type: {response.headers.get('Content-Type', 'unknown')}")

                    # Validate feed content
                    content = validate_feed_content(response.content)
                    if not content:
                        raise ValueError("Invalid feed content")

                    # If feed was previously problematic but now succeeded, reset its status
                    if feed_url in problematic_feeds:
                        del problematic_feeds[feed_url]

                    circuit_breaker.record_success(feed_url)
                    feed_monitor.record_fetch(feed_url, True)
                    return content

                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 403:
                        logging.warning(f"403 Forbidden with headers: {headers}")
                        continue  # Try next header combination
                    raise  # Re-raise other HTTP errors

        except requests.exceptions.Timeout:
            delay = BASE_DELAY * (2 ** (attempt - 1))  # Exponential backoff
            logging.warning(f"Timeout for feed {feed_url} on attempt {attempt}/{RETRY_ATTEMPTS}. Retrying in {delay}s...")
            print(f"Timeout for feed {feed_url}. Retrying in {delay}s...")
            time.sleep(delay)
            feed_monitor.record_fetch(feed_url, False, "Timeout")
            circuit_breaker.record_failure(feed_url)

        except requests.exceptions.RequestException as e:
            # Update the problematic feeds tracker
            current_time = time.time()
            if feed_url in problematic_feeds:
                _, failure_count = problematic_feeds[feed_url]
                problematic_feeds[feed_url] = (current_time, failure_count + 1)
            else:
                problematic_feeds[feed_url] = (current_time, 1)

            circuit_breaker.record_failure(feed_url)

            if isinstance(e, requests.exceptions.HTTPError) and hasattr(e, 'response'):
                status_code = e.response.status_code
                if status_code == 404:
                    logging.error(f"Feed not found (404): {feed_url}")
                    print(f"Feed not found (404): {feed_url}")
                    feed_monitor.record_fetch(feed_url, False, f"HTTP 404")
                    return None
                elif status_code == 403:
                    logging.error(f"Access forbidden (403) for feed: {feed_url}")
                    print(f"Access forbidden (403) for feed: {feed_url}")
                    feed_monitor.record_fetch(feed_url, False, f"HTTP 403")
                    if attempt > 1:
                        return None
                else:
                    logging.error(f"HTTP error {status_code} for feed {feed_url}: {e}")
                    print(f"HTTP error {status_code} for feed {feed_url}")
                    feed_monitor.record_fetch(feed_url, False, f"HTTP {status_code}")
            else:
                logging.error(f"Error fetching feed {feed_url}: {e}")
                print(f"Error fetching feed {feed_url}")
                feed_monitor.record_fetch(feed_url, False, str(e))

            if attempt < RETRY_ATTEMPTS:
                delay = BASE_DELAY * (2 ** (attempt - 1))  # Exponential backoff
                logging.info(f"Retrying in {delay}s... (Attempt {attempt}/{RETRY_ATTEMPTS})")
                print(f"Retrying in {delay}s... (Attempt {attempt}/{RETRY_ATTEMPTS})")
                time.sleep(delay)

    # If we get here, all retries failed
    logging.error(f"Failed to fetch feed after {RETRY_ATTEMPTS} attempts: {feed_url}")
    print(f"Failed to fetch feed after {RETRY_ATTEMPTS} attempts: {feed_url}")
    feed_monitor.record_fetch(feed_url, False, f"Failed after {RETRY_ATTEMPTS} attempts")
    return None

def extract_full_content(url, entry):
    """Extract full article content from the URL."""
    if not EXTRACT_FULL_CONTENT:
        return None

    logging.info(f"Extracting full content for: {url}")

    try:
        # Try using newspaper3k if available
        if NEWSPAPER_SUPPORT:
            # Configure newspaper
            config = NewsConfig()
            config.browser_user_agent = get_random_user_agent()
            config.request_timeout = DEFAULT_TIMEOUT

            article = NewsArticle(url, config=config)
            article.download()
            article.parse()

            if article.text and len(article.text) > 100:
                return {
                    'text': article.text,
                    'title': article.title,
                    'authors': article.authors,
                    'publish_date': article.publish_date,
                    'top_image': article.top_image,
                    'images': list(article.images),
                    'movies': list(article.movies),
                    'source': 'newspaper3k'
                }

        # Fallback to custom implementation
        session = create_session()
        headers = get_custom_headers(url)

        response = session.get(url, headers=headers, timeout=DEFAULT_TIMEOUT, verify=VERIFY_SSL)
        response.raise_for_status()

        # Check content size
        if len(response.content) > MAX_CONTENT_SIZE:
            logging.warning(f"Content too large: {len(response.content)} bytes")
            return None

        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')

        # Try to extract main content
        main_content = None

        # Look for article content
        for selector in [
            'article',
            '[role="main"]',
            '.post-content',
            '.entry-content',
            '.article-content',
            '.content-article',
            '.article-body',
            '.story-body',
            '#main-content',
            '.main-content'
        ]:
            content = soup.select(selector)
            if content:
                main_content = content[0]
                break

        # If no main content found, use body
        if main_content is None:
            main_content = soup.body

        # Extract text
        if main_content:
            # Remove unwanted elements
            for unwanted in main_content.select('nav, footer, aside, .sidebar, .comments, .related, .advertisement, script, style'):
                unwanted.decompose()

            text = main_content.get_text(separator='\n', strip=True)

            # Get images
            images = []
            for img in main_content.find_all('img', src=True):
                src = img['src']
                # Make relative URLs absolute
                if not src.startswith(('http:', 'https:')):
                    src = urljoin(url, src)
                images.append(src)

            return {
                'text': text,
                'images': images,
                'source': 'custom'
            }

        return None

    except Exception as e:
        logging.error(f"Error extracting full content from {url}: {e}")
        logging.error(traceback.format_exc()) #lowered from debug to error
        return None

def process_attachments(entry):
    """Process attachments in an entry, including PDFs."""
    if not PROCESS_ATTACHMENTS or not PDF_SUPPORT:
        return None

    attachments = []

    try:
        # Check for enclosures
        if hasattr(entry, 'enclosures') and entry.enclosures:
            for enclosure in entry.enclosures:
                if not hasattr(enclosure, 'type') or not hasattr(enclosure, 'href'):
                    continue

                mime_type = enclosure.type
                url = enclosure.href

                # Process PDFs
                if mime_type == 'application/pdf' or url.lower().endswith('.pdf'):
                    logging.info(f"Found PDF attachment: {url}")
                    try:
                        # Download the PDF
                        session = create_session()
                        response = session.get(url, timeout=DEFAULT_TIMEOUT, verify=VERIFY_SSL)
                        response.raise_for_status()

                        # Parse the PDF
                        try:
                            pdf_file = BytesIO(response.content)
                            pdf_reader = PdfReader(pdf_file)
                            text = ""
                            for page in pdf_reader.pages:
                                text += page.extract_text() + "\n"

                            if text:
                                attachments.append({
                                    'type': 'pdf',
                                    'url': url,
                                    'text': text,
                                    'pages': len(pdf_reader.pages)
                                })
                        except Exception as e:
                            logging.error(f"Error parsing PDF: {e}")

                    except Exception as e:
                        logging.error(f"Error downloading PDF: {e}")

                # Other attachment types
                else:
                    attachments.append({
                        'type': mime_type,
                        'url': url
                    })

        # Check for links that might be PDFs
        if hasattr(entry, 'links'):
            for link in entry.links:
                if hasattr(link, 'href') and hasattr(link, 'type'):
                    url = link.href
                    mime_type = link.type

                    # Skip if already processed as enclosure
                    if any(a.get('url') == url for a in attachments):
                        continue

                    # Process PDFs
                    if mime_type == 'application/pdf' or url.lower().endswith('.pdf'):
                        logging.info(f"Found PDF link: {url}")
                        try:
                            # Download the PDF
                            session = create_session()
                            response = session.get(url, timeout=DEFAULT_TIMEOUT, verify=VERIFY_SSL)
                            response.raise_for_status()

                            # Parse the PDF
                            try:
                                pdf_file = BytesIO(response.content)
                                pdf_reader = PdfReader(pdf_file)
                                text = ""
                                for page in pdf_reader.pages:
                                    text += page.extract_text() + "\n"

                                if text:
                                    attachments.append({
                                        'type': 'pdf',
                                        'url': url,
                                        'text': text,
                                        'pages': len(pdf_reader.pages)
                                    })
                            except Exception as e:
                                logging.error(f"Error parsing PDF: {e}")

                        except Exception as e:
                            logging.error(f"Error downloading PDF: {e}")

    except Exception as e:
        logging.error(f"Error processing attachments: {e}")

    return attachments if attachments else None

def fetch_rss_entries():
    """Fetch and parse RSS feeds, filtering for last 24 hours."""
    logging.info("Fetching RSS feeds...")
    print("Fetching RSS feeds...")
    entries = []
    now = time.time()
    unique_article_ids = set()

    # Group feeds by domain to avoid hammering the same server
    domain_grouped_feeds = {}
    for feed_url in RSS_FEEDS:
        domain = re.sub(r'^https?://', '', feed_url).split('/')[0]
        if domain not in domain_grouped_feeds:
            domain_grouped_feeds[domain] = []
        domain_grouped_feeds[domain].append(feed_url)

    # Process feeds by domain with delays between domains
    for domain, feeds in domain_grouped_feeds.items():
        logging.info(f"Processing {len(feeds)} feeds from domain: {domain}")
        print(f"Processing {len(feeds)} feeds from domain: {domain}")

        # Add delay between domains
        time.sleep(3)

        for feed_url in feeds:
            try:
                feed_content = fetch_feed_with_retry(feed_url)

                if not feed_content:
                    continue  # Skip to next feed if fetch failed

                # Handle JSON Feed format
                if isinstance(feed_content, bytes) and feed_content.strip().startswith(b'{'):
                    try:
                        json_feed = json.loads(feed_content)
                        if 'version' in json_feed and json_feed.get('version', '').startswith('https://jsonfeed.org/version/'):
                            # Convert JSON Feed to feedparser-compatible format
                            feed = {
                                'feed': {
                                    'title': json_feed.get('title', ''),
                                    'link': json_feed.get('home_page_url', '')
                                },
                                'entries': []
                            }

                            for item in json_feed.get('items', []):
                                entry = {
                                    'title': item.get('title', ''),
                                    'link': item.get('url', ''),
                                    'description': item.get('content_text', item.get('content_html', '')),
                                    'id': item.get('id', ''),
                                    'published': item.get('date_published', ''),
                                    'updated': item.get('date_modified', '')
                                }

                                # Convert timestamps to feedparser format if possible
                                if entry['published']:
                                    try:
                                        dt = datetime.fromisoformat(entry['published'].replace('Z', '+00:00'))
                                        entry['published_parsed'] = dt.timetuple()
                                    except (ValueError, AttributeError):
                                        pass

                                if entry['updated']:
                                    try:
                                        dt = datetime.fromisoformat(entry['updated'].replace('Z', '+00:00'))
                                        entry['updated_parsed'] = dt.timetuple()
                                    except (ValueError, AttributeError):
                                        pass

                                # Add attachments if present
                                if 'attachments' in item:
                                    entry['enclosures'] = []
                                    for attachment in item['attachments']:
                                        entry['enclosures'].append({
                                            'href': attachment.get('url', ''),
                                            'type': attachment.get('mime_type', ''),
                                            'length': attachment.get('size_in_bytes', 0)
                                        })

                                # Add author info
                                if 'author' in item:
                                    entry['author'] = item['author'].get('name', '')

                                # Add tags/categories
                                if 'tags' in item:
                                    entry['tags'] = [{'term': tag} for tag in item['tags']]

                                feed['entries'].append(entry)
                    except Exception as e:
                        logging.error(f"Error parsing JSON Feed: {e}")
                        continue
                else:
                    # Parse regular RSS/Atom feed
                    feed = feedparser.parse(feed_content)

                # Get feed title for source info
                feed_title = feed.get('feed', {}).get('title', get_domain_from_url(feed_url))

                for entry in feed.entries:
                    published_time = None

                    # Try multiple date fields with fallbacks
                    if 'published_parsed' in entry and entry.published_parsed:
                        published_time = time.mktime(entry.published_parsed)
                    elif 'updated_parsed' in entry and entry.updated_parsed:
                        published_time = time.mktime(entry.updated_parsed)
                    elif 'created_parsed' in entry and entry.created_parsed:
                        published_time = time.mktime(entry.created_parsed)
                    else:
                        # Try parsing date from string fields
                        date_fields = ['published', 'updated', 'created', 'date']
                        parsed_date = None

                        for field in date_fields:
                            if field in entry and entry[field]:
                                try:
                                    # Try different date formats
                                    date_formats = [
                                        '%a, %d %b %Y %H:%M:%S %z',  # RFC 822
                                        '%a, %d %b %Y %H:%M:%S %Z',  # RFC 822 with timezone name
                                        '%Y-%m-%dT%H:%M:%S%z',       # ISO 8601
                                        '%Y-%m-%dT%H:%M:%SZ',        # ISO 8601 UTC
                                        '%Y-%m-%dT%H:%M:%S',         # ISO 8601 without timezone
                                        '%Y-%m-%d %H:%M:%S',         # Simple datetime
                                        '%Y-%m-%d',                  # Simple date
                                    ]

                                    for fmt in date_formats:
                                        try:
                                            parsed_date = datetime.strptime(entry[field], fmt)
                                            break
                                        except ValueError:
                                            continue

                                    if parsed_date:
                                        published_time = time.mktime(parsed_date.timetuple())
                                        break

                                except Exception as e:
                                    logging.error(f"Failed to parse date from {field}: {e}") #lowered from debug to error

                        if not published_time:
                            logging.warning(f"No timestamp found for article: {entry.get('title', 'No Title')}. Using current time.")
                            published_time = now  # Use current time as fallback

                    # Keep articles within the past 24 hours
                    if (now - published_time) <= TIME_THRESHOLD:
                        # Generate a unique ID for this article
                        title = entry.get("title", "").strip()
                        link = entry.get("link", "").strip()
                        article_id = generate_article_id(title, link)

                        # Only add if we haven't seen this article before
                        if article_id not in unique_article_ids:
                            unique_article_ids.add(article_id)
                            # Add article ID and source info to the entry for later reference
                            entry['article_id'] = article_id
                            entry['source_info'] = {
                                'title': feed_title,
                                'url': feed_url,
                                'domain': get_domain_from_url(feed_url)
                            }
                            entries.append(entry)

                logging.info(f"Fetched from feed: {feed_url}")
                print(f"Fetched from feed: {feed_url}")

                # Add delay between feeds
                time.sleep(2)

            except Exception as e:
                logging.error(f"Unexpected error processing feed {feed_url}: {e}")
                print(f"Unexpected error processing feed {feed_url}: {e}")

    logging.info(f"Total unique articles fetched within 24 hours: {len(entries)}")
    print(f"Total unique articles fetched within 24 hours: {len(entries)}")
    return entries

def filter_rss_entries(entries):
    """Filter and process RSS entries based on keyword matches and exclusions."""
    logging.info("Filtering relevant RSS entries...")
    print("Filtering relevant RSS entries...")
    filtered_entries = []
    keyword_counts = Counter()

    # Use a ThreadPoolExecutor for parallel processing of entries
    with ThreadPoolExecutor(max_workers=30) as executor: #increase max_workers to 30 from 10 for more parallel processing
        # Submit tasks for content extraction
        future_to_entry = {}
        for entry in entries:
            future = executor.submit(process_entry, entry)
            future_to_entry[future] = entry

        # Process results as they complete
        for future in as_completed(future_to_entry):
            entry = future_to_entry[future]
            try:
                result = future.result()
                if result:
                    filtered_entry, matched_keywords, keyword_scores = result
                    filtered_entries.append(filtered_entry)

                    # Update keyword counts
                    for kw in matched_keywords:
                        keyword_counts[kw] += keyword_scores[kw]
            except Exception as e:
                logging.error(f"Error processing entry {entry.get('title', 'Unknown')}: {e}")
                traceback.print_exc()

    # Close any browser instances
    for thread_id, browser in list(browser_pool.items()):
        try:
            browser.quit()
        except:
            pass

    logging.info(f"Filtered relevant RSS articles: {len(filtered_entries)}")
    print(f"Filtered relevant RSS articles: {len(filtered_entries)}")
    return filtered_entries, keyword_counts

def process_entry(entry):
    """Process a single RSS entry."""
    try:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        description = entry.get("description", "").strip()
        source_info = entry.get("source_info", {})

        # Skip entries with missing required fields
        if not title or not link:
            logging.warning(f"Skipping entry with missing required fields: {title or 'No Title'}")
            return None

        # Extract content from various possible fields
        content_fields = [
            description,
            entry.get("content", [{}])[0].get("value", "") if isinstance(entry.get("content", []), list) and len(entry.get("content", [])) > 0 else "",
            entry.get("summary", ""),
            entry.get("summary_detail", {}).get("value", "")
        ]

        # Combine all content fields and clean HTML
        full_text = " ".join(filter(None, content_fields))
        soup = BeautifulSoup(full_text, "html.parser")
        full_text = soup.get_text(separator=" ", strip=True)

        # Extract full content if enabled
        full_content = None
        if EXTRACT_FULL_CONTENT and link:
            full_content = extract_full_content(link, entry)
            if full_content and full_content.get('text'):
                full_text += " " + full_content.get('text')

        # Process attachments
        attachments = process_attachments(entry)

        # Normalize text for keyword matching
        full_text_normalized = normalize_text(full_text)
        title_normalized = normalize_text(title)

        # Add spaces at beginning and end for word boundary checks
        padded_text = " " + full_text_normalized + " "
        padded_title = " " + title_normalized + " "

        # Check for keyword matches with weighted scoring
        matched_keywords = []
        keyword_scores = {}

        for kw in KEYWORDS:
            kw_normalized = normalize_text(kw)
            score = 0

            # Title matches are worth more
            if kw.startswith(" ") or kw.endswith(" "):
                if kw_normalized in padded_title:
                    score += 5  # Increased weight for title matches
                if kw_normalized in padded_text:
                    score += 1
            else:
                if kw_normalized in title_normalized:
                    score += 5  # Increased weight for title matches
                if kw_normalized in full_text_normalized:
                    score += 1

            # Bonus score for multiple occurrences
            if score > 0:
                # Count occurrences (with word boundaries for exact matches)
                if kw.startswith(" ") or kw.endswith(" "):
                    title_count = padded_title.count(kw_normalized)
                    text_count = padded_text.count(kw_normalized)
                else:
                    title_count = title_normalized.count(kw_normalized)
                    text_count = full_text_normalized.count(kw_normalized)

                # Add bonus for multiple occurrences
                if title_count > 1:
                    score += min(title_count - 1, 3) * 2  # Up to 3 bonus points for title
                if text_count > 2:
                    score += min(text_count - 2, 5)  # Up to 5 bonus points for text

                matched_keywords.append(kw)
                keyword_scores[kw] = score

        # Check for negative keywords
        excluded_keywords = []
        for kw in NEGATIVE_KEYWORDS:
            kw_normalized = normalize_text(kw)
            if (kw.startswith(" ") or kw.endswith(" ")) and kw_normalized in padded_text:
                excluded_keywords.append(kw)
            elif kw_normalized in full_text_normalized:
                excluded_keywords.append(kw)

        if matched_keywords and not excluded_keywords:
            # Extract snippet with improved formatting
            snippet = " ".join(full_text.split()[:150]) + "..." if len(full_text.split()) > 150 else full_text

            # Extract image with improved fallback chain
            image_url = None
            if full_content and 'images' in full_content and full_content['images']:
                image_url = full_content['images'][0]
            elif 'media_content' in entry and entry.media_content:
                for media in entry.media_content:
                    if 'url' in media and media.get('type', '').startswith('image/'):
                        image_url = media['url']
                        break
            elif 'enclosures' in entry and entry.enclosures:
                for enclosure in entry.enclosures:
                    if 'url' in enclosure and enclosure.get('type', '').startswith('image/'):
                        image_url = enclosure['url']
                        break
            elif 'links' in entry:
                for link_item in entry.links:
                    if link_item.get('type', '').startswith('image/'):
                        image_url = link_item.get('href')
                        break

            # Extract or generate publish date
            pub_date = entry.get('published', entry.get('updated', ''))
            if not pub_date and 'published_parsed' in entry and entry.published_parsed:
                pub_date = time.strftime('%Y-%m-%d %H:%M:%S', entry.published_parsed)
            elif not pub_date and 'updated_parsed' in entry and entry.updated_parsed:
                pub_date = time.strftime('%Y-%m-%d %H:%M:%S', entry.updated_parsed)

            # Extract author information
            author = entry.get('author', '')
            if not author and full_content and 'authors' in full_content and full_content['authors']:
                author = ', '.join(full_content['authors'])

            # Extract categories/tags
            categories = []
            if 'tags' in entry:
                categories = [tag.get('term', tag.get('label', '')) for tag in entry.tags if tag.get('term') or tag.get('label')]
            elif 'categories' in entry:
                categories = entry.categories

            # Store article data with additional metadata
            filtered_entry = {
                "title": title,
                "link": link,
                "snippet": snippet,
                "keywords": matched_keywords,
                "keyword_scores": keyword_scores,
                "article_id": entry.get('article_id'),
                "source_type": "rss",
                "source_info": source_info,
                "image_url": image_url,
                "pub_date": pub_date,
                "author": author,
                "categories": categories,
                "content_length": len(full_text),
                "full_content": full_content['text'] if full_content and 'text' in full_content else None,
                "attachments": attachments
            }

            return filtered_entry, matched_keywords, keyword_scores
        elif excluded_keywords:
            logging.info(f"Excluded article due to negative keyword match: {title}")
            return None

    except Exception as e:
        logging.error(f"Error processing entry: {e}", exc_info=True)
        return None

def process_rss_feeds():
    """Main function to process RSS feeds."""
    try:
        entries = fetch_rss_entries()
        if not entries:
            logging.warning("No RSS articles found within the last 24 hours.")
            print("No RSS articles found within the last 24 hours.")
            return [], Counter()

        filtered_articles, keyword_counts = filter_rss_entries(entries)
        return filtered_articles, keyword_counts
    except Exception as e:
        logging.error(f"Error processing RSS feeds: {e}", exc_info=True)
        print(f"Error processing RSS feeds: {e}")
        return [], Counter()

# If script is run directly
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("rss_processor.log"),
            logging.StreamHandler()
        ]
    )

    # Process feeds
    articles, keywords = process_rss_feeds()

    # Print results
    print(f"Total articles found: {len(articles)}")
    print(f"Top keywords: {keywords.most_common(10)}")

    # Clean up
    for thread_id, browser in list(browser_pool.items()):
        try:
            browser.quit()
        except:
            pass