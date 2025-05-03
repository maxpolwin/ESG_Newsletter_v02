#!/usr/bin/env python3
"""
Perplexity API integration module for the ESG Newsletter System.
Handles all interactions with the Perplexity API.
"""

import time
import logging
from typing import Dict, Any, Optional
import requests
from ..config.api_config import (
    PERPLEXITY_API_KEY,
    API_CONFIG,
    RATE_LIMITS,
    API_ERROR_MESSAGES
)

class PerplexityAPI:
    def __init__(self):
        self.api_key = PERPLEXITY_API_KEY
        self.config = API_CONFIG['perplexity']
        self.rate_limits = RATE_LIMITS['perplexity']
        self.error_messages = API_ERROR_MESSAGES['perplexity']
        self.last_call_time = 0
        self.min_seconds_between_calls = 2.0

    def _rate_limit(self):
        """Implement rate limiting between API calls."""
        current_time = time.time()
        time_since_last_call = current_time - self.last_call_time
        if time_since_last_call < self.min_seconds_between_calls:
            time.sleep(self.min_seconds_between_calls - time_since_last_call)
        self.last_call_time = time.time()

    def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make an API request with proper error handling."""
        self._rate_limit()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(
                f"{self.config['base_url']}{endpoint}",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 401:
                logging.error(self.error_messages['invalid_key'])
                return None
            elif response.status_code == 429:
                logging.error(self.error_messages['rate_limit'])
                return None
            elif response.status_code >= 500:
                logging.error(self.error_messages['server_error'])
                return None
                
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logging.error(f"API request failed: {str(e)}")
            return None

    def generate_summary(self, text: str, max_tokens: Optional[int] = None) -> Optional[str]:
        """Generate a summary using the Perplexity API."""
        if max_tokens is None:
            max_tokens = self.config['max_tokens']

        data = {
            "model": self.config['model'],
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that creates concise summaries of text."
                },
                {
                    "role": "user",
                    "content": f"Please provide a concise summary of the following text:\n\n{text}"
                }
            ],
            "max_tokens": max_tokens,
            "temperature": self.config['temperature'],
            "top_p": self.config['top_p'],
            "frequency_penalty": self.config['frequency_penalty'],
            "presence_penalty": self.config['presence_penalty']
        }

        response = self._make_request("/chat/completions", data)
        if response and 'choices' in response:
            return response['choices'][0]['message']['content']
        return None

    def analyze_content(self, text: str, keywords: list) -> Optional[Dict[str, Any]]:
        """Analyze content for relevance and extract key insights."""
        data = {
            "model": self.config['model'],
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that analyzes content for ESG relevance."
                },
                {
                    "role": "user",
                    "content": f"Analyze the following text for ESG relevance and extract key insights. Keywords to consider: {', '.join(keywords)}\n\n{text}"
                }
            ],
            "max_tokens": self.config['max_tokens'],
            "temperature": self.config['temperature']
        }

        response = self._make_request("/chat/completions", data)
        if response and 'choices' in response:
            return {
                'analysis': response['choices'][0]['message']['content'],
                'timestamp': time.time()
            }
        return None 