#!/usr/bin/env python3
"""
Newsletter System v07 - System Tester Module

Provides compatibility and system testing functionality to ensure
all required dependencies and configurations are in place.

Author: Max Polwin
"""

import os
import sys
import platform
import importlib
import logging

# Import configuration
from config import (
    BASE_DIR, OUTPUT_DIR, ATTACHMENTS_DIR, CSS_DIR,
    EMAIL_HOST, EMAIL_USER, EMAIL_PASSWORD, EMAIL_RECIPIENTS
)
from utils import create_css_file, create_js_file

def run_compatibility_check():
    """Run compatibility checks for the system."""
    print("Running Newsletter System v07 Compatibility Check...")
    print(f"Python Version: {platform.python_version()}")
    print(f"System: {platform.system()} {platform.release()}")

    # Check required packages
    required_packages = [
        'feedparser', 'bs4', 'requests', 'imaplib',
        'email', 'datetime', 'smtplib', 'json'
    ]

    package_results = {}
    for package in required_packages:
        try:
            importlib.import_module(package)
            package_results[package] = "Installed"
        except ImportError:
            package_results[package] = "Missing"

    print("\n=== Required Packages ===")
    for pkg, status in package_results.items():
        print(f"{pkg}: {status}")

    # Check directory access
    output_dir_exists = os.path.isdir(OUTPUT_DIR)
    output_dir_writable = os.access(OUTPUT_DIR, os.W_OK) if output_dir_exists else False

    attachments_dir_exists = os.path.isdir(ATTACHMENTS_DIR)
    attachments_dir_writable = os.access(ATTACHMENTS_DIR, os.W_OK) if attachments_dir_exists else False

    css_dir_exists = os.path.isdir(CSS_DIR)
    css_dir_writable = os.access(CSS_DIR, os.W_OK) if css_dir_exists else False

    print("\n=== Directory Access ===")
    print(f"Output Directory ({OUTPUT_DIR}): {'✅ Exists and writable' if (output_dir_exists and output_dir_writable) else '❌ Missing or not writable'}")
    print(f"Attachments Directory ({ATTACHMENTS_DIR}): {'✅ Exists and writable' if (attachments_dir_exists and attachments_dir_writable) else '❌ Missing or not writable'}")
    print(f"CSS Directory ({CSS_DIR}): {'✅ Exists and writable' if (css_dir_exists and css_dir_writable) else '❌ Missing or not writable'}")

    # Check environment variables
    env_results = {
        'EMAIL_HOST': EMAIL_HOST is not None,
        'EMAIL_USER': EMAIL_USER is not None,
        'EMAIL_PASSWORD': EMAIL_PASSWORD is not None
    }

    print("\n=== Environment Variables ===")
    for var, exists in env_results.items():
        print(f"{var}: {'✅ Set' if exists else '❌ Not set (required)'}")

    # Check keyword file
    keywords_path = os.path.join(BASE_DIR, 'keywords_config_v01.py')
    keyword_file_exists = os.path.isfile(keywords_path)

    print("\n=== Keyword Configuration ===")
    print(f"keywords_config_v01.py: {'✅ Exists' if keyword_file_exists else '❌ Missing (required)'} at {keywords_path}")

    if keyword_file_exists:
        try:
            from keywords_config import get_keywords
            kw_pos, kw_neg = get_keywords()
            print(f"Loaded {len(kw_pos)} positive keywords and {len(kw_neg)} negative keywords")
        except Exception as e:
            print(f"Error loading keywords: {e}")

    # Email recipients configuration check
    print("\n=== Email Recipients ===")
    if EMAIL_RECIPIENTS:
        print(f"Found {len(EMAIL_RECIPIENTS)} configured recipients")
    else:
        print("❌ No email recipients configured!")

    # Test CSS and JS file generation
    print("\n=== Testing CSS and JS Generation ===")
    try:
        css_file = create_css_file()
        print(f"✅ CSS file generated successfully: {css_file}")
    except Exception as e:
        print(f"❌ Error generating CSS file: {e}")

    try:
        js_file = create_js_file()
        print(f"✅ JavaScript file generated successfully: {js_file}")
    except Exception as e:
        print(f"❌ Error generating JavaScript file: {e}")

    # Overall status
    all_packages_installed = all(status == "Installed" for status in package_results.values())
    dirs_ok = output_dir_exists and output_dir_writable and attachments_dir_exists and attachments_dir_writable and css_dir_exists and css_dir_writable
    env_ok = all(env_results.values())
    keyword_ok = keyword_file_exists
    recipients_ok = bool(EMAIL_RECIPIENTS)

    print("\n=== Overall Status ===")
    if all_packages_installed and dirs_ok and env_ok and keyword_ok and recipients_ok:
        print("✅ All checks passed! The system should work correctly.")
    else:
        print("❌ Some checks failed. The system may not work correctly.")

        if not all_packages_installed:
            print("  - Missing packages. Install with pip install [package-name]")
        if not dirs_ok:
            print(f"  - Directory issues. Ensure these directories exist and are writable:")
            print(f"    - {OUTPUT_DIR}")
            print(f"    - {ATTACHMENTS_DIR}")
            print(f"    - {CSS_DIR}")
        if not env_ok:
            print("  - Environment variables not set. Create a .env file with EMAIL_HOST, EMAIL_USER, EMAIL_PASSWORD")
        if not keyword_ok:
            print(f"  - Keyword configuration file missing. Create {keywords_path}")
        if not recipients_ok:
            print("  - No email recipients configured. Add recipients to EMAIL_RECIPIENTS list.")

    return all_packages_installed and dirs_ok and env_ok and keyword_ok and recipients_ok
