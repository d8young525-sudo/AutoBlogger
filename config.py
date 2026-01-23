"""
AutoBlogger Configuration Module
환경 설정 및 상수 관리
"""
import os
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class Config:
    """Application Configuration"""
    
    # Application Info
    APP_NAME = "Auto Blogger Pro"
    VERSION = "3.10.1"
    
    # Paths
    BASE_DIR = Path(__file__).parent.resolve()
    
    # Backend API
    BACKEND_URL = os.getenv(
        "BACKEND_URL", 
        "https://generate-blog-post-yahp6ia25q-du.a.run.app"
    )
    
    # Timeouts
    API_TIMEOUT = int(os.getenv("API_TIMEOUT", "180"))
    SELENIUM_TIMEOUT = int(os.getenv("SELENIUM_TIMEOUT", "15"))
    
    # Browser Settings
    HEADLESS_BROWSER = os.getenv("HEADLESS_BROWSER", "false").lower() == "true"
    
    # Gemini API (for image generation)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    
    # 이미지 생성 모델 설정
    # 옵션: gemini-2.5-flash-image (권장), imagen-3.0-generate-001, gemini-2.0-flash-preview-image-generation
    GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    
    # Firebase Auth (웹 API 키 - Firebase Console에서 확인)
    # 환경변수가 없으면 기본값 사용
    FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY", "AIzaSyBAmWCulbDrqONvkA5Zd-Cr_e5GLu3y0Ac")
    
    # Window Settings
    WINDOW_WIDTH = 700
    WINDOW_HEIGHT = 1000
    
    @classmethod
    def is_gui_available(cls) -> bool:
        """Check if GUI environment is available"""
        # Check for display
        if os.environ.get('DISPLAY'):
            return True
        if os.environ.get('WAYLAND_DISPLAY'):
            return True
        # Windows always has GUI
        if sys.platform == 'win32':
            return True
        # macOS
        if sys.platform == 'darwin':
            return True
        return False
    
    @classmethod
    def get_info(cls) -> dict:
        """Get app info"""
        return {
            "app_name": cls.APP_NAME,
            "version": cls.VERSION,
            "backend_url": cls.BACKEND_URL,
            "gui_available": cls.is_gui_available(),
            "gemini_available": bool(cls.GEMINI_API_KEY),
            "image_model": cls.GEMINI_IMAGE_MODEL,
        }


config = Config()
