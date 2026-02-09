"""
Single-Shot LLM Module
Stage 2 of the detection pipeline - LLM-based classification
"""

from .classifier import SingleShotClassifier, ClassificationResult
from .prompts import SYSTEM_PROMPT, construct_analysis_prompt

__all__ = [
    "SingleShotClassifier",
    "ClassificationResult",
    "SYSTEM_PROMPT",
    "construct_analysis_prompt"
]
