"""
Single-Shot LLM Classifier
Main classifier that uses DeepSeek for phishing detection
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.llm import deepseek
from src.detection.triage import RuleBasedTriage, TriageResult
from .prompts import SYSTEM_PROMPT, construct_analysis_prompt


@dataclass
class ClassificationResult:
    """Result from Single-Shot LLM classification"""
    
    # Classification
    classification: str  # SAFE, SUSPICIOUS, PHISHING
    confidence: float  # 0.0-1.0
    reasoning: str
    risk_factors: list[str] = field(default_factory=list)
    
    # Escalation decision
    should_escalate_to_mad: bool = False
    escalation_reason: str = ""
    
    # Metadata
    tokens_input: int = 0
    tokens_output: int = 0
    processing_time_ms: int = 0
    
    # Original triage
    triage_result: dict | None = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "classification": self.classification,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "risk_factors": self.risk_factors,
            "should_escalate_to_mad": self.should_escalate_to_mad,
            "escalation_reason": self.escalation_reason,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "processing_time_ms": self.processing_time_ms
        }


class SingleShotClassifier:
    """
    Single-Shot LLM Classifier
    
    Stage 2 of the phishing detection pipeline.
    Acts as a ROUTER — uses DeepSeek LLM for initial classification.
    
    IMPORTANT: Single-shot is NOT the final judge for PHISHING.
    It can only finalize SAFE decisions. All PHISHING and ambiguous
    cases are escalated to MAD (Stage 3) for verification.
    
    This prevents "yakin tapi salah" — high confidence but wrong
    PHISHING labels that would cause false alerts and spam admin.
    
    Escalation to MAD (Stage 3) occurs when:
    - Classification is PHISHING (always — needs MAD verification)
    - Classification is SUSPICIOUS (always)
    - Confidence < 0.70 (ambiguous)
    - High triage risk + moderate LLM uncertainty
    
    Only finalized at this stage:
    - High confidence SAFE (≥90%)
    """
    
    # Thresholds for decision making
    HIGH_CONFIDENCE_SAFE = 0.90
    HIGH_CONFIDENCE_PHISHING = 0.85
    LOW_CONFIDENCE_THRESHOLD = 0.70
    MODERATE_CONFIDENCE_THRESHOLD = 0.80
    
    # Triage risk threshold for escalation
    HIGH_TRIAGE_RISK = 50
    
    def __init__(self, triage: RuleBasedTriage | None = None):
        """
        Initialize classifier.
        
        Args:
            triage: Optional RuleBasedTriage instance for pre-filtering
        """
        self.triage = triage or RuleBasedTriage()
        self._llm = None
    
    @property
    def llm(self):
        """Lazy load LLM client"""
        if self._llm is None:
            self._llm = deepseek()
        return self._llm
    
    def classify(
        self,
        message_text: str,
        message_timestamp: datetime | None = None,
        sender_info: dict | None = None,
        baseline_metrics: dict | None = None,
        skip_triage: bool = False,
        triage_result: TriageResult | None = None
    ) -> ClassificationResult:
        """
        Classify a message using Single-Shot LLM.
        
        Args:
            message_text: The message to classify
            message_timestamp: When the message was sent
            sender_info: Information about the sender
            baseline_metrics: User's baseline metrics
            skip_triage: If True, skip triage stage
            triage_result: Pre-computed triage result
            
        Returns:
            ClassificationResult with classification and escalation decision
        """
        start_time = time.time()
        
        if message_timestamp is None:
            message_timestamp = datetime.now()
        
        # Step 1: Run triage if not skipped
        if triage_result is None and not skip_triage:
            triage_result = self.triage.analyze(
                message_text,
                message_timestamp,
                baseline_metrics
            )
        
        # Check if triage says SAFE (skip LLM)
        if triage_result and triage_result.skip_llm:
            return ClassificationResult(
                classification="SAFE",
                confidence=1.0,
                reasoning="Pesan hanya berisi URL dari domain terpercaya atau tidak ada indikator risiko",
                risk_factors=[],
                should_escalate_to_mad=False,
                escalation_reason="",
                processing_time_ms=int((time.time() - start_time) * 1000),
                triage_result=triage_result.to_dict() if triage_result else None
            )
        
        # Step 2: Construct prompt
        triage_dict = triage_result.to_dict() if triage_result else None
        prompt = construct_analysis_prompt(
            message_text=message_text,
            message_timestamp=message_timestamp,
            sender_info=sender_info,
            baseline_metrics=baseline_metrics,
            triage_result=triage_dict
        )
        
        # Step 3: Call LLM
        try:
            llm_response = self.llm.chat_completion(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower for consistency
                max_tokens=500,   # Increased for full reasoning
                json_mode=True
            )
            
            # Parse response
            content = llm_response["content"]
            if isinstance(content, str):
                content = json.loads(content)
            
            classification = content.get("classification", "SUSPICIOUS")
            confidence = float(content.get("confidence", 0.5))
            reasoning = content.get("reasoning", "")
            risk_factors = content.get("risk_factors", [])
            
        except Exception as e:
            # Fallback to heuristic-based decision
            return self._fallback_classification(
                message_text,
                triage_result,
                str(e),
                int((time.time() - start_time) * 1000)
            )
        
        # Step 4: Determine escalation to MAD
        triage_risk = triage_result.risk_score if triage_result else 0
        should_escalate, escalation_reason = self._should_escalate(
            classification, confidence, triage_risk
        )
        
        processing_time = int((time.time() - start_time) * 1000)
        
        return ClassificationResult(
            classification=classification,
            confidence=confidence,
            reasoning=reasoning,
            risk_factors=risk_factors,
            should_escalate_to_mad=should_escalate,
            escalation_reason=escalation_reason,
            tokens_input=llm_response.get("tokens_input", 0),
            tokens_output=llm_response.get("tokens_output", 0),
            processing_time_ms=processing_time,
            triage_result=triage_dict
        )
    
    def _should_escalate(
        self,
        classification: str,
        confidence: float,
        triage_risk_score: int
    ) -> tuple[bool, str]:
        """
        Determine if case should escalate to Multi-Agent Debate.
        
        RULE: Single-shot NEVER finalizes PHISHING.
        All PHISHING labels must be verified by MAD to prevent
        false alerts ("yakin tapi salah" problem).
        
        Returns:
            Tuple of (should_escalate, reason)
        """
        # PHISHING always escalates — single-shot must not be final judge
        if classification == "PHISHING":
            return True, f"PHISHING classification always requires MAD verification (confidence: {confidence:.0%})"
        
        # SUSPICIOUS always escalates
        if classification == "SUSPICIOUS":
            return True, "SUSPICIOUS classification requires multi-agent verification"
        
        # High confidence SAFE: no escalation
        if confidence >= self.HIGH_CONFIDENCE_SAFE and classification == "SAFE":
            return False, ""
        
        # Low confidence SAFE: escalate (not sure enough)
        if confidence < self.LOW_CONFIDENCE_THRESHOLD:
            return True, f"Low confidence ({confidence:.0%}) requires multi-agent verification"
        
        # High triage risk + moderate uncertainty: escalate
        if triage_risk_score >= self.HIGH_TRIAGE_RISK and confidence < self.MODERATE_CONFIDENCE_THRESHOLD:
            return True, f"High triage risk ({triage_risk_score}) with moderate confidence ({confidence:.0%})"
        
        return False, ""
    
    def _fallback_classification(
        self,
        message_text: str,
        triage_result: TriageResult | None,
        error_message: str,
        processing_time_ms: int
    ) -> ClassificationResult:
        """
        Fallback classification when LLM fails.
        Uses triage result if available.
        """
        if triage_result:
            # Use triage classification
            if triage_result.classification == "HIGH_RISK":
                classification = "SUSPICIOUS"
                confidence = 0.6
            elif triage_result.classification == "LOW_RISK":
                classification = "SUSPICIOUS"
                confidence = 0.5
            else:
                classification = "SAFE"
                confidence = 0.7
        else:
            # Very conservative fallback
            classification = "SUSPICIOUS"
            confidence = 0.5
        
        return ClassificationResult(
            classification=classification,
            confidence=confidence,
            reasoning=f"Fallback classification due to LLM error: {error_message}",
            risk_factors=["llm_error"],
            should_escalate_to_mad=True,
            escalation_reason="LLM error - requires manual verification",
            processing_time_ms=processing_time_ms,
            triage_result=triage_result.to_dict() if triage_result else None
        )
    
    def quick_classify(self, message_text: str) -> str:
        """
        Quick classification without full context.
        
        Args:
            message_text: Message to classify
            
        Returns:
            Classification string: SAFE, SUSPICIOUS, or PHISHING
        """
        result = self.classify(message_text)
        return result.classification
