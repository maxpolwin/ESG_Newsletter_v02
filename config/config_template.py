"""
Configuration template for the ESG Newsletter System.
Copy this file to config.py and fill in your actual values.
"""

# Email Configuration
EMAIL_CONFIG = {
    'smtp_server': 'your_smtp_server',
    'smtp_port': 587,
    'username': 'your_email@example.com',
    'password': 'your_password',
    'from_email': 'your_email@example.com',
    'recipients': [
        'recipient1@example.com',
        'recipient2@example.com'
    ]
}

# API Keys
API_KEYS = {
    'perplexity': 'your_perplexity_api_key',
    'openai': 'your_openai_api_key'
}

# Database Configuration
DATABASE_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'esg_newsletter',
    'user': 'your_db_user',
    'password': 'your_db_password'
}

# Newsletter Settings
NEWSLETTER_SETTINGS = {
    'max_total_articles': 20,
    'max_articles_per_source': 5,
    'min_relevance_score': 0.6,
    'max_keywords': 10,
    'summary_max_words': 250
}

# Content Sections
SECTIONS = {
    'executive_summary': True,
    'keyword_statistics': True,
    'article_list': True,
    'source_breakdown': True
}

# Content Filters
FILTERS = {
    'min_relevance_score': 0.6,
    'min_word_count': 100,
    'max_age_days': 7,
    'excluded_domains': [
        'example.com',
        'spam.com'
    ]
}

# Logging Configuration
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': 'logs/newsletter.log'
} 