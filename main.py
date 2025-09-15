#!/usr/bin/env python3
"""
Main entry point for Dicti - Linux Live Dictation.
"""

import sys
import argparse
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dictation_app import DictationApp

def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('dictation.log')
        ]
    )

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Dicti - Linux Live Dictation with Whisper")
    parser.add_argument(
        "--model", 
        choices=["tiny", "base", "small", "medium", "large"],
        default="base",
        help="Whisper model size (default: base)"
    )
    parser.add_argument(
        "--language",
        choices=["en", "pl"],
        default=None,
        help="Language for transcription (default: auto-detect)"
    )
    parser.add_argument(
        "--hotkey",
        default="copilot",
        help="Global hotkey for activation (default: copilot)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show application status and exit"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    # Create application
    app = DictationApp(
        model_size=args.model,
        language=args.language,
        hotkey=args.hotkey
    )
    
    # Show status if requested
    if args.status:
        status = app.get_status()
        print("Dicti Status:")
        for key, value in status.items():
            print(f"  {key}: {value}")
        return
    
    # Start application
    logger.info("Starting Dicti...")
    logger.info(f"Model: {args.model}")
    logger.info(f"Language: {args.language or 'auto-detect'}")
    logger.info(f"Hotkey: {args.hotkey}")
    
    try:
        app.run_interactive()
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
