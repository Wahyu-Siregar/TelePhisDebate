"""
Test Rule-Based Triage System
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.detection.triage import RuleBasedTriage


def print_result(result, message: str):
    """Pretty print triage result"""
    print(f"\n{'='*60}")
    print(f"Message: {message[:80]}{'...' if len(message) > 80 else ''}")
    print(f"{'='*60}")
    print(f"  Classification: {result.classification}")
    print(f"  Risk Score: {result.risk_score}/100")
    print(f"  Skip LLM: {result.skip_llm}")
    
    if result.urls_found:
        print(f"  URLs Found: {result.urls_found}")
    if result.whitelisted_urls:
        print(f"  Whitelisted: {result.whitelisted_urls}")
    if result.triggered_flags:
        print(f"  Triggered Flags: {result.triggered_flags}")
    
    if result.red_flags:
        print(f"  Red Flags:")
        for flag in result.red_flags:
            print(f"    - {flag.flag_type}: {flag.description}")
    
    if result.behavioral_anomalies:
        print(f"  Behavioral Anomalies:")
        for anomaly in result.behavioral_anomalies:
            print(f"    - {anomaly.anomaly_type}: {anomaly.description}")


def main():
    print("\n" + "🔍 " * 20)
    print("  TelePhisDebate - Rule-Based Triage Test")
    print("🔍 " * 20)
    
    # Initialize triage system
    triage = RuleBasedTriage()
    
    # Test cases
    test_cases = [
        # SAFE - Only whitelisted URLs
        {
            "message": "Teman-teman, link tugas sudah di upload di https://classroom.google.com/c/abc123",
            "expected": "SAFE"
        },
        {
            "message": "Meeting zoom hari ini jam 10: https://zoom.us/j/123456789",
            "expected": "SAFE"
        },
        {
            "message": "Silakan cek repository di https://github.com/kampus/tugas-akhir",
            "expected": "SAFE"
        },
        
        # LOW RISK - Some suspicious patterns but not severe
        {
            "message": "Ada info menarik nih, cek di https://medium.com/artikel-bagus",
            "expected": "SAFE"  # medium.com is whitelisted
        },
        {
            "message": "Halo teman-teman, ada yang mau join grup belajar?",
            "expected": "SAFE"  # No URLs, no red flags
        },
        
        # HIGH RISK - Phishing indicators
        {
            "message": "URGENT!!! Akun telegram kamu akan diblokir! Verifikasi sekarang di bit.ly/verify123",
            "expected": "HIGH_RISK"
        },
        {
            "message": "Selamat! Kamu MENANG undian 10 JUTA! Klik segera https://hadiah-gratis.tk/claim",
            "expected": "HIGH_RISK"
        },
        {
            "message": "Dari pihak kampus: Update data mahasiswa sekarang di http://uir-update.ml/form",
            "expected": "HIGH_RISK"
        },
        {
            "message": "Buruan daftar beasiswa full S2!! Kesempatan terakhir hari ini! https://beasiswa.ga/daftar",
            "expected": "HIGH_RISK"
        },
        {
            "message": "Ada lowongan magang gaji tinggi, transfer 50rb dulu untuk registrasi https://tinyurl.com/magang123",
            "expected": "HIGH_RISK"
        },
        
        # Edge cases
        {
            "message": "Teman2 jangan lupa deadline tugas besok ya!",
            "expected": "SAFE"  # Urgency but no URL, normal context
        },
        {
            "message": "Link gdrive: https://drive.google.com/file/d/123",
            "expected": "SAFE"  # Google Drive is whitelisted
        },
    ]
    
    # Run tests
    passed = 0
    failed = 0
    
    for test in test_cases:
        result = triage.analyze(test["message"])
        print_result(result, test["message"])
        
        if result.classification == test["expected"]:
            print(f"  ✅ PASSED (expected {test['expected']})")
            passed += 1
        else:
            print(f"  ❌ FAILED (expected {test['expected']}, got {result.classification})")
            failed += 1
    
    # Summary
    print(f"\n{'='*60}")
    print(f"  Summary: {passed} passed, {failed} failed")
    print(f"{'='*60}")
    
    # Test with user baseline
    print("\n\n" + "👤 " * 20)
    print("  Testing with User Baseline")
    print("👤 " * 20)
    
    user_baseline = {
        "avg_message_length": 50,
        "typical_hours": [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
        "url_sharing_rate": 0.0,  # Never shared URLs
        "total_messages": 100,
        "emoji_usage_rate": 0.02
    }
    
    # Anomaly test: User posts URL at 3 AM
    anomaly_message = "Ada link menarik nih https://example.com/something"
    anomaly_time = datetime(2026, 2, 3, 3, 15)  # 3:15 AM
    
    result = triage.analyze(
        anomaly_message,
        message_timestamp=anomaly_time,
        user_baseline=user_baseline
    )
    
    print_result(result, f"[03:15 AM] {anomaly_message}")
    print("\n  Note: User has never shared URLs and this is at 3 AM!")
    print(f"  Expected behavioral anomalies detected: time_anomaly, first_time_url")


if __name__ == "__main__":
    main()
