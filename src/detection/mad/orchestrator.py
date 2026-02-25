"""
Multi-Agent Debate Orchestrator
Coordinates the debate between agents across rounds
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime

from .agents import ContentAnalyzer, SecurityValidator, SocialContextEvaluator, AgentResponse
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
    """Complete result from multi-agent debate"""
    
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
            "total_processing_time_ms": self.total_processing_time_ms
        }


class MultiAgentDebate:
    """
    Multi-Agent Debate System
    
    Stage 3 of the phishing detection pipeline.
    Uses 3 specialized agents that debate to reach consensus.
    
    Workflow:
    1. Round 1: Each agent independently analyzes the message
    2. Consensus Check: If unanimous or strong majority, skip Round 2
    3. Round 2: Agents see each other's arguments and may revise stance
    4. Aggregation: Weighted voting produces final decision
    """
    
    def __init__(
        self,
        skip_round_2_on_consensus: bool = True,
        max_rounds: int = 2,
        max_total_time_ms: int | None = None,
    ):
        """
        Initialize debate system.
        
        Args:
            skip_round_2_on_consensus: Skip Round 2 if consensus reached in Round 1
        """
        self.skip_round_2_on_consensus = skip_round_2_on_consensus
        self.max_rounds = max(1, int(max_rounds or 2))
        self.max_total_time_ms = int(max_total_time_ms) if max_total_time_ms else None
        
        # Initialize agents
        # Key by agent_type for simpler multi-round orchestration.
        agents_list = [ContentAnalyzer(), SecurityValidator(), SocialContextEvaluator()]
        self.agents = {a.agent_type: a for a in agents_list}
        
        # Initialize aggregator
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
        parallel: bool = True
    ) -> DebateResult:
        """
        Run the full multi-agent debate.
        
        Args:
            message_text: The message to analyze
            message_timestamp: When message was sent
            sender_info: Information about sender
            baseline_metrics: User's baseline behavior
            triage_result: Result from triage stage
            single_shot_result: Result from single-shot LLM
            url_checks: External URL check results
            parallel: Run agents in parallel (faster)
            
        Returns:
            DebateResult with final decision
        """
        start_time = time.time()
        
        if message_timestamp is None:
            message_timestamp = datetime.now()
        
        # Prepare message data
        message_data = {
            "content": message_text,
            "length": len(message_text),
            "timestamp": message_timestamp.strftime("%Y-%m-%d %H:%M"),
            "sender": sender_info or {},
            "urls": triage_result.get("urls_found", []) if triage_result else [],
            "triage": triage_result or {}
        }
        
        # Prepare context
        context = {
            "baseline": baseline_metrics or {},
            "url_checks": url_checks or {},
            "single_shot": single_shot_result or {},
            "recent_topics": []  # Could be populated from group history
        }
        
        rounds: list[list[AgentResponse]] = []
        consensus_round: int | None = None
        stop_reason = "max_rounds"

        # Round 1: Independent analysis
        round_1_responses = self._run_round_1(
            message_data, context, single_shot_result, parallel
        )
        rounds.append(round_1_responses)

        # Track earliest consensus.
        consensus, _, _ = self.aggregator.check_consensus(round_1_responses)
        if consensus:
            consensus_round = 1
            if self.skip_round_2_on_consensus and self.max_rounds <= 1:
                stop_reason = "consensus"

        # Additional rounds: deliberation loop (Round 2..max_rounds)
        previous_round = round_1_responses
        for round_idx in range(2, self.max_rounds + 1):
            if self.max_total_time_ms is not None:
                elapsed_ms = int((time.time() - start_time) * 1000)
                if elapsed_ms >= self.max_total_time_ms:
                    stop_reason = "timeout"
                    break

            # Early termination: stop as soon as consensus is reached.
            if self.skip_round_2_on_consensus:
                consensus_now, _, _ = self.aggregator.check_consensus(previous_round)
                if consensus_now:
                    stop_reason = "consensus"
                    break

            next_round = self._run_deliberation_round(
                message_data, previous_round, context, parallel
            )
            rounds.append(next_round)
            previous_round = next_round

            consensus_now, _, _ = self.aggregator.check_consensus(next_round)
            if consensus_now and consensus_round is None:
                consensus_round = round_idx

        # Aggregate decision from the final round, accumulate tokens/time across all rounds.
        aggregated = self.aggregator.aggregate_rounds(rounds)
        
        total_time = int((time.time() - start_time) * 1000)
        
        round_summaries = [[r.to_dict() for r in resp_round] for resp_round in rounds]
        return DebateResult(
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
            total_processing_time_ms=total_time
        )
    
    def _run_round_1(
        self,
        message_data: dict,
        context: dict,
        previous_result: dict | None,
        parallel: bool
    ) -> list[AgentResponse]:
        """Run Round 1: Independent analysis from each agent"""
        
        if parallel:
            responses = []
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(
                        agent.analyze, message_data, context, previous_result
                    ): agent.agent_type
                    for agent in self.agents.values()
                }
                
                for future in as_completed(futures):
                    try:
                        response = future.result()
                        responses.append(response)
                    except Exception as e:
                        if _is_fatal_llm_error(e):
                            raise
                        # Create error response
                        agent_name = futures[future]
                        responses.append(AgentResponse(
                            agent_type=agent_name,
                            stance="SUSPICIOUS",
                            confidence=0.5,
                            key_arguments=[f"Error: {str(e)}"]
                        ))
            
            return responses
        else:
            # Sequential execution
            return [
                agent.analyze(message_data, context, previous_result)
                for agent in self.agents.values()
            ]
    
    def _run_deliberation_round(
        self,
        message_data: dict,
        previous_round_responses: list[AgentResponse],
        context: dict,
        parallel: bool
    ) -> list[AgentResponse]:
        """Run a deliberation round using previous round as context."""
        
        # Map responses by agent type
        response_map = {r.agent_type: r for r in previous_round_responses}
        
        if parallel:
            responses = []
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {}
                
                for agent_type, agent in self.agents.items():
                    own_response = response_map.get(agent_type)
                    
                    if own_response is None:
                        continue
                    
                    other_responses = [
                        r for r in previous_round_responses
                        if r.agent_type != agent_type
                    ]
                    
                    futures[executor.submit(
                        agent.deliberate,
                        message_data,
                        own_response,
                        other_responses,
                        context
                    )] = agent_type
                
                for future in as_completed(futures):
                    try:
                        response = future.result()
                        responses.append(response)
                    except Exception as e:
                        if _is_fatal_llm_error(e):
                            raise
                        agent_name = futures[future]
                        # Keep original response on error
                        responses.append(response_map.get(agent_name, AgentResponse(
                            agent_type=agent_name,
                            stance="SUSPICIOUS",
                            confidence=0.5,
                            key_arguments=[f"Deliberation error: {str(e)}"]
                        )))
            
            return responses
        else:
            responses = []
            for agent_type, agent in self.agents.items():
                own_response = response_map.get(agent_type)
                
                if own_response is None:
                    continue
                
                other_responses = [
                    r for r in previous_round_responses
                    if r.agent_type != agent_type
                ]
                
                response = agent.deliberate(
                    message_data, own_response, other_responses, context
                )
                responses.append(response)
            
            return responses
