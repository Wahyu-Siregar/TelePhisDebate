"""
Detection Pipeline Module
Complete phishing detection system with 3 stages:
1. Rule-Based Triage
2. Single-Shot LLM
3. Multi-Agent Debate (MAD, configurable mad3/mad5)
"""

from .pipeline import PhishingDetectionPipeline, DetectionResult
from .triage import RuleBasedTriage, TriageResult
from .single_shot import SingleShotClassifier, ClassificationResult
from .mad import MultiAgentDebate
from .mad5 import MultiAgentDebate as MultiAgentDebate5
from .url_checker import (
    URLSecurityChecker,
    URLCheckResult,
    check_urls_external,
    get_url_checker,
    close_url_checker_sync
)

__all__ = [
    "PhishingDetectionPipeline",
    "DetectionResult",
    "RuleBasedTriage",
    "TriageResult",
    "SingleShotClassifier",
    "ClassificationResult",
    "MultiAgentDebate",
    "MultiAgentDebate5",
    "URLSecurityChecker",
    "URLCheckResult",
    "check_urls_external",
    "get_url_checker",
    "close_url_checker_sync"
]
