import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Application Info
    APP_NAME = "AutoBlogger"
    VERSION = "0.1.0"
    
    # API Keys (Loaded from environment variables)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase_key.json")
    
    # Naver Settings (Optional: default settings)
    NAVER_ID = os.getenv("NAVER_ID", "")
    NAVER_PW = os.getenv("NAVER_PW", "")

    # Window Settings
    WINDOW_WIDTH = 1200
    WINDOW_HEIGHT = 800
