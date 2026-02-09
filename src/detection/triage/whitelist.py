"""
Whitelist Checker - Trusted domains and patterns
Messages with ONLY whitelisted URLs bypass LLM stages
"""

import re
from typing import Set


class WhitelistChecker:
    """Check URLs against trusted domain whitelist"""
    
    # Trusted academic domains
    ACADEMIC_DOMAINS: Set[str] = {
        # UIR Official
        "uir.ac.id",
        "student.uir.ac.id",
        "kuliah.uir.ac.id",
        "elearning.uir.ac.id",
        "sia.uir.ac.id",
        "library.uir.ac.id",
        
        # Indonesian Education
        "kemdikbud.go.id",
        "dikti.go.id",
        "pddikti.kemdikbud.go.id",
        "lldikti.go.id",
        
        # Academic Platforms
        "classroom.google.com",
        "docs.google.com",
        "drive.google.com",
        "forms.google.com",
        "scholar.google.com",
        "github.com",
        "gitlab.com",
        "stackoverflow.com",
        "medium.com",
        "researchgate.net",
        "academia.edu",
        "ieee.org",
        "acm.org",
        "springer.com",
        "sciencedirect.com",
    }
    
    # Trusted meeting platforms
    MEETING_PLATFORMS: Set[str] = {
        "zoom.us",
        "meet.google.com",
        "teams.microsoft.com",
        "webex.com",
        "discord.com",
        "discord.gg",
    }
    
    # Trusted social/communication
    TRUSTED_SOCIAL: Set[str] = {
        "youtube.com",
        "youtu.be",
        "linkedin.com",
        "twitter.com",
        "x.com",
        "instagram.com",
        "facebook.com",
        "wa.me",
        "t.me",  # Telegram links
    }
    
    # Trusted Indonesian government
    GOV_DOMAINS: Set[str] = {
        "go.id",
        "kemenkeu.go.id",
        "pajak.go.id",
        "bps.go.id",
    }
    
    def __init__(self, custom_whitelist: Set[str] | None = None):
        """
        Initialize whitelist checker.
        
        Args:
            custom_whitelist: Additional domains to whitelist
        """
        self.whitelist = (
            self.ACADEMIC_DOMAINS | 
            self.MEETING_PLATFORMS | 
            self.TRUSTED_SOCIAL |
            self.GOV_DOMAINS
        )
        
        if custom_whitelist:
            self.whitelist |= custom_whitelist
    
    def extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        # Remove protocol
        url = re.sub(r'^https?://', '', url.lower())
        # Remove www.
        url = re.sub(r'^www\.', '', url)
        # Get domain (before first /)
        domain = url.split('/')[0]
        # Remove port if present
        domain = domain.split(':')[0]
        return domain
    
    def is_whitelisted(self, url: str) -> bool:
        """
        Check if URL domain is in whitelist.
        
        Args:
            url: URL to check
            
        Returns:
            True if domain is whitelisted
        """
        domain = self.extract_domain(url)
        
        # Direct match
        if domain in self.whitelist:
            return True
        
        # Check if subdomain of whitelisted domain
        for trusted in self.whitelist:
            if domain.endswith('.' + trusted):
                return True
        
        return False
    
    def check_urls(self, urls: list[str]) -> dict:
        """
        Check multiple URLs against whitelist.
        
        Args:
            urls: List of URLs to check
            
        Returns:
            Dict with results:
            - all_whitelisted: True if ALL URLs are whitelisted
            - whitelisted: List of whitelisted URLs
            - not_whitelisted: List of non-whitelisted URLs
        """
        whitelisted = []
        not_whitelisted = []
        
        for url in urls:
            if self.is_whitelisted(url):
                whitelisted.append(url)
            else:
                not_whitelisted.append(url)
        
        return {
            "all_whitelisted": len(not_whitelisted) == 0 and len(whitelisted) > 0,
            "whitelisted": whitelisted,
            "not_whitelisted": not_whitelisted
        }
    
    def add_to_whitelist(self, domain: str):
        """Add a domain to the whitelist"""
        self.whitelist.add(domain.lower())
    
    def remove_from_whitelist(self, domain: str):
        """Remove a domain from the whitelist"""
        self.whitelist.discard(domain.lower())
