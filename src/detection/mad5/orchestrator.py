"""
MAD v5 orchestrator.
Coordinates debate between detector, critic, defender, fact-checker, and judge.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime

from .agents import (
    AgentResponse,
    CriticAgent,
    DefenderAgent,
    DetectorAgent,
    FactCheckerAgent,
    JudgeAgent,
)
from .aggregator import VotingAggregator


def _is_fatal_llm_error(exc: Exception) -> bool:
    """
    Detect non-recoverable LLM errors (usually misconfiguration).

    If these happen, silently defaulting to SUSPICIOUS will poison evaluations.
    """
    name = exc.__class__.__name__
    msg = str(exc)
    fatal_markers = ("NotFoundError", "AuthenticationError", "PermissionDeniedError")
    if name in fatal_markers:
        return True
    return any(m in msg for m in fatal_markers)


@dataclass
class DebateResult:
    """Result from MAD v5 debate."""

    variant: str

    # Final decision
    decision: str
    confidence: float

    # Debate details
    rounds_executed: int
    consensus_reached: bool
    consensus_type: str
    consensus_round: int | None
    stop_reason: str  # consensus | max_rounds | timeout

    # Agent responses
    agent_votes: dict[str, str]
    round_1_summary: list[dict]
    round_2_summary: list[dict] | None
    round_summaries: list[list[dict]]

    # Metadata
    total_tokens: int
    total_processing_time_ms: int

    def to_dict(self) -> dict:
        return {
            "variant": self.variant,
            "decision": self.decision,
            "confidence": self.confidence,
            "rounds_executed": self.rounds_executed,
            "consensus_reached": self.consensus_reached,
            "consensus_type": self.consensus_type,
            "consensus_round": self.consensus_round,
            "stop_reason": self.stop_reason,
            "agent_votes": self.agent_votes,
            "round_1_summary": self.round_1_summary,
            "round_2_summary": self.round_2_summary,
            "round_summaries": self.round_summaries,
            "total_tokens": self.total_tokens,
            "total_processing_time_ms": self.total_processing_time_ms,
        }


class MultiAgentDebate:
    """Five-agent MAD implementation."""

    def __init__(
        self,
        skip_round_2_on_consensus: bool = True,
        max_rounds: int = 2,
        max_total_time_ms: int | None = None,
    ):
        self.skip_round_2_on_consensus = skip_round_2_on_consensus
        self.max_rounds = max(1, int(max_rounds or 2))
        self.max_total_time_ms = int(max_total_time_ms) if max_total_time_ms else None
        self.agents = {
            "detector": DetectorAgent(),
            "critic": CriticAgent(),
            "defender": DefenderAgent(),
            "fact_checker": FactCheckerAgent(),
            "judge": JudgeAgent(),
        }
        self.aggregator = VotingAggregator()

    def run_debate(
        self,
        message_text: str,
        message_timestamp: datetime | None = None,
        sender_info: dict | None = None,
        baseline_metrics: dict | None = None,
        triage_result: dict | None = None,
        single_shot_result: dict | None = None,
        url_checks: dict | None = None,
        parallel: bool = True,
    ) -> DebateResult:
        start_time = time.time()

        if message_timestamp is None:
            message_timestamp = datetime.now()

        message_data = {
            "content": message_text,
            "length": len(message_text),
            "timestamp": message_timestamp.strftime("%Y-%m-%d %H:%M"),
            "sender": sender_info or {},
            "urls": triage_result.get("urls_found", []) if triage_result else [],
            "triage": triage_result or {},
        }

        context = {
            "baseline": baseline_metrics or {},
            "url_checks": url_checks or {},
            "recent_topics": [],
        }

        rounds: list[list[AgentResponse]] = []
        consensus_round: int | None = None
        stop_reason = "max_rounds"

        round_1_responses = self._run_round_1(
            message_data=message_data,
            context=context,
            previous_result=single_shot_result,
            parallel=parallel,
        )
        rounds.append(round_1_responses)

        consensus, _, _ = self.aggregator.check_consensus(round_1_responses)
        if consensus:
            consensus_round = 1
            if self.skip_round_2_on_consensus and self.max_rounds <= 1:
                stop_reason = "consensus"

        previous_round = round_1_responses
        for round_idx in range(2, self.max_rounds + 1):
            if self.max_total_time_ms is not None:
                elapsed_ms = int((time.time() - start_time) * 1000)
                if elapsed_ms >= self.max_total_time_ms:
                    stop_reason = "timeout"
                    break

            if self.skip_round_2_on_consensus:
                consensus_now, _, _ = self.aggregator.check_consensus(previous_round)
                if consensus_now:
                    stop_reason = "consensus"
                    break

            next_round = self._run_deliberation_round(
                message_data=message_data,
                previous_round_responses=previous_round,
                context=context,
                parallel=parallel,
            )
            rounds.append(next_round)
            previous_round = next_round

            consensus_now, _, _ = self.aggregator.check_consensus(next_round)
            if consensus_now and consensus_round is None:
                consensus_round = round_idx

        aggregated = self.aggregator.aggregate_rounds(rounds)
        total_time = int((time.time() - start_time) * 1000)

        round_summaries = [[response.to_dict() for response in resp_round] for resp_round in rounds]
        return DebateResult(
            variant="mad5",
            decision=aggregated.decision,
            confidence=aggregated.confidence,
            rounds_executed=len(rounds),
            consensus_reached=aggregated.consensus_reached,
            consensus_type=aggregated.consensus_type,
            consensus_round=consensus_round if aggregated.consensus_reached else None,
            stop_reason=stop_reason,
            agent_votes=aggregated.agent_votes,
            round_1_summary=round_summaries[0],
            round_2_summary=round_summaries[1] if len(round_summaries) > 1 else None,
            round_summaries=round_summaries,
            total_tokens=aggregated.total_tokens,
            total_processing_time_ms=total_time,
        )

    def _run_round_1(
        self,
        message_data: dict,
        context: dict,
        previous_result: dict | None,
        parallel: bool,
    ) -> list[AgentResponse]:
        if parallel:
            responses: list[AgentResponse] = []
            with ThreadPoolExecutor(max_workers=len(self.agents)) as executor:
                futures = {
                    executor.submit(
                        agent.analyze, message_data, context, previous_result
                    ): agent
                    for agent in self.agents.values()
                }
                for future in as_completed(futures):
                    agent = futures[future]
                    try:
                        responses.append(future.result())
                    except Exception as exc:
                        if _is_fatal_llm_error(exc):
                            raise
                        responses.append(
                            AgentResponse(
                                agent_type=agent.agent_type,
                                stance="SUSPICIOUS",
                                confidence=0.5,
                                key_arguments=[f"Round 1 error: {exc}"],
                            )
                        )
            return responses

        return [
            agent.analyze(message_data, context, previous_result)
            for agent in self.agents.values()
        ]

    def _run_deliberation_round(
        self,
        message_data: dict,
        previous_round_responses: list[AgentResponse],
        context: dict,
        parallel: bool,
    ) -> list[AgentResponse]:
        response_map = {response.agent_type: response for response in previous_round_responses}

        if parallel:
            responses: list[AgentResponse] = []
            with ThreadPoolExecutor(max_workers=len(self.agents)) as executor:
                futures = {}
                for agent in self.agents.values():
                    own_response = response_map.get(agent.agent_type)
                    if own_response is None:
                        continue
                    other_responses = [
                        response
                        for response in previous_round_responses
                        if response.agent_type != agent.agent_type
                    ]
                    futures[
                        executor.submit(
                            agent.deliberate,
                            message_data,
                            own_response,
                            other_responses,
                            context,
                        )
                    ] = (agent, own_response)

                for future in as_completed(futures):
                    agent, own_response = futures[future]
                    try:
                        responses.append(future.result())
                    except Exception as exc:
                        if _is_fatal_llm_error(exc):
                            raise
                        responses.append(
                            AgentResponse(
                                agent_type=agent.agent_type,
                                stance=own_response.stance,
                                confidence=own_response.confidence,
                                key_arguments=own_response.key_arguments
                                + [f"Round 2 error: {exc}"],
                                evidence=own_response.evidence,
                            )
                        )
            return responses

        responses = []
        for agent in self.agents.values():
            own_response = response_map.get(agent.agent_type)
            if own_response is None:
                continue
            other_responses = [
                response
                for response in previous_round_responses
                if response.agent_type != agent.agent_type
            ]
            responses.append(
                agent.deliberate(
                    message_data, own_response, other_responses, context
                )
            )
        return responses
