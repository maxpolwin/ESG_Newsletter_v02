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

# Import modules
from config import EMAIL_RECIPIENTS, CLEANUP_THRESHOLD
from rss_processor import process_rss_feeds
from email_processor import process_email_newsletters, cleanup_old_emails
from html_generator import generate_html
from email_sender import send_email_with_attachments, send_latest_report
from system_tester import run_compatibility_check
from cleanup_files import cleanup_old_files


###########################################
# Main Program Functions
###########################################

# Import academic processor
from academic_processor import process_academic_papers


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

        # REORDERED: Finally process email newsletters
        logging.info("Finally processing email newsletters...")
        print("Finally processing email newsletters...")
        email_articles, email_keyword_counts, attachments = process_email_newsletters(cleanup_emails=True)
        logging.info(f"Processed {len(email_articles)} email newsletters with {len(attachments)} attachments")
        print(f"Processed {len(email_articles)} email newsletters with {len(attachments)} attachments")

        # Combine all articles from all sources
        all_articles = academic_articles + rss_articles + email_articles
        print(f"Total articles to include in report: {len(all_articles)}")

        # Combine keyword counts from all sources - start with academic counts
        all_keyword_counts = academic_keyword_counts.copy()

        # Add RSS keyword counts
        for keyword, count in rss_keyword_counts.items():
            all_keyword_counts[keyword] += count

        # Add email keyword counts
        for keyword, count in email_keyword_counts.items():
            all_keyword_counts[keyword] += count

        # Generate HTML report
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
        return False

###########################################
# Command Line Interface
###########################################

def show_help():
    """Show help message."""
    print(f"""
Newsletter System v08

Usage: python {sys.argv[0]} [command]

Commands:
  all      Process academic papers, RSS and email, generate report, send email (default)
  rss      Process only RSS feeds
  email    Process only email newsletters
  academic Process only academic papers
  cleanup  Clean up old emails
  files    Clean up old log and HTML files
  send     Send the latest report only
  test     Run compatibility tests
  help     Show this help message
    """)

def main():
    """Main entry point."""
    command = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    if command == "all":
        process_all()
    elif command == "rss":
        rss_articles, rss_counts = process_rss_feeds()
        print(f"Processed {len(rss_articles)} RSS articles")
    elif command == "email":
        email_articles, email_counts, attachments = process_email_newsletters(cleanup_emails=False)
        print(f"Processed {len(email_articles)} email newsletters with {len(attachments)} attachments")
    elif command == "academic":
        # Added command to process only academic papers
        academic_articles, academic_counts = process_academic_papers()
        print(f"Processed {len(academic_articles)} academic papers")
    elif command == "cleanup":
        deleted = cleanup_old_emails(days=CLEANUP_THRESHOLD)
        print(f"Cleaned up {deleted} old emails")
    elif command == "files":
        # Clean up old files
        stats = cleanup_old_files()
        print(f"Cleaned up {stats['logs_deleted']} logs, {stats['html_deleted']} HTML files, and {stats['attachments_deleted']} attachments")
    elif command == "send":
        send_latest_report()
    elif command == "test":
        run_compatibility_check()
    elif command in ["help", "-h", "--help"]:
        show_help()
    else:
        print(f"Unknown command: {command}")
        show_help()
        return 1

    return 0

# Import the function to clean up log files
#from log_entry_cleanup import cleanup_old_log_entries

# Call it with your log file path
#log_file = "/home/nbc4ss/ESG_Crawler_v02/ESG_Newsletter-main/latest_articles/newsletter_system.log"
#removed_count = cleanup_old_log_entries(log_file)
#print(f"Removed {removed_count} old log entries")

if __name__ == "__main__":
    sys.exit(main())