"""
Test Complete Detection Pipeline
End-to-end test of Triage → Single-Shot → MAD
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.detection import PhishingDetectionPipeline


def print_result(result, message: str, expected_class: str = None, expected_stage: str = None):
    """Pretty print pipeline result"""
    print(f"\n{'='*70}")
    print(f"Message: {message[:75]}{'...' if len(message) > 75 else ''}")
    print(f"{'='*70}")
    
    # Classification
    class_emoji = {"SAFE": "✅", "SUSPICIOUS": "⚠️", "PHISHING": "🚨"}.get(result.classification, "❓")
    print(f"\n{class_emoji} Classification: {result.classification}")
    print(f"   Confidence: {result.confidence:.0%}")
    print(f"   Decided by: {result.decided_by}")
    print(f"   Action: {result.action}")
    
    # Stage flow
    print(f"\n📊 Pipeline Flow:")
    print(f"   [1] Triage: {result.triage_result.get('classification', 'N/A')} (risk: {result.triage_result.get('risk_score', 0)})")
    
    if result.single_shot_result:
        ss = result.single_shot_result
        print(f"   [2] Single-Shot: {ss.get('classification', 'N/A')} ({ss.get('confidence', 0):.0%})")
        if ss.get('should_escalate_to_mad'):
            print(f"       → Escalated: {ss.get('escalation_reason', '')[:50]}")
    
    if result.mad_result:
        mad = result.mad_result
        print(f"   [3] MAD: {mad.get('decision', 'N/A')} ({mad.get('confidence', 0):.0%})")
        print(f"       Rounds: {mad.get('rounds_executed', 1)}, Consensus: {mad.get('consensus_type', 'N/A')}")
        print(f"       Votes: {mad.get('agent_votes', {})}")
    
    # Performance
    print(f"\n⏱️ Performance:")
    print(f"   Time: {result.total_processing_time_ms}ms")
    print(f"   Tokens: {result.total_tokens_used}")
    
    # Check expectations
    passed = True
    if expected_class:
        if result.classification == expected_class:
            print(f"\n   ✅ Classification PASSED (expected {expected_class})")
        else:
            print(f"\n   ❌ Classification FAILED (expected {expected_class}, got {result.classification})")
            passed = False
    
    if expected_stage:
        if result.decided_by == expected_stage:
            print(f"   ✅ Stage PASSED (expected {expected_stage})")
        else:
            print(f"   ❌ Stage FAILED (expected {expected_stage}, got {result.decided_by})")
            passed = False
    
    return passed


def main():
    print("\n" + "🔄 " * 20)
    print("  TelePhisDebate - Full Pipeline Test")
    print("🔄 " * 20)
    
    # Initialize pipeline
    print("\nInitializing detection pipeline...")
    pipeline = PhishingDetectionPipeline()
    
    # Test cases covering all stages
    test_cases = [
        # ============================================================
        # Stage 1: Triage decisions (no LLM needed)
        # ============================================================
        {
            "message": "Teman-teman, tugas sudah ada di https://classroom.google.com/c/MTIz",
            "expected_class": "SAFE",
            "expected_stage": "triage",
            "description": "Whitelisted URL only → Triage SAFE"
        },
        {
            "message": "Meeting zoom jam 10: https://zoom.us/j/123456789",
            "expected_class": "SAFE",
            "expected_stage": "triage",
            "description": "Whitelisted URL → Triage SAFE"
        },
        {
            "message": "Jangan lupa deadline tugas besok ya!",
            "expected_class": "SAFE",
            "expected_stage": "triage",
            "description": "No URL, no flags → Triage SAFE"
        },
        
        # ============================================================
        # Stage 2: Single-Shot decisions (high confidence)
        # ============================================================
        {
            "message": "URGENT!!! Akun telegram kamu akan DIBLOKIR!!! Verifikasi SEKARANG di bit.ly/verify123!!!",
            "expected_class": "PHISHING",
            "expected_stage": "single_shot",
            "description": "Clear phishing → Single-Shot high confidence"
        },
        {
            "message": "Selamat! Kamu MENANG undian 50 JUTA! Klaim di https://hadiah.tk/claim SEKARANG!",
            "expected_class": "PHISHING",
            "expected_stage": "single_shot",
            "description": "Lottery scam → Single-Shot PHISHING"
        },
        
        # ============================================================
        # Stage 3: MAD decisions (ambiguous cases)
        # ============================================================
        {
            "message": "Ada lowongan magang di startup bagus nih, gaji 5jt. Info: https://bit.ly/magang2026",
            "expected_class": "SUSPICIOUS",  # Could be PHISHING
            "expected_stage": "mad",
            "description": "Ambiguous job offer → MAD needed"
        },
        {
            "message": "Program beasiswa S2 Jepang, pendaftaran gratis! https://scholarship.xyz/apply",
            "expected_class": "SUSPICIOUS",  # Could be PHISHING
            "expected_stage": "mad",
            "description": "Suspicious scholarship → MAD needed"
        },
    ]
    
    # Run tests
    print(f"\nRunning {len(test_cases)} test cases...\n")
    print("Expected flow:")
    print("  - Cases 1-3: Triage only (instant)")
    print("  - Cases 4-5: Single-Shot LLM (~5s)")
    print("  - Cases 6-7: MAD escalation (~10-15s)")
    
    results = []
    total_tokens = 0
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'#'*70}")
        print(f"# Test {i}/{len(test_cases)}: {test['description']}")
        print(f"{'#'*70}")
        
        result = pipeline.process_message(
            message_text=test["message"],
            message_id=f"test_{i}",
            message_timestamp=datetime.now()
        )
        
        passed = print_result(
            result, 
            test["message"],
            test["expected_class"],
            test["expected_stage"]
        )
        
        # Accept PHISHING when SUSPICIOUS expected (stricter is OK)
        if not passed and test["expected_class"] == "SUSPICIOUS" and result.classification == "PHISHING":
            print("   ⚠️  Acceptable: PHISHING is stricter than SUSPICIOUS")
            passed = True
        
        results.append(passed)
        total_tokens += result.total_tokens_used
    
    # Summary
    passed_count = sum(results)
    failed_count = len(results) - passed_count
    
    print(f"\n{'='*70}")
    print(f"  PIPELINE TEST SUMMARY")
    print(f"{'='*70}")
    print(f"  Tests: {passed_count} passed, {failed_count} failed out of {len(test_cases)}")
    print(f"  Total Tokens: {total_tokens}")
    
    # Stage distribution
    stages = {"triage": 0, "single_shot": 0, "mad": 0}
    for i, test in enumerate(test_cases):
        result = pipeline.process_message(test["message"])
        stages[result.decided_by] = stages.get(result.decided_by, 0) + 1
    
    print(f"\n📊 Stage Distribution:")
    print(f"   Triage (free): {stages['triage']} messages")
    print(f"   Single-Shot: {stages['single_shot']} messages")
    print(f"   MAD: {stages['mad']} messages")
    
    # Cost estimate (DeepSeek pricing: $0.28/M input, $0.42/M output)
    input_cost = total_tokens * 0.6 * 0.28 / 1_000_000
    output_cost = total_tokens * 0.4 * 0.42 / 1_000_000
    print(f"\n💰 Estimated Cost: ${input_cost + output_cost:.4f}")
    
    if passed_count == len(test_cases):
        print(f"\n🎉 All tests passed! Pipeline is ready.")
    else:
        print(f"\n⚠️ Some tests failed. Review the results above.")


if __name__ == "__main__":
    main()
