"""
Voting Aggregator for Multi-Agent Debate
Combines agent responses into final decision
"""

from dataclasses import dataclass, field
from typing import Any

from .agents import AgentResponse


@dataclass
class AggregatedDecision:
    """Final decision from multi-agent debate"""
    
    # Final classification
    decision: str  # PHISHING, SUSPICIOUS, LEGITIMATE
    confidence: float
    
    # Voting details
    agent_votes: dict[str, str] = field(default_factory=dict)
    weighted_score: float = 0.0
    
    # Consensus info
    consensus_reached: bool = False
    consensus_type: str = ""  # unanimous, majority, weighted
    rounds_used: int = 1
    
    # All responses
    round_1_responses: list[dict] = field(default_factory=list)
    round_2_responses: list[dict] = field(default_factory=list)
    
    # Metadata
    total_tokens: int = 0
    total_processing_time_ms: int = 0
    
    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "confidence": self.confidence,
            "agent_votes": self.agent_votes,
            "weighted_score": self.weighted_score,
            "consensus_reached": self.consensus_reached,
            "consensus_type": self.consensus_type,
            "rounds_used": self.rounds_used,
            "total_tokens": self.total_tokens,
            "total_processing_time_ms": self.total_processing_time_ms
        }


class VotingAggregator:
    """
    Aggregates agent responses using weighted voting.
    
    Weights (tunable):
    - Content Analyzer: 1.0 (subjective analysis)
    - Security Validator: 1.5 (objective evidence, more trusted)
    - Social Context: 1.0 (contextual analysis)
    
    Decision thresholds:
    - PHISHING: weighted_score >= 0.75
    - LEGITIMATE: weighted_score <= 0.25
    - SUSPICIOUS: 0.25 < weighted_score < 0.75
    """
    
    # Agent weights (higher = more influence)
    WEIGHTS = {
        "content_analyzer": 1.0,
        "security_validator": 1.5,  # Objective evidence trusted more
        "social_context": 1.0
    }
    
    # Decision thresholds
    PHISHING_THRESHOLD = 0.65
    LEGITIMATE_THRESHOLD = 0.35
    
    def __init__(self, custom_weights: dict | None = None):
        """
        Initialize aggregator.
        
        Args:
            custom_weights: Override default agent weights
        """
        self.weights = self.WEIGHTS.copy()
        if custom_weights:
            self.weights.update(custom_weights)
    
    def check_consensus(
        self,
        responses: list[AgentResponse]
    ) -> tuple[bool, str | None, float]:
        """
        Check if agents reached consensus.
        
        Returns:
            Tuple of (consensus_reached, decision, confidence)
        """
        stances = [r.stance for r in responses]
        
        # Unanimous agreement
        if len(set(stances)) == 1:
            avg_confidence = sum(r.confidence for r in responses) / len(responses)
            return True, stances[0], avg_confidence
        
        # Check for strong majority (2 out of 3 with high confidence)
        stance_counts = {}
        for r in responses:
            if r.stance not in stance_counts:
                stance_counts[r.stance] = {"count": 0, "total_conf": 0}
            stance_counts[r.stance]["count"] += 1
            stance_counts[r.stance]["total_conf"] += r.confidence
        
        for stance, data in stance_counts.items():
            if data["count"] >= 2:
                avg_conf = data["total_conf"] / data["count"]
                if avg_conf >= 0.75:
                    return True, stance, avg_conf
        
        return False, None, 0.0
    
    def aggregate(
        self,
        responses: list[AgentResponse],
        round_2_responses: list[AgentResponse] | None = None
    ) -> AggregatedDecision:
        """
        Aggregate agent responses into final decision.
        
        Args:
            responses: Round 1 agent responses
            round_2_responses: Optional Round 2 responses (after deliberation)
            
        Returns:
            AggregatedDecision with final verdict
        """
        return self.aggregate_rounds([responses] + ([round_2_responses] if round_2_responses else []))

    def aggregate_rounds(
        self,
        rounds: list[list[AgentResponse]],
    ) -> AggregatedDecision:
        """
        Aggregate multi-round agent responses into final decision.

        Decision is computed from the final round's responses; metadata (tokens/time)
        is accumulated across all rounds.
        """
        if not rounds or not rounds[0]:
            return AggregatedDecision(
                decision="SUSPICIOUS",
                confidence=0.5,
                consensus_reached=False,
                consensus_type="",
                rounds_used=0,
                total_tokens=0,
                total_processing_time_ms=0,
            )

        round_1 = rounds[0]
        final_responses = rounds[-1]
        
        # Calculate weighted scores
        phishing_score = 0.0
        legitimate_score = 0.0
        total_weight = 0.0
        
        agent_votes = {}
        
        for response in final_responses:
            agent_type = response.agent_type
            weight = self.weights.get(agent_type, 1.0) * response.confidence
            
            agent_votes[agent_type] = response.stance
            
            if response.stance == "PHISHING":
                phishing_score += weight
            elif response.stance == "LEGITIMATE":
                legitimate_score += weight
            # SUSPICIOUS is neutral, doesn't contribute to either score
            
            total_weight += weight
        
        # Calculate weighted probability
        total_decisive = phishing_score + legitimate_score
        if total_decisive > 0:
            phishing_prob = phishing_score / total_decisive
        else:
            phishing_prob = 0.5  # All SUSPICIOUS
        
        # Determine decision
        if phishing_prob >= self.PHISHING_THRESHOLD:
            decision = "PHISHING"
        elif phishing_prob <= self.LEGITIMATE_THRESHOLD:
            decision = "LEGITIMATE"
        else:
            decision = "SUSPICIOUS"
        
        # Calculate confidence
        confidence = max(phishing_prob, 1 - phishing_prob)
        
        # Check consensus type
        consensus_reached, _, _ = self.check_consensus(final_responses)
        
        stances = [r.stance for r in final_responses]
        if len(set(stances)) == 1:
            consensus_type = "unanimous"
        elif stances.count(decision) >= 2:
            consensus_type = "majority"
        else:
            consensus_type = "weighted"
        
        # Calculate totals across all rounds
        all_responses: list[AgentResponse] = []
        for r in rounds:
            all_responses.extend(r)

        total_tokens = sum(r.tokens_input + r.tokens_output for r in all_responses)
        total_time = sum(r.processing_time_ms for r in all_responses)
        
        return AggregatedDecision(
            decision=decision,
            confidence=confidence,
            agent_votes=agent_votes,
            weighted_score=phishing_prob,
            consensus_reached=consensus_reached,
            consensus_type=consensus_type,
            rounds_used=len(rounds),
            round_1_responses=[r.to_dict() for r in round_1],
            # Keep "round_2_responses" as "post-round-1 deliberation responses" for compatibility.
            round_2_responses=[r.to_dict() for r in final_responses] if len(rounds) > 1 else [],
            total_tokens=total_tokens,
            total_processing_time_ms=total_time
        )
