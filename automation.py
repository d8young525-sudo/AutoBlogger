"""
Naver Blog Automation Module
네이버 블로그 자동 포스팅 봇
"""
import time
import logging
from typing import Tuple, Optional

try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException,
    WebDriverException
)

from config import Config

logger = logging.getLogger(__name__)


class NaverBlogBot:
    """Naver Blog Automation Bot"""
    
    def __init__(self, headless: bool = False):
        """
        Initialize bot
        
        Args:
            headless: Run browser in headless mode
        """
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.headless = headless or Config.HEADLESS_BROWSER
        self._is_logged_in = False

    def start_browser(self) -> Tuple[bool, str]:
        """Start Chrome browser with optimal settings"""
        try:
            options = Options()
            
            # Headless mode
            if self.headless:
                options.add_argument("--headless=new")
            
            # Anti-detection settings
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            
            # Stability settings
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            
            # Keep browser open after script ends (for debugging)
            if not self.headless:
                options.add_experimental_option("detach", True)
            
            # User agent
            options.add_argument(
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.wait = WebDriverWait(self.driver, Config.SELENIUM_TIMEOUT)
            self.driver.set_window_size(1280, 900)
            
            # Remove webdriver flag
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            
            logger.info("Browser started successfully")
            return True, "Browser started"
            
        except WebDriverException as e:
            logger.error(f"Failed to start browser: {e}")
            return False, f"Browser start failed: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error starting browser: {e}")
            return False, f"Unexpected error: {str(e)}"

    def clipboard_input(self, user_input: str) -> bool:
        """
        Input text using clipboard (bypasses automation detection)
        
        Args:
            user_input: Text to input
            
        Returns:
            True if successful
        """
        if not self.driver:
            return False
            
        try:
            if PYPERCLIP_AVAILABLE:
                pyperclip.copy(user_input)
                ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
            else:
                # Fallback: Use JavaScript
                active = self.driver.switch_to.active_element
                self.driver.execute_script(
                    "arguments[0].value = arguments[1]; "
                    "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
                    active, user_input
                )
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.error(f"Clipboard input failed: {e}")
            return False

    def login(self, user_id: str, user_pw: str) -> Tuple[bool, str]:
        """
        Login to Naver account
        
        Args:
            user_id: Naver ID
            user_pw: Naver password
            
        Returns:
            Tuple of (success, message)
        """
        if not self.driver:
            return False, "Browser not started"
        
        if self._is_logged_in:
            return True, "Already logged in"
            
        try:
            logger.info("Attempting Naver login...")
            self.driver.get("https://nid.naver.com/nidlogin.login")
            time.sleep(2)
            
            # Input ID
            id_input = self.wait.until(
                EC.element_to_be_clickable((By.ID, "id"))
            )
            id_input.click()
            time.sleep(0.3)
            
            if not self.clipboard_input(user_id):
                # Fallback: direct input
                id_input.clear()
                id_input.send_keys(user_id)
            
            time.sleep(0.5)
            
            # Input Password
            pw_input = self.driver.find_element(By.ID, "pw")
            pw_input.click()
            time.sleep(0.3)
            
            if not self.clipboard_input(user_pw):
                pw_input.clear()
                pw_input.send_keys(user_pw)
            
            time.sleep(0.5)
            
            # Click login button
            login_btn = self.driver.find_element(By.ID, "log.login")
            login_btn.click()
            time.sleep(3)
            
            # Check for CAPTCHA or 2FA
            current_url = self.driver.current_url
            if "captcha" in current_url.lower():
                return False, "CAPTCHA required - please login manually"
            if "device" in current_url.lower():
                return False, "Device verification required - please login manually"
            
            # 로그인 후 메인 페이지로 이동하여 세션 안정화
            self.driver.get("https://www.naver.com")
            time.sleep(2)
            
            self._is_logged_in = True
            logger.info("Login successful")
            return True, "Login success"
            
        except TimeoutException:
            return False, "Login timeout - page elements not found"
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False, f"Login error: {str(e)}"

    def go_to_editor(self) -> Tuple[bool, str]:
        """Navigate to blog editor"""
        if not self.driver:
            return False, "Browser not started"
            
        try:
            logger.info("Navigating to editor...")
            
            # 먼저 블로그 메인으로 이동하여 세션 확인
            self.driver.get("https://blog.naver.com")
            time.sleep(2)
            
            # 내 블로그 확인을 위해 블로그 홈 방문
            self.driver.get("https://blog.naver.com/MyBlog.naver")
            time.sleep(2)
            
            # 글쓰기 페이지로 이동
            self.driver.get("https://blog.naver.com/PostWriteForm.naver")
            time.sleep(3)
            
            # 접근 거부 페이지 체크
            page_source = self.driver.page_source.lower()
            if "정상적인 접근이 아닙니다" in self.driver.page_source or "비정상적인 접근" in self.driver.page_source:
                logger.warning("Access denied detected, trying alternative method...")
                
                # 대안: 블로그 홈에서 글쓰기 버튼 클릭
                self.driver.get("https://blog.naver.com/MyBlog.naver")
                time.sleep(2)
                
                try:
                    # 글쓰기 버튼 찾기
                    write_btn = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn_write, a[href*='PostWriteForm'], .write_btn"))
                    )
                    write_btn.click()
                    time.sleep(3)
                except:
                    # 직접 URL로 다시 시도
                    self.driver.get("https://blog.naver.com/PostWriteForm.naver?wtype=post&directAccess=true")
                    time.sleep(3)
            
            # Close draft popup if present
            try:
                cancel_btn = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.se-popup-button-cancel"))
                )
                cancel_btn.click()
                logger.info("Closed draft popup")
            except TimeoutException:
                pass
            
            # Close help panel if present
            try:
                help_btn = WebDriverWait(self.driver, 2).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.se-help-panel-close-button"))
                )
                help_btn.click()
                logger.info("Closed help panel")
            except TimeoutException:
                pass
            
            # 에디터가 로드되었는지 확인
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".se-component, .se-editor, [class*='editor']"))
                )
                logger.info("Editor loaded successfully")
                return True, "Editor loaded"
            except:
                # 최종 확인
                if "PostWriteForm" in self.driver.current_url or "편집" in self.driver.page_source:
                    return True, "Editor loaded"
                return False, "Editor elements not found"
            
        except TimeoutException:
            return False, "Editor load timeout"
        except Exception as e:
            logger.error(f"Failed to load editor: {e}")
            return False, f"Editor error: {str(e)}"

    def write_content(self, title: str, content: str) -> Tuple[bool, str]:
        """
        Write blog content
        
        Args:
            title: Blog post title
            content: Blog post content
            
        Returns:
            Tuple of (success, message)
        """
        if not self.driver:
            return False, "Browser not started"
            
        try:
            logger.info("Writing content...")
            
            # Click title area
            title_area = self.wait.until(
                EC.element_to_be_clickable((
                    By.XPATH, 
                    "//span[contains(@class, 'se-placeholder') and text()='제목']"
                ))
            )
            title_area.click()
            time.sleep(0.5)
            
            if not self.clipboard_input(title):
                ActionChains(self.driver).send_keys(title).perform()
            
            time.sleep(1)
            
            # Click content area
            content_area = self.driver.find_element(
                By.XPATH, 
                "//span[contains(@class, 'se-placeholder') and contains(text(), '글감과')]"
            )
            content_area.click()
            time.sleep(0.5)
            
            if not self.clipboard_input(content):
                ActionChains(self.driver).send_keys(content).perform()
            
            time.sleep(2)
            
            logger.info("Content written successfully")
            return True, "Content written"
            
        except TimeoutException:
            return False, "Content area not found"
        except NoSuchElementException:
            return False, "Editor elements not found"
        except Exception as e:
            logger.error(f"Failed to write content: {e}")
            return False, f"Write error: {str(e)}"

    def publish_post(self) -> Tuple[bool, str]:
        """Publish the blog post"""
        if not self.driver:
            return False, "Browser not started"
            
        try:
            logger.info("Publishing post...")
            
            # Click first publish button
            publish_btn = self.wait.until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR, 
                    "button[data-click-area='tpb.publish']"
                ))
            )
            publish_btn.click()
            time.sleep(1.5)
            
            # Select immediate publish option
            try:
                self.driver.execute_script("document.getElementById('radio_time1').click();")
            except Exception:
                pass
            
            time.sleep(0.5)
            
            # Click final publish button
            final_btn = self.wait.until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR, 
                    "button[data-testid='seOnePublishBtn']"
                ))
            )
            final_btn.click()
            
            time.sleep(2)
            logger.info("Post published successfully")
            return True, "Published"
            
        except TimeoutException:
            return False, "Publish button not found"
        except Exception as e:
            logger.error(f"Publish failed: {e}")
            return False, f"Publish error: {str(e)}"

    def close(self):
        """Close browser and cleanup resources"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Browser closed")
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
            finally:
                self.driver = None
                self.wait = None
                self._is_logged_in = False

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure cleanup"""
        self.close()
