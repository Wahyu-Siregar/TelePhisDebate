"""
Blacklist Checker - Known malicious patterns and suspicious indicators
"""

import re
from typing import Set
from dataclasses import dataclass


@dataclass
class RedFlag:
    """Represents a detected red flag"""
    flag_type: str
    description: str
    severity: int  # 1-10
    matched_value: str = ""


class BlacklistChecker:
    """Check messages for blacklisted patterns and red flags"""
    
    # Known URL shorteners (often used to hide malicious URLs)
    URL_SHORTENERS: Set[str] = {
        "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly",
        "is.gd", "buff.ly", "adf.ly", "j.mp", "tr.im",
        "shorte.st", "cutt.ly", "rb.gy", "shorturl.at",
        "s.id", "linktr.ee", "rebrand.ly",
    }
    
    # Suspicious TLDs (commonly used in phishing)
    SUSPICIOUS_TLDS: Set[str] = {
        ".tk", ".ml", ".ga", ".cf", ".gq",  # Free TLDs often abused
        ".xyz", ".top", ".work", ".click", ".link",
        ".monster", ".rest", ".icu",
    }
    
    # Known scam domains (can be updated from reports)
    BLACKLISTED_DOMAINS: Set[str] = set()
    
    # Urgency keywords in Indonesian
    URGENCY_KEYWORDS_ID: list[str] = [
        "segera", "mendesak", "urgent", "buruan", "cepat",
        "sekarang juga", "hari ini", "batas waktu", "deadline",
        "jangan sampai", "terlewat", "kesempatan terakhir",
        "limited", "terbatas", "akan berakhir", "expired",
        "hanya hari ini", "promo", "gratis", "hadiah",
        "verifikasi", "diblokir", "ditangguhkan",
    ]
    
    # Phishing indicator keywords
    PHISHING_KEYWORDS_ID: list[str] = [
        "verifikasi akun", "konfirmasi data", "update data",
        "akun diblokir", "akun ditangguhkan", "akun bermasalah",
        "transfer", "kirim uang", "bayar", "pembayaran",
        "hadiah", "menang", "pemenang", "undian", "lottery",
        "klik link", "klik disini", "klik sekarang",
        "login sekarang", "masuk sekarang",
        "password", "kata sandi", "pin", "otp",
        "data pribadi", "nomor rekening", "kartu kredit",
        "beasiswa penuh", "lowongan kerja", "gaji tinggi",
        "investasi", "keuntungan besar", "cuan", "pinjaman", "modal", "utang",
        "amanah", "dana", "keuangan", "cair",
    ]
    
    # Authority impersonation patterns
    AUTHORITY_PATTERNS: list[str] = [
        r"dari\s+(pihak\s+)?(kampus|universitas|uir|rektorat|dekanat)",
        r"(admin|operator)\s+(resmi|official)",
        r"pengumuman\s+(penting|resmi)",
        r"surat\s+edaran",
    ]
    
    def __init__(self, custom_blacklist: Set[str] | None = None):
        """
        Initialize blacklist checker.
        
        Args:
            custom_blacklist: Additional domains to blacklist
        """
        self.blacklisted_domains = self.BLACKLISTED_DOMAINS.copy()
        
        if custom_blacklist:
            self.blacklisted_domains |= custom_blacklist
    
    def extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        url = re.sub(r'^https?://', '', url.lower())
        url = re.sub(r'^www\.', '', url)
        domain = url.split('/')[0]
        domain = domain.split(':')[0]
        return domain
    
    def is_shortened_url(self, url: str) -> bool:
        """Check if URL uses a shortener service"""
        domain = self.extract_domain(url)
        return domain in self.URL_SHORTENERS
    
    def has_suspicious_tld(self, url: str) -> bool:
        """Check if URL has a suspicious TLD"""
        domain = self.extract_domain(url)
        return any(domain.endswith(tld) for tld in self.SUSPICIOUS_TLDS)
    
    def is_blacklisted_domain(self, url: str) -> bool:
        """Check if URL domain is blacklisted"""
        domain = self.extract_domain(url)
        return domain in self.blacklisted_domains
    
    def count_urgency_keywords(self, text: str) -> int:
        """Count urgency keywords in text"""
        text_lower = text.lower()
        count = 0
        for keyword in self.URGENCY_KEYWORDS_ID:
            if keyword in text_lower:
                count += 1
        return count
    
    def find_phishing_keywords(self, text: str) -> list[str]:
        """Find phishing indicator keywords in text"""
        text_lower = text.lower()
        found = []
        for keyword in self.PHISHING_KEYWORDS_ID:
            if keyword in text_lower:
                found.append(keyword)
        return found
    
    def check_caps_lock_abuse(self, text: str) -> float:
        """
        Calculate percentage of CAPS LOCK usage.
        
        Returns:
            Float 0.0-1.0 representing caps percentage
        """
        if not text:
            return 0.0
        
        letters = [c for c in text if c.isalpha()]
        if not letters:
            return 0.0
        
        upper_count = sum(1 for c in letters if c.isupper())
        return upper_count / len(letters)
    
    def check_excessive_punctuation(self, text: str) -> bool:
        """Check for excessive exclamation/question marks"""
        # More than 3 consecutive or more than 5 total
        if re.search(r'[!?]{3,}', text):
            return True
        if text.count('!') + text.count('?') > 5:
            return True
        return False
    
    def check_authority_impersonation(self, text: str) -> list[str]:
        """Check for authority impersonation patterns"""
        text_lower = text.lower()
        matched = []
        for pattern in self.AUTHORITY_PATTERNS:
            if re.search(pattern, text_lower):
                matched.append(pattern)
        return matched
    
    def analyze_url(self, url: str) -> list[RedFlag]:
        """
        Analyze a single URL for red flags.
        
        Returns:
            List of RedFlag objects
        """
        flags = []
        
        if self.is_blacklisted_domain(url):
            flags.append(RedFlag(
                flag_type="blacklisted_domain",
                description="URL domain is blacklisted",
                severity=10,
                matched_value=self.extract_domain(url)
            ))
        
        if self.is_shortened_url(url):
            flags.append(RedFlag(
                flag_type="shortened_url",
                description="URL uses shortener service (hides destination)",
                severity=6,
                matched_value=self.extract_domain(url)
            ))
        
        if self.has_suspicious_tld(url):
            flags.append(RedFlag(
                flag_type="suspicious_tld",
                description="URL uses suspicious TLD",
                severity=5,
                matched_value=url
            ))
        
        return flags
    
    def analyze_text(self, text: str) -> list[RedFlag]:
        """
        Analyze message text for red flags.
        
        Returns:
            List of RedFlag objects
        """
        flags = []
        
        # Check urgency keywords
        urgency_count = self.count_urgency_keywords(text)
        if urgency_count >= 2:
            flags.append(RedFlag(
                flag_type="urgency_keywords",
                description=f"Multiple urgency keywords detected ({urgency_count})",
                severity=min(4 + urgency_count, 8),
                matched_value=str(urgency_count)
            ))
        
        # Check phishing keywords
        phishing_keywords = self.find_phishing_keywords(text)
        if phishing_keywords:
            flags.append(RedFlag(
                flag_type="phishing_keywords",
                description=f"Phishing indicator keywords: {', '.join(phishing_keywords[:3])}",
                severity=min(5 + len(phishing_keywords), 9),
                matched_value=", ".join(phishing_keywords)
            ))
        
        # Check CAPS LOCK abuse
        caps_ratio = self.check_caps_lock_abuse(text)
        if caps_ratio > 0.5:
            flags.append(RedFlag(
                flag_type="caps_lock_abuse",
                description=f"Excessive caps lock usage ({caps_ratio:.0%})",
                severity=4,
                matched_value=f"{caps_ratio:.0%}"
            ))
        
        # Check excessive punctuation
        if self.check_excessive_punctuation(text):
            flags.append(RedFlag(
                flag_type="excessive_punctuation",
                description="Excessive exclamation/question marks",
                severity=3,
                matched_value=""
            ))
        
        # Check authority impersonation
        authority_matches = self.check_authority_impersonation(text)
        if authority_matches:
            flags.append(RedFlag(
                flag_type="authority_impersonation",
                description="Potential authority impersonation detected",
                severity=7,
                matched_value=str(authority_matches[0])
            ))
        
        return flags
    
    def add_to_blacklist(self, domain: str):
        """Add a domain to the blacklist"""
        self.blacklisted_domains.add(domain.lower())
    
    def remove_from_blacklist(self, domain: str):
        """Remove a domain from the blacklist"""
        self.blacklisted_domains.discard(domain.lower())
