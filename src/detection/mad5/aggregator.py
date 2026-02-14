"""
Voting aggregator for MAD v5 (five agents).
"""

from dataclasses import dataclass, field

from .agents import AgentResponse


@dataclass
class AggregatedDecision:
    """Final decision from MAD v5."""

    decision: str  # PHISHING, SUSPICIOUS, LEGITIMATE
    confidence: float

    # Voting details
    agent_votes: dict[str, str] = field(default_factory=dict)
    weighted_score: float = 0.0

    # Consensus info
    consensus_reached: bool = False
    consensus_type: str = ""
    rounds_used: int = 1

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
            "total_processing_time_ms": self.total_processing_time_ms,
        }


class VotingAggregator:
    """
    Weighted voting for five-agent MAD.

    The judge and fact-checker carry larger weight because they are expected
    to synthesize or verify evidence rather than only assert stance.
    """

    WEIGHTS = {
        "detector_agent": 1.3,
        "critic_agent": 1.0,
        "defender_agent": 1.0,
        "fact_checker_agent": 1.6,
        "judge_agent": 1.8,
    }

    PHISHING_THRESHOLD = 0.62
    LEGITIMATE_THRESHOLD = 0.38

    def __init__(self, custom_weights: dict | None = None):
        self.weights = self.WEIGHTS.copy()
        if custom_weights:
            self.weights.update(custom_weights)

    def check_consensus(
        self, responses: list[AgentResponse]
    ) -> tuple[bool, str | None, float]:
        stances = [r.stance for r in responses]

        # Unanimous across all 5 agents
        if len(set(stances)) == 1:
            avg_confidence = sum(r.confidence for r in responses) / len(responses)
            return True, stances[0], avg_confidence

        # Strong majority: at least 4 agents agree with decent confidence
        stance_counts: dict[str, dict[str, float]] = {}
        for response in responses:
            if response.stance not in stance_counts:
                stance_counts[response.stance] = {"count": 0, "total_conf": 0.0}
            stance_counts[response.stance]["count"] += 1
            stance_counts[response.stance]["total_conf"] += response.confidence

        for stance, data in stance_counts.items():
            if data["count"] >= 4:
                avg_conf = data["total_conf"] / data["count"]
                if avg_conf >= 0.7:
                    return True, stance, avg_conf

        return False, None, 0.0

    def aggregate(
        self,
        responses: list[AgentResponse],
        round_2_responses: list[AgentResponse] | None = None,
    ) -> AggregatedDecision:
        final_responses = round_2_responses if round_2_responses else responses

        phishing_score = 0.0
        legitimate_score = 0.0
        agent_votes: dict[str, str] = {}

        for response in final_responses:
            weight = self.weights.get(response.agent_type, 1.0) * response.confidence
            agent_votes[response.agent_type] = response.stance

            if response.stance == "PHISHING":
                phishing_score += weight
            elif response.stance == "LEGITIMATE":
                legitimate_score += weight

        decisive_total = phishing_score + legitimate_score
        phishing_prob = phishing_score / decisive_total if decisive_total > 0 else 0.5

        if phishing_prob >= self.PHISHING_THRESHOLD:
            decision = "PHISHING"
        elif phishing_prob <= self.LEGITIMATE_THRESHOLD:
            decision = "LEGITIMATE"
        else:
            decision = "SUSPICIOUS"

        confidence = max(phishing_prob, 1 - phishing_prob)

        consensus_reached, _, _ = self.check_consensus(final_responses)
        stances = [r.stance for r in final_responses]
        decision_votes = stances.count(decision)
        if len(set(stances)) == 1:
            consensus_type = "unanimous"
        elif decision_votes >= 4:
            consensus_type = "strong_majority"
        elif decision_votes >= 3:
            consensus_type = "majority"
        else:
            consensus_type = "weighted"

        all_responses = responses + (round_2_responses or [])
        total_tokens = sum(r.tokens_input + r.tokens_output for r in all_responses)
        total_time = sum(r.processing_time_ms for r in all_responses)

        return AggregatedDecision(
            decision=decision,
            confidence=confidence,
            agent_votes=agent_votes,
            weighted_score=phishing_prob,
            consensus_reached=consensus_reached,
            consensus_type=consensus_type,
            rounds_used=2 if round_2_responses else 1,
            total_tokens=total_tokens,
            total_processing_time_ms=total_time,
        )
