"""
Naver Blog Poster Module
네이버 블로그 자동 포스팅 기능

naver_blog_auto.automation.NaverBlogBot을 래핑하여 
core 모듈에서 일관된 인터페이스 제공
"""
import logging
from typing import Optional, Dict, Any

from config import Config

logger = logging.getLogger(__name__)


class NaverPosterError(Exception):
    """Naver posting related errors"""
    pass


class NaverPoster:
    """
    Naver Blog Automated Poster
    
    내부적으로 naver_blog_auto.automation.NaverBlogBot을 사용하여
    SmartEditor ONE 에디터에 대응
    """
    
    def __init__(
        self, 
        naver_id: Optional[str] = None, 
        naver_pw: Optional[str] = None,
        headless: bool = True
    ):
        """
        Initialize Naver poster
        
        Args:
            naver_id: Naver account ID
            naver_pw: Naver account password  
            headless: Run browser in headless mode
        """
        self.naver_id = naver_id or Config.NAVER_ID
        self.naver_pw = naver_pw or Config.NAVER_PW
        self.headless = headless if headless is not None else Config.SELENIUM_HEADLESS
        self.timeout = Config.SELENIUM_TIMEOUT
        
        self._bot = None
        self._logged_in = False
        
        if not self.naver_id or not self.naver_pw:
            logger.warning("Naver credentials not provided")
    
    def _init_bot(self):
        """Initialize NaverBlogBot from automation module"""
        if self._bot is not None:
            return
        
        try:
            from naver_blog_auto.automation import NaverBlogBot
            
            self._bot = NaverBlogBot(
                headless=self.headless,
                timeout=self.timeout
            )
            self._bot.start_browser()
            
            logger.info("NaverBlogBot initialized successfully")
            
        except ImportError as e:
            raise NaverPosterError(
                f"Failed to import automation module: {e}. "
                "Make sure naver_blog_auto package is available."
            )
        except Exception as e:
            raise NaverPosterError(f"Failed to initialize NaverBlogBot: {e}")
    
    def login(self) -> bool:
        """
        Login to Naver account
        
        Returns:
            True if login successful
        """
        if not self.naver_id or not self.naver_pw:
            raise NaverPosterError("Naver credentials not configured")
        
        if self._logged_in:
            return True
        
        self._init_bot()
        
        try:
            logger.info("Attempting Naver login...")
            
            success, message = self._bot.login(self.naver_id, self.naver_pw)
            
            if success:
                self._logged_in = True
                logger.info("Naver login successful")
                return True
            else:
                raise NaverPosterError(f"Login failed: {message}")
            
        except NaverPosterError:
            raise
        except Exception as e:
            logger.error(f"Login failed: {e}")
            raise NaverPosterError(f"Login failed: {e}")
    
    def post_blog(
        self,
        title: str,
        content: str,
        tags: Optional[list] = None,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Post content to Naver Blog
        
        Args:
            title: Blog post title
            content: Blog post content
            tags: List of tags/hashtags (현재 미지원)
            category: Blog category (현재 미지원)
            
        Returns:
            Dict with posting result
        """
        if not self._logged_in:
            self.login()
        
        try:
            logger.info(f"Posting blog: {title}")
            
            # 1. 에디터로 이동
            success, message = self._bot.go_to_editor()
            if not success:
                return {
                    "success": False,
                    "title": title,
                    "url": None,
                    "message": f"Failed to open editor: {message}"
                }
            
            # 2. 제목 및 본문 작성
            success, message = self._bot.write_content(title, content)
            if not success:
                return {
                    "success": False,
                    "title": title,
                    "url": None,
                    "message": f"Failed to write content: {message}"
                }
            
            # 3. 발행
            success, message = self._bot.publish_post()
            if not success:
                return {
                    "success": False,
                    "title": title,
                    "url": None,
                    "message": f"Failed to publish: {message}"
                }
            
            # 발행 성공
            current_url = self._bot.get_current_url()
            logger.info(f"Blog posted successfully: {current_url}")
            
            return {
                "success": True,
                "title": title,
                "url": current_url,
                "message": "Blog posted successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to post blog: {e}")
            return {
                "success": False,
                "title": title,
                "url": None,
                "message": f"Posting failed: {e}"
            }
    
    def close(self):
        """Close browser and cleanup"""
        if self._bot:
            try:
                self._bot.close()
                logger.info("NaverBlogBot closed")
            except Exception as e:
                logger.error(f"Error closing NaverBlogBot: {e}")
            finally:
                self._bot = None
                self._logged_in = False
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
    
    def is_available(self) -> bool:
        """Check if Naver poster is available"""
        return bool(self.naver_id and self.naver_pw)
