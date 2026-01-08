"""
AutoBlogger Configuration Module
환경변수 로딩 및 애플리케이션 설정 관리
"""
import os
import sys
import logging
from pathlib import Path
from typing import Optional

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Configuration related errors"""
    pass


class Config:
    """Application Configuration Class"""
    
    # Application Info
    APP_NAME = "AutoBlogger"
    VERSION = "0.2.0"
    
    # Base Paths
    BASE_DIR = Path(__file__).parent.resolve()
    
    # API Keys (Loaded from environment variables)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    FIREBASE_CREDENTIALS_PATH: str = os.getenv(
        "FIREBASE_CREDENTIALS_PATH", 
        str(BASE_DIR / "firebase_key.json")
    )
    
    # Naver Settings (Optional: default settings)
    NAVER_ID: str = os.getenv("NAVER_ID", "")
    NAVER_PW: str = os.getenv("NAVER_PW", "")
    
    # Window Settings (for GUI mode)
    WINDOW_WIDTH = 1200
    WINDOW_HEIGHT = 800
    
    # Selenium Settings
    SELENIUM_HEADLESS = os.getenv("SELENIUM_HEADLESS", "true").lower() == "true"
    SELENIUM_TIMEOUT = int(os.getenv("SELENIUM_TIMEOUT", "30"))
    
    # Application Mode
    HEADLESS_MODE = os.getenv("HEADLESS_MODE", "false").lower() == "true"
    DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
    
    @classmethod
    def validate(cls, require_api_keys: bool = False) -> bool:
        """
        Validate configuration settings
        
        Args:
            require_api_keys: If True, API keys are required
            
        Returns:
            bool: True if validation passes
            
        Raises:
            ConfigError: If validation fails
        """
        errors = []
        
        if require_api_keys:
            if not cls.GEMINI_API_KEY:
                errors.append("GEMINI_API_KEY is not set")
            
            if not cls.NAVER_ID or not cls.NAVER_PW:
                logger.warning("Naver credentials not set - Naver posting will be disabled")
        
        # Check Firebase credentials file if path is set
        if cls.FIREBASE_CREDENTIALS_PATH:
            firebase_path = Path(cls.FIREBASE_CREDENTIALS_PATH)
            if not firebase_path.exists():
                logger.warning(f"Firebase credentials file not found: {firebase_path}")
        
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            logger.error(error_msg)
            raise ConfigError(error_msg)
        
        logger.info("Configuration validated successfully")
        return True
    
    @classmethod
    def get_info(cls) -> dict:
        """Get application info as dictionary"""
        return {
            "app_name": cls.APP_NAME,
            "version": cls.VERSION,
            "base_dir": str(cls.BASE_DIR),
            "headless_mode": cls.HEADLESS_MODE,
            "debug_mode": cls.DEBUG_MODE,
            "has_gemini_key": bool(cls.GEMINI_API_KEY),
            "has_naver_credentials": bool(cls.NAVER_ID and cls.NAVER_PW),
        }
    
    @classmethod
    def is_gui_available(cls) -> bool:
        """Check if GUI is available in current environment"""
        # Check for display environment variable
        if os.environ.get('DISPLAY'):
            return True
        
        # Check for Wayland
        if os.environ.get('WAYLAND_DISPLAY'):
            return True
        
        # Check for Windows
        if sys.platform == 'win32':
            return True
        
        # Check for macOS
        if sys.platform == 'darwin':
            return True
        
        return False


# Create a singleton-like access
config = Config()
