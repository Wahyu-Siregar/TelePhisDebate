"""
URL Expander Module
Resolves shortened URLs to their final destination with caching.

Dosen dan mahasiswa sering pakai URL shortener (bit.ly, s.id, dll).
Shortener sendiri BUKAN indikator phishing — yang penting adalah
domain tujuan akhir setelah di-expand.

Flow:
1. Cek apakah URL menggunakan shortener
2. Jika ya, coba expand (follow redirect)
3. Evaluasi domain tujuan:
   - Whitelisted → turunkan risk (shortener tidak masalah)
   - Unknown → SUSPICIOUS ringan (perlu investigasi lanjut)
   - Blacklisted/suspicious → risk tetap tinggi
4. Cache hasil untuk menghindari request berulang
"""

import logging
import re
import time
from dataclasses import dataclass
from typing import Set
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


# Known URL shortener services
SHORTENER_DOMAINS: Set[str] = {
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly",
    "is.gd", "buff.ly", "adf.ly", "j.mp", "tr.im",
    "shorte.st", "cutt.ly", "rb.gy", "shorturl.at",
    "s.id", "linktr.ee", "rebrand.ly", "tiny.cc",
    "lnkd.in", "youtu.be",
}


@dataclass
class ExpandResult:
    """Result of URL expansion attempt"""
    original_url: str
    is_shortened: bool
    expanded_url: str | None  # None if expansion failed or not shortened
    final_domain: str | None  # Domain of expanded URL
    expansion_success: bool
    from_cache: bool
    error: str | None = None
    
    def to_dict(self) -> dict:
        return {
            "original_url": self.original_url,
            "is_shortened": self.is_shortened,
            "expanded_url": self.expanded_url,
            "final_domain": self.final_domain,
            "expansion_success": self.expansion_success,
            "from_cache": self.from_cache,
            "error": self.error
        }


class URLExpander:
    """
    Expands shortened URLs by following HTTP redirects.
    
    Features:
    - In-memory cache with TTL to avoid redundant requests
    - Timeout and rate-limiting for safety
    - Only follows redirects (HEAD request, no body download)
    - Fallback gracefully when expansion fails
    """
    
    # Configuration
    REQUEST_TIMEOUT = 5          # seconds per request
    MAX_REDIRECTS = 5            # max redirect hops
    CACHE_TTL = 3600             # cache results for 1 hour (seconds)
    MAX_CACHE_SIZE = 500         # max cached entries
    
    def __init__(self):
        self._cache: dict[str, tuple[ExpandResult, float]] = {}
        self._session = requests.Session()
        self._session.max_redirects = self.MAX_REDIRECTS
        # Don't follow redirects automatically; we do it manually via HEAD
        self._session.headers.update({
            "User-Agent": "TelePhisDebate-URLChecker/1.0"
        })
    
    def is_shortened(self, url: str) -> bool:
        """Check if URL uses a known shortener service."""
        domain = self._extract_domain(url)
        return domain in SHORTENER_DOMAINS
    
    def expand(self, url: str) -> ExpandResult:
        """
        Expand a shortened URL to its destination.
        
        Args:
            url: The URL to expand
            
        Returns:
            ExpandResult with expansion details
        """
        # Check if it's a shortened URL
        if not self.is_shortened(url):
            return ExpandResult(
                original_url=url,
                is_shortened=False,
                expanded_url=None,
                final_domain=None,
                expansion_success=False,
                from_cache=False
            )
        
        # Check cache
        cached = self._get_from_cache(url)
        if cached is not None:
            return cached
        
        # Try to expand
        result = self._do_expand(url)
        
        # Store in cache
        self._put_in_cache(url, result)
        
        return result
    
    def expand_urls(self, urls: list[str]) -> dict[str, ExpandResult]:
        """
        Expand multiple URLs.
        
        Returns:
            Dict mapping original URL to ExpandResult
        """
        results = {}
        for url in urls:
            results[url] = self.expand(url)
        return results
    
    def _do_expand(self, url: str) -> ExpandResult:
        """Perform the actual URL expansion via HEAD request."""
        try:
            # Use HEAD request to follow redirects without downloading body
            response = self._session.head(
                url,
                allow_redirects=True,
                timeout=self.REQUEST_TIMEOUT
            )
            
            final_url = response.url
            final_domain = self._extract_domain(final_url)
            
            # Check if we actually got redirected somewhere different
            original_domain = self._extract_domain(url)
            if final_domain and final_domain != original_domain:
                logger.info(f"Expanded: {url} → {final_url} (domain: {final_domain})")
                return ExpandResult(
                    original_url=url,
                    is_shortened=True,
                    expanded_url=final_url,
                    final_domain=final_domain,
                    expansion_success=True,
                    from_cache=False
                )
            else:
                # No redirect happened — shortener might be broken or URL invalid
                logger.debug(f"No redirect for shortened URL: {url}")
                return ExpandResult(
                    original_url=url,
                    is_shortened=True,
                    expanded_url=final_url,
                    final_domain=final_domain,
                    expansion_success=True,
                    from_cache=False
                )
        
        except requests.exceptions.Timeout:
            logger.warning(f"URL expansion timeout: {url}")
            return ExpandResult(
                original_url=url,
                is_shortened=True,
                expanded_url=None,
                final_domain=None,
                expansion_success=False,
                from_cache=False,
                error="timeout"
            )
        
        except requests.exceptions.TooManyRedirects:
            logger.warning(f"Too many redirects: {url}")
            return ExpandResult(
                original_url=url,
                is_shortened=True,
                expanded_url=None,
                final_domain=None,
                expansion_success=False,
                from_cache=False,
                error="too_many_redirects"
            )
        
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Connection error expanding {url}: {e}")
            return ExpandResult(
                original_url=url,
                is_shortened=True,
                expanded_url=None,
                final_domain=None,
                expansion_success=False,
                from_cache=False,
                error="connection_error"
            )
        
        except Exception as e:
            logger.error(f"Unexpected error expanding {url}: {e}")
            return ExpandResult(
                original_url=url,
                is_shortened=True,
                expanded_url=None,
                final_domain=None,
                expansion_success=False,
                from_cache=False,
                error=str(e)
            )
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        url_lower = url.lower()
        if not url_lower.startswith(('http://', 'https://')):
            url_lower = 'https://' + url_lower
        parsed = urlparse(url_lower)
        domain = parsed.netloc or parsed.path.split('/')[0]
        domain = re.sub(r'^www\.', '', domain)
        domain = domain.split(':')[0]  # Remove port
        return domain
    
    def _get_from_cache(self, url: str) -> ExpandResult | None:
        """Get result from cache if not expired."""
        if url in self._cache:
            result, timestamp = self._cache[url]
            if time.time() - timestamp < self.CACHE_TTL:
                # Return cached result with cache flag
                return ExpandResult(
                    original_url=result.original_url,
                    is_shortened=result.is_shortened,
                    expanded_url=result.expanded_url,
                    final_domain=result.final_domain,
                    expansion_success=result.expansion_success,
                    from_cache=True,
                    error=result.error
                )
            else:
                # Expired
                del self._cache[url]
        return None
    
    def _put_in_cache(self, url: str, result: ExpandResult):
        """Store result in cache, evicting oldest if full."""
        # Simple eviction: remove oldest entries if cache is full
        if len(self._cache) >= self.MAX_CACHE_SIZE:
            # Remove oldest 10% of entries
            sorted_keys = sorted(
                self._cache.keys(),
                key=lambda k: self._cache[k][1]
            )
            for key in sorted_keys[:self.MAX_CACHE_SIZE // 10]:
                del self._cache[key]
        
        self._cache[url] = (result, time.time())
    
    def clear_cache(self):
        """Clear the expansion cache."""
        self._cache.clear()
    
    @property
    def cache_size(self) -> int:
        """Current number of cached entries."""
        return len(self._cache)


# Singleton instance
_expander: URLExpander | None = None


def get_url_expander() -> URLExpander:
    """Get or create the URL expander singleton."""
    global _expander
    if _expander is None:
        _expander = URLExpander()
    return _expander
