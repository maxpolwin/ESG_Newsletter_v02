import logging
import os
import datetime
from bs4 import BeautifulSoup
from collections import Counter
from config import OUTPUT_DIR, CSS_DIR, COLORS
from utils import create_css_file, create_js_file
from mistral import MistralAPI  # Add import for Mistral API

# Helper functions for safe type conversion
def ensure_str(value, default=""):
    """Safely convert a value to string."""
    if value is None:
        return default
    try:
        return str(value)
    except (ValueError, TypeError):
        return default

def ensure_int(value, default=0):
    """Safely convert a value to integer."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def extract_organization_name(article):
    """Extract organization name from article source info."""
    source_info = article.get("source_info", {})
    if source_info:
        if "title" in source_info and source_info["title"]:
            return ensure_str(source_info["title"])
        if "domain" in source_info and source_info["domain"]:
            return ensure_str(source_info["domain"])
    return "Unknown"

def is_sciencedirect_article(article):
    """Check if the article is from ScienceDirect."""
    source_info = article.get("source_info", {})
    if source_info and source_info.get("domain", "").lower() in ["sciencedirect.com", "www.sciencedirect.com"]:
        return True
    return False

def enhanced_executive_summary(articles):
    """Generate an enhanced executive summary of the articles using Mistral API with fallback to simple stats."""
    if not articles:
        return "<p>No articles were found matching your keywords in the last 24 hours.</p>"

    # Count source types for fallback
    rss_count = sum(1 for a in articles if ensure_str(a.get("source_type", "")) == "rss")
    email_count = sum(1 for a in articles if ensure_str(a.get("source_type", "")) == "email")
    academic_count = sum(1 for a in articles if ensure_str(a.get("source_type", "")) == "academic" or is_sciencedirect_article(a))
    podcast_count = sum(1 for a in articles if ensure_str(a.get("source_type", "")) == "podcast")  # NEW

    logging.info(f"Article breakdown: {rss_count} RSS articles, {email_count} email newsletters, {academic_count} academic papers, {podcast_count} podcasts")

    # Create fallback summary
    fallback_summary = f"<p>In the last 24 hours, we found <strong>{len(articles)}</strong> articles matching your tracked keywords "
    fallback_summary += f"from <strong>{rss_count}</strong> RSS feeds, <strong>{email_count}</strong> newsletters, "
    fallback_summary += f"from <strong>{podcast_count}</strong> podcasts, and <strong>{academic_count}</strong> academic papers.</p>"

    try:
        # Initialize Mistral API
        mistral_api = MistralAPI()
        
        # Collect all article content for summary
        all_content = []
        for article in articles:
            # Get the most relevant content based on source type
            if article.get("source_type") == "academic":
                content = article.get("snippet", "")  # Use the abstract/snippet for academic papers
            elif article.get("source_type") == "email":
                content = article.get("full_text", article.get("snippet", ""))  # Prefer full text for emails
            else:  # RSS
                content = article.get("snippet", "")  # Use snippet for RSS feeds
            
            if content:
                # Add title and source info for context
                title = article.get("title", "Untitled")
                source = article.get("source_info", {}).get("title", "Unknown Source")
                all_content.append(f"Title: {title}\nSource: {source}\nContent: {content}\n\n")

        # Combine all content with a limit to avoid token limits
        combined_content = "\n".join(all_content)
        if len(combined_content) > 8000:  # Limit content to avoid token limits
            combined_content = combined_content[:8000] + "\n\n[Content truncated for length]"

        # Generate AI summary
        ai_summary = mistral_api.generate_summary(combined_content)
        
        if ai_summary:
            # Combine AI summary with basic stats
            return f"""
            <div class="executive-summary-content">
                {ai_summary}
                <div class="stats-summary">
                    {fallback_summary}
                </div>
            </div>
            """
        
    except Exception as e:
        logging.warning(f"Failed to generate AI summary, using fallback: {str(e)}")
    
    # Return fallback summary if AI summary fails
    return fallback_summary


def extract_actual_url(link_str):
    """
    Extract the actual URL from complex link formats that may contain embedded URLs.

    Args:
        link_str (str): The complex link string that may contain embedded URLs

    Returns:
        str: The extracted actual URL or the original link if no URL could be extracted
    """
    import urllib.parse
    import re
    import logging

    # Ensure we have a string to work with
    link_str = ensure_str(link_str, "")
    if not link_str:
        return ""

    # Case 1: Common pattern like x-webdoc://ID/{...} or pm-incoming-mail://ID/{...}
    # For links like: x-webdoc://664B8DDC-208A-4FA5-8C8F-5FBF09CD3619/%7B'rel': 'alternate', 'href': 'https://...'%7D
    custom_protocol_pattern = r'(?:x-webdoc|pm-incoming-mail)://[^/]+/(.+)$'
    custom_match = re.search(custom_protocol_pattern, link_str)

    if custom_match:
        encoded_part = custom_match.group(1)
        try:
            # Decode the URL-encoded part
            decoded_json = urllib.parse.unquote(encoded_part)

            # Extract href using regex - handles both 'href': and "href": formats
            href_match = re.search(r"['\"](href)['\"]:\s*['\"]([^'\"]+)['\"]", decoded_json)
            if href_match:
                return href_match.group(2)
        except Exception as e:
            logging.debug(f"Error extracting URL from custom protocol: {e}")

    # Case 2: Handle URL redirect services or tracking parameters
    redirect_patterns = [
        # Common redirect patterns
        r'[?&](?:url|redirect|link|u)=([^&]+)',
        r'/(?:go|redirect|out)/([^?&]+)',
        # RSS specific redirects
        r'/rss/click/\?resource=([^&]+)'
    ]

    for pattern in redirect_patterns:
        match = re.search(pattern, link_str)
        if match:
            encoded_url = match.group(1)
            try:
                # URL might be encoded multiple times
                decoded_url = urllib.parse.unquote(encoded_url)
                if decoded_url.startswith('http'):
                    return decoded_url
            except Exception:
                pass

    # Case 3: Handle direct embedded JSON-like structures
    # For patterns like: {href: 'https://...'}
    try:
        if '{' in link_str and '}' in link_str:
            # Extract content between curly braces, handling potentially escaped content
            json_like = re.search(r'{([^}]+)}', link_str)
            if json_like:
                json_content = json_like.group(1)
                href_match = re.search(r"['\"](href)['\"]:\s*['\"]([^'\"]+)['\"]", json_content)
                if href_match:
                    return href_match.group(2)
    except Exception as e:
        logging.debug(f"Error parsing embedded JSON-like content: {e}")

    # No transformation needed/possible - return original link
    return link_str

def generate_podcast_section(podcast_articles):
    """
    Generate HTML for podcast episodes, with special handling for Deutschlandfunk podcasts.
    Args:
        podcast_articles: List of podcast article dicts
    Returns:
        str: HTML string for podcast section
    """
    if not podcast_articles:
        return ""
    
    podcast_html = ""
    for article in podcast_articles:
        title = ensure_str(article.get("title", "Untitled"))
        description = ensure_str(article.get("snippet", ""))
        link = ensure_str(article.get("link", ""))
        pub_date = ensure_str(article.get("pub_date", ""))
        duration = ensure_str(article.get("duration", ""))
        keywords = article.get("keywords", [])
        source_info = article.get("source_info", {})
        
        # Extract Deutschlandfunk specific metadata
        is_deutschlandfunk = False
        if source_info and source_info.get("domain", "").lower() in ["deutschlandfunk.de", "deutschlandfunkkultur.de", "deutschlandfunknova.de"]:
            is_deutschlandfunk = True
            # Extract additional metadata if available
            series = article.get("series", "")
            episode_number = article.get("episode_number", "")
            author = article.get("author", "")
            image_url = article.get("image_url", "")
        
        # Build the keywords line
        keywords_html = ""
        for kw in keywords:
            keywords_html += f"<span style='display: inline-block; background-color: #BDD7D6; padding: 2px 5px; margin: 2px; border-radius: 3px;'>{ensure_str(kw)}</span> "

        # Special styling for Deutschlandfunk podcasts
        if is_deutschlandfunk:
            podcast_html += f"""
            <tr>
                <td style="padding: 0 0 20px 0;">
                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #F5F5F5; border-radius: 8px; border-left: 4px solid #003366;">
                        <tr>
                            <td style="padding: 15px;">
                                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px;">
                                    <h3 style="margin: 0; font-family: Arial, sans-serif; font-size: 16px;">
                                        <a href="{link}" style="color: #003366; text-decoration: none;">🎙️ {title}</a>
                                    </h3>
                                    <span style="display: inline-block; background-color: #003366; color: #FFFFFF;
                                          padding: 3px 8px; font-size: 12px; border-radius: 4px; font-weight: bold;">Deutschlandfunk</span>
                                </div>
                                {f'<div style="font-family: Arial, sans-serif; font-size: 13px; color: #666; margin: 5px 0;">{series}</div>' if series else ''}
                                {f'<div style="font-family: Arial, sans-serif; font-size: 13px; color: #666; margin: 5px 0;">Episode {episode_number}</div>' if episode_number else ''}
                                {f'<div style="font-family: Arial, sans-serif; font-size: 13px; color: #666; margin: 5px 0;">{author}</div>' if author else ''}
                                <div style="margin: 10px 0; font-family: Arial, sans-serif; font-size: 14px; line-height: 1.5;">
                                    {description}
                                </div>
                                <div style="font-family: Arial, sans-serif; font-size: 12px; color: #003366;">
                                    {pub_date} {f'| Duration: {duration}' if duration else ''}
                                </div>
                                <div style="font-family: Arial, sans-serif; font-size: 12px; color: #5E9E9A; margin-top: 8px;">
                                    Keywords: {keywords_html}
                                </div>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            """
        else:
            # Original podcast styling for non-Deutschlandfunk podcasts
            podcast_html += f"""
            <tr>
                <td style="padding: 0 0 20px 0;">
                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #FFF7E6; border-radius: 8px;">
                        <tr>
                            <td style="padding: 15px;">
                                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px;">
                                    <h3 style="margin: 0; font-family: Arial, sans-serif; font-size: 16px;">
                                        <a href="{link}" style="color: #D2691E; text-decoration: none;">🎙️ {title}</a>
                                    </h3>
                                    <span style="display: inline-block; background-color: #FFE4B5; color: #D2691E;
                                          padding: 3px 8px; font-size: 12px; border-radius: 4px; font-weight: bold;">Podcast</span>
                                </div>
                                <div style="margin: 10px 0; font-family: Arial, sans-serif; font-size: 14px; line-height: 1.5;">
                                    {description}
                                </div>
                                <div style="font-family: Arial, sans-serif; font-size: 12px; color: #D2691E;">
                                    {pub_date} {f'| Duration: {duration}' if duration else ''}
                                </div>
                                <div style="font-family: Arial, sans-serif; font-size: 12px; color: #5E9E9A; margin-top: 8px;">
                                    Keywords: {keywords_html}
                                </div>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            """
    return podcast_html

def generate_html(articles, keyword_counts):
    """
    Generate a modern HTML report with the original article rendering style.

    Args:
        articles (list): List of article dictionaries
        keyword_counts (dict): Dictionary of keyword frequencies

    Returns:
        str: File path of generated HTML report
    """
    logging.info("Generating HTML report...")
    print("Generating HTML report...")
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    file_name = f"latest_articles_{timestamp}.html"
    file_path = os.path.join(OUTPUT_DIR, file_name)

    # Create the CSS file
    css_path = create_css_file()

    # Create the JavaScript file
    js_path = create_js_file()

    # Calculate article counts by source type - we still need this for logging
    rss_count = sum(1 for a in articles if ensure_str(a.get("source_type", "")) == "rss")
    email_count = sum(1 for a in articles if ensure_str(a.get("source_type", "")) == "email")
    academic_count = sum(1 for a in articles if ensure_str(a.get("source_type", "")) == "academic" or is_sciencedirect_article(a))
    podcast_count = sum(1 for a in articles if ensure_str(a.get("source_type", "")) == "podcast")  
    logging.info(f"Article breakdown: {rss_count} RSS articles, {email_count} email newsletters, {podcast_count} podcasts, {academic_count} academic papers")

    # Generate the executive summary - use the enhanced version
    executive_summary = enhanced_executive_summary(articles)

    # Executive Summary Section
    executive_summary_html = f"""
    <div class="executive-summary-container">
        <h3 class="executive-summary-title">Executive Summary</h3>
        <div class="executive-summary-content">
            {executive_summary}
        </div>
    </div>
    """

    # --- Keyword Statistics section is commented out ---
    # Keyword Bubbles Section
    # if keyword_counts:
    #     # Find the maximum count to scale bubbles appropriately
    #     try:
    #         # Make sure all values are integers
    #         normalized_counts = {k: ensure_int(v, 1) for k, v in keyword_counts.items()}
    #         max_count = max(normalized_counts.values()) if normalized_counts else 1
    #     except ValueError:
    #         # Fallback if there's an issue
    #         max_count = 1
    #
    #     min_size = 5  # Minimum bubble size in pixels
    #     max_size = 120  # Maximum bubble size in pixels
    #
    #     keyword_bubbles_html = ""
    #     for kw, count in keyword_counts.items():
    #         # Safe conversion of count to integer
    #         count_int = ensure_int(count, 1)
    #
    #         # Calculate bubble size based on count relative to max_count (safely)
    #         size_ratio = count_int / max_count if max_count > 0 else 1.0
    #         size = min_size + int(size_ratio * (max_size - min_size))
    #
    #         # Try to find a font size that keeps text inside the bubble.
    #         # If it doesn't fit at smaller font sizes, use alternative display
    #         text_content = f"{kw} ({count_int})"
    #         inside_bubble = False
    #         chosen_font_size = 10  # Start from a readable minimum font size
    #         for fs in range(20, 9, -1):
    #             # Quick check to see if text can fit in the bubble
    #             approx_width = len(text_content) * fs * 0.6
    #             approx_height = fs * 1.6  # extra space for line break
    #             if approx_width <= size * 0.9 and approx_height <= size * 0.9:
    #                 chosen_font_size = fs
    #                 inside_bubble = True
    #                 break
    #
    #         if inside_bubble:
    #             # Render text inside the bubble
    #             keyword_bubbles_html += f"""
    #             <div style="display: inline-block; position: relative; margin: 10px; width: {size}px; height: {size}px;
    #                         background-color: #00827C; border-radius: 50%; text-align: center;
    #                         vertical-align: middle; box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
    #                 <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
    #                            width: 90%; color: white; font-family: Arial, sans-serif; font-size: {chosen_font_size}px;
    #                            font-weight: bold; line-height: 1.2;">
    #                     {kw}<br><span style="font-size: smaller;">({count_int})</span>
    #                 </div>
    #             </div>
    #             """
    #         else:
    #             # Render text above the bubble (since it won't fit inside)
    #             keyword_bubbles_html += f"""
    #             <div style="display: inline-block; margin: 10px; text-align: center;">
    #                 <div style="font-family: Arial, sans-serif; font-weight: bold; font-size: 12px; color: #00827C; margin-bottom: 5px;">
    #                     {kw} ({count_int})
    #                 </div>
    #                 <div style="position: relative; width: {size}px; height: {size}px;
    #                             background-color: #00827C; border-radius: 50%; box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
    #                 </div>
    #             </div>
    #             """
    # else:
    #     # If no keywords matched, show empty stats
    #     keyword_bubbles_html = "<div style='padding: 15px; text-align: center; color: #666;'>No keyword matches found.</div>"

    # Articles Section (using original v02 style)
    if articles:
        article_entries_html = []
        for article in articles:
            title = ensure_str(article.get("title", "No Title"))
            source_type = ensure_str(article.get("source_type", "rss"))

            # Extract organization name
            organization = extract_organization_name(article)

            # Create organization tag
            org_tag = f"""<span class="organization-tag">{organization}</span>"""

            # Different styling based on the source type - using original v02 styling
            if source_type == "rss":
                raw_link = ensure_str(article.get("link", ""))
                link = extract_actual_url(raw_link)
                snippet = ensure_str(article.get("snippet", ""))
                keywords = article.get("keywords", [])

                # Build the keywords line (original v02 style)
                keywords_html = ""
                for kw in keywords:
                    keywords_html += f"<span style='display: inline-block; background-color: #BDD7D6; padding: 2px 5px; margin: 2px; border-radius: 3px;'>{ensure_str(kw)}</span> "

                article_entry = f"""
                <tr>
                    <td style="padding: 0 0 20px 0;">
                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #FFFFFF; border-radius: 8px;">
                            <tr>
                                <td style="padding: 15px;">
                                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px;">
                                        <h3 style="margin: 0; font-family: Arial, sans-serif; font-size: 16px;">
                                            <a href="{link}" style="color: #00827C; text-decoration: none;">{title}</a>
                                        </h3>
                                        <span style="display: inline-block; background-color: {COLORS["primary_light"]}; color: {COLORS["primary_dark"]};
                                              padding: 3px 8px; font-size: 12px; border-radius: 4px; font-weight: bold;">{organization}</span>
                                    </div>
                                    <div style="margin: 10px 0; font-family: Arial, sans-serif; font-size: 14px; line-height: 1.5;">
                                        {snippet}
                                    </div>
                                    <div style="font-family: Arial, sans-serif; font-size: 12px; color: #5E9E9A;">
                                        Keywords: {keywords_html}
                                    </div>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
                """
            elif source_type == "academic" or is_sciencedirect_article(article):
                # Special handling for academic papers and ScienceDirect articles
                raw_url = ensure_str(article.get("url", ""))
                url = extract_actual_url(raw_url)
                snippet = ensure_str(article.get("snippet", ""))
                keywords = article.get("keywords", [])
                authors = ensure_str(article.get("authors_formatted", ""))
                venue = ensure_str(article.get("venue", ""))
                year = ensure_str(article.get("year", ""))
                citation_count = ensure_int(article.get("citationCount", 0))
                doi = ensure_str(article.get("doi", ""))
                journal = ensure_str(article.get("journal", ""))
                volume = ensure_str(article.get("volume", ""))
                issue = ensure_str(article.get("issue", ""))

                # Build the keywords line (original v02 style)
                keywords_html = ""
                for kw in keywords:
                    keywords_html += f"<span style='display: inline-block; background-color: #BDD7D6; padding: 2px 5px; margin: 2px; border-radius: 3px;'>{ensure_str(kw)}</span> "

                # Add a note about the abstract source if it's not from the original paper
                abstract_source_html = ""
                if article.get("abstract_source") and article["abstract_source"] != "original":
                    source_type_text = ensure_str(article["abstract_source"])
                    abstract_source_html = f"""
                    <div style="font-style: italic; font-size: 11px; color: #666; margin-top: 5px;">
                        Note: Abstract {source_type_text}.
                    </div>
                    """

                # Special styling for ScienceDirect articles
                if is_sciencedirect_article(article):
                    background_color = "#F0F5FF"
                    border_color = "#FF6B00"  # ScienceDirect orange
                    source_badge = "ScienceDirect"
                else:
                    background_color = "#F0F5FF"
                    border_color = "#00827C"
                    source_badge = "Academic Paper"

                article_entry = f"""
                <tr>
                    <td style="padding: 0 0 20px 0;">
                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: {background_color}; border-radius: 8px; border-left: 4px solid {border_color};">
                            <tr>
                                <td style="padding: 15px;">
                                    <div style="display: flex; justify-content: space-between; align-items: center;">
                                        <div style="font-family: Arial, sans-serif; font-size: 11px; color: #666; margin-bottom: 5px;">
                                            {source_badge} {year} | {citation_count} citations
                                        </div>
                                        <span style="display: inline-block; background-color: {COLORS["primary_light"]}; color: {COLORS["primary_dark"]};
                                              padding: 3px 8px; font-size: 12px; border-radius: 4px; font-weight: bold;">{organization}</span>
                                    </div>
                                    <h3 style="margin: 0; font-family: Arial, sans-serif; font-size: 16px;">
                                        <a href="{url}" style="color: #00827C; text-decoration: none;">{title}</a>
                                    </h3>
                                    <div style="margin: 5px 0; font-family: Arial, sans-serif; font-size: 13px; font-style: italic; color: #666;">
                                        {authors}
                                    </div>
                                    {f'<div style="margin: 5px 0; font-family: Arial, sans-serif; font-size: 13px; color: #666;">{journal}</div>' if journal else ''}
                                    {f'<div style="margin: 5px 0; font-family: Arial, sans-serif; font-size: 13px; color: #666;">Volume {volume}, Issue {issue}</div>' if volume and issue else ''}
                                    {f'<div style="margin: 5px 0; font-family: Arial, sans-serif; font-size: 13px; color: #666;">DOI: {doi}</div>' if doi else ''}
                                    <div style="margin: 10px 0; font-family: Arial, sans-serif; font-size: 14px; line-height: 1.5;">
                                        {snippet}
                                        {abstract_source_html}
                                    </div>
                                    <div style="font-family: Arial, sans-serif; font-size: 12px; color: #5E9E9A;">
                                        Keywords: {keywords_html}
                                    </div>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
                """
            elif source_type == "email":
                sender = ensure_str(article.get("sender", "Unknown"))
                raw_webview_link = ensure_str(article.get("webview_link", ""))
                webview_link = extract_actual_url(raw_webview_link)
                relevant_links = article.get("relevant_links", [])
                attachment_filename = article.get("attachment_filename", None)
                snippet = ensure_str(article.get("snippet", ""))
                keywords = article.get("keywords", [])

                # Build the keywords line (original v02 style)
                keywords_html = ""
                for kw in keywords:
                    keywords_html += f"<span style='display: inline-block; background-color: #BDD7D6; padding: 2px 5px; margin: 2px; border-radius: 3px;'>{ensure_str(kw)}</span> "

                # Headline: link the title to the webview link if available
                if webview_link:
                    title_html = f'<a href="{webview_link}" style="color: #00827C; text-decoration: underline;">{title}</a>'
                else:
                    title_html = title

                # Only show related links if at least one link contains a matching keyword
                related_links_html = ""
                if relevant_links and keywords:
                    # Normalize keywords for matching
                    normalized_keywords = [ensure_str(kw).lower().strip() for kw in keywords]
                    links_list = ""
                    for i, link_item in enumerate(relevant_links):
                        if isinstance(link_item, (list, tuple)) and len(link_item) >= 2:
                            link_text, raw_link_url = link_item
                            link_url = extract_actual_url(raw_link_url)
                        else:
                            link_text = f"Related link {i+1}"
                            raw_link_url = ensure_str(link_item)
                            link_url = extract_actual_url(raw_link_url)
                        # Only include the link if it contains a matching keyword
                        link_text_normalized = ensure_str(link_text).lower()
                        if any(kw in link_text_normalized for kw in normalized_keywords):
                            links_list += f"\n<li style=\"margin-bottom: 5px;\">\n<a href=\"{ensure_str(link_url)}\" style=\"color: #00827C; text-decoration: underline;\">{ensure_str(link_text)}</a>\n</li>\n"
                    if links_list:
                        related_links_html = f"""
                        <div style="margin-top: 8px; font-family: Arial, sans-serif; font-size: 12px;">
                            <p style="margin-bottom: 5px; font-weight: bold;">Related links:</p>
                            <ul style="margin-top: 0; padding-left: 20px;">
                                {links_list}
                            </ul>
                        </div>
                        """

                # Add information about attachment if present (using updated EML text)
                attachment_html = ""
                if attachment_filename and ensure_str(attachment_filename).endswith(".eml"):
                    attachment_html = f"""
                    <div style="margin-top: 8px; font-family: Arial, sans-serif; font-size: 12px; background-color: #f0f7f7; padding: 5px; border-left: 3px solid #00827C;">
                        <p style="margin: 0;">📎 The original email is attached as \"{attachment_filename}\" - open with your email client</p>
                    </div>
                    """

                # Original v02 style for email newsletters with organization badge
                article_entry = f"""
                <tr>
                    <td style="padding: 0 0 20px 0;">
                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #F8F8FF; border-radius: 8px;">
                            <tr>
                                <td style="padding: 15px;">
                                    <div style="display: flex; justify-content: space-between; align-items: center;">
                                        <div style="font-family: Arial, sans-serif; font-size: 11px; color: #666; margin-bottom: 5px;">
                                            NEWSLETTER FROM: {sender}
                                        </div>
                                        <span style="display: inline-block; background-color: {COLORS["primary_light"]}; color: {COLORS["primary_dark"]};
                                              padding: 3px 8px; font-size: 12px; border-radius: 4px; font-weight: bold;">{organization}</span>
                                    </div>
                                    <h3 style="margin: 0; font-family: Arial, sans-serif; font-size: 16px; color: #444;">
                                        {title_html}
                                    </h3>
                                    <div style="margin: 10px 0; font-family: Arial, sans-serif; font-size: 14px; line-height: 1.5;">
                                        {snippet}
                                    </div>
                                    {related_links_html}
                                    {attachment_html}
                                    <div style="font-family: Arial, sans-serif; font-size: 12px; color: #5E9E9A;">
                                        Keywords: {keywords_html}
                                    </div>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
                """
            elif source_type == "podcast":
                podcast_entry = generate_podcast_section([article])
                article_entry = podcast_entry

            article_entries_html.append(article_entry)

        articles_block = "\n".join(article_entries_html)
    else:
        # If no articles found, display a message (original v02 style)
        articles_block = """
        <tr>
            <td style="padding: 0 0 20px 0;">
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #FFFFFF; border-radius: 8px;">
                    <tr>
                        <td style="padding: 15px;">
                            <h3 style="margin: 0; font-family: Arial, sans-serif; font-size: 16px; color: #333;">No Articles Found</h3>
                            <div style="margin: 10px 0; font-family: Arial, sans-serif; font-size: 14px; line-height: 1.5;">
                                There are no new articles that match the specified keywords within the last 24 hours.
                            </div>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        """

    # Preheader text for email clients
    preheader_text = f"Your daily digest: {len(articles)} articles found matching your keywords"

    # Additional CSS for the executive summary section and organization tags
    additional_css = """
    /* Executive Summary styling */
    .executive-summary-container {
        margin: 20px 15px;
        padding: 15px;
        background-color: var(--color-background-light);
        border-radius: var(--border-radius);
        border-left: 4px solid var(--color-primary);
        box-shadow: var(--box-shadow);
    }

    .executive-summary-title {
        color: var(--color-primary);
        margin-top: 0;
        margin-bottom: 10px;
        font-size: 1.2rem;
    }

    .executive-summary-content {
        font-family: var(--font-primary);
        line-height: 1.6;
        color: var(--color-text-medium);
    }

    /* Organization tag styling */
    .organization-tag {
        display: inline-block;
        background-color: var(--color-primary-light);
        color: var(--color-primary-dark);
        padding: 3px 8px;
        font-size: 12px;
        border-radius: 4px;
        font-weight: bold;
    }

    @media (prefers-color-scheme: dark) {
        .executive-summary-container {
            background-color: var(--color-background-alt);
        }

        .organization-tag {
            background-color: var(--color-primary-dark);
            color: var(--color-primary-light);
        }
    }
    """

    # Combine all sections to create the complete HTML document - mixing modern framework with original article rendering
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="color-scheme" content="light dark">
    <meta name="format-detection" content="telephone=no, date=no, address=no, email=no">
    <meta name="x-apple-disable-message-reformatting">
    <title>Latest Relevant Articles - {datetime.datetime.now().strftime('%Y-%m-%d')}</title>
   
    <style>
        /* Embedded critical CSS for email clients */
        body {{
            margin: 0;
            padding: 0;
            width: 100%;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.5;
            color: {COLORS["text_dark"]};
            background-color: {COLORS["background"]};
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
            background-color: {COLORS["background_alt"]};
            border-radius: 8px;
            overflow: hidden;
        }}
        .header {{
            background-color: {COLORS["primary"]};
            color: white;
            padding: 32px 24px;
            text-align: center;
        }}

        /* Executive Summary styling (inline) */
        .executive-summary-container {{
            margin: 20px 15px;
            padding: 15px;
            background-color: #f8f8ff;
            border-radius: 8px;
            border-left: 4px solid {COLORS["primary"]};
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        }}
        .executive-summary-title {{
            color: {COLORS["primary"]};
            margin-top: 0;
            margin-bottom: 10px;
            font-size: 1.2rem;
        }}
        .executive-summary-content {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: {COLORS["text_medium"]};
        }}

        /* Basic responsive adjustments for email clients */
        @media screen and (max-width: 600px) {{
            .container {{
                width: 100% !important;
            }}
        }}
        /* Dark mode for supported clients */
        @media (prefers-color-scheme: dark) {{
            body {{
                background-color: #232323;
                color: #f0f0f0;
            }}
            .container {{
                background-color: #2a2a2a;
            }}
            .executive-summary-container {{
                background-color: #333333;
            }}
        }}
    </style>

    <!-- Link to external CSS for web viewing -->
    <link rel="stylesheet" href="css/newsletter_styles.css">

    <!--[if mso]>
    <style type="text/css">
        /* Outlook-specific styles */
        table {{border-collapse: collapse;}}
        .mso-line-height-rule {{line-height: exactly 120%;}}
        body, table, td {{font-family: Arial, sans-serif;}}
    </style>
    <![endif]-->
</head>
<body>
    <!-- Preheader text (hidden) -->
    <div class="preheader">{preheader_text}</div>

    <!--[if mso]>
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="800" align="center" style="background-color: {COLORS["background"]};">
    <tr>
    <td>
    <![endif]-->

    <div class="container">
        <!-- Header -->
        <header class="header" role="banner">
            <h1>Latest Relevant Articles</h1>
            <p>Articles collected in the last 24 hours ({datetime.datetime.utcnow().strftime('%Y-%m-%d')})</p>
        </header>

        <!-- Executive Summary Section -->
        <section class="content-section" aria-labelledby="executive-summary">
            {executive_summary_html}
        </section>

    <!--
    <section class="content-section" aria-labelledby="keywords-header">
        <h2 id="keywords-header" class="section-header">Keyword Statistics</h2>
        <div style="padding: 15px; text-align: center;">
            
            <div style="font-family: Arial, sans-serif; font-size: 12px; color: #666; margin-top: 10px; text-align: center;">
                Bubble size represents frequency of keyword occurrence
            </div>
        </div>
    </section>
    -->

    <!-- Articles Section (using original v02 style) -->
    <section aria-labelledby="articles-header">
        <h2 id="articles-header" class="section-header">Articles</h2>
        <div>
            <!-- Original v02 table-based article layout -->
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="padding: 20px;">
                {articles_block}
            </table>
        </div>
    </section>

    <!-- Footer -->
    <footer class="footer" role="contentinfo">
        <p>Generated by v05 on-prem on {datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC</p>

    </footer>
</div>

    <!--[if mso]>
    </td>
    </tr>
    </table>
    <![endif]-->

    <!-- External JavaScript for interactive features when viewed in browser -->
    <script src="css/newsletter_scripts.js"></script>
</body>
</html>
"""

    # Update the CSS file to include executive summary styling
    with open(css_path, "r", encoding="utf-8") as css_file:
        css_content = css_file.read()

    if "executive-summary-container" not in css_content:
        # Add our executive summary styles to the CSS file
        css_content += additional_css
        with open(css_path, "w", encoding="utf-8") as css_file:
            css_file.write(css_content)

    # Write to file
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(html_content)

    logging.info(f"HTML report with executive summary generated successfully: {file_path}")
    print(f"HTML report with executive summary generated successfully: {file_path}")
    return file_path