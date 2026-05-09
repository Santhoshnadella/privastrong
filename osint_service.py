"""
OSINT Service for Reverse Image Search
Performs web-wide searches for image matches using external APIs
"""

import logging
import requests
import json
import os
from typing import List, Dict, Optional
import numpy as np

logger = logging.getLogger(__name__)

class OsintService:
    """
    Handles reverse image searches across the web using Google Vision and TinEye
    """
    
    def __init__(self, google_api_key: Optional[str] = None, tineye_api_key: Optional[str] = None):
        self.google_api_key = google_api_key or os.getenv('GOOGLE_VISION_API_KEY')
        self.tineye_api_key = tineye_api_key or os.getenv('TINEYE_API_KEY')
        self.is_mock_mode = not (self.google_api_key or self.tineye_api_key)
        
        if self.is_mock_mode:
            logger.warning("No API keys found for Google Vision or TinEye. Running in MOCK MODE.")
        else:
            logger.info("OsintService initialized with API keys")

    async def search_web(self, image_url: Optional[str] = None, image_bytes: Optional[bytes] = None) -> List[Dict]:
        """
        Perform reverse image search on the web
        
        Args:
            image_url: Publicly accessible URL of the image
            image_bytes: Raw image bytes
            
        Returns:
            List of external matches found on the web
        """
        if self.is_mock_mode:
            return self._get_mock_results()
            
        matches = []
        
        # 1. Search via Google Vision API (Web Detection)
        if self.google_api_key:
            google_matches = await self._search_google_vision(image_url, image_bytes)
            matches.extend(google_matches)
            
        # 2. Search via TinEye API
        if self.tineye_api_key:
            tineye_matches = await self._search_tineye(image_url, image_bytes)
            matches.extend(tineye_matches)
            
        # Deduplicate results by URL
        unique_matches = {}
        for match in matches:
            url = match.get('source_url')
            if url not in unique_matches or match.get('similarity', 0) > unique_matches[url].get('similarity', 0):
                unique_matches[url] = match
                
        return list(unique_matches.values())

    async def _search_google_vision(self, image_url: Optional[str], image_bytes: Optional[bytes]) -> List[Dict]:
        """Search using Google Cloud Vision API"""
        try:
            url = f"https://vision.googleapis.com/v1/images:annotate?key={self.google_api_key}"
            
            # Prepare request body
            if image_url:
                image_source = {"imageUri": image_url}
            else:
                import base64
                image_source = {"content": base64.b64encode(image_bytes).decode('utf-8')}
                
            payload = {
                "requests": [{
                    "image": image_source,
                    "features": [{"type": "WEB_DETECTION"}]
                }]
            }
            
            response = requests.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            web_detection = data['responses'][0].get('webDetection', {})
            matches = []
            
            # Extract full matches
            for match in web_detection.get('fullMatchingImages', []):
                matches.append({
                    'source_url': match['url'],
                    'detection_method': 'google_vision_full',
                    'similarity': 1.0,
                    'site_name': self._extract_site_name(match['url'])
                })
                
            # Extract partial matches
            for match in web_detection.get('partialMatchingImages', []):
                matches.append({
                    'source_url': match['url'],
                    'detection_method': 'google_vision_partial',
                    'similarity': 0.85,
                    'site_name': self._extract_site_name(match['url'])
                })
                
            # Extract pages with matching images
            for page in web_detection.get('pagesWithMatchingImages', []):
                matches.append({
                    'source_url': page['url'],
                    'page_title': page.get('pageTitle'),
                    'detection_method': 'google_vision_page',
                    'similarity': 0.9,
                    'site_name': self._extract_site_name(page['url'])
                })
                
            return matches
            
        except Exception as e:
            logger.error(f"Google Vision API error: {e}")
            return []

    async def _search_tineye(self, image_url: Optional[str], image_bytes: Optional[bytes]) -> List[Dict]:
        """Search using TinEye API"""
        # Placeholder for TinEye API implementation
        # Requires 'tineye-api' python package or direct HTTP requests
        return []

    def _extract_site_name(self, url: str) -> str:
        """Extract domain from URL"""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        return domain.replace('www.', '')

    def _get_mock_results(self) -> List[Dict]:
        """Return simulated results for development/testing"""
        import random
        
        sites = [
            ('https://twitter.com/user_123/status/123456789', 'Twitter'),
            ('https://reddit.com/r/art/comments/abcxyz', 'Reddit'),
            ('https://instagram.com/p/B9x123abc/', 'Instagram'),
            ('https://pinterest.com/pin/456789123/', 'Pinterest'),
            ('https://news-site.com/articles/stolen-art-scandal', 'News Site')
        ]
        
        num_matches = random.randint(1, 3)
        selected = random.sample(sites, num_matches)
        
        results = []
        for url, name in selected:
            results.append({
                'source_url': url,
                'site_name': name,
                'detection_method': 'mock_osint',
                'similarity': random.uniform(0.75, 0.99),
                'page_title': f"Shared on {name}"
            })
            
        return results
