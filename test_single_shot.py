"""
Test Single-Shot LLM Classifier
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.detection.single_shot import SingleShotClassifier


def print_result(result, message: str, expected: str = None):
    """Pretty print classification result"""
    print(f"\n{'='*70}")
    print(f"Message: {message[:80]}{'...' if len(message) > 80 else ''}")
    print(f"{'='*70}")
    print(f"  Classification: {result.classification}")
    print(f"  Confidence: {result.confidence:.0%}")
    print(f"  Reasoning: {result.reasoning}")
    
    if result.risk_factors:
        print(f"  Risk Factors: {result.risk_factors}")
    
    print(f"  Escalate to MAD: {result.should_escalate_to_mad}")
    if result.escalation_reason:
        print(f"  Escalation Reason: {result.escalation_reason}")
    
    print(f"  Tokens: {result.tokens_input} in, {result.tokens_output} out")
    print(f"  Processing Time: {result.processing_time_ms}ms")
    
    if expected:
        if result.classification == expected:
            print(f"  ✅ PASSED (expected {expected})")
        else:
            print(f"  ❌ FAILED (expected {expected}, got {result.classification})")


def main():
    print("\n" + "🤖 " * 20)
    print("  TelePhisDebate - Single-Shot LLM Test")
    print("🤖 " * 20)
    
    # Initialize classifier
    print("\nInitializing classifier...")
    classifier = SingleShotClassifier()
    
    # Test cases
    test_cases = [
        # Clear SAFE cases
        {
            "message": "Teman-teman, link tugas sudah di upload di https://classroom.google.com/c/abc123. Deadline minggu depan ya.",
            "expected": "SAFE",
            "description": "Academic - Google Classroom link"
        },
        {
            "message": "Besok kita meeting zoom jam 10 pagi untuk bahas proyek akhir. Link: https://zoom.us/j/123456789",
            "expected": "SAFE",
            "description": "Academic - Zoom meeting"
        },
        
        # Clear PHISHING cases
        {
            "message": "URGENT!!! Akun telegram kamu akan DIBLOKIR! Verifikasi sekarang di bit.ly/verify123 sebelum terlambat!!!",
            "expected": "PHISHING",
            "description": "Phishing - Account blocking threat"
        },
        {
            "message": "Selamat! Kamu MENANG undian 10 JUTA rupiah! Klik segera https://hadiah-gratis.tk/claim untuk klaim hadiahmu!",
            "expected": "PHISHING",
            "description": "Phishing - Lottery scam"
        },
        {
            "message": "Dari pihak kampus: Semua mahasiswa WAJIB update data sekarang di http://uir-update.ml/form atau akun dinonaktifkan!",
            "expected": "PHISHING",
            "description": "Phishing - Authority impersonation"
        },
        
        # Ambiguous/SUSPICIOUS cases
        {
            "message": "Halo teman-teman, ada lowongan magang nih di perusahaan bagus. Info lebih lanjut: https://bit.ly/magang2026",
            "expected": "SUSPICIOUS",
            "description": "Ambiguous - Shortened URL, job offer"
        },
        {
            "message": "Ada yang mau gabung program beasiswa S2 di luar negeri? Link pendaftaran: https://scholarship-program.xyz/apply",
            "expected": "SUSPICIOUS",
            "description": "Ambiguous - Suspicious TLD, scholarship"
        },
    ]
    
    # Run tests
    print(f"\nRunning {len(test_cases)} test cases...\n")
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n--- Test {i}/{len(test_cases)}: {test['description']} ---")
        
        result = classifier.classify(
            message_text=test["message"],
            message_timestamp=datetime.now()
        )
        
        print_result(result, test["message"], test["expected"])
        
        # Check if passed (exact match or SUSPICIOUS is acceptable for ambiguous)
        if result.classification == test["expected"]:
            passed += 1
        elif test["expected"] == "SUSPICIOUS" and result.classification in ["SAFE", "PHISHING"]:
            # SUSPICIOUS cases can be classified either way with low confidence
            if result.confidence < 0.7:
                print(f"  ⚠️  ACCEPTABLE (low confidence {result.classification})")
                passed += 1
            else:
                failed += 1
        else:
            failed += 1
    
    # Summary
    print(f"\n{'='*70}")
    print(f"  Summary: {passed} passed, {failed} failed out of {len(test_cases)}")
    print(f"{'='*70}")
    
    # Token usage
    usage = classifier.llm.get_usage_stats()
    print(f"\n📊 Token Usage:")
    print(f"  Total tokens: {usage['total_tokens']}")
    print(f"  Input: {usage['total_tokens_input']}")
    print(f"  Output: {usage['total_tokens_output']}")
    print(f"  Requests: {usage['request_count']}")
    
    # Estimate cost (DeepSeek pricing: $0.28/M input, $0.42/M output)
    input_cost = usage['total_tokens_input'] * 0.28 / 1_000_000
    output_cost = usage['total_tokens_output'] * 0.42 / 1_000_000
    total_cost = input_cost + output_cost
    print(f"  Estimated cost: ${total_cost:.4f}")


if __name__ == "__main__":
    main()
