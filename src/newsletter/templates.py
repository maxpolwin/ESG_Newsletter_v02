#!/usr/bin/env python3
"""
Templates module for the ESG Newsletter System.
Handles HTML and email templates for newsletter generation.
"""

import os
from typing import Dict, Any
from jinja2 import Environment, FileSystemLoader
from ..config.paths import TEMPLATES_DIR
from ..config.newsletter_config import NEWSLETTER_SETTINGS

class TemplateManager:
    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(TEMPLATES_DIR),
            autoescape=True
        )
        self.settings = NEWSLETTER_SETTINGS
        
    def get_html_template(self) -> Any:
        """Get the HTML newsletter template."""
        return self.env.get_template('newsletter.html')
        
    def get_email_template(self) -> Any:
        """Get the email template."""
        return self.env.get_template('email.html')
        
    def get_subject_template(self) -> Any:
        """Get the email subject template."""
        return self.env.get_template('subject.txt')
        
    def render_newsletter(self, data: Dict[str, Any]) -> str:
        """Render the newsletter HTML."""
        template = self.get_html_template()
        return template.render(
            title=self.settings['title'],
            description=self.settings['description'],
            generated_at=data['metadata']['generated_at'],
            executive_summary=data['executive_summary'],
            keyword_stats=data['keyword_stats'],
            articles=data['articles'],
            sections=self.settings['sections']
        )
        
    def render_email(self, data: Dict[str, Any]) -> str:
        """Render the email HTML."""
        template = self.get_email_template()
        return template.render(
            title=self.settings['title'],
            content=data['content'],
            generated_at=data['metadata']['generated_at']
        )
        
    def render_subject(self, data: Dict[str, Any]) -> str:
        """Render the email subject."""
        template = self.get_subject_template()
        return template.render(
            title=self.settings['title'],
            date=data['metadata']['generated_at'],
            article_count=data['metadata']['article_count']
        ) 