#!/usr/bin/env python3
"""
Email Deduplication System

This module handles persistent deduplication of emails across multiple runs
and days, similar to the academic and RSS deduplication systems.

Author: Max Polwin
"""

import os
import json
import logging
from datetime import datetime
from config import CACHE_DIR

def get_email_history():
    """
    Get the history of emails included in previous newsletters.
    Returns a set of email IDs that have been included before.
    """
    history_file = os.path.join(CACHE_DIR, "email_history.json")
    if not os.path.exists(history_file):
        return set()
        
    try:
        with open(history_file, 'r') as f:
            history_data = json.load(f)
            return set(history_data.get('email_ids', []))
    except Exception as e:
        logging.error(f"Error reading email history: {e}")
        return set()

def update_email_history(email_ids):
    """
    Update the history of emails included in newsletters.
    
    Args:
        email_ids (set): Set of email IDs to add to the history
    """
    history_file = os.path.join(CACHE_DIR, "email_history.json")
    try:
        # Read existing history
        existing_history = set()
        if os.path.exists(history_file):
            with open(history_file, 'r') as f:
                history_data = json.load(f)
                existing_history = set(history_data.get('email_ids', []))
        
        # Add new email IDs
        updated_history = existing_history.union(email_ids)
        
        # Save updated history
        with open(history_file, 'w') as f:
            json.dump({
                'email_ids': list(updated_history),
                'last_updated': datetime.now().isoformat()
            }, f)
            
        logging.info(f"Updated email history with {len(email_ids)} new emails")
    except Exception as e:
        logging.error(f"Error updating email history: {e}")

def filter_duplicate_emails(emails):
    """
    Filter out emails that have been included in previous newsletters.
    
    Args:
        emails (list): List of email dictionaries to filter
        
    Returns:
        list: Filtered list of emails with duplicates removed
    """
    # Get email history
    history = get_email_history()
    logging.info(f"Loaded {len(history)} emails from history")
    
    # Filter out duplicates
    filtered_emails = []
    duplicate_count = 0
    
    for email in emails:
        email_id = email.get('email_id')
        if email_id and email_id not in history:
            filtered_emails.append(email)
        else:
            duplicate_count += 1
            
    if duplicate_count > 0:
        logging.info(f"Filtered out {duplicate_count} duplicate emails")
        
    # Update history with new emails
    new_email_ids = {email.get('email_id') for email in filtered_emails if email.get('email_id')}
    if new_email_ids:
        update_email_history(new_email_ids)
        
    return filtered_emails

def generate_email_id(subject, sender, date):
    """
    Generate a unique ID for an email based on its metadata.
    
    Args:
        subject (str): Email subject
        sender (str): Email sender
        date (str): Email date
        
    Returns:
        str: Unique email ID
    """
    # Create a string combining the unique identifiers
    unique_str = f"{subject}|{sender}|{date}"
    
    # Generate a hash of the string
    import hashlib
    return hashlib.md5(unique_str.encode()).hexdigest()

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Test the module
    test_emails = [
        {
            'subject': 'Test Email 1',
            'sender': 'test@example.com',
            'date': '2024-03-20',
            'email_id': generate_email_id('Test Email 1', 'test@example.com', '2024-03-20')
        },
        {
            'subject': 'Test Email 2',
            'sender': 'test@example.com',
            'date': '2024-03-20',
            'email_id': generate_email_id('Test Email 2', 'test@example.com', '2024-03-20')
        }
    ]
    
    # Test filtering
    filtered = filter_duplicate_emails(test_emails)
    print(f"Filtered {len(filtered)} emails") 