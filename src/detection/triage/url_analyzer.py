"""
URL Analyzer - Extract and analyze URLs from messages
"""

import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class URLInfo:
    """Information about an extracted URL"""
    original: str
    domain: str
    tld: str
    is_https: bool
    has_path: bool
    has_query: bool
    path_depth: int


class URLAnalyzer:
    """Extract and analyze URLs from message text"""
    
    # Comprehensive URL regex pattern
    URL_PATTERN = re.compile(
        r'https?://[^\s<>"{}|\\^`\[\]]+'  # Standard URLs
        r'|'
        r'(?:www\.)[^\s<>"{}|\\^`\[\]]+'  # www. URLs
        r'|'
        r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}/[^\s<>"{}|\\^`\[\]]*'  # domain.tld/path
        , re.IGNORECASE
    )
    
    def __init__(self):
        pass
    
    def extract_urls(self, text: str) -> list[str]:
        """
        Extract all URLs from text.
        
        Args:
            text: Message text to analyze
            
        Returns:
            List of extracted URLs
        """
        if not text:
            return []
        
        urls = self.URL_PATTERN.findall(text)
        
        # Normalize URLs
        normalized = []
        for url in urls:
            # Add https:// if missing
            if not url.startswith(('http://', 'https://')):
                if url.startswith('www.'):
                    url = 'https://' + url
                else:
                    url = 'https://' + url
            
            # Clean trailing punctuation
            url = url.rstrip('.,;:!?)')
            
            normalized.append(url)
        
        return list(set(normalized))  # Remove duplicates
    
    def analyze_url(self, url: str) -> URLInfo:
        """
        Analyze a single URL and extract information.
        
        Args:
            url: URL to analyze
            
        Returns:
            URLInfo dataclass with analysis results
        """
        # Ensure URL has protocol
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        parsed = urlparse(url)
        
        # Extract domain parts
        domain = parsed.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Extract TLD
        parts = domain.split('.')
        tld = '.' + parts[-1] if parts else ''
        
        # Calculate path depth
        path = parsed.path.strip('/')
        path_depth = len(path.split('/')) if path else 0
        
        return URLInfo(
            original=url,
            domain=domain,
            tld=tld,
            is_https=parsed.scheme == 'https',
            has_path=bool(parsed.path and parsed.path != '/'),
            has_query=bool(parsed.query),
            path_depth=path_depth
        )
    
    def has_urls(self, text: str) -> bool:
        """Quick check if text contains any URLs"""
        return bool(self.URL_PATTERN.search(text or ''))
    
    def count_urls(self, text: str) -> int:
        """Count number of URLs in text"""
        return len(self.extract_urls(text))
    
    def extract_and_analyze(self, text: str) -> list[URLInfo]:
        """
        Extract and analyze all URLs from text.
        
        Args:
            text: Message text
            
        Returns:
            List of URLInfo objects
        """
        urls = self.extract_urls(text)
        return [self.analyze_url(url) for url in urls]
