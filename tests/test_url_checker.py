"""
Test script for VirusTotal URL checker integration
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.detection.url_checker import URLSecurityChecker, get_url_checker, check_urls_external
from src.config import Config


async def test_virustotal_checker():
    """Test VirusTotal URL checker"""
    print("=" * 60)
    print("VirusTotal URL Checker Test")
    print("=" * 60)
    
    checker = URLSecurityChecker()
    
    # Check if API is configured
    print(f"\nVirusTotal API Key configured: {checker.is_configured}")
    
    if not checker.is_configured:
        print("⚠️  VIRUSTOTAL_API_KEY not set in environment")
        print("   Set it in .env file to enable external URL checking")
        print("   Falling back to heuristic analysis...")
    
    # Test URLs
    test_urls = [
        "https://uir.ac.id",              # Trusted academic domain
        "https://google.com",              # Known safe
        "https://bit.ly/suspicious123",    # URL shortener (suspicious)
        "https://free-bitcoin.tk",         # Suspicious TLD
        "http://192.168.1.1/login",        # IP address (suspicious)
        "https://bank-login.xyz/verify",   # Suspicious keywords + TLD
    ]
    
    print("\n" + "-" * 60)
    print("Testing URLs:")
    print("-" * 60)
    
    for url in test_urls:
        print(f"\n🔍 Checking: {url}")
        result = await checker.check_url(url)
        
        status = "⚠️ MALICIOUS" if result.is_malicious else "✅ SAFE"
        print(f"   Status: {status}")
        print(f"   Risk Score: {result.risk_score:.2f}")
        print(f"   Source: {result.source}")
        
        if result.details:
            if 'risk_factors' in result.details:
                print(f"   Risk Factors: {', '.join(result.details['risk_factors'])}")
            if 'malicious' in result.details:
                print(f"   VT Detection: {result.details.get('malicious', 0)}/{result.details.get('total_engines', 0)} engines")
    
    await checker.close()
    
    print("\n" + "=" * 60)
    print("Sync API Test (for pipeline integration)")
    print("=" * 60)
    
    # Test synchronous wrapper
    sync_results = check_urls_external(["https://google.com", "https://bit.ly/test123"])
    
    for url, result in sync_results.items():
        print(f"\n{url}:")
        print(f"  is_malicious: {result['is_malicious']}")
        print(f"  risk_score: {result['risk_score']:.2f}")
    
    print("\n✅ URL checker integration test complete!")


if __name__ == "__main__":
    asyncio.run(test_virustotal_checker())
