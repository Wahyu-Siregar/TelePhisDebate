"""
Run TelePhisDebate Dashboard
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.dashboard import run_dashboard


def main():
    parser = argparse.ArgumentParser(description="TelePhisDebate Dashboard")
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to bind (default: 5000)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )
    
    args = parser.parse_args()
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║              TelePhisDebate Dashboard                        ║
║              Multi-Agent Debate Phishing Detection           ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    run_dashboard(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
