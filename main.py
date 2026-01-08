#!/usr/bin/env python3
"""
AutoBlogger - 자동 블로그 포스팅 도구
GUI 및 CLI 모드 지원
"""
import sys
import argparse
import logging
from typing import Optional

from config import Config, ConfigError, config

logger = logging.getLogger(__name__)


def setup_logging(debug: bool = False) -> None:
    """Configure logging based on debug mode"""
    level = logging.DEBUG if debug else logging.INFO
    logging.getLogger().setLevel(level)
    
    # Add file handler in debug mode
    if debug:
        file_handler = logging.FileHandler('autoblogger.log')
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        logging.getLogger().addHandler(file_handler)


def run_gui_mode() -> int:
    """Run application in GUI mode"""
    try:
        # Check if GUI is available
        if not Config.is_gui_available():
            logger.error("GUI is not available in this environment.")
            logger.info("Run with --headless flag for command-line mode.")
            return 1
        
        # Import GUI components only when needed
        from PySide6.QtWidgets import QApplication
        from ui.main_window import MainWindow
        
        app = QApplication(sys.argv)
        
        # Create and show the main window
        window = MainWindow()
        window.show()
        
        logger.info(f"Starting {Config.APP_NAME} v{Config.VERSION} in GUI mode")
        return app.exec()
        
    except ImportError as e:
        logger.error(f"Failed to import GUI components: {e}")
        logger.info("Make sure PySide6 is installed: pip install PySide6")
        logger.info("Or run with --headless flag for command-line mode.")
        return 1
    except Exception as e:
        logger.error(f"GUI mode failed: {e}")
        return 1


def run_headless_mode(topic: Optional[str] = None) -> int:
    """Run application in headless (CLI) mode"""
    logger.info(f"Starting {Config.APP_NAME} v{Config.VERSION} in headless mode")
    
    try:
        # Validate configuration
        Config.validate(require_api_keys=False)
        
        # Display configuration info
        info = Config.get_info()
        logger.info(f"Configuration: {info}")
        
        if topic:
            logger.info(f"Topic to process: {topic}")
            # Here you would call the blog generation logic
            from core.blog_generator import BlogGenerator
            generator = BlogGenerator()
            result = generator.generate(topic)
            if result:
                logger.info(f"Blog post generated successfully: {result}")
            else:
                logger.warning("Blog generation returned no result")
        else:
            logger.info("No topic provided. Use --topic 'your topic' to generate a blog post.")
            logger.info("Available commands:")
            logger.info("  --topic 'topic'  : Generate a blog post about the topic")
            logger.info("  --validate      : Validate configuration")
            logger.info("  --info          : Show application info")
        
        return 0
        
    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except ImportError as e:
        logger.error(f"Import error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Headless mode failed: {e}")
        if Config.DEBUG_MODE:
            import traceback
            traceback.print_exc()
        return 1


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description=f"{Config.APP_NAME} - Automated Blog Posting Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Run in GUI mode
  python main.py --headless         # Run in CLI mode
  python main.py --topic "AI 기술"  # Generate blog about AI
  python main.py --validate         # Validate configuration
  python main.py --info             # Show application info
        """
    )
    
    parser.add_argument(
        '--headless', '-H',
        action='store_true',
        help='Run in headless (CLI) mode without GUI'
    )
    
    parser.add_argument(
        '--topic', '-t',
        type=str,
        help='Topic for blog post generation'
    )
    
    parser.add_argument(
        '--validate', '-v',
        action='store_true',
        help='Validate configuration and exit'
    )
    
    parser.add_argument(
        '--info', '-i',
        action='store_true',
        help='Show application info and exit'
    )
    
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Enable debug mode'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'{Config.APP_NAME} v{Config.VERSION}'
    )
    
    return parser.parse_args()


def main() -> int:
    """Main entry point"""
    args = parse_arguments()
    
    # Setup logging
    setup_logging(debug=args.debug or Config.DEBUG_MODE)
    
    # Handle info command
    if args.info:
        info = Config.get_info()
        print(f"\n{Config.APP_NAME} v{Config.VERSION}")
        print("=" * 40)
        for key, value in info.items():
            print(f"  {key}: {value}")
        print()
        return 0
    
    # Handle validate command
    if args.validate:
        try:
            Config.validate(require_api_keys=True)
            print("✓ Configuration is valid")
            return 0
        except ConfigError as e:
            print(f"✗ Configuration error: {e}")
            return 1
    
    # Determine mode
    headless = args.headless or Config.HEADLESS_MODE or args.topic is not None
    
    if headless:
        return run_headless_mode(topic=args.topic)
    else:
        return run_gui_mode()


if __name__ == "__main__":
    sys.exit(main())
