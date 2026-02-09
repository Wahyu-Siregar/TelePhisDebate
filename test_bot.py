"""
Test Bot Module
Quick verification that bot can initialize properly
"""

import sys
import asyncio
from pathlib import Path

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
    valid = len(missing) == 0
    print(f"\n   Config Valid: {'✅ Yes' if valid else '❌ No - Missing: ' + ', '.join(missing)}")
    return valid


def test_pipeline():
    """Test detection pipeline initialization"""
    print("\n" + "="*60)
    print("2. Testing Detection Pipeline")
    print("="*60)
    
    try:
        pipeline = PhishingDetectionPipeline()
        print("   ✅ Pipeline initialized successfully")
        
        # Quick test
        result = pipeline.process_message(
            "Test message tanpa URL",
            message_id="test"
        )
        print(f"   ✅ Test classification: {result.classification}")
        return True
    except Exception as e:
        print(f"   ❌ Pipeline error: {e}")
        return False


def test_bot_init():
    """Test bot initialization (without running)"""
    print("\n" + "="*60)
    print("3. Testing Bot Initialization")
    print("="*60)
    
    try:
        bot = TelePhisBot(enable_logging=False)
        print("   ✅ Bot initialized successfully")
        print(f"   ✅ Application created: {bot.application is not None}")
        print(f"   ✅ Pipeline ready: {bot.pipeline is not None}")
        print(f"   ✅ Message handler ready: {bot.message_handler is not None}")
        return True
    except Exception as e:
        print(f"   ❌ Bot init error: {e}")
        return False


async def test_bot_connection():
    """Test bot can connect to Telegram"""
    print("\n" + "="*60)
    print("4. Testing Telegram Connection")
    print("="*60)
    
    try:
        bot = TelePhisBot(enable_logging=False)
        
        # Get bot info
        await bot.application.initialize()
        bot_user = await bot.application.bot.get_me()
        
        print(f"   ✅ Connected to Telegram")
        print(f"   ✅ Bot username: @{bot_user.username}")
        print(f"   ✅ Bot name: {bot_user.first_name}")
        print(f"   ✅ Bot ID: {bot_user.id}")
        
        await bot.application.shutdown()
        return True
    except Exception as e:
        print(f"   ❌ Connection error: {e}")
        return False


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
