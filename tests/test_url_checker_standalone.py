"""
Standalone test for URL checker (minimal dependencies)
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load env before importing
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# Import directly from module file, bypassing __init__.py
import importlib.util
spec = importlib.util.spec_from_file_location(
    "url_checker", 
    project_root / "src" / "detection" / "url_checker.py"
)
url_checker_module = importlib.util.module_from_spec(spec)
sys.modules["url_checker"] = url_checker_module
spec.loader.exec_module(url_checker_module)

URLSecurityChecker = url_checker_module.URLSecurityChecker


async def test_url_checker():
    """Test URL checker standalone"""
    print("=" * 60)
    print("VirusTotal URL Checker Test")
    print("=" * 60)
    
    checker = URLSecurityChecker()
    
    print(f"\nVirusTotal API Key configured: {checker.is_configured}")
    
    if not checker.is_configured:
        print("⚠️  VIRUSTOTAL_API_KEY not set")
        print("   Falling back to heuristic analysis...")
    
    # Test URLs
    test_urls = [
        "https://uir.ac.id",
        "https://google.com",
        "https://bit.ly/suspicious123",
        "https://free-bitcoin.tk",
        "http://192.168.1.1/login",
        "https://bank-login.xyz/verify",
    ]
    
    print("\n" + "-" * 60)
    
    for url in test_urls:
        print(f"\n🔍 Checking: {url}")
        result = await checker.check_url(url)
        
        status = "⚠️ MALICIOUS" if result.is_malicious else "✅ SAFE"
        print(f"   Status: {status}")
        print(f"   Risk Score: {result.risk_score:.2f}")
        print(f"   Source: {result.source}")
        
        if result.details:
            # Show heuristic factors
            if 'heuristic_risk_factors' in result.details:
                factors = result.details['heuristic_risk_factors']
                if factors:
                    print(f"   Heuristic Factors: {', '.join(factors)}")
            # Show VT detection
            if 'malicious' in result.details:
                mal = result.details.get('malicious', 0)
                total = result.details.get('total_engines', 0)
                if mal > 0:
                    print(f"   VT Detection: {mal}/{total} engines")
    
    await checker.close()
    print("\n✅ Test complete!")


if __name__ == "__main__":
    asyncio.run(test_url_checker())
