"""
Test Multi-Agent Debate (MAD) System
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.detection.mad import MultiAgentDebate
from src.detection.triage import RuleBasedTriage


def print_agent_response(response: dict, indent: int = 2):
    """Print agent response details"""
    prefix = " " * indent
    print(f"{prefix}Stance: {response['stance']}")
    print(f"{prefix}Confidence: {response['confidence']:.0%}")
    print(f"{prefix}Arguments: {response['key_arguments'][:2]}")  # First 2 args


def print_result(result, message: str, expected: str = None):
    """Pretty print debate result"""
    print(f"\n{'='*70}")
    print(f"Message: {message[:80]}{'...' if len(message) > 80 else ''}")
    print(f"{'='*70}")
    
    print(f"\n📊 Final Decision:")
    print(f"  Classification: {result.decision}")
    print(f"  Confidence: {result.confidence:.0%}")
    print(f"  Rounds Used: {result.rounds_executed}")
    print(f"  Consensus: {result.consensus_type}")
    
    print(f"\n🗳️ Agent Votes:")
    for agent, vote in result.agent_votes.items():
        print(f"  - {agent}: {vote}")
    
    print(f"\n📝 Round 1 Details:")
    for resp in result.round_1_summary:
        print(f"\n  [{resp['agent_type']}]")
        print_agent_response(resp, indent=4)
    
    if result.round_2_summary:
        print(f"\n📝 Round 2 Details (after deliberation):")
        for resp in result.round_2_summary:
            print(f"\n  [{resp['agent_type']}]")
            print_agent_response(resp, indent=4)
    
    print(f"\n⏱️ Performance:")
    print(f"  Total Tokens: {result.total_tokens}")
    print(f"  Processing Time: {result.total_processing_time_ms}ms")
    
    if expected:
        if result.decision == expected:
            print(f"\n  ✅ PASSED (expected {expected})")
            return True
        else:
            print(f"\n  ❌ FAILED (expected {expected}, got {result.decision})")
            return False
    return True


def main():
    print("\n" + "🎭 " * 20)
    print("  TelePhisDebate - Multi-Agent Debate Test")
    print("🎭 " * 20)
    
    # Initialize
    print("\nInitializing Multi-Agent Debate system...")
    mad = MultiAgentDebate(skip_round_2_on_consensus=True)
    triage = RuleBasedTriage()
    
    # Test cases - Only ambiguous ones that would be escalated to MAD
    test_cases = [
        # Case 1: Ambiguous job offer with shortened URL
        {
            "message": "Halo teman-teman, ada lowongan magang nih di perusahaan teknologi bagus. Gaji 5jt/bulan. Info lebih lanjut: https://bit.ly/magang2026",
            "expected": "SUSPICIOUS",
            "description": "Job offer with shortened URL"
        },
        
        # Case 2: Scholarship with suspicious TLD
        {
            "message": "Ada yang mau gabung program beasiswa S2 full di Jepang? Pendaftaran gratis! Link: https://scholarship-japan.xyz/apply",
            "expected": "SUSPICIOUS",  # Could be PHISHING
            "description": "Scholarship with suspicious TLD"
        },
        
        # Case 3: Clear phishing - lottery scam
        {
            "message": "SELAMAT!!! Kamu terpilih sebagai pemenang undian 50 JUTA! Klaim hadiahmu SEKARANG di https://hadiah-gratis.tk/klaim sebelum expired!!!",
            "expected": "PHISHING",
            "description": "Lottery scam (clear phishing)"
        },
        
        # Case 4: Borderline - could be legitimate event
        {
            "message": "Ada kompetisi programming berhadiah total 20jt, deadline besok! Daftar di https://bit.ly/lomba-coding",
            "expected": "SUSPICIOUS",  # Ambiguous
            "description": "Competition with urgency and shortened URL"
        },
    ]
    
    # Run tests
    print(f"\nRunning {len(test_cases)} test cases...\n")
    print("Note: MAD uses parallel API calls - each test takes ~5-10 seconds\n")
    
    passed = 0
    failed = 0
    total_tokens = 0
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'#'*70}")
        print(f"# Test {i}/{len(test_cases)}: {test['description']}")
        print(f"{'#'*70}")
        
        # Run triage first
        triage_result = triage.analyze(test["message"])
        print(f"\nTriage: {triage_result.classification} (risk: {triage_result.risk_score})")
        
        # Run MAD
        result = mad.run_debate(
            message_text=test["message"],
            message_timestamp=datetime.now(),
            triage_result=triage_result.to_dict(),
            parallel=True  # Faster execution
        )
        
        if print_result(result, test["message"], test["expected"]):
            passed += 1
        else:
            # For SUSPICIOUS expected, also accept PHISHING
            if test["expected"] == "SUSPICIOUS" and result.decision == "PHISHING":
                print("  ⚠️  Acceptable: PHISHING is stricter than SUSPICIOUS")
                passed += 1
            else:
                failed += 1
        
        total_tokens += result.total_tokens
    
    # Summary
    print(f"\n{'='*70}")
    print(f"  SUMMARY")
    print(f"{'='*70}")
    print(f"  Tests: {passed} passed, {failed} failed out of {len(test_cases)}")
    print(f"  Total Tokens Used: {total_tokens}")
    
    # Estimate cost (DeepSeek pricing: $0.28/M input, $0.42/M output)
    input_cost = total_tokens * 0.6 * 0.28 / 1_000_000  # ~60% input
    output_cost = total_tokens * 0.4 * 0.42 / 1_000_000  # ~40% output
    print(f"  Estimated Cost: ${input_cost + output_cost:.4f}")
    
    print(f"\n💡 Note: MAD is only called for ambiguous cases (~20-30% of messages)")
    print(f"   Most messages are handled by Triage (free) or Single-Shot (~$0.0001)")


if __name__ == "__main__":
    main()
