#!/usr/bin/env python3
"""
Newsletter System v07 - Cleanup Module

Handles deletion of old log files and newsletter HTML files.
Designed to keep the system clean and prevent disk space issues.

Author: Max Polwin
"""

import os
import time
import logging
import datetime
import glob
import shutil
from pathlib import Path

# Import configuration
from config import OUTPUT_DIR, CSS_DIR, ATTACHMENTS_DIR

def get_file_age_days(file_path):
    """Get the age of a file in days."""
    try:
        mtime = os.path.getmtime(file_path)
        age_seconds = time.time() - mtime
        return age_seconds / (60 * 60 * 24)  # Convert to days
    except Exception as e:
        logging.error(f"Error getting age of file {file_path}: {e}")
        return 0

def cleanup_old_files(log_days=2, html_days=7, attachments_days=7):
    """
    Clean up old log and HTML files.

    Args:
        log_days (int): Delete log files older than this many days
        html_days (int): Delete HTML files older than this many days
        attachments_days (int): Delete attachment files older than this many days

    Returns:
        dict: Statistics on deleted files
    """
    logging.info(f"Starting file cleanup: logs > {log_days} days, HTML > {html_days} days, attachments > {attachments_days} days")
    print(f"Starting file cleanup: logs > {log_days} days, HTML > {html_days} days, attachments > {attachments_days} days")

    stats = {
        "logs_deleted": 0,
        "html_deleted": 0,
        "attachments_deleted": 0,
        "errors": 0
    }

    # Create a timestamp string for logging
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    try:
        # Process log files
        log_pattern = os.path.join(OUTPUT_DIR, "*.log")
        log_pattern_with_date = os.path.join(OUTPUT_DIR, "newsletter_system_*.log")

        # Find all log files (both patterns)
        log_files = glob.glob(log_pattern) + glob.glob(log_pattern_with_date)

        for log_file in log_files:
            # Skip the currently active log
            if os.path.basename(log_file) == "newsletter_system.log":
                continue

            file_age = get_file_age_days(log_file)
            if file_age > log_days:
                try:
                    os.remove(log_file)
                    stats["logs_deleted"] += 1
                    logging.info(f"Deleted log file: {log_file} (age: {file_age:.1f} days)")
                    print(f"Deleted log file: {os.path.basename(log_file)} (age: {file_age:.1f} days)")
                except Exception as e:
                    logging.error(f"Error deleting log file {log_file}: {e}")
                    stats["errors"] += 1

        # Process HTML files
        html_pattern = os.path.join(OUTPUT_DIR, "latest_articles_*.html")
        html_files = glob.glob(html_pattern)

        # Sort by modification time to keep the most recent ones
        html_files.sort(key=os.path.getmtime, reverse=True)

        # Always keep at least the 3 most recent HTML files regardless of age
        html_files_to_check = html_files[3:] if len(html_files) > 3 else []

        for html_file in html_files_to_check:
            file_age = get_file_age_days(html_file)
            if file_age > html_days:
                try:
                    os.remove(html_file)
                    stats["html_deleted"] += 1
                    logging.info(f"Deleted HTML file: {html_file} (age: {file_age:.1f} days)")
                    print(f"Deleted HTML file: {os.path.basename(html_file)} (age: {file_age:.1f} days)")
                except Exception as e:
                    logging.error(f"Error deleting HTML file {html_file}: {e}")
                    stats["errors"] += 1

        # Process attachment files
        if os.path.exists(ATTACHMENTS_DIR):
            attachment_files = []
            for ext in ['*.eml', '*.html', '*.pdf', '*.docx', '*.xlsx']:
                attachment_files.extend(glob.glob(os.path.join(ATTACHMENTS_DIR, ext)))

            for attachment_file in attachment_files:
                file_age = get_file_age_days(attachment_file)
                if file_age > attachments_days:
                    try:
                        os.remove(attachment_file)
                        stats["attachments_deleted"] += 1
                        logging.info(f"Deleted attachment: {attachment_file} (age: {file_age:.1f} days)")
                        print(f"Deleted attachment: {os.path.basename(attachment_file)} (age: {file_age:.1f} days)")
                    except Exception as e:
                        logging.error(f"Error deleting attachment {attachment_file}: {e}")
                        stats["errors"] += 1

        # Clean up empty subdirectories in OUTPUT_DIR
        for root, dirs, files in os.walk(OUTPUT_DIR, topdown=False):
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                # Skip CSS_DIR and ATTACHMENTS_DIR
                if dir_path == CSS_DIR or dir_path == ATTACHMENTS_DIR:
                    continue

                # If directory is empty, remove it
                if not os.listdir(dir_path):
                    try:
                        os.rmdir(dir_path)
                        logging.info(f"Removed empty directory: {dir_path}")
                        print(f"Removed empty directory: {dir_path}")
                    except Exception as e:
                        logging.error(f"Error removing directory {dir_path}: {e}")
                        stats["errors"] += 1

        # Rotate the current log file if it exists and is larger than 1MB
        current_log = os.path.join(OUTPUT_DIR, "newsletter_system.log")
        if os.path.exists(current_log) and os.path.getsize(current_log) > 1024 * 1024:
            try:
                # Create a backup with timestamp
                backup_log = os.path.join(OUTPUT_DIR, f"newsletter_system_{timestamp}.log")
                shutil.copy2(current_log, backup_log)
                # Clear the current log file but don't delete it
                with open(current_log, 'w') as f:
                    f.write(f"Log rotated at {timestamp}\n")
                logging.info(f"Rotated log file to: {backup_log}")
                print(f"Rotated log file to: {os.path.basename(backup_log)}")
            except Exception as e:
                logging.error(f"Error rotating log file: {e}")
                stats["errors"] += 1

    except Exception as e:
        logging.error(f"Error during file cleanup: {e}")
        stats["errors"] += 1
        print(f"Error during file cleanup: {e}")

    # Log summary statistics
    total_deleted = stats["logs_deleted"] + stats["html_deleted"] + stats["attachments_deleted"]
    logging.info(f"Cleanup complete: {total_deleted} files deleted ({stats['logs_deleted']} logs, {stats['html_deleted']} HTML, {stats['attachments_deleted']} attachments)")
    print(f"Cleanup complete: {total_deleted} files deleted ({stats['logs_deleted']} logs, {stats['html_deleted']} HTML, {stats['attachments_deleted']} attachments)")

    return stats

if __name__ == "__main__":
    # When run directly, clean up files with default settings
    cleanup_old_files()