"""
Test all API connections - Run this to verify setup is correct
"""

import asyncio
import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import config


pytestmark = [pytest.mark.integration]


def print_header(text: str):
    print(f"\n{'='*50}")
    print(f"  {text}")
    print(f"{'='*50}")


def print_result(name: str, success: bool, message: str = ""):
    status = "✅" if success else "❌"
    print(f"{status} {name}: {message}")


@pytest.mark.asyncio
async def test_telegram():
    """Test Telegram Bot API connection"""
    print_header("Testing Telegram Bot API")
    
    if not config.TELEGRAM_BOT_TOKEN:
        pytest.skip("TELEGRAM_BOT_TOKEN not configured")

    from telegram import Bot

    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    me = await bot.get_me()

    print_result("Connection", True, "Connected!")
    print(f"   Bot Username: @{me.username}")
    print(f"   Bot Name: {me.first_name}")
    print(f"   Bot ID: {me.id}")
    assert me.id is not None


def test_deepseek():
    """Test DeepSeek API connection"""
    print_header("Testing DeepSeek API")
    
    if not config.DEEPSEEK_API_KEY and not config.OPENROUTER_API_KEY:
        pytest.skip("No LLM API key configured")

    from src.llm import deepseek

    client = deepseek()

    # Simple test prompt
    result = client.chat_completion(
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Reply with exactly: API connection successful"}
        ],
        temperature=0.0,
        max_tokens=50
    )

    print_result("Connection", True, "Connected!")
    print(f"   Response: {result['content'][:100]}")
    print(f"   Tokens used: {result['tokens_input']} in, {result['tokens_output']} out")
    print(f"   Processing time: {result['processing_time_ms']}ms")
    assert "content" in result


def test_supabase():
    """Test Supabase connection"""
    print_header("Testing Supabase Database")
    
    if not config.SUPABASE_URL or not config.SUPABASE_KEY:
        pytest.skip("Supabase credentials not configured")

    from src.database import db

    client = db()

    # Test query - count users (should be 0)
    result = client.table("users").select("id", count="exact").execute()

    print_result("Connection", True, "Connected!")
    print(f"   Users table count: {result.count}")

    # Test other tables
    messages_count = client.table("messages").select("id", count="exact").execute()
    print(f"   Messages table count: {messages_count.count}")

    url_cache_count = client.table("url_cache").select("id", count="exact").execute()
    print(f"   URL Cache table count: {url_cache_count.count}")
    assert result is not None


def test_virustotal():
    """Test VirusTotal API (optional)"""
    print_header("Testing VirusTotal API (Optional)")
    
    if not config.VIRUSTOTAL_API_KEY:
        pytest.skip("VIRUSTOTAL_API_KEY not configured")
    
    try:
        import requests
        
        # Test with a known safe domain
        url = "https://www.virustotal.com/api/v3/domains/google.com"
        headers = {"x-apikey": config.VIRUSTOTAL_API_KEY}
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            print_result("Connection", True, "Connected!")
            data = response.json()
            print(f"   Test domain: google.com")
            print(f"   Reputation: {data.get('data', {}).get('attributes', {}).get('reputation', 'N/A')}")
            assert data.get("data") is not None
        else:
            pytest.fail(f"VirusTotal returned status code: {response.status_code}")
            
    except Exception as e:
        pytest.fail(str(e))


async def main():
    print("\n" + "🔌 " * 20)
    print("  TelePhisDebate - API Connection Test")
    print("🔌 " * 20)
    
    # Validate config first
    print_header("Validating Configuration")
    missing = config.validate()
    if missing:
        print(f"❌ Missing required config: {', '.join(missing)}")
        print("   Please update your .env file")
        return
    print("✅ All required configuration present")
    
    # Run tests
    results = {}
    
    results["Telegram"] = await test_telegram()
    results["DeepSeek"] = test_deepseek()
    results["Supabase"] = test_supabase()
    results["VirusTotal"] = test_virustotal()
    
    # Summary
    print_header("Summary")
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    
    print(f"   ✅ Passed: {passed}")
    print(f"   ❌ Failed: {failed}")
    print(f"   ⏭️  Skipped: {skipped}")
    
    if failed == 0:
        print("\n🎉 All tests passed! Ready for development.")
    else:
        print("\n⚠️  Some tests failed. Please check your configuration.")


if __name__ == "__main__":
    asyncio.run(main())
