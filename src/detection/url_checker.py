"""
URL Security Checker Module

Provides external API integration for URL reputation checking:
- VirusTotal API for domain/URL reputation
- Google Safe Browsing API (optional)
- Suspicious TLD database from dataset
"""

import asyncio
import base64
import csv
import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import aiohttp

from src.config import Config

logger = logging.getLogger(__name__)

# Load suspicious TLDs from dataset
SUSPICIOUS_TLDS: dict[str, dict] = {}

def _load_suspicious_tlds():
    """Load suspicious TLDs from CSV dataset"""
    global SUSPICIOUS_TLDS
    
    # Path to dataset
    dataset_path = Path(__file__).parent.parent.parent / "dataset" / "suspicious_tlds_list.csv"
    
    if not dataset_path.exists():
        logger.warning(f"Suspicious TLDs dataset not found: {dataset_path}")
        return
    
    try:
        with open(dataset_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                tld = row.get('metadata_tld', '').strip()
                if tld and tld != 'xn--*':  # Skip wildcard pattern
                    SUSPICIOUS_TLDS[f".{tld}"] = {
                        'category': row.get('metadata_category', 'Suspicious'),
                        'severity': row.get('metadata_severity', 'Low'),
                        'comment': row.get('metadata_comment', ''),
                        'popularity': row.get('metadata_popularity', 'Low')
                    }
        logger.info(f"Loaded {len(SUSPICIOUS_TLDS)} suspicious TLDs from dataset")
    except Exception as e:
        logger.error(f"Failed to load suspicious TLDs: {e}")

# Load on module import
_load_suspicious_tlds()


@dataclass
class URLCheckResult:
    """Result from URL security check"""
    url: str
    is_malicious: bool
    risk_score: float  # 0.0 (safe) to 1.0 (dangerous)
    source: str  # "virustotal", "safebrowsing", "heuristic"
    details: dict
    expanded_url: str | None = None  # Final URL after following redirects
    
    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "expanded_url": self.expanded_url,
            "is_malicious": self.is_malicious,
            "risk_score": self.risk_score,
            "source": self.source,
            "details": self.details
        }


class VirusTotalChecker:
    """VirusTotal API v3 integration for URL/domain checking"""
    
    BASE_URL = "https://www.virustotal.com/api/v3"
    
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or Config.VIRUSTOTAL_API_KEY
        self._session: aiohttp.ClientSession | None = None
    
    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"x-apikey": self.api_key}
            )
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _get_url_id(self, url: str) -> str:
        """Get VirusTotal URL identifier (base64 of URL)"""
        return base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        parsed = urlparse(url)
        return parsed.netloc or parsed.path.split("/")[0]
    
    async def check_url(self, url: str) -> URLCheckResult:
        """
        Check a URL against VirusTotal database.
        
        First tries to get existing analysis, if not found submits for analysis.
        """
        if not self.is_configured:
            logger.warning("VirusTotal API key not configured")
            return self._fallback_result(url, "API key not configured")
        
        try:
            session = await self._get_session()
            
            # Try to get existing URL analysis
            url_id = self._get_url_id(url)
            async with session.get(f"{self.BASE_URL}/urls/{url_id}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return self._parse_url_response(url, data)
                elif resp.status == 404:
                    # URL not in database, check domain instead
                    return await self.check_domain(self._extract_domain(url))
                else:
                    logger.warning(f"VirusTotal URL check failed: {resp.status}")
                    return await self.check_domain(self._extract_domain(url))
                    
        except asyncio.TimeoutError:
            logger.error("VirusTotal request timeout")
            return self._fallback_result(url, "Request timeout")
        except Exception as e:
            logger.error(f"VirusTotal check error: {e}")
            return self._fallback_result(url, str(e))
    
    async def check_domain(self, domain: str) -> URLCheckResult:
        """Check domain reputation against VirusTotal"""
        if not self.is_configured:
            return self._fallback_result(domain, "API key not configured")
        
        try:
            session = await self._get_session()
            
            async with session.get(f"{self.BASE_URL}/domains/{domain}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return self._parse_domain_response(domain, data)
                else:
                    logger.warning(f"VirusTotal domain check failed: {resp.status}")
                    return self._fallback_result(domain, f"API error: {resp.status}")
                    
        except Exception as e:
            logger.error(f"VirusTotal domain check error: {e}")
            return self._fallback_result(domain, str(e))
    
    def _parse_url_response(self, url: str, data: dict) -> URLCheckResult:
        """Parse VirusTotal URL analysis response"""
        attrs = data.get("data", {}).get("attributes", {})
        stats = attrs.get("last_analysis_stats", {})
        
        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)
        harmless = stats.get("harmless", 0)
        undetected = stats.get("undetected", 0)
        
        total = malicious + suspicious + harmless + undetected
        
        # Calculate risk score
        if total > 0:
            risk_score = (malicious * 1.0 + suspicious * 0.5) / total
        else:
            risk_score = 0.0
        
        # Only mark as malicious if significant detection (at least 3 engines or risk > 0.1)
        is_malicious = (malicious >= 3) or (risk_score > 0.1)
        
        return URLCheckResult(
            url=url,
            is_malicious=is_malicious,
            risk_score=min(risk_score, 1.0),
            source="virustotal",
            details={
                "malicious": malicious,
                "suspicious": suspicious,
                "harmless": harmless,
                "undetected": undetected,
                "total_engines": total,
                "categories": attrs.get("categories", {}),
                "reputation": attrs.get("reputation", 0)
            }
        )
    
    def _parse_domain_response(self, domain: str, data: dict) -> URLCheckResult:
        """Parse VirusTotal domain response"""
        attrs = data.get("data", {}).get("attributes", {})
        stats = attrs.get("last_analysis_stats", {})
        
        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)
        harmless = stats.get("harmless", 0)
        undetected = stats.get("undetected", 0)
        
        total = malicious + suspicious + harmless + undetected
        reputation = attrs.get("reputation", 0)
        
        # Calculate risk score based on analysis and reputation
        if total > 0:
            analysis_risk = (malicious * 1.0 + suspicious * 0.5) / total
        else:
            analysis_risk = 0.0
        
        # Reputation is typically negative for bad domains
        # Normalize: positive reputation = safe, negative = risky
        reputation_factor = max(0, min(1, (100 - reputation) / 200)) if reputation < -20 else 0
        
        risk_score = max(analysis_risk, reputation_factor)
        
        # Only mark as malicious if significant detection
        is_malicious = (malicious >= 3) or (reputation < -50) or (risk_score > 0.15)
        
        return URLCheckResult(
            url=f"https://{domain}",
            is_malicious=is_malicious,
            risk_score=min(risk_score, 1.0),
            source="virustotal",
            details={
                "domain": domain,
                "malicious": malicious,
                "suspicious": suspicious,
                "harmless": harmless,
                "undetected": undetected,
                "total_engines": total,
                "reputation": reputation,
                "categories": attrs.get("categories", {}),
                "registrar": attrs.get("registrar", ""),
                "creation_date": attrs.get("creation_date", "")
            }
        )
    
    def _fallback_result(self, url: str, error: str) -> URLCheckResult:
        """Return fallback result when API fails"""
        return URLCheckResult(
            url=url,
            is_malicious=False,
            risk_score=0.5,  # Unknown = medium risk
            source="heuristic",
            details={"error": error, "note": "Could not verify with VirusTotal"}
        )


class URLSecurityChecker:
    """
    Main URL security checker that aggregates multiple sources.
    Currently supports:
    - VirusTotal API
    - URL Expansion (following redirects)
    - Trusted domain whitelist
    - (Future) Google Safe Browsing
    """
    
    # Known URL shorteners
    URL_SHORTENERS = {
        'bit.ly', 'tinyurl.com', 't.co', 'goo.gl', 'ow.ly', 'is.gd',
        'buff.ly', 's.id', 'rebrand.ly', 'cutt.ly', 'short.link',
        'lnkd.in', 'youtu.be', 'v.gd', 'rb.gy', 'clck.ru', 'shorturl.at'
    }
    
    # Trusted domains - skip VirusTotal check, always safe
    TRUSTED_DOMAINS = {
        # Google services
        'google.com', 'google.co.id', 'accounts.google.com', 
        'docs.google.com', 'drive.google.com', 'meet.google.com',
        'classroom.google.com', 'forms.google.com', 'sites.google.com',
        'calendar.google.com', 'mail.google.com', 'youtube.com',
        # Microsoft services
        'microsoft.com', 'office.com', 'live.com', 'outlook.com',
        'onedrive.com', 'sharepoint.com', 'teams.microsoft.com',
        # Academic platforms
        'github.com', 'gitlab.com', 'zoom.us', 'zoom.com',
        # Indonesian academic
        'uir.ac.id', 'kemdikbud.go.id', 'dikti.go.id',
        # Common trusted
        'linkedin.com', 'whatsapp.com', 'telegram.org',
    }
    
    def __init__(self):
        self.virustotal = VirusTotalChecker()
        self._cache: dict[str, URLCheckResult] = {}
        self._expand_session: aiohttp.ClientSession | None = None
    
    async def _get_expand_session(self) -> aiohttp.ClientSession:
        """Get or create session for URL expansion"""
        if self._expand_session is None or self._expand_session.closed:
            # Use timeout and custom headers to mimic browser
            timeout = aiohttp.ClientTimeout(total=10)
            self._expand_session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )
        return self._expand_session
    
    async def expand_url(self, url: str, max_redirects: int = 10) -> tuple[str, list[str]]:
        """
        Follow redirects to get the final destination URL.
        
        Returns:
            tuple: (final_url, list of redirect chain)
        """
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Only expand known shorteners to save time
        if domain not in self.URL_SHORTENERS:
            return url, []
        
        redirect_chain = [url]
        current_url = url
        
        try:
            session = await self._get_expand_session()
            
            for _ in range(max_redirects):
                try:
                    # Use HEAD request first (faster), fallback to GET
                    async with session.head(
                        current_url, 
                        allow_redirects=False,
                        ssl=False  # Some shorteners have SSL issues
                    ) as resp:
                        if resp.status in (301, 302, 303, 307, 308):
                            location = resp.headers.get('Location')
                            if location:
                                # Handle relative redirects
                                if location.startswith('/'):
                                    parsed = urlparse(current_url)
                                    location = f"{parsed.scheme}://{parsed.netloc}{location}"
                                
                                current_url = location
                                redirect_chain.append(current_url)
                            else:
                                break
                        else:
                            break
                except aiohttp.ClientError:
                    # Try GET if HEAD fails
                    async with session.get(
                        current_url,
                        allow_redirects=False,
                        ssl=False
                    ) as resp:
                        if resp.status in (301, 302, 303, 307, 308):
                            location = resp.headers.get('Location')
                            if location:
                                if location.startswith('/'):
                                    parsed = urlparse(current_url)
                                    location = f"{parsed.scheme}://{parsed.netloc}{location}"
                                current_url = location
                                redirect_chain.append(current_url)
                            else:
                                break
                        else:
                            break
                            
        except asyncio.TimeoutError:
            logger.warning(f"Timeout expanding URL: {url}")
        except Exception as e:
            logger.error(f"Error expanding URL {url}: {e}")
        
        final_url = redirect_chain[-1] if redirect_chain else url
        return final_url, redirect_chain[1:] if len(redirect_chain) > 1 else []
    
    def _is_trusted_domain(self, url: str) -> bool:
        """Check if URL belongs to a trusted domain"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Check exact match
        if domain in self.TRUSTED_DOMAINS:
            return True
        
        # Check subdomain match (e.g., docs.google.com matches google.com)
        for trusted in self.TRUSTED_DOMAINS:
            if domain.endswith(f".{trusted}") or domain == trusted:
                return True
        
        return False
    
    @property
    def is_configured(self) -> bool:
        return self.virustotal.is_configured
    
    async def check_url(self, url: str, use_cache: bool = True, expand_url: bool = True) -> URLCheckResult:
        """Check a single URL using VirusTotal + heuristics + URL expansion"""
        # Check cache first
        if use_cache and url in self._cache:
            logger.debug(f"Cache hit for URL: {url}")
            return self._cache[url]
        
        # Expand shortened URLs first
        expanded_url = None
        redirect_chain = []
        if expand_url:
            expanded_url, redirect_chain = await self.expand_url(url)
            if expanded_url != url:
                logger.info(f"URL expanded: {url} -> {expanded_url}")
        
        # Check if final destination is a trusted domain
        final_url = expanded_url if expanded_url else url
        if self._is_trusted_domain(final_url):
            logger.info(f"Trusted domain detected: {final_url}")
            result = URLCheckResult(
                url=url,
                is_malicious=False,
                risk_score=0.0,
                source="whitelist",
                details={
                    "trusted_domain": True,
                    "note": "URL points to trusted domain",
                    "redirect_chain": redirect_chain if redirect_chain else []
                },
                expanded_url=expanded_url if expanded_url != url else None
            )
            self._cache[url] = result
            return result
        
        # Start with heuristic analysis (on both original and expanded)
        heuristic_result = self._heuristic_check(url)
        
        # Also check expanded URL if different
        if expanded_url and expanded_url != url:
            expanded_heuristic = self._heuristic_check(expanded_url)
            # Use higher risk score
            if expanded_heuristic.risk_score > heuristic_result.risk_score:
                heuristic_result = expanded_heuristic
        
        # If VirusTotal configured, enhance with API data
        if self.virustotal.is_configured:
            # Check the expanded URL with VirusTotal (more accurate)
            url_to_check = expanded_url if expanded_url else url
            vt_result = await self.virustotal.check_url(url_to_check)
            
            # Combine results - use higher risk score
            combined_risk = max(heuristic_result.risk_score, vt_result.risk_score)
            
            # Malicious if either source says so
            is_malicious = vt_result.is_malicious or heuristic_result.is_malicious
            
            # Merge details
            combined_details = {
                **vt_result.details,
                "heuristic_risk_factors": heuristic_result.details.get("risk_factors", []),
                "heuristic_risk_score": heuristic_result.risk_score
            }
            
            # Add redirect info
            if redirect_chain:
                combined_details["redirect_chain"] = redirect_chain
            
            result = URLCheckResult(
                url=url,
                is_malicious=is_malicious,
                risk_score=combined_risk,
                source="virustotal+heuristic",
                details=combined_details,
                expanded_url=expanded_url if expanded_url != url else None
            )
        else:
            # Use heuristic only
            result = URLCheckResult(
                url=url,
                is_malicious=heuristic_result.is_malicious,
                risk_score=heuristic_result.risk_score,
                source="heuristic",
                details=heuristic_result.details,
                expanded_url=expanded_url if expanded_url != url else None
            )
        
        # Cache result
        self._cache[url] = result
        return result
    
    async def check_urls(self, urls: list[str]) -> dict[str, URLCheckResult]:
        """
        Check multiple URLs concurrently.
        
        Returns dict mapping URL to its check result.
        """
        if not urls:
            return {}
        
        # Run checks concurrently with rate limiting
        results = {}
        
        # VirusTotal free tier: 4 requests/minute
        # Process in small batches with delay
        batch_size = 4
        delay_between_batches = 15  # seconds
        
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            
            tasks = [self.check_url(url) for url in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for url, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Error checking {url}: {result}")
                    results[url] = self._heuristic_check(url)
                else:
                    results[url] = result
            
            # Wait between batches (except for last batch)
            if i + batch_size < len(urls):
                await asyncio.sleep(delay_between_batches)
        
        return results
    
    def check_urls_sync(self, urls: list[str]) -> dict[str, dict]:
        """
        Synchronous wrapper for check_urls.
        Returns dict suitable for passing to agents.
        Works both in sync context and within existing async event loop.
        """
        import nest_asyncio
        
        try:
            loop = asyncio.get_running_loop()
            # We're inside an async context, use nest_asyncio
            nest_asyncio.apply()
            results = loop.run_until_complete(self.check_urls(urls))
        except RuntimeError:
            # No running loop, create one
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            results = loop.run_until_complete(self.check_urls(urls))
        
        return {url: result.to_dict() for url, result in results.items()}
    
    def _heuristic_check(self, url: str) -> URLCheckResult:
        """
        Basic heuristic check when API is not available.
        Analyzes URL structure for suspicious patterns.
        Uses suspicious TLD dataset for enhanced detection.
        """
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        risk_factors = []
        risk_score = 0.0
        tld_info = None
        
        # Check for IP address instead of domain
        if self._is_ip_address(domain):
            risk_factors.append("IP address instead of domain")
            risk_score += 0.3
        
        # Check for suspicious TLDs using dataset
        tld_match = self._check_suspicious_tld(domain)
        if tld_match:
            tld_info = tld_match
            severity = tld_match.get('severity', 'Low').lower()
            category = tld_match.get('category', 'Suspicious')
            
            # Score based on severity
            if severity == 'critical':
                risk_score += 0.4
                risk_factors.append(f"Critical TLD ({category})")
            elif severity == 'high':
                risk_score += 0.3
                risk_factors.append(f"High-risk TLD ({category})")
            elif severity == 'medium':
                risk_score += 0.2
                risk_factors.append(f"Medium-risk TLD ({category})")
            else:  # Low
                risk_score += 0.1
                risk_factors.append(f"Suspicious TLD ({category})")
        
        # Check for URL shorteners
        shorteners = ['bit.ly', 'tinyurl.com', 't.co', 'goo.gl', 'ow.ly', 'is.gd', 'buff.ly', 'rebrand.ly', 's.id', 'cutt.ly', 'rb.gy']
        if any(shortener in domain for shortener in shorteners):
            risk_factors.append("URL shortener detected")
            risk_score += 0.2
        
        # Check for excessive subdomains
        subdomain_count = domain.count('.')
        if subdomain_count > 3:
            risk_factors.append("Excessive subdomains")
            risk_score += 0.15
        
        # Check for suspicious keywords in URL path (not domain)
        suspicious_keywords = ['login', 'signin', 'verify', 'secure', 'account', 'update', 'confirm', 'bank', 'paypal', 'password', 'credential']
        url_lower = url.lower()
        for keyword in suspicious_keywords:
            if keyword in url_lower and keyword not in domain:
                risk_factors.append(f"Suspicious keyword: {keyword}")
                risk_score += 0.1
                break
        
        # Check for HTTP (not HTTPS)
        if parsed.scheme == 'http':
            risk_factors.append("No HTTPS")
            risk_score += 0.1
        
        # Check for unusual characters
        if '@' in url or '!' in parsed.path:
            risk_factors.append("Unusual characters in URL")
            risk_score += 0.2
        
        # Check for punycode/IDN (internationalized domain)
        if domain.startswith('xn--') or '.xn--' in domain:
            risk_factors.append("Punycode/IDN domain (potential homograph attack)")
            risk_score += 0.25
        
        # Check for numeric domain patterns (e.g., bank1-login.com)
        import re
        if re.search(r'\d{2,}', domain.split('.')[0]):
            risk_factors.append("Numeric pattern in domain")
            risk_score += 0.1
        
        is_malicious = risk_score >= 0.5
        
        details = {
            "risk_factors": risk_factors,
            "domain": domain,
            "scheme": parsed.scheme,
            "note": "Heuristic analysis (dataset-enhanced)"
        }
        
        if tld_info:
            details["tld_info"] = tld_info
        
        return URLCheckResult(
            url=url,
            is_malicious=is_malicious,
            risk_score=min(risk_score, 1.0),
            source="heuristic",
            details=details
        )
    
    def _check_suspicious_tld(self, domain: str) -> dict | None:
        """Check if domain uses a suspicious TLD from dataset"""
        for tld, info in SUSPICIOUS_TLDS.items():
            if domain.endswith(tld):
                return info
        return None
    
    def _is_ip_address(self, domain: str) -> bool:
        """Check if domain is an IP address"""
        import re
        # Remove port if present
        domain = domain.split(':')[0]
        # IPv4 pattern
        ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        return bool(re.match(ipv4_pattern, domain))
    
    async def close(self):
        """Close all connections"""
        await self.virustotal.close()
        if self._expand_session and not self._expand_session.closed:
            await self._expand_session.close()


# Singleton instance
_checker: URLSecurityChecker | None = None


def get_url_checker() -> URLSecurityChecker:
    """Get or create the URL security checker singleton"""
    global _checker
    if _checker is None:
        _checker = URLSecurityChecker()
    return _checker


def check_urls_external(urls: list[str]) -> dict[str, dict]:
    """
    Convenience function to check URLs externally.
    
    This is the main entry point for the pipeline to use.
    Returns a dict mapping URL to check results.
    """
    checker = get_url_checker()
    return checker.check_urls_sync(urls)


async def check_urls_external_async(urls: list[str]) -> dict[str, dict]:
    """
    Async version of check_urls_external.
    Use this when already in an async context (e.g., Telegram bot).
    """
    checker = get_url_checker()
    results = await checker.check_urls(urls)
    return {url: result.to_dict() for url, result in results.items()}
