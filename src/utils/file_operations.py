#!/usr/bin/env python3
"""
File operations utilities for the ESG Newsletter System.
Handles file operations and management.
"""

import os
import shutil
import logging
from typing import List, Optional
from datetime import datetime, timedelta
from .text_processing import sanitize_filename

def ensure_directory(directory: str) -> bool:
    """Ensure a directory exists, create if it doesn't."""
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except Exception as e:
        logging.error(f"Error creating directory {directory}: {e}")
        return False

def save_file(content: str, directory: str, filename: str) -> Optional[str]:
    """Save content to a file."""
    try:
        # Ensure directory exists
        if not ensure_directory(directory):
            return None
            
        # Create safe filename
        safe_filename = sanitize_filename(filename)
        filepath = os.path.join(directory, safe_filename)
        
        # Save content
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
            
        logging.info(f"Saved file: {filepath}")
        return filepath
        
    except Exception as e:
        logging.error(f"Error saving file {filename}: {e}")
        return None

def read_file(filepath: str) -> Optional[str]:
    """Read content from a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logging.error(f"Error reading file {filepath}: {e}")
        return None

def find_latest_file(directory: str, pattern: str) -> Optional[str]:
    """Find the latest file matching a pattern in a directory."""
    try:
        files = [f for f in os.listdir(directory) if f.endswith(pattern)]
        if not files:
            return None
            
        # Sort by modification time
        latest_file = max(files, key=lambda x: os.path.getmtime(os.path.join(directory, x)))
        return os.path.join(directory, latest_file)
        
    except Exception as e:
        logging.error(f"Error finding latest file in {directory}: {e}")
        return None

def cleanup_old_files(directory: str, days: int = 7) -> int:
    """Remove files older than specified days."""
    try:
        count = 0
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath):
                file_date = datetime.fromtimestamp(os.path.getmtime(filepath))
                if file_date < cutoff_date:
                    os.remove(filepath)
                    count += 1
                    
        logging.info(f"Cleaned up {count} old files in {directory}")
        return count
        
    except Exception as e:
        logging.error(f"Error cleaning up files in {directory}: {e}")
        return 0

def copy_file(src: str, dst: str) -> bool:
    """Copy a file from source to destination."""
    try:
        shutil.copy2(src, dst)
        logging.info(f"Copied file from {src} to {dst}")
        return True
    except Exception as e:
        logging.error(f"Error copying file from {src} to {dst}: {e}")
        return False

def list_files(directory: str, pattern: str = "*") -> List[str]:
    """List files in a directory matching a pattern."""
    try:
        import glob
        return glob.glob(os.path.join(directory, pattern))
    except Exception as e:
        logging.error(f"Error listing files in {directory}: {e}")
        return [] 