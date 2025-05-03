#!/usr/bin/env python3
"""
Email configuration module for the ESG Newsletter System.
Handles email-related settings and validation.
"""

import re
from typing import List
from .base import get_required_env_var, ConfigError

def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def get_recipient_emails() -> List[str]:
    """
    Get recipient emails from environment variable.
    Expects a comma-separated list of email addresses.
    
    Returns:
        list: List of validated email addresses
        
    Raises:
        ConfigError: If no valid email addresses are found
    """
    recipients_str = get_required_env_var("EMAIL_RECIPIENTS")
    recipients = [email.strip() for email in recipients_str.split(",")]
    
    # Validate each email
    invalid_emails = [email for email in recipients if not validate_email(email)]
    if invalid_emails:
        raise ConfigError(f"Invalid email format(s) in EMAIL_RECIPIENTS: {', '.join(invalid_emails)}")
    
    return recipients

# Email settings from environment variables
EMAIL_HOST = get_required_env_var("EMAIL_HOST")
EMAIL_USER = get_required_env_var("EMAIL_USER")
EMAIL_PASSWORD = get_required_env_var("EMAIL_PASSWORD")

# Validate sender email
if not validate_email(EMAIL_USER):
    raise ConfigError(f"Invalid email format for EMAIL_USER: {EMAIL_USER}")

# Initialize recipient list
EMAIL_RECIPIENTS = get_recipient_emails()

# List of trusted newsletter senders
TRUSTED_SENDERS = [
    "noreply@esma.europa.eu",
    "bradzarnett@substack.com",
    "info@greencentralbanking.com",
    "esgonasunday@substack.com",
    "information@kpmg.de",
    "webmestre@ngfs.net",
    "max.polwin@posteo.de",
    "newsletters@bruegel.org",
    "briefing@nature.com",
    "info@messagent.fdmediagroep.nl",
    "noreply@esma.europa.eu",
    "noreply@e.economist.com",
    "precourt_institute@stanford.edu",
    "WorldBank@newsletterext.worldbank.org",
    "newsletters@e.economist.com",
    "naturalcapitalproject@stanford.edu",
    "newsletters@nautil.us",
    "briefings@gs.com",
    "noreply@esma.europa.eu",
    "newsletters@e.economist.com",
    "acanizares-imf.org@shared1.ccsend.com",
    "Newsletter.Research@info.kfw.com",
    "info@greencentralbanking.com",
    "in.context.newsletter@jpmcib.jpmorgan.com",
    "newsletter@project-syndicate.org",
    "briefings@gs.com",
    "newsletter@netzpolitik.org",
    "info@climatepolicyinitiative.org",
    "in.context.newsletter@jpmcib.jpmorgan.com",
    "taylorandfrancis@email.taylorandfrancis.com"
] 