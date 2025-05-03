#!/usr/bin/env python3
"""
Newsletter System v07 - Email Sender Module

Handles sending email reports with HTML content and attachments.
This module provides email delivery functionality for the newsletter system.

Author: Max Polwin
"""

import os
import smtplib
import logging
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# Import configuration and utilities
from config import EMAIL_HOST, EMAIL_USER, EMAIL_PASSWORD, EMAIL_RECIPIENTS
from config import ATTACHMENTS_DIR, CSS_DIR
from utils import find_latest_html_file

def send_email_with_attachments(html_file_path, recipients=None, attachments=None):
    """Send the HTML file content as an email to multiple recipients with optional attachments."""
    if recipients is None:
        recipients = EMAIL_RECIPIENTS

    # Email configuration
    sender_email = EMAIL_USER
    sender_password = EMAIL_PASSWORD
    smtp_server = EMAIL_HOST
    smtp_port = 465  # Using SSL/TLS encryption as recommended by Posteo

    # Ensure recipients is a list
    if isinstance(recipients, str):
        recipients = [recipients]

    try:
        # Read HTML content
        with open(html_file_path, 'r', encoding='utf-8') as file:
            html_content = file.read()

        # Connect to SMTP server using SSL/TLS
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            # No need for starttls() when using SMTP_SSL
            server.login(sender_email, sender_password)

            # Send to each recipient individually
            successful_sends = 0
            for recipient in recipients:
                try:
                    # Create a new message for each recipient
                    msg = MIMEMultipart('mixed')
                    msg['Subject'] = f"Latest Articles Update - {datetime.datetime.now().strftime('%Y-%m-%d')}"
                    msg['From'] = sender_email
                    msg['To'] = recipient

                    # Create alternative part for the HTML content
                    html_part = MIMEMultipart('alternative')
                    html_part.attach(MIMEText(html_content, 'html'))
                    msg.attach(html_part)

                    # Attach any newsletter files
                    if attachments:
                        for attachment_path in attachments:
                            try:
                                if os.path.exists(attachment_path) and os.path.isfile(attachment_path):
                                    # Get the filename only
                                    filename = os.path.basename(attachment_path)

                                    # Read the attachment content
                                    with open(attachment_path, 'rb') as f:
                                        attachment_content = f.read()

                                    # Create attachment part
                                    attachment_part = MIMEApplication(attachment_content)
                                    attachment_part.add_header('Content-Disposition', 'attachment', filename=filename)
                                    msg.attach(attachment_part)

                                    logging.info(f"Added attachment: {filename}")
                                    print(f"Added attachment: {filename}")
                                else:
                                    logging.warning(f"Attachment file not found: {attachment_path}")
                                    print(f"Attachment file not found: {attachment_path}")
                            except Exception as e:
                                logging.error(f"Error attaching file {attachment_path}: {e}")
                                print(f"Error attaching file {attachment_path}: {e}")

                    # Send the email
                    server.send_message(msg)
                    logging.info(f"Email sent successfully to {recipient}")
                    print(f"Email sent successfully to {recipient}")
                    successful_sends += 1

                except Exception as e:
                    logging.error(f"Failed to send email to {recipient}: {e}")
                    print(f"Failed to send email to {recipient}: {e}")

            logging.info(f"Email sending complete. Successfully sent to {successful_sends}/{len(recipients)} recipients")
            print(f"Email sending complete. Successfully sent to {successful_sends}/{len(recipients)} recipients")
            return successful_sends == len(recipients)  # Return True only if all emails were sent successfully

    except Exception as e:
        logging.error(f"Error in email sending process: {e}")
        print(f"Error in email sending process: {e}")
        return False

def send_latest_report():
    """Find the latest HTML report and send it via email."""
    logging.info("Sending latest report...")
    print("Sending latest report...")

    try:
        # Find the latest HTML file
        latest_html_file = find_latest_html_file()

        if not latest_html_file:
            logging.error("No HTML report found to send.")
            print("No HTML report found to send.")
            return False

        # Check for any attachments
        attachments = []
        if os.path.isdir(ATTACHMENTS_DIR):
            for filename in os.listdir(ATTACHMENTS_DIR):
                if filename.startswith("newsletter_") and (filename.endswith(".html") or filename.endswith(".eml")):
                    attachment_path = os.path.join(ATTACHMENTS_DIR, filename)
                    attachments.append(attachment_path)
                # Now also include .eml files with title-based names
                elif filename.endswith(".eml"):
                    attachment_path = os.path.join(ATTACHMENTS_DIR, filename)
                    attachments.append(attachment_path)

        # Also make sure to include the CSS file (for web viewing)
        css_file = os.path.join(CSS_DIR, "newsletter_styles.css")
        js_file = os.path.join(CSS_DIR, "newsletter_scripts.js")

        if os.path.exists(css_file):
            attachments.append(css_file)

        if os.path.exists(js_file):
            attachments.append(js_file)

        # Send the email
        success = send_email_with_attachments(latest_html_file, EMAIL_RECIPIENTS, attachments)

        if success:
            logging.info(f"Email report sent successfully to all {len(EMAIL_RECIPIENTS)} recipients.")
            print(f"Email report sent successfully to all {len(EMAIL_RECIPIENTS)} recipients.")
        else:
            logging.warning("Some emails failed to send. Check the logs for details.")
            print("Some emails failed to send. Check the logs for details.")

        return success

    except Exception as e:
        logging.error(f"Error sending latest report: {e}", exc_info=True)
        print(f"Error sending latest report: {e}")
        return False
