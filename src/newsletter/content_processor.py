#!/usr/bin/env python3
"""
Content processor module for the ESG Newsletter System.
Handles processing and analysis of newsletter content.
"""

import re
import logging
from typing import Dict, Any, List
from collections import Counter
from ..utils.text_processing import normalize_text
from ..config.newsletter_config import FILTERS
from ..api.mistral import MistralAPI
from ..api.semantic_scholar import SemanticScholarAPI
from ..utils.retry import RetryManager

class ContentProcessor:
    def __init__(self):
        self.filters = FILTERS
        self.api = MistralAPI()
        self.semantic_scholar = SemanticScholarAPI()
        self.retry_manager = RetryManager(
            max_retries=3,
            initial_delay=5.0,  # Start with 5 seconds delay
            max_delay=60.0,     # Max delay of 60 seconds
            timeout_minutes=60  # 60 minutes total timeout
        )
        
    def process_content(self, content: str) -> Dict[str, Any]:
        """Process content and extract relevant information."""
        try:
            # Normalize text
            normalized_text = normalize_text(content)
            
            # Extract keywords
            keywords = self._extract_keywords(normalized_text)
            
            # Generate summary
            summary = self._generate_summary(content)
            
            # Calculate relevance score
            relevance_score = self._calculate_relevance(normalized_text, keywords)
            
            # Analyze content
            analysis = self._analyze_content(content, keywords)
            
            # Get related academic papers with retry mechanism
            academic_papers = self._get_related_papers(keywords)
            
            return {
                'keywords': keywords,
                'summary': summary,
                'relevance_score': relevance_score,
                'analysis': analysis,
                'word_count': len(content.split()),
                'academic_papers': academic_papers,
                'api_status': {
                    'semantic_scholar': 'success',
                    'mistral': 'success'
                }
            }
        except Exception as e:
            logging.error(f"Error processing content: {str(e)}")
            return {
                'keywords': [],
                'summary': "Error processing content",
                'relevance_score': 0.0,
                'analysis': {
                    'insights': "Error analyzing content",
                    'timestamp': None
                },
                'word_count': len(content.split()),
                'academic_papers': [],
                'api_status': {
                    'semantic_scholar': 'error',
                    'mistral': 'error'
                },
                'error': str(e)
            }
        
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        # Get required keywords
        required_keywords = self.filters['required_keywords']
        
        # Find all occurrences of required keywords
        found_keywords = []
        for keyword in required_keywords:
            if keyword.lower() in text:
                found_keywords.append(keyword)
                
        return found_keywords
        
    def _generate_summary(self, content: str) -> str:
        """Generate a summary of the content using Mistral API."""
        try:
            # Use Mistral API to generate summary
            summary = self.api.generate_summary(content)
            return summary or "No summary available."
        except Exception as e:
            logging.error(f"Error generating summary: {str(e)}")
            return "Error generating summary. Please try again later."
        
    def _calculate_relevance(self, text: str, keywords: List[str]) -> float:
        """Calculate content relevance score."""
        if not keywords:
            return 0.0
            
        # Count keyword occurrences
        keyword_counts = Counter()
        for keyword in keywords:
            count = len(re.findall(r'\b' + re.escape(keyword.lower()) + r'\b', text))
            keyword_counts[keyword] = count
            
        # Calculate average relevance
        total_occurrences = sum(keyword_counts.values())
        max_possible = len(keywords) * 3  # Assume 3 occurrences per keyword is maximum
        
        return min(1.0, total_occurrences / max_possible)
        
    def _analyze_content(self, content: str, keywords: List[str]) -> Dict[str, Any]:
        """Analyze content for ESG relevance."""
        try:
            # Use Mistral API to analyze content
            analysis = self.api.analyze_content(content, keywords)
            
            if analysis:
                return {
                    'insights': analysis['analysis'],
                    'timestamp': analysis['timestamp']
                }
                
            return {
                'insights': "No analysis available.",
                'timestamp': None
            }
        except Exception as e:
            logging.error(f"Error analyzing content: {str(e)}")
            return {
                'insights': "Error analyzing content. Please try again later.",
                'timestamp': None
            }
        
    def _get_related_papers(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """Get related academic papers using Semantic Scholar API with retry mechanism."""
        if not keywords:
            return []
            
        def _search_papers(keyword: str) -> List[Dict[str, Any]]:
            """Wrapper function for the API call to be used with retry mechanism."""
            papers = self.semantic_scholar.search_papers(keyword, days_ago=1)
            if not papers:
                raise Exception(f"No papers found for keyword: {keyword}")
            return papers
            
        def _error_handler(error: Exception, attempt: int) -> None:
            """Handle errors during retry attempts."""
            logging.warning(
                f"Attempt {attempt} failed for keyword '{keywords[0]}': {str(error)}"
            )
            
        try:
            # Use the first keyword for search with retry mechanism
            papers = self.retry_manager.execute_with_retry(
                _search_papers,
                keywords[0],
                error_callback=_error_handler
            )
            
            if papers:
                return papers[:5]  # Return top 5 papers
            return []
            
        except Exception as e:
            logging.error(f"All retry attempts failed for keyword '{keywords[0]}': {str(e)}")
            return [] 