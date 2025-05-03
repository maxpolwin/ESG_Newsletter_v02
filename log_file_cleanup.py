#!/usr/bin/env python3
import os
import re
import datetime
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger()

def cleanup_old_log_entries(log_file_path, retention_hours=48):
    """
    Remove log entries older than specified retention hours, keeping the file.

    Args:
        log_file_path (str): Path to the log file
        retention_hours (int): Number of hours to keep log entries

    Returns:
        int: Number of log entries removed
    """
    try:
        # Calculate cutoff time (48 hours ago)
        cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=retention_hours)

        # Create a temporary file to write the filtered content
        temp_file_path = log_file_path + ".tmp"

        removed_entries = 0
        kept_entries = 0

        # Regular expression to extract timestamp from log entries
        # Format: 2025-03-26 17:57:54,671
        timestamp_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')

        # Process the log file line by line
        with open(log_file_path, 'r') as input_file, open(temp_file_path, 'w') as output_file:
            for line in input_file:
                # Check if this is a "Log rotated" line
                if line.startswith("Log rotated at "):
                    rotation_timestamp_str = line.strip().replace("Log rotated at ", "").replace("_", " ").replace("-", ":")
                    try:
                        # Convert rotation timestamp to datetime for comparison
                        rotation_timestamp = datetime.datetime.strptime(rotation_timestamp_str, "%Y:%m:%d %H:%M:%S")
                        if rotation_timestamp >= cutoff_time:
                            output_file.write(line)
                            kept_entries += 1
                        else:
                            removed_entries += 1
                    except ValueError:
                        # If timestamp parsing fails, keep the line to be safe
                        output_file.write(line)
                        kept_entries += 1
                    continue

                # Try to extract timestamp for regular log entries
                match = timestamp_pattern.match(line)
                if match:
                    timestamp_str = match.group(1)
                    try:
                        # Convert log timestamp to datetime for comparison
                        entry_timestamp = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                        if entry_timestamp >= cutoff_time:
                            output_file.write(line)
                            kept_entries += 1
                        else:
                            removed_entries += 1
                    except ValueError:
                        # If timestamp parsing fails, keep the line to be safe
                        output_file.write(line)
                        kept_entries += 1
                else:
                    # If there's no timestamp, keep the line (could be continuation of previous line)
                    output_file.write(line)
                    kept_entries += 1

        # Replace the original file with the filtered one
        os.replace(temp_file_path, log_file_path)

        logger.info(f"Log cleanup complete: {removed_entries} entries removed, {kept_entries} entries kept")
        return removed_entries

    except Exception as e:
        logger.error(f"Error during log cleanup: {str(e)}")
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)  # Clean up temp file in case of error
        return 0

def main():
    # Path to the log file
    log_file_path = "/home/nbc4ss/ESG_Crawler_v02/ESG_Newsletter-main/latest_articles/newsletter_system.log"

    # Run cleanup and get number of deleted entries
    logger.info("Starting log entry cleanup process")
    deleted_entries = cleanup_old_log_entries(log_file_path)

    # Log summary
    logger.info(f"Log cleanup complete: {deleted_entries} entries removed")
    logger.info(f"Next cleanup will remove entries older than {datetime.datetime.now() - datetime.timedelta(hours=48)}")

if __name__ == "__main__":
    main()