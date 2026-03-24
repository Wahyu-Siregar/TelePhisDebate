"""
Test Bot Module
Quick verification that bot can initialize properly
"""

import sys
import asyncio
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import config
from src.bot import TelePhisBot
from src.detection import PhishingDetectionPipeline


def test_config():
    """Test configuration loading"""
    print("\n" + "="*60)
    print("1. Testing Configuration")
    print("="*60)
    
    print(f"   Telegram Token: {'✅ Set' if config.TELEGRAM_BOT_TOKEN else '❌ Missing'}")
    print(f"   DeepSeek API: {'✅ Set' if config.DEEPSEEK_API_KEY else '❌ Missing'}")
    print(f"   Supabase URL: {'✅ Set' if config.SUPABASE_URL else '❌ Missing'}")
    print(f"   Supabase Key: {'✅ Set' if config.SUPABASE_KEY else '❌ Missing'}")
    
    missing = config.validate()
    print(f"\n   Missing config keys: {missing}")
    assert isinstance(missing, list)


def test_pipeline():
    """Test detection pipeline initialization"""
    print("\n" + "="*60)
    print("2. Testing Detection Pipeline")
    print("="*60)
    
    pipeline = PhishingDetectionPipeline()
    print("   ✅ Pipeline initialized successfully")

    # Quick test
    result = pipeline.process_message(
        "Test message tanpa URL",
        message_id="test"
    )
    print(f"   ✅ Test classification: {result.classification}")
    assert result.classification == "SAFE"
    assert result.decided_by == "triage"


def test_bot_init():
    """Test bot initialization (without running)"""
    print("\n" + "="*60)
    print("3. Testing Bot Initialization")
    print("="*60)
    
    original_token = config.TELEGRAM_BOT_TOKEN
    if not config.TELEGRAM_BOT_TOKEN:
        config.TELEGRAM_BOT_TOKEN = "123456:TEST_TOKEN_FOR_PYTEST"

    try:
        bot = TelePhisBot(enable_logging=False)
        print("   ✅ Bot initialized successfully")
        print(f"   ✅ Application created: {bot.application is not None}")
        print(f"   ✅ Pipeline ready: {bot.pipeline is not None}")
        print(f"   ✅ Message handler ready: {bot.message_handler is not None}")
        assert bot.application is not None
        assert bot.pipeline is not None
        assert bot.message_handler is not None
    finally:
        config.TELEGRAM_BOT_TOKEN = original_token


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bot_connection():
    """Test bot can connect to Telegram"""
    print("\n" + "="*60)
    print("4. Testing Telegram Connection")
    print("="*60)
    
    if not config.TELEGRAM_BOT_TOKEN:
        pytest.skip("TELEGRAM_BOT_TOKEN not configured")

    bot = TelePhisBot(enable_logging=False)

    # Get bot info
    await bot.application.initialize()
    try:
        bot_user = await bot.application.bot.get_me()
        print(f"   ✅ Connected to Telegram")
        print(f"   ✅ Bot username: @{bot_user.username}")
        print(f"   ✅ Bot name: {bot_user.first_name}")
        print(f"   ✅ Bot ID: {bot_user.id}")
        assert bot_user.id is not None
    finally:
        await bot.application.shutdown()


def main():
    print("\n" + "🤖 " * 20)
    print("  TelePhisDebate - Bot Module Test")
    print("🤖 " * 20)
    
    results = []
    
    # Test 1: Configuration
    results.append(("Configuration", test_config()))
    
    # Test 2: Pipeline
    results.append(("Pipeline", test_pipeline()))
    
    # Test 3: Bot init
    results.append(("Bot Init", test_bot_init()))
    
    # Test 4: Telegram connection
    results.append(("Telegram", asyncio.run(test_bot_connection())))
    
    # Summary
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    failed = len(results) - passed
    
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {name}: {status}")
    
    print(f"\n   Total: {passed} passed, {failed} failed")
    
    if passed == len(results):
        print("\n🎉 All tests passed! Bot is ready to run.")
        print("\n📝 To start the bot:")
        print("   python main.py")
        print("\n📝 Or with options:")
        print("   python main.py --debug              # Enable debug logging")
        print("   python main.py --no-db              # Disable database logging")
        print("   python main.py --admin-chat 123456  # Set admin chat ID")
    else:
        print("\n⚠️ Some tests failed. Please check the configuration.")


if __name__ == "__main__":
    main()
