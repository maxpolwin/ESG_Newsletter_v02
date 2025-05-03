#!/usr/bin/env python3
"""
Utilities package for the ESG Newsletter System.
Exposes utility functions for text processing, file operations, and validation.
"""

from .text_processing import (
    normalize_text,
    clean_text,
    extract_links,
    truncate_text,
    sanitize_filename,
    extract_keywords,
    calculate_relevance
)

from .file_operations import (
    ensure_directory,
    save_file,
    read_file,
    find_latest_file,
    cleanup_old_files,
    copy_file,
    list_files
)

from .validation import (
    validate_email,
    validate_url,
    validate_date,
    validate_keywords,
    validate_article,
    validate_config,
    sanitize_input
)

__all__ = [
    # Text processing
    'normalize_text',
    'clean_text',
    'extract_links',
    'truncate_text',
    'sanitize_filename',
    'extract_keywords',
    'calculate_relevance',
    
    # File operations
    'ensure_directory',
    'save_file',
    'read_file',
    'find_latest_file',
    'cleanup_old_files',
    'copy_file',
    'list_files',
    
    # Validation
    'validate_email',
    'validate_url',
    'validate_date',
    'validate_keywords',
    'validate_article',
    'validate_config',
    'sanitize_input'
] 