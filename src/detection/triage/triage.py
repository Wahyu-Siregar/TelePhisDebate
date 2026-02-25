"""
Main Triage Module
Combines all rule-based checks into a unified triage system
"""

from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse

from .whitelist import WhitelistChecker
from .blacklist import BlacklistChecker, RedFlag
from .url_analyzer import URLAnalyzer
from .behavioral import BehavioralAnomalyDetector, AnomalyResult
from .url_expander import get_url_expander


@dataclass
class TriageResult:
    """Complete result from triage analysis"""
    
    # Classification
    classification: str  # SAFE, LOW_RISK, HIGH_RISK
    risk_score: int  # 0-100
    
    # Skip LLM?
    skip_llm: bool
    
    # Details
    urls_found: list[str] = field(default_factory=list)
    whitelisted_urls: list[str] = field(default_factory=list)
    expanded_urls: dict = field(default_factory=dict)  # shortened_url → ExpandResult.to_dict()
    
    # Red flags
    red_flags: list[RedFlag] = field(default_factory=list)
    behavioral_anomalies: list[AnomalyResult] = field(default_factory=list)
    
    # Summary
    triggered_flags: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "classification": self.classification,
            "risk_score": self.risk_score,
            "skip_llm": self.skip_llm,
            "urls_found": self.urls_found,
            "whitelisted_urls": self.whitelisted_urls,
            "expanded_urls": self.expanded_urls,
            "triggered_flags": self.triggered_flags,
            "red_flags_count": len(self.red_flags),
            "anomalies_count": len(self.behavioral_anomalies)
        }


class RuleBasedTriage:
    """
    Sistem Triage Berbasis Rule
    
    Stage 1 dari pipeline deteksi phishing.
    Melakukan penyaringan cepat berbasis rule sebelum analisis LLM.
    
    Perhitungan Risk Score:
    - Blacklisted domain: +50
    - Shortened URL (destination unknown/suspicious): +10
    - Shortened URL (destination whitelisted): 0 (risk dihapus)
    - Suspicious TLD: +15
    - Urgency keywords (2+): +15
    - Phishing keywords: +20
    - First-time URL sharing: +10
    - Time anomaly: +10
    - Style deviation: +15
    - CAPS LOCK abuse: +10
    - Authority impersonation: +20
    
    Kebijakan URL Shortener:
    - Shortener BUKAN indikator kuat phishing (dosen sering pakai).
    - Sistem akan expand (follow redirect) untuk mendapatkan domain tujuan.
    - Jika tujuan whitelisted → risk dikurangi (shortener aman).
    - Jika tujuan unknown → hanya sedikit mencurigakan.
    - Jika tujuan blacklisted → risk tetap tinggi via blacklisted_domain.
    
    Klasifikasi:
    - SAFE: risk_score == 0 DAN hanya URL whitelisted
    - LOW_RISK: risk_score < 30
    - HIGH_RISK: risk_score >= 30
    """
    
    # Score weights for different red flags
    # NOTE: shortened_url turun dari 20 → 10. Shortener sendiri bukan
    # indikator kuat phishing. Yang penting adalah domain tujuan.
    SCORE_WEIGHTS = {
        "blacklisted_domain": 50,
        "shortened_url": 10,             # ← turun dari 20 (mild signal)
        "shortened_url_expand_failed": 15,  # gagal expand → sedikit lebih curiga
        "suspicious_tld": 15,
        "urgency_keywords": 15,
        "phishing_keywords": 20,
        "caps_lock_abuse": 10,
        "excessive_punctuation": 5,
        "authority_impersonation": 20,
        "time_anomaly": 10,
        "length_anomaly": 10,
        "first_time_url": 10,
        "emoji_anomaly": 5,
    }
    
    # Negative weight: shortener pointing to whitelisted domain
    # This REMOVES the shortened_url risk score
    SHORTENER_WHITELISTED_BONUS = -10
    
    # Thresholds
    LOW_RISK_THRESHOLD = 30
    
    def __init__(
        self,
        custom_whitelist: set[str] | None = None,
        custom_blacklist: set[str] | None = None
    ):
        """
        Initialize triage system.
        
        Args:
            custom_whitelist: Additional domains to whitelist
            custom_blacklist: Additional domains to blacklist
        """
        self.whitelist_checker = WhitelistChecker(custom_whitelist)
        self.blacklist_checker = BlacklistChecker(custom_blacklist)
        self.url_analyzer = URLAnalyzer()
        self.behavioral_detector = BehavioralAnomalyDetector()
        self.url_expander = get_url_expander()
    
    def analyze(
        self,
        message_text: str,
        message_timestamp: datetime | None = None,
        user_baseline: dict | None = None,
        url_checks: dict | None = None
    ) -> TriageResult:
        """
        Perform complete triage analysis on a message.
        
        Args:
            message_text: The message content to analyze
            message_timestamp: When the message was sent
            user_baseline: User's baseline metrics from database
            url_checks: Pre-computed URL check results from URLSecurityChecker
                        (contains expanded_url, is_malicious, source=whitelist, etc.)
            
        Returns:
            TriageResult with classification and details
        """
        if message_timestamp is None:
            message_timestamp = datetime.now()
        
        if user_baseline is None:
            user_baseline = {}
        
        if url_checks is None:
            url_checks = {}
        
        # Initialize result
        risk_score = 0
        red_flags: list[RedFlag] = []
        behavioral_anomalies: list[AnomalyResult] = []
        triggered_flags: list[str] = []
        expanded_urls: dict = {}  # Track expansion results
        expanded_destinations: dict[str, str | None] = {}  # url → final_domain
        
        # Pre-process url_checks to find trusted URLs (from URLSecurityChecker)
        # These URLs were already expanded and determined to be safe
        trusted_urls_from_checker: set[str] = set()
        for url, check_result in url_checks.items():
            if isinstance(check_result, dict):
                # URL is trusted if: source=whitelist OR (not malicious AND risk_score=0)
                source = check_result.get('source', '')
                is_malicious = check_result.get('is_malicious', False)
                try:
                    risk = float(check_result.get('risk_score', 1.0))
                except (TypeError, ValueError):
                    risk = 1.0
                
                if source == 'whitelist' or (not is_malicious and risk <= 0.10):
                    trusted_urls_from_checker.add(url)
                
                # Preserve expansion evidence from external checker for downstream LLM prompts
                expanded_url = check_result.get("expanded_url")
                if expanded_url:
                    parsed = urlparse(expanded_url)
                    final_domain = (parsed.netloc or "").lower()
                    if final_domain.startswith("www."):
                        final_domain = final_domain[4:]
                    final_domain = final_domain.split(":")[0]
                    
                    expanded_urls[url] = {
                        "original_url": url,
                        "is_shortened": self.url_expander.is_shortened(url),
                        "expanded_url": expanded_url,
                        "final_domain": final_domain or None,
                        "expansion_success": True,
                        "from_cache": False,
                        "error": None,
                        "source": check_result.get("source", "url_checker")
                    }
                    if final_domain:
                        expanded_destinations[url] = final_domain
        
        # Step 1: Extract and analyze URLs
        urls = self.url_analyzer.extract_urls(message_text)
        has_urls = len(urls) > 0
        
        # Step 2: Expand shortened URLs → get destination domain
        # BUT: skip expansion if URL was already checked by URLSecurityChecker
        for url in urls:
            # Already have expansion evidence from URLSecurityChecker
            if url in expanded_urls:
                continue
            
            # If URL was already verified as trusted by async checker, skip local expansion
            if url in trusted_urls_from_checker:
                continue
            
            expand_result = self.url_expander.expand(url)
            if expand_result.is_shortened:
                expanded_urls[url] = expand_result.to_dict()
                expanded_destinations[url] = expand_result.final_domain
        
        # Step 3: Check whitelist
        whitelist_result = self.whitelist_checker.check_urls(urls)
        whitelisted_urls = whitelist_result["whitelisted"]
        non_whitelisted_urls = whitelist_result["not_whitelisted"]
        
        # IMPORTANT: Add trusted URLs from URLSecurityChecker to whitelisted
        # These URLs were already expanded + verified (e.g., bit.ly → Google Forms)
        for url in list(non_whitelisted_urls):
            if url in trusted_urls_from_checker:
                non_whitelisted_urls.remove(url)
                whitelisted_urls.append(url)
        
        # Check if expanded destinations are whitelisted
        # If a shortener points to a whitelisted domain,
        # move it from non_whitelisted to whitelisted
        shortener_whitelisted: list[str] = []
        for url in list(non_whitelisted_urls):
            if url in expanded_destinations:
                final_domain = expanded_destinations[url]
                if final_domain and self.whitelist_checker.is_whitelisted(f"https://{final_domain}"):
                    # Shortener → whitelisted domain: treat as safe
                    non_whitelisted_urls.remove(url)
                    whitelisted_urls.append(url)
                    shortener_whitelisted.append(url)
        
        # Recalculate all_whitelisted after expansion
        all_whitelisted = len(non_whitelisted_urls) == 0 and len(whitelisted_urls) > 0
        
        # Step 4: Check URLs for red flags (only non-whitelisted)
        for url in non_whitelisted_urls:
            url_flags = self.blacklist_checker.analyze_url(url)
            
            # If this was a shortened URL, adjust the flag
            if url in expanded_destinations:
                final_domain = expanded_destinations[url]
                expand_data = expanded_urls.get(url, {})
                expansion_success = expand_data.get("expansion_success", False)
                
                # Replace shortened_url flag with more nuanced flags
                adjusted_flags = []
                for flag in url_flags:
                    if flag.flag_type == "shortened_url":
                        if not expansion_success:
                            # Could not expand → slightly more suspicious
                            adjusted_flags.append(RedFlag(
                                flag_type="shortened_url_expand_failed",
                                description="Shortened URL could not be expanded (destination unknown)",
                                severity=5,
                                matched_value=flag.matched_value
                            ))
                        else:
                            # Expanded but destination not whitelisted → mild signal
                            adjusted_flags.append(RedFlag(
                                flag_type="shortened_url",
                                description=f"Shortened URL → {final_domain} (not whitelisted, needs review)",
                                severity=3,  # Reduced from 6
                                matched_value=f"{flag.matched_value} → {final_domain}"
                            ))
                    else:
                        adjusted_flags.append(flag)
                
                # Also check expanded destination for blacklist/suspicious TLD
                if final_domain and expansion_success:
                    expanded_url_str = f"https://{final_domain}"
                    dest_flags = self.blacklist_checker.analyze_url(expanded_url_str)
                    adjusted_flags.extend(dest_flags)
                
                red_flags.extend(adjusted_flags)
            else:
                red_flags.extend(url_flags)
        
        # Step 5: Check text for red flags
        text_flags = self.blacklist_checker.analyze_text(message_text)
        red_flags.extend(text_flags)
        
        # Step 6: Check behavioral anomalies
        behavioral_anomalies = self.behavioral_detector.analyze_all(
            message_text,
            message_timestamp,
            has_urls,
            user_baseline
        )
        
        # Step 7: Calculate risk score
        for flag in red_flags:
            weight = self.SCORE_WEIGHTS.get(flag.flag_type, 10)
            risk_score += weight
            triggered_flags.append(flag.flag_type)
        
        for anomaly in behavioral_anomalies:
            weight = self.SCORE_WEIGHTS.get(anomaly.anomaly_type, 10)
            # Scale by deviation score
            risk_score += int(weight * anomaly.deviation_score)
            triggered_flags.append(anomaly.anomaly_type)
        
        # Apply bonus: if shortened URL resolved to whitelisted domain,
        # remove the shortened_url risk that was added
        for url in shortener_whitelisted:
            risk_score += self.SHORTENER_WHITELISTED_BONUS
        
        # Ensure risk_score doesn't go negative, cap at 100
        risk_score = max(0, min(risk_score, 100))
        
        # Step 8: Determine classification
        if risk_score == 0:
            if all_whitelisted or not has_urls:
                # Safe: No red flags AND (only whitelisted URLs OR no URLs)
                classification = "SAFE"
                skip_llm = True
            else:
                # Has non-whitelisted URLs but no red flags
                classification = "LOW_RISK"
                skip_llm = False
        elif risk_score < self.LOW_RISK_THRESHOLD:
            classification = "LOW_RISK"
            skip_llm = False
        else:
            classification = "HIGH_RISK"
            skip_llm = False
        
        return TriageResult(
            classification=classification,
            risk_score=risk_score,
            skip_llm=skip_llm,
            urls_found=urls,
            whitelisted_urls=whitelisted_urls,
            expanded_urls=expanded_urls,
            red_flags=red_flags,
            behavioral_anomalies=behavioral_anomalies,
            triggered_flags=list(set(triggered_flags))
        )
    
    def quick_check(self, message_text: str) -> str:
        """
        Quick classification without full analysis.
        
        Args:
            message_text: Message to check
            
        Returns:
            Classification string: SAFE, LOW_RISK, or HIGH_RISK
        """
        result = self.analyze(message_text)
        return result.classification
