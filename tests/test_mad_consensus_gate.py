from src.detection.mad.agents import AgentResponse as Mad3AgentResponse
from src.detection.mad.aggregator import VotingAggregator as Mad3VotingAggregator
from src.detection.mad5.agents import AgentResponse as Mad5AgentResponse
from src.detection.mad5.aggregator import VotingAggregator as Mad5VotingAggregator


def test_mad3_unanimous_low_confidence_not_consensus():
    agg = Mad3VotingAggregator()
    responses = [
        Mad3AgentResponse("content_analyzer", "PHISHING", 0.60),
        Mad3AgentResponse("security_validator", "PHISHING", 0.55),
        Mad3AgentResponse("social_context", "PHISHING", 0.58),
    ]

    consensus, decision, confidence = agg.check_consensus(responses)

    assert consensus is False
    assert decision is None
    assert confidence == 0.0


def test_mad5_unanimous_low_confidence_not_consensus():
    agg = Mad5VotingAggregator()
    responses = [
        Mad5AgentResponse("detector_agent", "PHISHING", 0.60),
        Mad5AgentResponse("critic_agent", "PHISHING", 0.60),
        Mad5AgentResponse("defender_agent", "PHISHING", 0.60),
        Mad5AgentResponse("fact_checker_agent", "PHISHING", 0.60),
        Mad5AgentResponse("judge_agent", "PHISHING", 0.60),
    ]

    consensus, decision, confidence = agg.check_consensus(responses)

    assert consensus is False
    assert decision is None
    assert confidence == 0.0
