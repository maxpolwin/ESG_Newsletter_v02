#!/usr/bin/env python3
"""
Newsletter System v07 - Utilities Module

Contains shared utility functions for text processing, file operations,
and other common tasks used across the newsletter system.

Author: Max Polwin
"""

import os
import re
import unicodedata
import hashlib
import logging
import datetime
from html import unescape
from email.header import decode_header
from bs4 import BeautifulSoup

# Import configuration
from config import OUTPUT_DIR, CSS_DIR, COLORS

def log_and_print(message, level=logging.INFO):
    """Log a message and print it to stdout. Reduces duplicate logging/print pairs."""
    logging.log(level, message)
    print(message)


def normalize_text(text):
    """Normalize text to remove inconsistencies in encoding and case."""
    if not text:
        return ""
    if isinstance(text, bytes):
        text = text.decode('utf-8', errors='ignore')
    return unicodedata.normalize("NFKD", unescape(text)).lower()

def generate_article_id(title, link):
    """Generate a unique ID for an article based on title and link."""
    normalized_title = normalize_text(title)
    normalized_link = normalize_text(link)
    combined = f"{normalized_title}|{normalized_link}"
    return hashlib.md5(combined.encode()).hexdigest()

def decode_email_header(header):
    """Decode email header to handle various encodings."""
    if not header:
        return ""
    try:
        decoded_parts = []
        for part, encoding in decode_header(header):
            if isinstance(part, bytes):
                if encoding:
                    decoded_parts.append(part.decode(encoding or 'utf-8', errors='ignore'))
                else:
                    decoded_parts.append(part.decode('utf-8', errors='ignore'))
            else:
                decoded_parts.append(part)
        return ''.join(decoded_parts)
    except Exception as e:
        logging.error(f"Error decoding header: {e}")
        return header

def generate_email_id(sender, subject, date):
    """Generate a unique ID for an email based on sender, subject, and date."""
    normalized_sender = normalize_text(sender)
    normalized_subject = normalize_text(subject)
    normalized_date = str(date) if date else ""
    combined = f"{normalized_sender}|{normalized_subject}|{normalized_date}"
    return hashlib.md5(combined.encode()).hexdigest()

def sanitize_filename(filename):
    """Create a safe filename from a string (typically a newsletter title)."""
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

def highlight_keywords(text, keywords):
    """Function kept for compatibility but now doesn't highlight keywords."""
    # As per requirements, we're not highlighting keywords
    return text

def find_latest_html_file(directory=OUTPUT_DIR):
    """Find the most recent HTML file in the specified directory."""
    print(f"Looking for latest HTML file in {directory}")
    try:
        html_files = [f for f in os.listdir(directory) if f.startswith('latest_articles_') and f.endswith('.html')]

        if not html_files:
            logging.error(f"No HTML files found in {directory}")
            print(f"No HTML files found in {directory}")
            return None

        # Extract timestamps from filenames and find the latest one
        # Pattern matches: latest_articles_YYYY-MM-DD_HH-MM-SS.html
        pattern = r'latest_articles_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\.html'

        latest_file = None
        latest_timestamp = None

        for file in html_files:
            match = re.match(pattern, file)
            if match:
                timestamp_str = match.group(1)
                timestamp = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d_%H-%M-%S")

                if latest_timestamp is None or timestamp > latest_timestamp:
                    latest_timestamp = timestamp
                    latest_file = file

        if latest_file:
            full_path = os.path.join(directory, latest_file)
            logging.info(f"Latest HTML file found: {full_path}")
            print(f"Latest HTML file found: {full_path}")
            return full_path
        else:
            logging.error("No valid HTML files found matching the pattern")
            print("No valid HTML files found matching the pattern")
            return None

    except Exception as e:
        logging.error(f"Error finding latest HTML file: {e}")
        print(f"Error finding latest HTML file: {e}")
        return None

def get_domain_from_url(url):
    """Extract the domain name from a URL."""
    if not url:
        return ""

    try:
        # Remove protocol
        domain = url.split('//')[1] if '//' in url else url
        # Remove path and query params
        domain = domain.split('/')[0]
        # Remove subdomains except 'www'
        parts = domain.split('.')
        if len(parts) > 2:
            if parts[0] == 'www':
                domain = '.'.join(parts[-2:])
            else:
                # Try to handle cases like co.uk
                if len(parts[-2]) <= 3 and len(parts[-1]) <= 3:
                    domain = '.'.join(parts[-3:])
                else:
                    domain = '.'.join(parts[-2:])
        return domain
    except Exception:
        return url

def create_css_file():
    """Create and save the CSS file for the HTML report."""
    css_content = f"""
    :root {{
        --color-primary: {COLORS["primary"]};
        --color-primary-dark: {COLORS["primary_dark"]};
        --color-primary-light: {COLORS["primary_light"]};
        --color-secondary: {COLORS["secondary"]};
        --color-background: {COLORS["background"]};
        --color-background-light: {COLORS["background_light"]};
        --color-background-alt: {COLORS["background_alt"]};
        --color-text-dark: {COLORS["text_dark"]};
        --color-text-medium: {COLORS["text_medium"]};
        --color-text-light: {COLORS["text_light"]};
        --color-accent: {COLORS["accent"]};

        --font-primary: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen-Sans, Ubuntu, Cantarell, 'Helvetica Neue', sans-serif;
        --spacing-unit: 0.5rem;
        --border-radius: 8px;
        --box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
    }}

    @media (prefers-color-scheme: dark) {{
        :root {{
            --color-primary: {COLORS["primary"]};
            --color-primary-dark: {COLORS["primary_light"]};
            --color-primary-light: {COLORS["primary_dark"]};
            --color-secondary: {COLORS["secondary"]};
            --color-background: #232323;
            --color-background-light: #333333;
            --color-background-alt: #2a2a2a;
            --color-text-dark: #f0f0f0;
            --color-text-medium: #cccccc;
            --color-text-light: #aaaaaa;
            --color-accent: #8EBEBB;
            --box-shadow: 0 2px 5px rgba(0, 0, 0, 0.3);
        }}
    }}

    * {{
        box-sizing: border-box;
        margin: 0;
        padding: 0;
    }}

    body {{
        font-family: var(--font-primary);
        line-height: 1.6;
        color: var(--color-text-dark);
        background-color: var(--color-background);
        margin: 0;
        padding: var(--spacing-unit);
        -webkit-text-size-adjust: 100%;
        -ms-text-size-adjust: 100%;
    }}

    /* Container */
    .container {{
        max-width: 800px;
        margin: 0 auto;
        background-color: var(--color-background-alt);
        border-radius: var(--border-radius);
        box-shadow: var(--box-shadow);
        overflow: hidden;
    }}

    /* Header */
    .header {{
        background-color: var(--color-primary);
        color: white;
        padding: calc(var(--spacing-unit) * 4) calc(var(--spacing-unit) * 3);
        text-align: center;
    }}

    .header h1 {{
        margin: 0;
        font-size: 1.75rem;
        font-weight: bold;
    }}

    .header p {{
        margin-top: calc(var(--spacing-unit) * 1);
        font-size: 1rem;
        opacity: 0.9;
    }}

    /* Section Headers */
    .section-header {{
        margin: 0;
        padding: calc(var(--spacing-unit) * 3);
        border-bottom: 2px solid var(--color-secondary);
        font-size: 1.25rem;
        color: var(--color-secondary);
        background-color: var(--color-background-alt);
    }}

    /* Content Sections */
    .content-section {{
        padding: calc(var(--spacing-unit) * 3);
        background-color: var(--color-background-alt);
    }}

    /* Keyword Bubbles */
    .keyword-bubbles {{
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        text-align: center;
        padding: 10px;
    }}

    .keyword-bubble {{
        display: inline-flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        margin: 10px;
        padding: 15px;
        border-radius: 50%;
        background-color: var(--color-primary);
        color: white;
        font-weight: bold;
        box-shadow: var(--box-shadow);
    }}

    .keyword-bubble-text {{
        font-family: var(--font-primary);
        max-width: 90%;
        overflow-wrap: break-word;
        text-align: center;
    }}

    .keyword-bubble-count {{
        font-size: 0.8em;
        margin-top: 3px;
    }}

    .keyword-bubble-wrapper {{
        display: inline-block;
        margin: 10px;
        text-align: center;
    }}

    .keyword-bubble-label {{
        margin-bottom: 5px;
        font-weight: bold;
        color: var(--color-primary);
    }}

    /* Collapsible sections */
    .collapsible-header {{
        cursor: pointer;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }}

    .collapsible-header::after {{
        content: '▼';
        font-size: 0.8rem;
        transition: transform 0.3s ease;
    }}

    .collapsible-header.collapsed::after {{
        transform: rotate(-90deg);
    }}

    .collapsible-content {{
        max-height: 2000px;
        overflow: hidden;
        transition: max-height 0.5s ease;
    }}

    .collapsible-content.collapsed {{
        max-height: 0;
    }}

    /* Domain indicator */
    .domain-indicator {{
        display: inline-flex;
        align-items: center;
        padding: 2px 6px;
        background-color: var(--color-primary-light);
        border-radius: 4px;
        font-size: 0.75rem;
        margin-left: 8px;
        color: var(--color-text-dark);
        vertical-align: middle;
    }}

    .domain-indicator::before {{
        content: '';
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: var(--color-primary);
        margin-right: 4px;
    }}

    /* Footer */
    .footer {{
        padding: calc(var(--spacing-unit) * 3);
        text-align: center;
        color: var(--color-primary);
        font-size: 0.85rem;
        background-color: var(--color-background-alt);
        border-top: 1px solid var(--color-primary-light);
    }}

    /* Responsive adjustments */
    @media (max-width: 767px) {{
        .header h1 {{
            font-size: 1.5rem;
        }}

        .section-header {{
            font-size: 1.1rem;
            padding: calc(var(--spacing-unit) * 2);
        }}

        .content-section {{
            padding: calc(var(--spacing-unit) * 2);
        }}
    }}

    /* Preheader text (hidden) */
    .preheader {{
        display: none !important;
        font-size: 1px;
        color: #ffffff;
        line-height: 1px;
        max-height: 0px;
        max-width: 0px;
        opacity: 0;
        overflow: hidden;
    }}
    """

    css_path = os.path.join(CSS_DIR, "newsletter_styles.css")
    with open(css_path, "w", encoding="utf-8") as file:
        file.write(css_content)

    logging.info(f"CSS file generated: {css_path}")
    return css_path

def create_js_file():
    """Create and save the JavaScript file for interactive features."""
    js_content = """
    document.addEventListener('DOMContentLoaded', function() {
        // Collapsible sections
        document.querySelectorAll('.collapsible-header').forEach(function(header) {
            header.addEventListener('click', function() {
                this.classList.toggle('collapsed');
                const content = this.nextElementSibling;
                content.classList.toggle('collapsed');
            });
        });

        // Dark mode toggle
        const darkModeToggle = document.getElementById('dark-mode-toggle');
        if (darkModeToggle) {
            darkModeToggle.addEventListener('click', function() {
                document.body.classList.toggle('dark-mode');
                localStorage.setItem('dark-mode', document.body.classList.contains('dark-mode'));
            });

            // Check for saved dark mode preference
            if (localStorage.getItem('dark-mode') === 'true') {
                document.body.classList.add('dark-mode');
            }
        }
    });
    """

    js_path = os.path.join(CSS_DIR, "newsletter_scripts.js")
    with open(js_path, "w", encoding="utf-8") as file:
        file.write(js_content)

    logging.info(f"JavaScript file generated: {js_path}")
    return js_path

def extract_text_from_html(html_content):
    """Extract readable text from HTML content."""
    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, 'html.parser')

    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.extract()

    # Get text
    text = soup.get_text(separator=' ', strip=True)

    # Break into lines and remove leading and trailing space on each
    lines = (line.strip() for line in text.splitlines())

    # Break multi-headlines into a line each
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))

    # Drop blank lines
    text = ' '.join(chunk for chunk in chunks if chunk)

    return text
