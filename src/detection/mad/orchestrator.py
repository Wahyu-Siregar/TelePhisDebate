"""
Multi-Agent Debate Orchestrator
Coordinates the debate between agents across rounds
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .agents import ContentAnalyzer, SecurityValidator, SocialContextEvaluator, AgentResponse
from .aggregator import VotingAggregator, AggregatedDecision


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
    
    # Agent responses
    agent_votes: dict[str, str]
    round_1_summary: list[dict]
    round_2_summary: list[dict] | None
    
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
            "agent_votes": self.agent_votes,
            "round_1_summary": self.round_1_summary,
            "round_2_summary": self.round_2_summary,
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
    
    def __init__(self, skip_round_2_on_consensus: bool = True):
        """
        Initialize debate system.
        
        Args:
            skip_round_2_on_consensus: Skip Round 2 if consensus reached in Round 1
        """
        self.skip_round_2_on_consensus = skip_round_2_on_consensus
        
        # Initialize agents
        self.agents = {
            "content": ContentAnalyzer(),
            "security": SecurityValidator(),
            "social": SocialContextEvaluator()
        }
        
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
            "recent_topics": []  # Could be populated from group history
        }
        
        # Round 1: Independent Analysis
        round_1_responses = self._run_round_1(
            message_data, context, single_shot_result, parallel
        )
        
        # Check for early consensus
        consensus, decision, confidence = self.aggregator.check_consensus(round_1_responses)
        
        round_2_responses = None
        
        if not consensus or not self.skip_round_2_on_consensus:
            # Round 2: Deliberation
            round_2_responses = self._run_round_2(
                message_data, round_1_responses, context, parallel
            )
        
        # Aggregate final decision
        aggregated = self.aggregator.aggregate(round_1_responses, round_2_responses)
        
        total_time = int((time.time() - start_time) * 1000)
        
        return DebateResult(
            decision=aggregated.decision,
            confidence=aggregated.confidence,
            rounds_executed=2 if round_2_responses else 1,
            consensus_reached=aggregated.consensus_reached,
            consensus_type=aggregated.consensus_type,
            agent_votes=aggregated.agent_votes,
            round_1_summary=[r.to_dict() for r in round_1_responses],
            round_2_summary=[r.to_dict() for r in round_2_responses] if round_2_responses else None,
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
                    ): name
                    for name, agent in self.agents.items()
                }
                
                for future in as_completed(futures):
                    try:
                        response = future.result()
                        responses.append(response)
                    except Exception as e:
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
    
    def _run_round_2(
        self,
        message_data: dict,
        round_1_responses: list[AgentResponse],
        context: dict,
        parallel: bool
    ) -> list[AgentResponse]:
        """Run Round 2: Deliberation with cross-agent context"""
        
        # Map responses by agent type
        response_map = {r.agent_type: r for r in round_1_responses}
        
        agent_type_map = {
            "content": "content_analyzer",
            "security": "security_validator",
            "social": "social_context"
        }
        
        if parallel:
            responses = []
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {}
                
                for name, agent in self.agents.items():
                    agent_type = agent_type_map[name]
                    own_response = response_map.get(agent_type)
                    
                    if own_response is None:
                        continue
                    
                    other_responses = [
                        r for r in round_1_responses 
                        if r.agent_type != agent_type
                    ]
                    
                    futures[executor.submit(
                        agent.deliberate,
                        message_data,
                        own_response,
                        other_responses,
                        context
                    )] = name
                
                for future in as_completed(futures):
                    try:
                        response = future.result()
                        responses.append(response)
                    except Exception as e:
                        agent_name = futures[future]
                        agent_type = agent_type_map[agent_name]
                        # Keep original response on error
                        responses.append(response_map.get(agent_type, AgentResponse(
                            agent_type=agent_type,
                            stance="SUSPICIOUS",
                            confidence=0.5,
                            key_arguments=[f"Deliberation error: {str(e)}"]
                        )))
            
            return responses
        else:
            responses = []
            for name, agent in self.agents.items():
                agent_type = agent_type_map[name]
                own_response = response_map.get(agent_type)
                
                if own_response is None:
                    continue
                
                other_responses = [
                    r for r in round_1_responses 
                    if r.agent_type != agent_type
                ]
                
                response = agent.deliberate(
                    message_data, own_response, other_responses, context
                )
                responses.append(response)
            
            return responses
