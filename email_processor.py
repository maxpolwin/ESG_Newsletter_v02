#!/usr/bin/env python3
"""
Newsletter System v07 - Email Newsletter Processor

Handles fetching, parsing, filtering of email newsletters.
Extracts relevant content, saves attachments, and cleans up old emails.

Author: Max Polwin
"""

import os
import re
import time
import imaplib
import email
import logging
import datetime
import gc
from bs4 import BeautifulSoup
from collections import Counter

# Import configuration and utilities
from config import (
    EMAIL_HOST, EMAIL_USER, EMAIL_PASSWORD, TRUSTED_SENDERS,
    KEYWORDS, NEGATIVE_KEYWORDS, TIME_THRESHOLD, CLEANUP_THRESHOLD,
    ATTACHMENTS_DIR
)
from utils import (
    normalize_text, decode_email_header, generate_email_id,
    sanitize_filename, extract_text_from_html
)

def extract_images_from_email(html_content):
    """Extract image URLs from email HTML content."""
    if not html_content:
        return []

    image_urls = []
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        images = soup.find_all('img')

        for img in images:
            # Skip small icons and spacers (common in emails)
            width = img.get('width', '0')
            height = img.get('height', '0')

            try:
                width_val = int(width) if width.isdigit() else 0
                height_val = int(height) if height.isdigit() else 0

                # Skip tiny images (likely spacers or icons)
                if width_val < 20 or height_val < 20:
                    continue
            except:
                # If we can't parse the dimensions, include the image anyway
                pass

            # Get the image URL
            src = img.get('src', '')
            if src and not src.startswith('data:'):  # Skip data URLs
                image_urls.append(src)

                # We only need one good image
                if len(image_urls) >= 1:
                    break
    except Exception as e:
        logging.error(f"Error extracting images from HTML: {e}")

    return image_urls

def extract_text_from_email(msg):
    """Extract text from email parts, handling both plain text and HTML."""
    text_content = ""
    html_content = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            # Skip attachments
            if "attachment" in content_disposition:
                continue

            # Get the payload
            payload = part.get_payload(decode=True)
            if payload is None:
                continue

            if content_type == "text/plain":
                text_content += payload.decode('utf-8', errors='ignore')
            elif content_type == "text/html":
                html_content += payload.decode('utf-8', errors='ignore')
    else:
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True)

        if payload is None:
            return "", None

        if content_type == "text/plain":
            text_content = payload.decode('utf-8', errors='ignore')
        elif content_type == "text/html":
            html_content = payload.decode('utf-8', errors='ignore')

    # Prefer HTML content as it's more informative, but fall back to plain text
    if html_content:
        return extract_text_from_html(html_content), html_content
    else:
        return text_content, None

def fetch_email_newsletters():
    """Fetch email newsletters from a mailbox within the time threshold."""
    logging.info("Fetching email newsletters...")
    print("Fetching email newsletters...")
    now = time.time()
    newsletters = []
    unique_email_ids = set()
    mail = None

    try:
        # Verify credentials exist
        if not EMAIL_USER or not EMAIL_PASSWORD:
            logging.error("Email credentials missing. Cannot fetch newsletters.")
            print("Email credentials missing. Cannot fetch newsletters.")
            return []

        # Connect to the mail server
        mail = imaplib.IMAP4_SSL(EMAIL_HOST)
        mail.login(EMAIL_USER, EMAIL_PASSWORD)
        mail.select('INBOX')

        # Search for all emails from the past 24 hours
        date_since = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%d-%b-%Y")

        # Use a simpler IMAP search that will work with most servers
        # First, just search for emails since the date
        search_criteria = f'SINCE {date_since}'  # Removed parentheses which some servers don't like

        try:
            print(f"Searching for emails with criteria: {search_criteria}")
            status, data = mail.search(None, search_criteria)
            if status != 'OK':
                logging.error(f"IMAP search failed with status: {status}")
                print(f"IMAP search failed with status: {status}")
                return []

            email_ids = data[0].split()
            if not email_ids:
                print("No emails found matching the date criteria")
                return []

            print(f"Found {len(email_ids)} emails from the past 24 hours")
        except imaplib.IMAP4.error as e:
            logging.error(f"IMAP search error: {e}")
            print(f"IMAP search error: {e}")
            return []
        except Exception as e:
            logging.error(f"Unexpected error during email search: {e}")
            print(f"Unexpected error during email search: {e}")
            return []

        logging.info(f"Found {len(email_ids)} emails from the past 24 hours.")

        # Process in smaller batches to be PythonAnywhere friendly
        batch_size = 10  # Adjust based on memory constraints
        for i in range(0, len(email_ids), batch_size):
            batch = email_ids[i:i+batch_size]
            logging.info(f"Processing email batch {i//batch_size + 1}/{(len(email_ids) + batch_size - 1)//batch_size}")
            print(f"Processing email batch {i//batch_size + 1}/{(len(email_ids) + batch_size - 1)//batch_size}")

            for email_id in batch:
                try:
                    # Fetch email with timeout
                    status, data = mail.fetch(email_id, '(RFC822)')
                    if status != 'OK':
                        logging.warning(f"Failed to fetch email {email_id}")
                        continue

                    raw_email = data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    # Extract email metadata
                    from_header = decode_email_header(msg.get("From", ""))
                    subject = decode_email_header(msg.get("Subject", ""))
                    date_str = msg.get("Date", "")

                    # Extract sender email from the From header
                    sender_email = re.search(r'<([^>]+)>', from_header)
                    if sender_email:
                        sender_email = sender_email.group(1).lower()
                    else:
                        sender_email = from_header.lower()

                    # Extract sender domain for source info
                    sender_domain = sender_email.split('@')[-1] if '@' in sender_email else ''

                    # Check if this is from a trusted sender - we'll do this in Python code instead of IMAP search
                    is_trusted = any(trusted.lower() in sender_email.lower() for trusted in TRUSTED_SENDERS)
                    if not is_trusted:
                        logging.debug(f"Skipping untrusted sender: {sender_email}")
                        continue

                    # Parse date to timestamp
                    try:
                        date_tuple = email.utils.parsedate_tz(date_str)
                        if date_tuple:
                            timestamp = email.utils.mktime_tz(date_tuple)
                        else:
                            timestamp = time.time()
                    except Exception as e:
                        logging.warning(f"Error parsing date {date_str}: {e}")
                        timestamp = time.time()

                    # Skip if outside time threshold
                    if (now - timestamp) > TIME_THRESHOLD:
                        continue

                    # Generate a unique ID for this email
                    email_id_hash = generate_email_id(from_header, subject, timestamp)

                    if email_id_hash in unique_email_ids:
                        continue

                    unique_email_ids.add(email_id_hash)

                    # Extract text content from the email
                    text_content, html_content = extract_text_from_email(msg)

                    # Extract images from HTML if available
                    image_urls = extract_images_from_email(html_content) if html_content else []

                    # Store newsletter data with the raw email content
                    newsletters.append({
                        "sender": from_header,
                        "subject": subject,
                        "date": timestamp,
                        "text_content": text_content,
                        "html_content": html_content,
                        "email_id": email_id_hash,
                        "raw_email": raw_email,  # Store the raw email data
                        "source_info": {
                            "title": from_header,
                            "domain": sender_domain,
                            "email": sender_email
                        },
                        "image_urls": image_urls
                    })

                    # Print found newsletters for debugging
                    print(f"Found newsletter from: {sender_email}, Subject: {subject[:30]}...")
                except Exception as e:
                    logging.error(f"Error processing email {email_id}: {e}")
                    print(f"Error processing email {email_id}: {e}")
                    continue

            # Free memory after each batch
            gc.collect()

        logging.info(f"Successfully fetched {len(newsletters)} unique newsletters.")
        print(f"Successfully fetched {len(newsletters)} unique newsletters.")
        return newsletters

    except imaplib.IMAP4.error as e:
        logging.error(f"IMAP error: {e}", exc_info=True)
        print(f"IMAP error: {e}")
        return []
    except Exception as e:
        logging.error(f"Error fetching emails: {e}", exc_info=True)
        print(f"Error fetching emails: {e}")
        return []
    finally:
        if mail:
            try:
                mail.close()
                mail.logout()
            except:
                pass  # Ignore errors during cleanup

def filter_newsletters(newsletters):
    """Filter newsletters based on keywords."""
    logging.info("Filtering relevant newsletter content...")
    print("Filtering relevant newsletter content...")
    filtered_content = []
    keyword_counts = Counter()
    attachments = []  # List to track attachments

    for newsletter in newsletters:
        sender = newsletter["sender"]
        subject = newsletter["subject"]
        text_content = newsletter["text_content"]
        html_content = newsletter.get("html_content", "")
        email_id = newsletter["email_id"]
        raw_email = newsletter.get("raw_email", None)  # Get the raw email data
        source_info = newsletter.get("source_info", {})
        image_urls = newsletter.get("image_urls", [])

        # Extract links from HTML content - look for "View in browser" or similar links
        webview_link = None
        article_links = []

        if html_content:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Look for webview/browser view links with specific patterns
            webview_patterns = [
                "view in browser", "view online", "web version", "view as webpage",
                "read online", "open in browser", "read in browser", "View this email in your browser",
                "View this email in your browser", "Im Browser anzeigen", "View email in browser",
                "View in browser", "View it in your browser.", "Having trouble viewing this email? Click here to open it in a web browser.",
                "View this email in your browser", "Diese E-Mail im Browser darstellen.",
                "Wird diese E-Mail nicht richtig angezeigt? Im Browser öffnen", "Browser View"
                "View this email in your browser", "Im Browser öffnen und Ergänzungen lesen.",
                "View this email in your browser", "Click here to view in your browser", "heatmapdaily_logo"
            ]
            
            # Extract all links for potential article references
            all_links = []
            substack_app_link = None
            for link in soup.find_all('a', href=True):
                link_text = link.get_text().lower().strip()
                href = link['href']
                
                # Check for webview link
                if any(pattern in link_text for pattern in webview_patterns):
                    webview_link = href
                    continue
                # Check for Substack app-link as fallback
                if href.startswith("@https://substack.com/app-link/post?publication_id="):
                    substack_app_link = href
                
                # Skip unwanted links
                skip_patterns = ["unsubscribe", "get more in the substack app", "manage email preferences"]
                if not any(pattern in link_text.lower() for pattern in skip_patterns):
                    all_links.append((link_text, href))
            # If no webview link found, use the Substack app-link if available
            if not webview_link and substack_app_link:
                webview_link = substack_app_link
            
            article_links = all_links

        # Combine text for searching keywords (include subject for better matching)
        full_text = f"{subject} {text_content}".strip()
        full_text_normalized = normalize_text(full_text)

        # Add spaces at beginning and end for word boundary checks
        padded_text = " " + full_text_normalized + " "

        # Check for keyword matches - respecting space requirements
        matched_keywords = []
        for kw in KEYWORDS:
            kw_normalized = normalize_text(kw)

            # Check if the keyword already has spaces specified
            if kw.startswith(" ") or kw.endswith(" "):
                # For keywords with explicit spaces, match exactly as specified
                if kw_normalized in padded_text:
                    matched_keywords.append(kw)
            else:
                # For keywords without explicit spaces, allow them to be part of other words
                if kw_normalized in full_text_normalized:
                    matched_keywords.append(kw)

        # Check for negative keywords (exclusions) - same space handling logic
        excluded_keywords = []
        for kw in NEGATIVE_KEYWORDS:
            kw_normalized = normalize_text(kw)

            if kw.startswith(" ") or kw.endswith(" "):
                # For keywords with explicit spaces, match exactly as specified
                if kw_normalized in padded_text:
                    excluded_keywords.append(kw)
            else:
                # For keywords without explicit spaces, allow them to be part of other words
                if kw_normalized in full_text_normalized:
                    excluded_keywords.append(kw)

        # Only include newsletters that match at least one positive keyword and no negative keywords
        if matched_keywords and not excluded_keywords:
            filtered_content.append({
                "title": subject,
                "sender": sender,
                "snippet": text_content[:800] + "..." if len(text_content) > 800 else text_content,  # Use full text as snippet
                "keywords": matched_keywords,
                "email_id": email_id,
                "source_type": "email",  # Mark this as coming from email
                "source_info": source_info,
                "webview_link": webview_link,  # Store webview link
                "relevant_links": article_links,  # Store all article links
                "attachment_filename": None,  # Will be set if needed
                "image_urls": image_urls,  # Store any extracted image URLs
                "full_text": text_content  # Add the full text content for executive summary generation
            })
            # Process attachments and update keyword counts
            for kw in matched_keywords:
                keyword_counts[kw] += 1

            # Save the original email as an EML file using the newsletter's title (subject)
            if raw_email:
                # Create a safe filename based on the newsletter's title (subject)
                safe_filename = sanitize_filename(subject) + ".eml"
                attachment_path = os.path.join(ATTACHMENTS_DIR, safe_filename)

                # Check if file already exists, and add a counter if needed
                if os.path.exists(attachment_path):
                    counter = 1
                    base_name = safe_filename[:-4]  # Remove .eml
                    while os.path.exists(attachment_path):
                        safe_filename = f"{base_name}_{counter}.eml"
                        attachment_path = os.path.join(ATTACHMENTS_DIR, safe_filename)
                        counter += 1

                # Save the raw email data to a file
                try:
                    with open(attachment_path, 'wb') as file:  # Use binary mode for raw email data
                        file.write(raw_email)
                    logging.info(f"Saved original email as EML attachment: {attachment_path}")
                    print(f"Saved original email as EML attachment: {attachment_path}")
                    attachments.append(attachment_path)
                    # Update the attachment filename in the filtered content
                    filtered_content[-1]["attachment_filename"] = safe_filename
                except Exception as e:
                    logging.error(f"Error saving email as EML attachment: {e}")
                    print(f"Error saving email as EML attachment: {e}")
        elif excluded_keywords:
            logging.info(f"Excluded newsletter due to negative keyword match: {subject}")

    logging.info(f"Filtered relevant newsletter content: {len(filtered_content)}")
    logging.info(f"Created {len(attachments)} EML attachments")
    print(f"Filtered relevant newsletter content: {len(filtered_content)}")
    print(f"Created {len(attachments)} EML attachments")
    return filtered_content, keyword_counts, attachments

def cleanup_old_emails(days=CLEANUP_THRESHOLD):
    """
    Delete emails that are older than the specified number of days.

    Args:
        days (int): Number of days old an email must be to be deleted

    Returns:
        int: Number of emails deleted
    """
    logging.info(f"Starting cleanup of emails older than {days} days...")
    print(f"Starting cleanup of emails older than {days} days...")

    # Verify credentials exist
    if not EMAIL_USER or not EMAIL_PASSWORD:
        logging.error("Email credentials missing. Cannot clean up emails.")
        print("Email credentials missing. Cannot clean up emails.")
        return 0

    deleted_count = 0
    mail = None

    try:
        # Connect to the mail server
        mail = imaplib.IMAP4_SSL(EMAIL_HOST)
        mail.login(EMAIL_USER, EMAIL_PASSWORD)
        mail.select('INBOX')

        # Calculate the date threshold (current date - days)
        date_threshold = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%d-%b-%Y")

        # Search for all emails older than the threshold date - simplified syntax
        # BEFORE operator in IMAP is non-inclusive of the specified date
        search_criteria = f'BEFORE {date_threshold}'  # Removed parentheses

        print(f"Searching for emails with criteria: {search_criteria}")
        status, data = mail.search(None, search_criteria)
        if status != 'OK':
            logging.error(f"IMAP search failed with status: {status}")
            print(f"IMAP search failed with status: {status}")
            return 0

        email_ids = data[0].split()
        total_emails = len(email_ids)
        logging.info(f"Found {total_emails} emails older than {days} days")
        print(f"Found {total_emails} emails older than {days} days")

        if not email_ids:
            logging.info("No old emails to delete")
            print("No old emails to delete")
            return 0

        # Process in batches to be more efficient
        batch_size = 50  # Adjust based on your needs
        for i in range(0, len(email_ids), batch_size):
            batch = email_ids[i:i+batch_size]

            # Convert list of IDs to comma-separated string
            ids_to_delete = b','.join(batch)

            # Mark emails for deletion
            mail.store(ids_to_delete, '+FLAGS', '\\Deleted')
            deleted_count += len(batch)

            logging.info(f"Marked batch of {len(batch)} emails for deletion ({i+len(batch)}/{total_emails})")
            print(f"Marked batch of {len(batch)} emails for deletion ({i+len(batch)}/{total_emails})")

        # Permanently remove emails marked for deletion
        mail.expunge()

        logging.info(f"Successfully deleted {deleted_count} old emails")
        print(f"Successfully deleted {deleted_count} old emails")
        return deleted_count

    except imaplib.IMAP4.error as e:
        logging.error(f"IMAP error during cleanup: {e}", exc_info=True)
        print(f"IMAP error during cleanup: {e}")
        return 0
    except Exception as e:
        logging.error(f"Error during email cleanup: {e}", exc_info=True)
        print(f"Error during email cleanup: {e}")
        return 0
    finally:
        if mail:
            try:
                mail.close()
                mail.logout()
            except:
                pass  # Ignore errors during cleanup

def process_email_newsletters(max_retries=3, cleanup_emails=True):
    """
    Main function to process email newsletters with retry logic and optional cleanup.

    Args:
        max_retries (int): Maximum number of retry attempts for transient errors
        cleanup_emails (bool): Whether to delete old emails after processing

    Returns:
        tuple: (filtered_content, keyword_counts, attachments)
    """
    retry_count = 0
    while retry_count < max_retries:
        try:
            newsletters = fetch_email_newsletters()

            if newsletters:
                filtered_content, keyword_counts, attachments = filter_newsletters(newsletters)

                # Clean up old emails after successfully fetching and processing
                if cleanup_emails:
                    try:
                        deleted_count = cleanup_old_emails(days=CLEANUP_THRESHOLD)
                        logging.info(f"Cleanup completed: {deleted_count} old emails deleted")
                        print(f"Cleanup completed: {deleted_count} old emails deleted")
                    except Exception as cleanup_error:
                        logging.error(f"Email cleanup failed but continuing processing: {cleanup_error}")
                        print(f"Email cleanup failed but continuing processing: {cleanup_error}")

                return filtered_content, keyword_counts, attachments
            else:
                # Even if no newsletters were found, we can still clean up old emails
                if cleanup_emails:
                    try:
                        deleted_count = cleanup_old_emails(days=CLEANUP_THRESHOLD)
                        logging.info(f"Cleanup completed: {deleted_count} old emails deleted")
                        print(f"Cleanup completed: {deleted_count} old emails deleted")
                    except Exception as cleanup_error:
                        logging.error(f"Email cleanup failed: {cleanup_error}")
                        print(f"Email cleanup failed: {cleanup_error}")

                return [], Counter(), []

        except (imaplib.IMAP4.abort, ConnectionResetError) as e:
            # These are transient errors, so we can retry
            retry_count += 1
            logging.warning(f"Transient error (attempt {retry_count}/{max_retries}): {e}")
            print(f"Transient error (attempt {retry_count}/{max_retries}): {e}")
            time.sleep(10)  # Wait before retrying
        except Exception as e:
            # For other errors, log and exit
            logging.error(f"Non-recoverable error: {e}", exc_info=True)
            print(f"Non-recoverable error: {e}")
            return [], Counter(), []

    # If we got here, we've exhausted our retries
    logging.error(f"Failed to process newsletters after {max_retries} attempts")
    print(f"Failed to process newsletters after {max_retries} attempts")
    return [], Counter(), []
