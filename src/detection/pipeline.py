"""
Phishing Detection Pipeline
Unified pipeline that orchestrates all detection stages
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .triage import RuleBasedTriage, TriageResult
from .single_shot import SingleShotClassifier
from .single_shot.classifier import ClassificationResult
from .mad import MultiAgentDebate
from .mad.orchestrator import DebateResult
from .url_checker import get_url_checker

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    """Complete result from the phishing detection pipeline"""
    
    # Final classification
    classification: str  # SAFE, SUSPICIOUS, PHISHING
    confidence: float
    
    # Decision source
    decided_by: str  # triage, single_shot, mad
    
    # Recommended action
    action: str  # none, warn, flag_review, delete
    
    # Stage results
    triage_result: dict | None = None
    single_shot_result: dict | None = None
    mad_result: dict | None = None
    
    # Performance
    total_processing_time_ms: int = 0
    total_tokens_used: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    
    # Metadata
    message_id: str | None = None
    timestamp: str = ""
    
    def to_dict(self) -> dict:
        return {
            "classification": self.classification,
            "confidence": self.confidence,
            "decided_by": self.decided_by,
            "action": self.action,
            "triage_result": self.triage_result,
            "single_shot_result": self.single_shot_result,
            "mad_result": self.mad_result,
            "total_processing_time_ms": self.total_processing_time_ms,
            "total_tokens_used": self.total_tokens_used,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "message_id": self.message_id,
            "timestamp": self.timestamp
        }


class PhishingDetectionPipeline:
    """
    Complete Phishing Detection Pipeline
    
    Flow:
    1. Triage (Rule-Based): Fast filtering
       - SAFE with whitelisted URLs only → Done
       - Shortened URLs expanded & re-evaluated before scoring
       - Otherwise → Stage 2
       
    2. Single-Shot LLM: Quick classification (ROUTER, not final judge)
       - High confidence SAFE (≥90%) → Done
       - PHISHING (any confidence) → Always escalate to Stage 3
       - SUSPICIOUS or low confidence → Stage 3
       
       NOTE: Single-shot NEVER finalizes PHISHING. This prevents
       "yakin tapi salah" — high confidence but wrong PHISHING labels
       that would cause false alerts and spam admin notifications.
       
    3. Multi-Agent Debate: Final verification for PHISHING
       - 3 agents debate and vote
       - Weighted aggregation for final decision
       - Only stage that can finalize PHISHING classification
       
    Action Mapping:
    - SAFE: no action
    - SUSPICIOUS (low conf): flag for review
    - SUSPICIOUS (high conf): warn users
    - PHISHING (conf < 80%): warn + flag
    - PHISHING (conf ≥ 80%): delete message
    """
    
    # Action thresholds
    DELETE_CONFIDENCE_THRESHOLD = 0.80
    WARN_CONFIDENCE_THRESHOLD = 0.60
    
    def __init__(
        self,
        custom_whitelist: set[str] | None = None,
        custom_blacklist: set[str] | None = None
    ):
        """
        Initialize the detection pipeline.
        
        Args:
            custom_whitelist: Additional domains to whitelist
            custom_blacklist: Additional domains to blacklist
        """
        # Initialize stages
        self.triage = RuleBasedTriage(custom_whitelist, custom_blacklist)
        self.single_shot = SingleShotClassifier(triage=self.triage)
        self.mad = MultiAgentDebate(skip_round_2_on_consensus=True)
    
    def process_message(
        self,
        message_text: str,
        message_id: str | None = None,
        message_timestamp: datetime | None = None,
        sender_info: dict | None = None,
        baseline_metrics: dict | None = None,
        url_checks: dict | None = None
    ) -> DetectionResult:
        """
        Process a message through the complete detection pipeline.
        
        Args:
            message_text: The message content to analyze
            message_id: Optional message identifier
            message_timestamp: When message was sent
            sender_info: Information about the sender
            baseline_metrics: User's baseline behavior metrics
            url_checks: Pre-computed URL check results
            
        Returns:
            DetectionResult with final classification and action
        """
        start_time = time.time()
        
        if message_timestamp is None:
            message_timestamp = datetime.now()
        
        total_tokens = 0
        total_tokens_in = 0
        total_tokens_out = 0
        
        # ============================================================
        # Stage 1: Rule-Based Triage
        # ============================================================
        triage_result = self.triage.analyze(
            message_text,
            message_timestamp,
            baseline_metrics,
            url_checks=url_checks  # Pass URL check results from URLSecurityChecker
        )
        
        # If triage says SAFE (only whitelisted URLs), we're done
        if triage_result.skip_llm:
            return self._finalize(
                classification="SAFE",
                confidence=1.0,
                decided_by="triage",
                triage_result=triage_result.to_dict(),
                start_time=start_time,
                total_tokens=0,
                message_id=message_id,
                timestamp=message_timestamp
            )
        
        # ============================================================
        # Stage 2: Single-Shot LLM
        # ============================================================
        single_shot_result = self.single_shot.classify(
            message_text=message_text,
            message_timestamp=message_timestamp,
            sender_info=sender_info,
            baseline_metrics=baseline_metrics,
            skip_triage=True,  # Already have triage result
            triage_result=triage_result
        )
        
        total_tokens_in += single_shot_result.tokens_input
        total_tokens_out += single_shot_result.tokens_output
        total_tokens += single_shot_result.tokens_input + single_shot_result.tokens_output
        
        # Check if we need to escalate to MAD
        if not single_shot_result.should_escalate_to_mad:
            return self._finalize(
                classification=single_shot_result.classification,
                confidence=single_shot_result.confidence,
                decided_by="single_shot",
                triage_result=triage_result.to_dict(),
                single_shot_result=single_shot_result.to_dict(),
                start_time=start_time,
                total_tokens=total_tokens,
                tokens_in=total_tokens_in,
                tokens_out=total_tokens_out,
                message_id=message_id,
                timestamp=message_timestamp
            )
        
        # ============================================================
        # Stage 3: Multi-Agent Debate
        # ============================================================
        
        # URL checks should be passed from handler (async context)
        # If not provided, use heuristic fallback
        if url_checks is None:
            urls_found = triage_result.urls_found if triage_result else []
            if urls_found:
                try:
                    checker = get_url_checker()
                    url_checks = {}
                    for url in urls_found:
                        result = checker._heuristic_check(url)
                        url_checks[url] = result.to_dict()
                    logger.debug(f"Heuristic URL check for {len(urls_found)} URLs")
                except Exception as e:
                    logger.warning(f"Heuristic URL check failed: {e}")
                    url_checks = None
        
        mad_result = self.mad.run_debate(
            message_text=message_text,
            message_timestamp=message_timestamp,
            sender_info=sender_info,
            baseline_metrics=baseline_metrics,
            triage_result=triage_result.to_dict(),
            single_shot_result=single_shot_result.to_dict(),
            url_checks=url_checks,
            parallel=True
        )
        
        total_tokens += mad_result.total_tokens
        
        # Sum MAD agent tokens (each agent response has tokens_input/tokens_output)
        for r in (mad_result.round_1_summary or []):
            total_tokens_in += r.get("tokens_input", 0)
            total_tokens_out += r.get("tokens_output", 0)
        for r in (mad_result.round_2_summary or []):
            total_tokens_in += r.get("tokens_input", 0)
            total_tokens_out += r.get("tokens_output", 0)
        
        return self._finalize(
            classification=self._normalize_classification(mad_result.decision),
            confidence=mad_result.confidence,
            decided_by="mad",
            triage_result=triage_result.to_dict(),
            single_shot_result=single_shot_result.to_dict(),
            mad_result=mad_result.to_dict(),
            start_time=start_time,
            total_tokens=total_tokens,
            tokens_in=total_tokens_in,
            tokens_out=total_tokens_out,
            message_id=message_id,
            timestamp=message_timestamp
        )
    
    def _normalize_classification(self, classification: str) -> str:
        """Normalize classification labels across stages"""
        classification = classification.upper()
        
        # MAD uses LEGITIMATE, pipeline uses SAFE
        if classification == "LEGITIMATE":
            return "SAFE"
        
        return classification
    
    def _determine_action(self, classification: str, confidence: float) -> str:
        """
        Determine recommended action based on classification and confidence.
        
        Returns:
            Action string: none, warn, flag_review
            NOTE: Bot does NOT auto-delete. Admin handles deletion manually.
        """
        if classification == "SAFE":
            return "none"
        
        if classification == "PHISHING":
            # Always flag for admin review, never auto-delete
            return "flag_review"
        
        if classification == "SUSPICIOUS":
            if confidence >= self.WARN_CONFIDENCE_THRESHOLD:
                return "warn"
            else:
                return "flag_review"
        
        return "flag_review"  # Default to review
    
    def _finalize(
        self,
        classification: str,
        confidence: float,
        decided_by: str,
        triage_result: dict | None = None,
        single_shot_result: dict | None = None,
        mad_result: dict | None = None,
        start_time: float = 0,
        total_tokens: int = 0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        message_id: str | None = None,
        timestamp: datetime | None = None
    ) -> DetectionResult:
        """Create final DetectionResult"""
        
        processing_time = int((time.time() - start_time) * 1000)
        action = self._determine_action(classification, confidence)
        
        return DetectionResult(
            classification=classification,
            confidence=confidence,
            decided_by=decided_by,
            action=action,
            triage_result=triage_result,
            single_shot_result=single_shot_result,
            mad_result=mad_result,
            total_processing_time_ms=processing_time,
            total_tokens_used=total_tokens,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            message_id=message_id,
            timestamp=timestamp.isoformat() if timestamp else ""
        )
    
    def quick_check(self, message_text: str) -> tuple[str, str]:
        """
        Quick classification for simple use cases.
        
        Args:
            message_text: Message to check
            
        Returns:
            Tuple of (classification, action)
        """
        result = self.process_message(message_text)
        return result.classification, result.action
