#!/usr/bin/env python3
"""
Newsletter generator module for the ESG Newsletter System.
Handles the generation of newsletters from processed content.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime
from collections import Counter
from .html_generator import HTMLGenerator
from .content_processor import ContentProcessor
from ..config.newsletter_config import (
    NEWSLETTER_SETTINGS,
    SECTIONS,
    FILTERS
)
from ..api.mistral import MistralAPI
from ..utils.text_processing import (
    normalize_text,
    clean_text,
    extract_links,
    truncate_text,
    sanitize_filename,
    extract_keywords,
    calculate_relevance
)
from ..utils.validation import (
    validate_email,
    validate_url,
    validate_date,
    validate_keywords,
    validate_article,
    validate_config,
    sanitize_input
)

class NewsletterGenerator:
    def __init__(self):
        self.settings = NEWSLETTER_SETTINGS
        self.sections = SECTIONS
        self.filters = FILTERS
        self.html_generator = HTMLGenerator()
        self.content_processor = ContentProcessor()
        self.api = MistralAPI()
        
    def generate(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a complete newsletter from articles."""
        logging.info("Generating newsletter...")
        
        # Process and filter articles
        processed_articles = self._process_articles(articles)
        
        # Generate keyword statistics
        keyword_counts = self._generate_keyword_stats(processed_articles)
        
        # Generate executive summary
        executive_summary = self._generate_executive_summary(processed_articles)
        
        # Collect academic papers
        academic_papers = self._collect_academic_papers(processed_articles)
        
        # Generate HTML content
        html_content = self.html_generator.generate(
            articles=processed_articles,
            keyword_counts=keyword_counts,
            executive_summary=executive_summary,
            academic_papers=academic_papers
        )
        
        return {
            'content': html_content,
            'metadata': {
                'generated_at': datetime.utcnow().isoformat(),
                'article_count': len(processed_articles),
                'keyword_count': len(keyword_counts),
                'academic_paper_count': len(academic_papers)
            },
            'articles': processed_articles,
            'keyword_stats': keyword_counts,
            'executive_summary': executive_summary,
            'academic_papers': academic_papers
        }
        
    def _process_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process and filter articles based on relevance."""
        processed = []
        
        for article in articles:
            # Process content
            processed_content = self.content_processor.process_content(
                article.get('content', '')
            )
            
            # Check relevance score
            if processed_content['relevance_score'] >= self.filters['min_relevance_score']:
                article.update(processed_content)
                processed.append(article)
                
        return processed[:self.settings['max_total_articles']]
        
    def _generate_keyword_stats(self, articles: List[Dict[str, Any]]) -> Dict[str, int]:
        """Generate keyword statistics from articles."""
        keyword_counts = {}
        
        for article in articles:
            for keyword in article.get('keywords', []):
                keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
                
        return keyword_counts
        
    def _generate_executive_summary(self, articles: List[Dict[str, Any]], max_words: int = 100) -> str:
        """
        Generate an enhanced executive summary of the articles using Mistral API.
        
        Args:
            articles: List of processed articles
            max_words: Maximum number of words in the summary
            
        Returns:
            str: Generated executive summary
        """
        logging.info("Generating enhanced executive summary using Mistral API...")
        
        if not articles:
            return "No articles found to summarize."
            
        # Process articles for summary
        processed_texts = []
        for article in articles[:5]:  # Use top 5 articles for summary
            title = article.get('title', '')
            content = article.get('content', '')
            url = article.get('url', '')
            source = article.get('source_type', '')
            
            # Clean and normalize text
            clean_title = clean_text(title)
            clean_content = clean_text(content)
            
            # Create summary text with source information
            summary_text = f"Title: {clean_title}\nSource: {source}\nURL: {url}\nContent: {clean_content}"
            processed_texts.append(summary_text)
            
        # Combine processed texts
        combined_text = "\n\n".join(processed_texts)
        
        # Generate summary using Mistral API
        summary = self.api.generate_summary(combined_text)
        
        if not summary:
            # Fallback to basic summary if API fails
            summary = self._generate_fallback_summary(articles)
            
        # Truncate to max words if needed
        return truncate_text(summary, max_words)
        
    def _generate_fallback_summary(self, articles: List[Dict[str, Any]]) -> str:
        """Generate a basic summary when API is unavailable."""
        summary_parts = []
        
        # Add overview
        summary_parts.append(f"This newsletter contains {len(articles)} articles.")
        
        # Add top keywords
        all_keywords = []
        for article in articles:
            all_keywords.extend(article.get('keywords', []))
        keyword_counts = Counter(all_keywords)
        top_keywords = [kw for kw, _ in keyword_counts.most_common(3)]
        if top_keywords:
            summary_parts.append(f"Key topics include: {', '.join(top_keywords)}.")
            
        # Add article highlights
        for article in articles[:3]:
            title = article.get('title', '')
            url = article.get('url', '')
            if title:
                summary_parts.append(f"• <a href='{url}'>{clean_text(title)}</a>")
                
        return " ".join(summary_parts)
        
    def _collect_academic_papers(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Collect and deduplicate academic papers from articles."""
        papers = []
        seen_papers = set()
        
        for article in articles:
            for paper in article.get('academic_papers', []):
                paper_id = paper.get('paperId')
                if paper_id and paper_id not in seen_papers:
                    seen_papers.add(paper_id)
                    papers.append(paper)
                    
        return papers[:self.settings.get('max_academic_papers', 10)] 