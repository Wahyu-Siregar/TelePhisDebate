"""
Multi-Agent Debate (MAD) v5 Module
Stage 3 alternative with five specialized debate agents.
"""

from .orchestrator import MultiAgentDebate
from .agents import (
    DetectorAgent,
    CriticAgent,
    DefenderAgent,
    FactCheckerAgent,
    JudgeAgent,
)
from .aggregator import VotingAggregator

__all__ = [
    "MultiAgentDebate",
    "DetectorAgent",
    "CriticAgent",
    "DefenderAgent",
    "FactCheckerAgent",
    "JudgeAgent",
    "VotingAggregator",
]
