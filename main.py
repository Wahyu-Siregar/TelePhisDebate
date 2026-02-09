"""
TelePhisDebate - Main Entry Point
Telegram Phishing Detection Bot using Multi-Agent Debate
"""

import os
import sys
import argparse
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import config
from src.bot import TelePhisBot


def main():
    """Main entry point for the bot"""
    
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="TelePhisDebate - Telegram Phishing Detection Bot"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Disable database logging"
    )
    parser.add_argument(
        "--admin-chat",
        type=str,
        help="Admin chat ID for notifications"
    )
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=log_level
    )
    logger = logging.getLogger(__name__)
    
    # Validate configuration
    missing = config.validate()
    if missing:
        logger.error(f"Configuration validation failed! Missing: {', '.join(missing)}")
        sys.exit(1)
    
    # Print banner
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     ████████╗███████╗██╗     ███████╗██████╗ ██╗  ██╗██╗███████╗    ║
║     ╚══██╔══╝██╔════╝██║     ██╔════╝██╔══██╗██║  ██║██║██╔════╝    ║
║        ██║   █████╗  ██║     █████╗  ██████╔╝███████║██║███████╗    ║
║        ██║   ██╔══╝  ██║     ██╔══╝  ██╔═══╝ ██╔══██║██║╚════██║    ║
║        ██║   ███████╗███████╗███████╗██║     ██║  ██║██║███████║    ║
║        ╚═╝   ╚══════╝╚══════╝╚══════╝╚═╝     ╚═╝  ╚═╝╚═╝╚══════╝    ║
║                                                              ║
║              Multi-Agent Debate Phishing Detection           ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    logger.info("Starting TelePhisDebate Bot...")
    logger.info(f"Database logging: {'Disabled' if args.no_db else 'Enabled'}")
    logger.info(f"Debug mode: {'Enabled' if args.debug else 'Disabled'}")
    
    # Get admin chat ID
    admin_chat = args.admin_chat or os.getenv("ADMIN_CHAT_ID")
    if admin_chat:
        logger.info(f"Admin notifications: Enabled (chat: {admin_chat})")
    else:
        logger.warning("Admin notifications: Disabled (no ADMIN_CHAT_ID)")
    
    # Initialize and run bot
    try:
        bot = TelePhisBot(
            admin_chat_id=admin_chat,
            enable_logging=not args.no_db
        )
        
        logger.info("Bot initialized. Starting polling...")
        print("\n🤖 Bot is running. Press Ctrl+C to stop.\n")
        
        bot.run()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
