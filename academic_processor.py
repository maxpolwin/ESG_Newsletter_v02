#!/usr/bin/env python3
"""
Semantic Scholar API Integration for Newsletter System

This module fetches academic publications related to tracked keywords
using the Semantic Scholar API.

Author: Max Polwin
"""

import requests
import logging
import datetime
import time
import sys
import os
from collections import Counter
import PyPDF2
from mistral import MistralAPI  # Ensure this import is at the top of your file


# Import configuration
from config import KEYWORDS

# Base URL for Semantic Scholar API
SEMANTIC_SCHOLAR_API_BASE = "https://api.semanticscholar.org/graph/v1"

# We're using post-filtering to get only recent papers, so we need to look at more papers
MAX_RESULTS_TO_FETCH = 200

# Maximum number of papers per keyword to return after filtering
MAX_PAPERS_PER_KEYWORD = 10

# New approach: distribute API calls over a 60-minute period
TOTAL_TIME_MINUTES = 0.5  # Total time period in minutes . changed from 60 to 0.5
TOTAL_TIME_SECONDS = TOTAL_TIME_MINUTES * 60  # Convert to seconds

# Safety parameters for API fair use
MIN_SECONDS_BETWEEN_CALLS = 20  # Minimum seconds between calls to respect API limits
SAFETY_FACTOR = 3  # Additional safety margin for timing
MAX_CALLS_PER_MINUTE = 121  # Conservative maximum call rate

# We'll dynamically calculate the delay in the process_academic_papers function
# based on the actual number of keywords to process
RATE_LIMIT_DELAY = None  # Will be set dynamically

# Tracking variables for API call timing
api_call_times = []  # List to store the duration of each API call

# Global variable to track the last Perplexity API call time for rate limiting
last_perplexity_api_call = 0
MIN_SECONDS_BETWEEN_PERPLEXITY_CALLS = 2.0  # Conservative rate limit

# Debug level control
# 0 = minimal output, 1 = basic info, 2 = detailed info, 3 = full debugging (no API responses)
DEBUG_LEVEL = 2

def debug_print(message, level=1):
    """Print debug messages based on current debug level."""
    if DEBUG_LEVEL >= level:
        print(message)

def ensure_int(value, default=0):
    """
    Safely convert a value to integer.

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        int: Converted integer value
    """
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def ensure_str(value, default=""):
    """
    Safely convert a value to string.

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        str: Converted string value
    """
    if value is None:
        return default
    try:
        return str(value)
    except (ValueError, TypeError):
        return default




def generate_fallback_abstract(paper):
    """Generate a more sophisticated fallback abstract when API calls fail."""
    # Extract metadata
    title = ensure_str(paper.get("title", ""))
    authors = ensure_str(paper.get("authors_formatted", ""))
    year = ensure_str(paper.get("year", ""))
    fields = paper.get("fieldsOfStudy", [])
    venue = ensure_str(paper.get("venue", ""))
    citations = ensure_int(paper.get("citationCount", 0))

    # Format first author
    first_author = authors.split(',')[0] if authors else "The authors"

    # Format fields
    field_text = ""
    if fields and len(fields) > 0:
        field_text = f"in the field{'s' if len(fields) > 1 else ''} of {', '.join(ensure_str(f) for f in fields[:2])}"

    # Citation impact text
    citation_text = ""
    if citations > 0:
        if citations > 100:
            citation_text = f"This highly-cited work ({citations} citations) "
        elif citations > 50:
            citation_text = f"This well-cited research ({citations} citations) "
        elif citations > 10:
            citation_text = f"This paper, cited {citations} times, "

    # Build the abstract with different variations based on available metadata
    if year and venue:
        fallback_abstract = f"{citation_text}This {year} study published in {venue} by {first_author} et al. {field_text} examines {title}. The research likely contributes to the advancement of knowledge in this domain through methodological innovation or empirical findings. The work may inform both theoretical frameworks and practical applications in related fields, potentially opening avenues for future research that builds upon these discoveries."
    elif year:
        fallback_abstract = f"{citation_text}In this {year} research work by {first_author} et al., the authors explore {title}. {field_text} This work potentially offers insights into relevant methodologies and findings that could influence future research directions. The analysis likely addresses key challenges or gaps in current understanding, providing a valuable contribution to the scholarly literature in this area."
    elif venue:
        fallback_abstract = f"{citation_text}In their paper published in {venue}, {first_author} and colleagues investigate {title}. {field_text} The study appears to contribute theoretical or empirical knowledge that may be applicable to researchers and practitioners in related domains. Their findings likely enhance our understanding of fundamental concepts or processes, potentially leading to new perspectives or applications."
    else:
        fallback_abstract = f"{citation_text}This research by {first_author} examines {title}. {field_text} The work potentially presents findings that could deepen understanding in this area and inform future studies. By addressing important questions in the field, the authors likely provide valuable insights that may influence both theoretical frameworks and practical implementations."

    # Add attribution
    fallback_abstract += " [Abstract generated from metadata]"

    return fallback_abstract

def extract_first_paragraph_from_pdf(pdf_url):
    """Extract the first paragraph from a PDF paper."""
    try:
        # Try to import PyPDF2 - it might not be installed
        try:
            import PyPDF2
        except ImportError:
            logging.warning("PyPDF2 not installed - cannot extract text from PDFs")
            return None

        import requests
        import io

        debug_print(f"Attempting to extract text from PDF: {pdf_url}", 2)

        # Download PDF
        response = requests.get(pdf_url, timeout=120)
        file = io.BytesIO(response.content)

        # Extract text from first page
        reader = PyPDF2.PdfReader(file)
        first_page_text = reader.pages[0].extract_text()

        # Find abstract or first paragraph after title/authors
        paragraphs = first_page_text.split('\n\n')
        for para in paragraphs:
            # Skip title, authors, headers, but try to find abstract
            if "abstract" in para.lower()[:20]:
                debug_print("Found abstract section in PDF", 2)
                return para[:300] + "..." if len(para) > 300 else para

        # If no clear abstract, get the first substantial paragraph
        for para in paragraphs:
            if len(para) > 100 and not para.lower().startswith(('title', 'author', 'introduction')):
                debug_print("Using first substantial paragraph from PDF", 2)
                return para[:300] + "..." if len(para) > 300 else para

        debug_print("Could not extract useful text from PDF", 2)
        return None
    except Exception as e:
        logging.error(f"Error extracting from PDF: {e}")
        debug_print(f"Error extracting from PDF: {e}", 2)
        return None

def search_papers_by_keyword(keyword, days_ago=3, fields=None, request_number=None, total_requests=None):
    """
    Search for papers related to a keyword that were published in the last 24 hours.
    Now includes retry logic for better reliability.

    Args:
        keyword (str): Keyword to search for
        days_ago (int): Number of days to look back (default: 1 day)
        fields (list): Fields to include in the response
        request_number (int): Current request number (for progress tracking)
        total_requests (int): Total number of requests (for progress tracking)

    Returns:
        list: Papers matching the keyword published within the last 24 hours
    """
    global RATE_LIMIT_DELAY, api_call_times

    # Add retry constants
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 2  # Base delay for exponential backoff

    # Ensure days_ago is an integer
    days_ago = ensure_int(days_ago, 1)

    if fields is None:
        fields = ["paperId", "title", "abstract", "url", "venue", "year",
                 "authors", "publicationDate", "citationCount",
                 "tldr", "fieldsOfStudy", "references", "influentialCitationCount"]

    # Calculate exact cutoff time - precisely 24 hours ago (or days_ago * 24 hours)
    current_time = datetime.datetime.now()
    cutoff_time = current_time - datetime.timedelta(days=days_ago)

    # Format dates in YYYY-MM-DD format for the API
    today_str = current_time.strftime("%Y-%m-%d")
    yesterday_str = cutoff_time.strftime("%Y-%m-%d")

    # We'll use a broader initial search and then filter strictly
    params = {
        "query": ensure_str(keyword),
        "fields": ",".join(fields),
        "limit": 100,  # Get more results for post-filtering
        "publicationDate": f"{yesterday_str}:{today_str}",  # Initial date filter
        "sort": "publicationDate:desc"  # Most recent first
    }

    endpoint = f"{SEMANTIC_SCHOLAR_API_BASE}/paper/search"

    # Debug output - print query parameters (no full response)
    debug_print("\n" + "="*40, 1)
    if request_number and total_requests:
        debug_print(f"API CALL {request_number}/{total_requests}: Searching for keyword '{keyword}'", 1)
    else:
        debug_print(f"API CALL: Searching for keyword '{keyword}'", 1)

    debug_print(f"ENDPOINT: {endpoint}", 2)
    debug_print(f"DATE RANGE: {yesterday_str} to {today_str}", 2)
    debug_print("="*40, 1)

    # Adjust RATE_LIMIT_DELAY based on previous call times
    if len(api_call_times) > 0:
        avg_call_time = sum(api_call_times) / len(api_call_times)
        min_total_time_needed = MIN_SECONDS_BETWEEN_CALLS * SAFETY_FACTOR

        if avg_call_time + RATE_LIMIT_DELAY < min_total_time_needed:
            old_delay = RATE_LIMIT_DELAY
            RATE_LIMIT_DELAY = min_total_time_needed - avg_call_time
            debug_print(f"SAFETY ADJUSTMENT: Average API call takes {avg_call_time:.2f}s", 2)
            debug_print(f"Increasing delay from {old_delay:.2f}s to {RATE_LIMIT_DELAY:.2f}s", 2)

            if 60 / (avg_call_time + RATE_LIMIT_DELAY) > MAX_CALLS_PER_MINUTE:
                RATE_LIMIT_DELAY = (60 / MAX_CALLS_PER_MINUTE) - avg_call_time
                debug_print(f"ADDITIONAL ADJUSTMENT: Further increasing delay to {RATE_LIMIT_DELAY:.2f}s", 2)

    # Implement retry logic
    for retry_attempt in range(1, MAX_RETRIES + 1):
        try:
            # Add rate limiting - show countdown timer if delay is significant
            if RATE_LIMIT_DELAY > 5 and DEBUG_LEVEL >= 2:
                delay_remaining = int(RATE_LIMIT_DELAY)
                debug_print(f"Waiting {delay_remaining} seconds before making API request...", 2)

                if DEBUG_LEVEL >= 3:
                    for i in range(min(10, delay_remaining)):
                        if i > 0:
                            remaining = delay_remaining - i
                            if remaining % 5 == 0 or remaining <= 10:
                                debug_print(f"  {remaining} seconds remaining...", 3)
                        time.sleep(min(1, delay_remaining - i))
                else:
                    time.sleep(RATE_LIMIT_DELAY)

                remaining_sleep = max(0, RATE_LIMIT_DELAY - 10)
                if remaining_sleep > 0:
                    time.sleep(remaining_sleep)
            else:
                time.sleep(RATE_LIMIT_DELAY)

            # Make API request - track how long it takes
            debug_print(f"Sending request to Semantic Scholar API (attempt {retry_attempt}/{MAX_RETRIES})...", 2)
            api_call_start_time = time.time()
            response = requests.get(endpoint, params=params)
            api_call_end_time = time.time()

            # Record the time taken for this API call
            api_call_duration = api_call_end_time - api_call_start_time
            api_call_times.append(api_call_duration)
            debug_print(f"API call completed in {api_call_duration:.2f} seconds", 2)

            # Log status and rate limit info
            debug_print(f"RESPONSE STATUS: {response.status_code}", 2)

            # Check for rate limiting headers
            if 'x-rate-limit-limit' in response.headers and DEBUG_LEVEL >= 2:
                debug_print(f"RATE LIMIT INFO: {response.headers.get('x-rate-limit-limit', 'N/A')} requests per minute", 2)
                debug_print(f"RATE LIMIT REMAINING: {response.headers.get('x-rate-limit-remaining', 'N/A')}", 2)

            logging.info(f"Received response from Semantic Scholar API for keyword '{keyword}'")

            response.raise_for_status()

            # Now parse the response data
            data = response.json()
            all_papers = data.get("data", [])
            total = data.get("total", 0)

            # Apply strict 24-hour filter with special handling for date-only entries
            filtered_papers = []

            # Get the exact cutoff time (precisely 24 hours ago)
            current_time = datetime.datetime.now()
            cutoff_time = current_time - datetime.timedelta(days=days_ago)

            # Also get just the date portion for handling date-only entries
            cutoff_date = cutoff_time.date()
            current_date = current_time.date()

            debug_print(f"\nApplying {days_ago*24}-hour filter to {len(all_papers)} returned papers...", 2)

            for paper in all_papers:
                pub_date_str = ensure_str(paper.get("publicationDate", ""))
                title = ensure_str(paper.get("title", "No title"))

                if not pub_date_str:
                    continue  # Skip without logging

                try:
                    # Check if this is a date-only entry (YYYY-MM-DD) or has time component
                    has_time_component = 'T' in pub_date_str or ' ' in pub_date_str

                    if has_time_component:
                        # Entry has a time component - use full timestamp comparison
                        try:
                            if 'T' in pub_date_str:
                                # ISO format with time (YYYY-MM-DDTHH:MM:SS)
                                # Handle the 'Z' timezone indicator if present
                                if pub_date_str.endswith('Z'):
                                    pub_date_str = pub_date_str[:-1] + '+00:00'
                                pub_time = datetime.datetime.fromisoformat(pub_date_str)
                            else:
                                # Space-separated format (YYYY-MM-DD HH:MM:SS)
                                pub_time = datetime.datetime.strptime(pub_date_str, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            # Try other common formats
                            formats_to_try = [
                                "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO with milliseconds and Z
                                "%Y-%m-%dT%H:%M:%SZ",     # ISO with Z
                                "%Y-%m-%d %H:%M"          # Date with hours and minutes
                            ]

                            pub_time = None
                            for fmt in formats_to_try:
                                try:
                                    pub_time = datetime.datetime.strptime(pub_date_str, fmt)
                                    break
                                except ValueError:
                                    continue

                            if pub_time is None:
                                # If all formats failed, fall back to date-only
                                pub_time = datetime.datetime.strptime(pub_date_str[:10], "%Y-%m-%d")
                                has_time_component = False

                        # Check if within the exact 24-hour window using timestamp
                        if pub_time >= cutoff_time:
                            filtered_papers.append(paper)

                    else:
                        # Date-only entry (YYYY-MM-DD) - compare just the date portion
                        pub_date = datetime.datetime.strptime(pub_date_str, "%Y-%m-%d").date()

                        # For date-only entries, include if it's on or after the cutoff date
                        if pub_date >= cutoff_date:
                            filtered_papers.append(paper)

                except (ValueError, TypeError) as e:
                    # Skip invalid dates without logging
                    continue

            papers = filtered_papers
            debug_print(f"\n24-HOUR FILTER RESULTS: {len(papers)} of {len(all_papers)} papers published within the last {days_ago*24} hours", 1)

            debug_print(f"TOTAL PAPERS FOUND IN SEARCH: {total}", 1)
            debug_print(f"PAPERS RETURNED FROM API: {len(all_papers)}", 1)
            debug_print(f"PAPERS AFTER DATE FILTERING: {len(papers)}", 1)

            # Limit to the maximum number after filtering
            if len(papers) > MAX_PAPERS_PER_KEYWORD:
                debug_print(f"Limiting to {MAX_PAPERS_PER_KEYWORD} papers after filtering", 1)
                papers = papers[:MAX_PAPERS_PER_KEYWORD]

            # Print brief information about each paper (no detailed data)
            if papers and DEBUG_LEVEL >= 1:
                debug_print("\nPAPERS FOUND:", 1)
                for i, paper in enumerate(papers):
                    debug_print(f"  {i+1}. '{ensure_str(paper.get('title', 'No title'))}' ({ensure_str(paper.get('year', 'No year'))})", 1)
                    if DEBUG_LEVEL >= 2:
                        author_names = [ensure_str(a.get('name', 'Unknown')) for a in paper.get('authors', [])]
                        author_str = ', '.join(author_names)
                        if len(author_str) > 80:
                            author_str = author_str[:80] + "..."
                        debug_print(f"     Authors: {author_str}", 2)
                        debug_print(f"     Has Abstract: {'Yes' if paper.get('abstract') else 'No'}", 2)
            else:
                debug_print("NO PAPERS FOUND FOR THIS KEYWORD", 1)

            logging.info(f"Found {len(papers)} papers for keyword '{keyword}' (Total available: {total})")
            return papers

        except requests.exceptions.RequestException as e:
            # Handle different types of errors
            if retry_attempt == MAX_RETRIES:
                debug_print(f"ERROR: All {MAX_RETRIES} attempts failed for keyword '{keyword}'", 1)
                logging.error(f"Error searching papers for keyword '{keyword}' after {MAX_RETRIES} attempts: {e}")
                return []

            # Check if it's a specific HTTP error
            if isinstance(e, requests.exceptions.HTTPError):
                status_code = e.response.status_code if hasattr(e, 'response') else None
                if status_code == 429:  # Rate limit exceeded
                    retry_delay = BASE_RETRY_DELAY * (3 ** (retry_attempt - 1))  # Longer delay for rate limits
                    debug_print(f"Rate limit exceeded. Waiting {retry_delay} seconds before retry {retry_attempt}/{MAX_RETRIES}", 1)
                elif status_code == 404:  # Not found - no need to retry
                    debug_print(f"ERROR: API endpoint not found (404) for keyword '{keyword}'", 1)
                    return []
                else:
                    retry_delay = BASE_RETRY_DELAY * (2 ** (retry_attempt - 1))
                    debug_print(f"HTTP error {status_code}. Waiting {retry_delay} seconds before retry {retry_attempt}/{MAX_RETRIES}", 1)
            else:
                # General network error - use exponential backoff
                retry_delay = BASE_RETRY_DELAY * (2 ** (retry_attempt - 1))
                debug_print(f"Network error: {e}. Waiting {retry_delay} seconds before retry {retry_attempt}/{MAX_RETRIES}", 1)

            logging.warning(f"Retry {retry_attempt}/{MAX_RETRIES} for keyword '{keyword}' after error: {e}")
            time.sleep(retry_delay)

def enrich_paper_data(paper):
    """
    Enrich paper data with additional details.

    Args:
        paper (dict): Paper data from the search API

    Returns:
        dict: Enriched paper data
    """
    # Add a source type for consistent processing in the newsletter system
    paper["source_type"] = "academic"

    # Extract keywords from the paper (if available)
    # The Semantic Scholar API doesn't directly provide keywords, so we use a simple approach
    paper_keywords = []

    # Extract from abstract if available
    abstract_text = ensure_str(paper.get("abstract", ""))
    if abstract_text:
        # Check which of our tracked keywords appear in the abstract
        for kw in KEYWORDS:
            if ensure_str(kw).lower() in abstract_text.lower():
                paper_keywords.append(kw)
    # If no abstract, try to match keywords in title
    elif paper.get("title"):
        for kw in KEYWORDS:
            if ensure_str(kw).lower() in ensure_str(paper.get("title", "")).lower():
                paper_keywords.append(kw)

    # Extract from fieldsOfStudy if available
    if not paper_keywords and paper.get("fieldsOfStudy"):
        for field in paper.get("fieldsOfStudy", []):
            for kw in KEYWORDS:
                if ensure_str(kw).lower() in ensure_str(field).lower():
                    paper_keywords.append(kw)

    # Only log basic info about keyword matching
    debug_print(f"Enriching paper: '{ensure_str(paper.get('title', 'No title'))}'", 2)
    debug_print(f"  Found {len(paper_keywords)} matching keywords", 2)

    # Add keywords to the paper data
    paper["keywords"] = paper_keywords

    # Format authors for display
    if "authors" in paper and paper["authors"]:
        authors_list = [ensure_str(author.get("name", "")) for author in paper["authors"] if "name" in author]
        paper["authors_formatted"] = ", ".join(authors_list[:3])
        if len(authors_list) > 3:
            paper["authors_formatted"] += f" et al. ({len(authors_list)})"
    else:
        paper["authors_formatted"] = "Unknown Authors"

    # Create a snippet for display using fallback chain
    # 1. Use original abstract if available
    if abstract_text:
        max_snippet_length = 300
        paper["snippet"] = abstract_text[:max_snippet_length] + "..." if len(abstract_text) > max_snippet_length else abstract_text
        paper["abstract_source"] = "original"

    # 2. Try to use Semantic Scholar's tldr if available
    elif "tldr" in paper and paper["tldr"] and paper["tldr"].get("text"):
        paper["snippet"] = "AI Summary: " + ensure_str(paper["tldr"]["text"])
        paper["abstract_source"] = "ai-generated by Semantic Scholar"

    # 3. Try to extract from PDF if URL is available
    elif "url" in paper and paper["url"] and ensure_str(paper["url"]).endswith(".pdf"):
        pdf_extract = extract_first_paragraph_from_pdf(paper["url"])
        if pdf_extract:
            paper["snippet"] = pdf_extract
            paper["abstract_source"] = "extracted from paper PDF"
        else:
            # 4. Generate an AI abstract as last resort
            paper["snippet"] = generate_ai_abstract(paper)
            paper["abstract_source"] = "ai-generated"

    # 5. Generate an AI abstract if all else fails
    else:
        paper["snippet"] = generate_ai_abstract(paper)
        paper["abstract_source"] = "ai-generated"

    # Add source info
    paper["source_info"] = {
        "title": ensure_str(paper.get("venue")) if paper.get("venue") else "Semantic Scholar",
        "domain": "semanticscholar.org",
        "url": "https://www.semanticscholar.org/"
    }

    return paper

def generate_ai_abstract(paper):
    """
    Generate an abstract for an academic paper using the Mistral API.
    Uses all available metadata and the paper's URL to prompt the API.
    Returns the generated abstract as a string, or None if generation fails.
    """
    try:
        # Gather metadata
        title = ensure_str(paper.get("title", ""))
        authors = ensure_str(paper.get("authors_formatted", ""))
        year = ensure_str(paper.get("year", ""))
        venue = ensure_str(paper.get("venue", ""))
        fields = paper.get("fieldsOfStudy", [])
        paper_url = ensure_str(paper.get("url", ""))
        citation_count = ensure_str(paper.get("citationCount", "Unknown"))

        # Compose a prompt for the Mistral API
        prompt = (
            f"Generate a comprehensive academic abstract (200-300 words) for the following research paper.\n\n"
            f"Paper metadata:\n"
            f"Title: {title}\n"
            f"Authors: {authors}\n"
            f"Year: {year}\n"
            f"Venue: {venue}\n"
            f"Fields of Study: {', '.join(ensure_str(f) for f in fields) if fields else 'Not specified'}\n"
            f"Citations: {citation_count}\n"
            f"URL: {paper_url}\n\n"
            f"Instructions:\n"
            f"- Use any available information from the metadata and the URL (if accessible) to generate the abstract.\n"
            f"- The abstract should cover the likely purpose, methodology, main findings, and significance of the work.\n"
            f"- Write in a formal academic style. Do not invent specific results if they are not available.\n"
            f"- Begin directly with the abstract text, no preambles or section headers.\n"
        )

        # Call the Mistral API
        mistral_api = MistralAPI()
        abstract = mistral_api.generate_summary(prompt, max_tokens=350)

        # Validate and return the abstract
        if abstract and len(abstract) > 50 and not abstract.lower().startswith("error") and not abstract.lower().startswith("i apologize"):
            logging.info(f"Successfully generated abstract with Mistral API for: {title}")
            # Optionally trim if too long
            if len(abstract) > 700:
                abstract = abstract[:700] + "..."
            return abstract + " [AI-generated by Mistral]"
        else:
            logging.warning(f"Generated abstract was too short or contained error message for: {title}")
            return None

    except Exception as e:
        logging.error(f"Error generating AI abstract with Mistral: {e}")
        return None

def process_academic_papers(days_lookback=3, process_all=False): #changed from True to False
    """
    Process academic papers for the newsletter.

    Args:
        days_lookback (int): Number of days to look back for papers (default: 1 day)
        process_all (bool): Whether to process all keywords or limit to 10

    Returns:
        tuple: (list of papers, keyword counter)
    """
    global RATE_LIMIT_DELAY, api_call_times

    # Ensure days_lookback is an integer
    days_lookback = ensure_int(days_lookback, 1)

    # Reset timing data for a fresh start
    api_call_times = []

    logging.info(f"Fetching academic papers from Semantic Scholar (last {days_lookback} day(s))...")
    debug_print("\n" + "*"*40, 1)
    debug_print(f"STARTING SEMANTIC SCHOLAR API PROCESSING - LAST {days_lookback*24} HOURS", 1)
    debug_print("*"*40, 1)
    debug_print(f"Fetching academic papers published in the last {days_lookback*24} hours...", 1)

    all_papers = []
    keyword_counts = Counter()

    # Convert the set of keywords to a list
    keywords_list = list(KEYWORDS)

    # Only print detailed keyword list at higher debug levels
    debug_print(f"\nTRACKING {len(keywords_list)} KEYWORDS", 1)
    if DEBUG_LEVEL >= 2:
        for i, kw in enumerate(keywords_list[:5]):  # Show just first 5 at most
            debug_print(f"  {i+1}. '{ensure_str(kw)}'", 2)
        if len(keywords_list) > 5:
            debug_print(f"  ... and {len(keywords_list) - 5} more", 2)

    # Determine which keywords to process
    if process_all:
        # Process all keywords
        keywords_to_process = keywords_list
        logging.info(f"Processing all {len(keywords_to_process)} keywords")
        debug_print(f"\nProcessing all {len(keywords_to_process)} keywords", 1)
    else:
        # Limit to 10 keywords to avoid excessive API calls
        keywords_to_process = keywords_list[:2] if len(keywords_list) > 10 else keywords_list
        logging.info(f"Processing {len(keywords_to_process)} keywords (limited to 10)")
        debug_print(f"\nProcessing {len(keywords_to_process)} keywords (limited to 10)", 1)

    # Calculate the delay between API calls to spread evenly over the total time period
    num_keywords = len(keywords_to_process)

    # If we have no keywords or just one, use a default delay
    if num_keywords <= 1:
        RATE_LIMIT_DELAY = 10  # Default 10 seconds delay if only one keyword
    else:
        # Distribute (num_keywords) API calls evenly over TOTAL_TIME_SECONDS
        # We need (num_keywords - 1) gaps between the calls
        RATE_LIMIT_DELAY = TOTAL_TIME_SECONDS / (num_keywords - 1) if num_keywords > 1 else TOTAL_TIME_SECONDS

    # Apply minimum safety delay to start with
    min_delay = 60 / MAX_CALLS_PER_MINUTE  # Ensure we're below MAX_CALLS_PER_MINUTE
    if RATE_LIMIT_DELAY < min_delay:
        RATE_LIMIT_DELAY = min_delay

    debug_print(f"SPREADING API CALLS: {num_keywords} calls over at least {TOTAL_TIME_MINUTES} minutes", 2)
    debug_print(f"INITIAL DELAY BETWEEN CALLS: {RATE_LIMIT_DELAY:.2f} seconds", 2)

    # Calculate total runtime based on initial delay (only detailed at higher debug levels)
    total_runtime = RATE_LIMIT_DELAY * (num_keywords - 1) if num_keywords > 1 else 0
    logging.info(f"Initial estimated processing time: {total_runtime/60:.1f} minutes")
    debug_print(f"ESTIMATED RUNTIME: {total_runtime/60:.1f} minutes", 2)

    # Process each keyword
    start_time = time.time()

    for i, keyword in enumerate(keywords_to_process):
        # Calculate and display progress information
        current_time = time.time()
        elapsed_time = current_time - start_time

        logging.info(f"Processing keyword {i+1}/{len(keywords_to_process)}: '{keyword}'")
        debug_print(f"\nProcessing keyword {i+1}/{len(keywords_to_process)}: '{ensure_str(keyword)}'", 1)

        if i > 0 and DEBUG_LEVEL >= 2:
            # Calculate progress and estimated completion
            progress_percent = (i / len(keywords_to_process)) * 100
            total_estimated_time = elapsed_time / (i / len(keywords_to_process))
            remaining_time = total_estimated_time - elapsed_time

            debug_print(f"PROGRESS: {progress_percent:.1f}% complete", 2)
            debug_print(f"TIME ELAPSED: {elapsed_time/60:.1f} minutes", 2)
            debug_print(f"ESTIMATED TIME REMAINING: {remaining_time/60:.1f} minutes", 2)

        # Pass progress information to the search function
        papers = search_papers_by_keyword(
            keyword,
            days_ago=days_lookback,
            request_number=i+1,
            total_requests=len(keywords_to_process)
        )

        for paper in papers:
            # Enrich paper data
            enriched_paper = enrich_paper_data(paper)

            # Check if paper is already in our list (by paperId)
            if not any(p.get("paperId") == paper.get("paperId") for p in all_papers):
                all_papers.append(enriched_paper)

                # Count keywords
                for kw in enriched_paper["keywords"]:
                    keyword_counts[kw] += 1
            else:
                debug_print(f"Skipping duplicate paper: {ensure_str(paper.get('title', 'No title'))}", 2)

    # Summary output (minimal)
    debug_print("\n" + "*"*40, 1)
    debug_print(f"PROCESSING COMPLETE: Found {len(all_papers)} unique academic papers", 1)

    if len(all_papers) == 0:
        debug_print("NO PAPERS FOUND PUBLISHED IN THE LAST 24 HOURS", 1)

    # Display timing statistics only at higher debug levels
    if api_call_times and DEBUG_LEVEL >= 2:
        avg_call_time = sum(api_call_times) / len(api_call_times)
        min_call_time = min(api_call_times)
        max_call_time = max(api_call_times)
        total_api_time = sum(api_call_times)

        debug_print("\nAPI CALL STATISTICS:", 2)
        debug_print(f"  Total API calls made: {len(api_call_times)}", 2)
        debug_print(f"  Average call duration: {avg_call_time:.2f} seconds", 2)
        debug_print(f"  Fastest call: {min_call_time:.2f} seconds", 2)
        debug_print(f"  Slowest call: {max_call_time:.2f} seconds", 2)
        debug_print(f"  Final delay between calls: {RATE_LIMIT_DELAY:.2f} seconds", 2)

    debug_print("*"*40, 1)

    logging.info(f"Processed {len(all_papers)} academic papers")
    return all_papers, keyword_counts

if __name__ == "__main__":
    # Set a more minimal debug level when running as a script
    DEBUG_LEVEL = 1

    # Test the module
    debug_print("Running academic_processor.py directly - testing API functionality", 1)

    try:
        # Default to processing just a subset of keywords when running as a standalone script
        process_all_keywords = False
        days_to_look_back = 1  # Default to 1 day (24 hours)

        # Check for command line arguments
        if len(sys.argv) > 1:
            if sys.argv[1].lower() == "all":
                process_all_keywords = True
                debug_print("Command line argument 'all' detected - will process ALL keywords", 1)
            elif sys.argv[1].lower() == "debug":
                DEBUG_LEVEL = 2
                debug_print("Debug level set to 2 - showing more detailed output", 1)
            elif sys.argv[1].lower() == "verbose":
                DEBUG_LEVEL = 3
                debug_print("Debug level set to 3 - showing detailed output without API responses", 1)
            else:
                try:
                    days_to_look_back = int(sys.argv[1])
                    debug_print(f"Will look back {days_to_look_back} days for papers", 1)
                except ValueError:
                    debug_print(f"Unrecognized argument: {sys.argv[1]}", 1)
                    debug_print("Usage: python academic_processor.py [all|debug|verbose|NUMBER_OF_DAYS]", 1)
                    sys.exit(1)

        # Run the processor - no user confirmation needed
        papers, counts = process_academic_papers(
            days_lookback=days_to_look_back,
            process_all=process_all_keywords
        )

        debug_print("\nSUMMARY OF RESULTS:", 1)
        debug_print(f"Total papers found: {len(papers)}", 1)
        if len(counts) > 0:
            debug_print(f"Top keywords matched:", 1)
            for kw, count in counts.most_common(5):
                debug_print(f"  - {kw}: {count}", 1)

        if papers and DEBUG_LEVEL >= 2:
            debug_print("\nPAPER DETAILS:", 2)
            for i, paper in enumerate(papers):
                debug_print(f"\n{i+1}. Title: {ensure_str(paper['title'])}", 2)
                debug_print(f"   Authors: {ensure_str(paper['authors_formatted'])}", 2)
                debug_print(f"   Keywords: {paper['keywords']}", 2)
                debug_print(f"   Abstract Source: {ensure_str(paper.get('abstract_source', 'unknown'))}", 2)
                if DEBUG_LEVEL >= 3:
                    snippet = ensure_str(paper['snippet'])
                    short_snippet = snippet[:100] + "..." if len(snippet) > 100 else snippet
                    debug_print(f"   Snippet: {short_snippet}", 3)
                debug_print("-" * 40, 2)
    except KeyboardInterrupt:
        debug_print("\nOperation cancelled by user (Ctrl+C)", 1)
        sys.exit(1)