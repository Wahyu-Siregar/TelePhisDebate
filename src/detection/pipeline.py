"""
Phishing Detection Pipeline
Unified pipeline that orchestrates all detection stages
"""

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.config import config
from .triage import RuleBasedTriage, TriageResult
from .single_shot import SingleShotClassifier
from .single_shot.classifier import ClassificationResult
from .mad import MultiAgentDebate as MultiAgentDebateV3
from .mad5 import MultiAgentDebate as MultiAgentDebateV5
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
    Pipeline Deteksi Phishing Lengkap
    
    Alur:
    1. Triage (Berbasis Rule): Filtering cepat
       - SAFE dengan hanya URLs terdaftar → Selesai
       - Shortened URLs diperluas & dievaluasi ulang sebelum scoring
       - Selainnya → Stage 2
       
    2. Single-Shot LLM: Klasifikasi cepat (ROUTER, bukan judge final)
       - SAFE dengan confidence tinggi (≥90%) → Selesai
       - PHISHING (confidence apapun) → Selalu eskalasi ke Stage 3
       - SUSPICIOUS atau confidence rendah → Stage 3
       
       CATATAN: Single-shot TIDAK PERNAH menyelesaikan PHISHING. Ini mencegah
       "yakin tapi salah" — label PHISHING dengan confidence tinggi tapi hasil
       yang salah yang akan menyebabkan false alerts dan spam notifikasi admin.
       
    3. Multi-Agent Debate: Verifikasi final untuk PHISHING
       - Mode `mad3`: 3 agents berdebat dan memberikan vote
       - Mode `mad5`: 5 agents (detector/critic/defender/fact-checker/judge)
       - Weighted aggregation untuk keputusan final
       - Hanya stage yang dapat menyelesaikan klasifikasi PHISHING
       
    Pemetaan Action:
    - SAFE: tidak ada action
    - SUSPICIOUS (confidence rendah): tandai untuk review
    - SUSPICIOUS (confidence tinggi): peringatkan users
    - PHISHING (confidence < 80%): peringatkan + tandai
    - PHISHING (confidence ≥ 80%): hapus pesan
    """
    
    # Action thresholds
    DELETE_CONFIDENCE_THRESHOLD = 0.80
    WARN_CONFIDENCE_THRESHOLD = 0.60
    
    def __init__(
        self,
        custom_whitelist: set[str] | None = None,
        custom_blacklist: set[str] | None = None,
        mad_mode: str = "mad3",
    ):
        """
        Initialize the detection pipeline.
        
        Args:
            custom_whitelist: Additional domains to whitelist
            custom_blacklist: Additional domains to blacklist
            mad_mode: MAD variant to use ("mad3" default or "mad5")
        """
        # Initialize stages
        self.triage = RuleBasedTriage(custom_whitelist, custom_blacklist)
        self.single_shot = SingleShotClassifier(triage=self.triage)
        self.mad_mode = (mad_mode or "mad3").strip().lower()

        # MAD runtime tuning (optional). Defaults preserve existing behavior.
        # Example: export MAD_MAX_ROUNDS=3
        try:
            mad_max_rounds = int(os.getenv("MAD_MAX_ROUNDS", "2"))
        except ValueError:
            mad_max_rounds = 2

        mad_skip_round_on_consensus = os.getenv("MAD_EARLY_TERMINATION", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "y",
            "on",
        }

        try:
            mad_max_total_time_ms_raw = os.getenv("MAD_MAX_TOTAL_TIME_MS", "").strip()
            mad_max_total_time_ms = int(mad_max_total_time_ms_raw) if mad_max_total_time_ms_raw else None
        except ValueError:
            mad_max_total_time_ms = None

        if self.mad_mode == "mad3":
            self.mad = MultiAgentDebateV3(
                skip_round_2_on_consensus=mad_skip_round_on_consensus,
                max_rounds=mad_max_rounds,
                max_total_time_ms=mad_max_total_time_ms,
            )
        elif self.mad_mode == "mad5":
            self.mad = MultiAgentDebateV5(
                skip_round_2_on_consensus=mad_skip_round_on_consensus,
                max_rounds=mad_max_rounds,
                max_total_time_ms=mad_max_total_time_ms,
            )
        else:
            raise ValueError(
                f"Unsupported mad_mode='{mad_mode}'. Use 'mad3' or 'mad5'."
            )
    
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
        # If not provided, run synchronous URL checker (expand + VT/heuristic)
        if url_checks is None:
            urls_found = triage_result.urls_found if triage_result else []
            if urls_found:
                try:
                    checker = get_url_checker()
                    try:
                        url_checks = checker.check_urls_sync(urls_found)
                        logger.debug(f"Sync URL check for {len(urls_found)} URLs")
                    except Exception as e:
                        logger.warning(f"Sync URL check failed, fallback to heuristic: {e}")
                        try:
                            url_checks = {}
                            for url in urls_found:
                                result = checker._heuristic_check(url)
                                url_checks[url] = result.to_dict()
                        except Exception as fallback_error:
                            logger.warning(f"Heuristic URL check failed: {fallback_error}")
                            url_checks = None
                except Exception as checker_error:
                    logger.warning(f"URL checker initialization failed: {checker_error}")
                    url_checks = None
        
        mad_result = self.mad.run_debate(
            message_text=message_text,
            message_timestamp=message_timestamp,
            sender_info=sender_info,
            baseline_metrics=baseline_metrics,
            triage_result=triage_result.to_dict(),
            single_shot_result=single_shot_result.to_dict(),
            url_checks=url_checks,
            # OpenRouter free tier is sensitive to burst; default to sequential agent calls.
            parallel=(
                (config.LLM_PROVIDER or "deepseek").strip().lower() != "openrouter"
                or bool(getattr(config, "OPENROUTER_PARALLEL", False))
            )
        )
        
        total_tokens += mad_result.total_tokens
        
        # Sum MAD agent tokens (each agent response has tokens_input/tokens_output)
        for r in (mad_result.round_1_summary or []):
            total_tokens_in += r.get("tokens_input", 0)
            total_tokens_out += r.get("tokens_output", 0)
        for r in (mad_result.round_2_summary or []):
            total_tokens_in += r.get("tokens_input", 0)
            total_tokens_out += r.get("tokens_output", 0)
        
        mad_payload = mad_result.to_dict()
        mad_payload.setdefault("variant", self.mad_mode)

        return self._finalize(
            classification=self._normalize_classification(mad_result.decision),
            confidence=mad_result.confidence,
            decided_by="mad",
            triage_result=triage_result.to_dict(),
            single_shot_result=single_shot_result.to_dict(),
            mad_result=mad_payload,
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
