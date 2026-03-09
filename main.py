#!/usr/bin/env python3
"""

A comprehensive system for collecting, analyzing, and distributing newsletters.
This system processes both RSS feeds and email newsletters, searching for
specified keywords, and generates an HTML report that can be emailed.


This is the main entry point that coordinates all modules of the system.

Components (now separated into modules):
- RSS Feed Processing (rss_processor.py)
- Email Newsletter Processing (email_processor.py)
- HTML Report Generation (html_generator.py)
- Email Sending (email_sender.py)
- System Compatibility Testing (system_tester.py)
- File Cleanup (cleanup_files.py)
- Shared Utilities (utils.py)
- Configuration (config.py)


Commands:
- all: Process RSS and email, generate report, send email
- rss: Process only RSS feeds
- email: Process only email newsletters
- cleanup: Clean up old emails
- files: Clean up old log and HTML files
- send: Send the latest report only
- test: Run compatibility tests

Author: Max Polwin
"""

import sys
import logging
import traceback
import json
import os

# Import modules
from config import EMAIL_RECIPIENTS, CLEANUP_THRESHOLD, OUTPUT_DIR
from rss_processor import process_rss_feeds
from email_processor import process_email_newsletters, cleanup_old_emails
from html_generator import generate_html
from email_sender import send_email_with_attachments, send_latest_report
from system_tester import run_compatibility_check
from cleanup_files import cleanup_old_files
from academic_processor import process_academic_papers
from podcast_processor import process_podcasts
from youtube_processor import process_videos

USE_BROWSER_AUTOMATION = True

def process_all():
    """Process both RSS and email, generate report, and send email."""
    logging.info("Starting full newsletter processing...")
    print("Starting full newsletter processing...")

    try:
        # Add file cleanup at the beginning
        cleanup_stats = cleanup_old_files()
        logging.info(f"File cleanup: {cleanup_stats['logs_deleted']} logs, {cleanup_stats['html_deleted']} HTML files, and {cleanup_stats['attachments_deleted']} attachments deleted")
        print(f"File cleanup: {cleanup_stats['logs_deleted']} logs, {cleanup_stats['html_deleted']} HTML files, and {cleanup_stats['attachments_deleted']} attachments deleted")

        # REORDERED: First process academic papers (Semantic Scholar API)
        logging.info("Starting with academic papers processing...")
        print("Starting with academic papers processing...")
        academic_articles, academic_keyword_counts = process_academic_papers()
        logging.info(f"Processed {len(academic_articles)} academic papers")
        print(f"Processed {len(academic_articles)} academic papers")

        # REORDERED: Second process RSS feeds
        logging.info("Now processing RSS feeds...")
        print("Now processing RSS feeds...")
        rss_articles, rss_keyword_counts = process_rss_feeds()
        logging.info(f"Processed {len(rss_articles)} RSS articles")
        print(f"Processed {len(rss_articles)} RSS articles")

        # REORDERED: Process podcasts
        logging.info("Now processing podcasts...")
        print("Now processing podcasts...")
        podcast_articles, podcast_keyword_counts = process_podcasts()
        logging.info(f"Processed {len(podcast_articles)} podcast episodes")
        print(f"Processed {len(podcast_articles)} podcast episodes")

        # REORDERED: Process YouTube videos
        logging.info("Now processing YouTube videos...")
        print("Now processing YouTube videos...")
        youtube_articles, youtube_keyword_counts = process_videos()
        logging.info(f"Processed {len(youtube_articles)} YouTube videos")
        print(f"Processed {len(youtube_articles)} YouTube videos")

        # REORDERED: Finally process email newsletters
        logging.info("Finally processing email newsletters...")
        print("Finally processing email newsletters...")
        email_articles, email_keyword_counts, attachments = process_email_newsletters(cleanup_emails=True)
        logging.info(f"Processed {len(email_articles)} email newsletters with {len(attachments)} attachments")
        print(f"Processed {len(email_articles)} email newsletters with {len(attachments)} attachments")

        # Combine all articles from all sources
        all_articles = academic_articles + rss_articles + podcast_articles + youtube_articles + email_articles
        print(f"Total articles to include in report: {len(all_articles)}")

        # Combine keyword counts from all sources - start with academic counts
        all_keyword_counts = academic_keyword_counts.copy()

        # Add RSS keyword counts
        for keyword, count in rss_keyword_counts.items():
            all_keyword_counts[keyword] += count

        # Add podcast keyword counts
        for keyword, count in podcast_keyword_counts.items():
            all_keyword_counts[keyword] += count

        # Add YouTube keyword counts
        for keyword, count in youtube_keyword_counts.items():
            all_keyword_counts[keyword] += count

        # Add email keyword counts
        for keyword, count in email_keyword_counts.items():
            all_keyword_counts[keyword] += count

        # Save intermediate results as checkpoint before HTML generation
        # This prevents data loss if HTML generation crashes
        try:
            checkpoint_path = os.path.join(OUTPUT_DIR, "latest_checkpoint.json")
            checkpoint_data = {
                "articles": [
                    {k: str(v) if not isinstance(v, (str, int, float, bool, list, dict, type(None))) else v
                     for k, v in article.items()}
                    for article in all_articles
                ],
                "keyword_counts": dict(all_keyword_counts),
                "timestamp": str(datetime.datetime.utcnow()) if 'datetime' in dir() else "unknown"
            }
            with open(checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, default=str)
            print(f"Saved checkpoint with {len(all_articles)} articles to {checkpoint_path}")
        except Exception as cp_err:
            print(f"Warning: Could not save checkpoint: {cp_err}")

        # Generate HTML report only if we have articles
        if all_articles:
            html_file = generate_html(all_articles, all_keyword_counts)
            logging.info(f"Generated HTML report: {html_file}")
            print(f"Generated HTML report: {html_file}")

            # Send email with attachments
            success = send_email_with_attachments(html_file, EMAIL_RECIPIENTS, attachments)
            if success:
                logging.info("Email sent successfully")
                print("Email sent successfully")
            else:
                logging.warning("Failed to send email")
                print("Failed to send email")

            return True
        else:
            logging.warning("No articles found to include in report")
            print("No articles found to include in report - email will not be sent")
            return False

    except Exception as e:
        logging.error(f"Error in full processing: {e}", exc_info=True)
        print(f"Error in full processing: {e}")
        traceback.print_exc()  # Print full traceback to console for PythonAnywhere debugging
        return False



if __name__ == "__main__":
    sys.exit(process_all())