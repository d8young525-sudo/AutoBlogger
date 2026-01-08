"""
Naver Blog Poster Module
네이버 블로그 자동 포스팅 기능
"""
import logging
import time
from typing import Optional, Dict, Any
from pathlib import Path

from config import Config

logger = logging.getLogger(__name__)


class NaverPosterError(Exception):
    """Naver posting related errors"""
    pass


class NaverPoster:
    """Naver Blog Automated Poster using Selenium"""
    
    NAVER_LOGIN_URL = "https://nid.naver.com/nidlogin.login"
    NAVER_BLOG_WRITE_URL = "https://blog.naver.com/{blog_id}/postwrite"
    
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
        
        self._driver = None
        self._logged_in = False
        
        if not self.naver_id or not self.naver_pw:
            logger.warning("Naver credentials not provided")
    
    def _init_driver(self):
        """Initialize Selenium WebDriver"""
        if self._driver is not None:
            return
        
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            from webdriver_manager.chrome import ChromeDriverManager
            
            options = Options()
            
            if self.headless:
                options.add_argument("--headless=new")
            
            # Common options for stability
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            
            # User agent
            options.add_argument(
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            service = Service(ChromeDriverManager().install())
            self._driver = webdriver.Chrome(service=service, options=options)
            self._driver.implicitly_wait(self.timeout)
            
            # Stealth mode
            self._driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            
            logger.info("WebDriver initialized successfully")
            
        except ImportError:
            raise NaverPosterError(
                "Selenium packages not installed. "
                "Install with: pip install selenium webdriver-manager"
            )
        except Exception as e:
            raise NaverPosterError(f"Failed to initialize WebDriver: {e}")
    
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
        
        self._init_driver()
        
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.common.keys import Keys
            
            logger.info("Attempting Naver login...")
            
            self._driver.get(self.NAVER_LOGIN_URL)
            time.sleep(2)
            
            # Find login form elements
            wait = WebDriverWait(self._driver, self.timeout)
            
            # Input ID
            id_input = wait.until(
                EC.presence_of_element_located((By.ID, "id"))
            )
            id_input.clear()
            
            # Use JavaScript to set value (bypass copy-paste detection)
            self._driver.execute_script(
                f"arguments[0].value = '{self.naver_id}'", id_input
            )
            
            time.sleep(0.5)
            
            # Input Password
            pw_input = self._driver.find_element(By.ID, "pw")
            pw_input.clear()
            self._driver.execute_script(
                f"arguments[0].value = '{self.naver_pw}'", pw_input
            )
            
            time.sleep(0.5)
            
            # Click login button
            login_btn = self._driver.find_element(By.ID, "log.login")
            login_btn.click()
            
            time.sleep(3)
            
            # Check if login was successful
            current_url = self._driver.current_url
            
            if "nid.naver.com" in current_url and "login" not in current_url.lower():
                self._logged_in = True
                logger.info("Naver login successful")
                return True
            
            # Check for captcha or 2FA
            if "captcha" in current_url.lower() or "device" in current_url.lower():
                raise NaverPosterError(
                    "Captcha or device verification required. "
                    "Please login manually first."
                )
            
            raise NaverPosterError("Login failed - check credentials")
            
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
            tags: List of tags/hashtags
            category: Blog category
            
        Returns:
            Dict with posting result
        """
        if not self._logged_in:
            self.login()
        
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            logger.info(f"Posting blog: {title}")
            
            # Navigate to blog write page
            write_url = self.NAVER_BLOG_WRITE_URL.format(blog_id=self.naver_id)
            self._driver.get(write_url)
            time.sleep(3)
            
            wait = WebDriverWait(self._driver, self.timeout)
            
            # Switch to editor iframe if needed
            try:
                iframe = wait.until(
                    EC.presence_of_element_located((By.TAG_NAME, "iframe"))
                )
                self._driver.switch_to.frame(iframe)
            except Exception:
                pass  # No iframe, continue
            
            # Input title
            title_input = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "[placeholder*='제목'], .se-title-input, #title")
                )
            )
            title_input.clear()
            title_input.send_keys(title)
            
            time.sleep(1)
            
            # Input content
            content_area = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, ".se-content, .content-area, #content")
                )
            )
            content_area.click()
            
            # Use JavaScript to insert content
            self._driver.execute_script(
                "arguments[0].innerHTML = arguments[1]",
                content_area,
                content.replace("\n", "<br>")
            )
            
            time.sleep(1)
            
            # Add tags if provided
            if tags:
                try:
                    tag_input = self._driver.find_element(
                        By.CSS_SELECTOR, "[placeholder*='태그'], .tag-input"
                    )
                    tag_str = ", ".join(tags)
                    tag_input.send_keys(tag_str)
                    time.sleep(0.5)
                except Exception as e:
                    logger.warning(f"Could not add tags: {e}")
            
            # Publish
            publish_btn = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "[class*='publish'], .btn-publish, #publish")
                )
            )
            publish_btn.click()
            
            time.sleep(3)
            
            # Get posted URL
            current_url = self._driver.current_url
            
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
        """Close WebDriver"""
        if self._driver:
            try:
                self._driver.quit()
                logger.info("WebDriver closed")
            except Exception as e:
                logger.error(f"Error closing WebDriver: {e}")
            finally:
                self._driver = None
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
