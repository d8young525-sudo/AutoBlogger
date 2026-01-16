"""
Naver Blog Automation Module
네이버 블로그 자동 포스팅 봇
v3.5.2: 글쓰기 에디터 진입 플로우 개선, 카테고리 선택 기능 추가
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
        self.category = ""  # 발행할 카테고리

    def set_category(self, category: str):
        """발행할 카테고리 설정"""
        self.category = category

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
        
        플로우: 네이버 메인 -> 로그인 페이지 -> 로그인 -> 네이버 메인 -> 블로그 메인
        
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
            
            # Step 1: 네이버 메인 페이지 방문
            self.driver.get("https://www.naver.com")
            time.sleep(2)
            
            # Step 2: 로그인 페이지로 이동
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
            
            # Step 3: 로그인 후 네이버 메인 페이지로 이동하여 세션 안정화
            self.driver.get("https://www.naver.com")
            time.sleep(2)
            
            # Step 4: 블로그 메인 페이지로 이동
            self.driver.get("https://blog.naver.com")
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
        """
        Navigate to blog editor
        
        플로우: 블로그 메인 -> 글쓰기 버튼 클릭 -> 에디터 진입
        """
        if not self.driver:
            return False, "Browser not started"
            
        try:
            logger.info("Navigating to editor...")
            
            # Step 1: 블로그 메인으로 이동
            self.driver.get("https://blog.naver.com")
            time.sleep(2)
            
            # Step 2: 글쓰기 에디터로 직접 이동 (GoBlogWrite.naver)
            self.driver.get("https://blog.naver.com/GoBlogWrite.naver")
            time.sleep(3)
            
            # Step 3: "작성 중인 글이 있습니다" 팝업 처리
            self._handle_draft_popup()
            
            # Step 4: 에디터 로드 확인
            try:
                # 에디터의 제목 placeholder 확인
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR, 
                        ".se-placeholder, .se-text-paragraph, [class*='editor']"
                    ))
                )
                logger.info("Editor loaded successfully")
                return True, "Editor loaded"
            except TimeoutException:
                # URL 확인
                if "PostWriteForm" in self.driver.current_url or "GoBlogWrite" in self.driver.current_url:
                    return True, "Editor loaded (URL verified)"
                return False, "Editor elements not found"
            
        except TimeoutException:
            return False, "Editor load timeout"
        except Exception as e:
            logger.error(f"Failed to load editor: {e}")
            return False, f"Editor error: {str(e)}"

    def _handle_draft_popup(self):
        """
        "작성 중인 글이 있습니다" 팝업 처리
        취소 버튼을 클릭하여 새 글 작성
        """
        try:
            # 팝업이 나타날 때까지 잠시 대기
            cancel_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR, 
                    "button.se-popup-button-cancel"
                ))
            )
            cancel_btn.click()
            logger.info("Closed draft popup - starting fresh")
            time.sleep(1)
        except TimeoutException:
            # 팝업이 없으면 정상 진행
            logger.info("No draft popup found")
        except Exception as e:
            logger.warning(f"Draft popup handling: {e}")

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
            
            # Step 1: 제목 입력
            # 제목 placeholder 클릭
            try:
                title_area = self.wait.until(
                    EC.element_to_be_clickable((
                        By.CSS_SELECTOR, 
                        ".se-placeholder.se-fs32, span.se-placeholder[class*='fs32']"
                    ))
                )
                title_area.click()
            except:
                # 대안: 제목 텍스트로 찾기
                title_area = self.wait.until(
                    EC.element_to_be_clickable((
                        By.XPATH, 
                        "//span[contains(@class, 'se-placeholder') and text()='제목']"
                    ))
                )
                title_area.click()
            
            time.sleep(0.5)
            
            # 제목 입력
            if not self.clipboard_input(title):
                ActionChains(self.driver).send_keys(title).perform()
            
            time.sleep(1)
            
            # Step 2: 본문 입력
            # 본문 placeholder 클릭
            try:
                content_area = self.driver.find_element(
                    By.CSS_SELECTOR,
                    ".se-placeholder.se-fs15, span.se-placeholder[class*='fs15']"
                )
                content_area.click()
            except:
                # 대안: 본문 텍스트로 찾기
                content_area = self.driver.find_element(
                    By.XPATH, 
                    "//span[contains(@class, 'se-placeholder') and contains(text(), '글감과')]"
                )
                content_area.click()
            
            time.sleep(0.5)
            
            # 본문 입력
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

    def publish_post(self, category: str = "") -> Tuple[bool, str]:
        """
        Publish the blog post
        
        Args:
            category: 발행할 카테고리명 (선택사항)
        
        플로우:
        1. 발행 버튼 클릭
        2. 카테고리 선택 (있으면)
        3. 즉시 발행 선택
        4. 최종 발행 버튼 클릭
        """
        if not self.driver:
            return False, "Browser not started"
        
        # 카테고리 설정 (인자로 전달되거나, 미리 설정된 값 사용)
        target_category = category or self.category
            
        try:
            logger.info("Publishing post...")
            
            # Step 1: 발행 버튼 클릭 (상단 발행 버튼)
            publish_btn = self.wait.until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR, 
                    "button.publish_btn__m9KHH, button[data-click-area='tpb.publish']"
                ))
            )
            publish_btn.click()
            time.sleep(1.5)
            
            # Step 2: 카테고리 선택 (설정된 카테고리가 있으면)
            if target_category:
                self._select_category(target_category)
            
            # Step 3: 즉시 발행 선택
            try:
                # 현재 라디오 버튼 클릭
                immediate_radio = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "label[for='radio_time1'], input#radio_time1"
                )
                immediate_radio.click()
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"Could not click immediate publish radio: {e}")
                # JavaScript로 시도
                try:
                    self.driver.execute_script(
                        "document.getElementById('radio_time1').click();"
                    )
                except:
                    pass
            
            time.sleep(0.5)
            
            # Step 4: 최종 발행 버튼 클릭
            final_btn = self.wait.until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR, 
                    "button.confirm_btn__WEaBq, button[data-testid='seOnePublishBtn']"
                ))
            )
            final_btn.click()
            
            time.sleep(3)
            logger.info("Post published successfully")
            return True, "Published"
            
        except TimeoutException:
            return False, "Publish button not found"
        except Exception as e:
            logger.error(f"Publish failed: {e}")
            return False, f"Publish error: {str(e)}"

    def _select_category(self, category_name: str):
        """
        카테고리 선택
        
        Args:
            category_name: 선택할 카테고리명
        """
        try:
            logger.info(f"Selecting category: {category_name}")
            
            # Step 1: 카테고리 드롭다운 버튼 클릭
            category_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR,
                    "span.text__sraQE[data-testid^='categoryItemText'], .category_btn, [class*='category']"
                ))
            )
            category_btn.click()
            time.sleep(1)
            
            # Step 2: 카테고리 목록에서 해당 카테고리 찾아서 클릭
            try:
                # data-testid로 카테고리 항목 찾기
                category_items = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "span.text__sraQE[data-testid^='categoryItemText']"
                )
                
                for item in category_items:
                    item_text = item.text.strip()
                    # 카테고리명 비교 (비공개 아이콘 등 제외하고 텍스트만)
                    if category_name in item_text or item_text in category_name:
                        # 해당 카테고리의 label 클릭
                        parent = item.find_element(By.XPATH, "./ancestor::label")
                        parent.click()
                        logger.info(f"Selected category: {item_text}")
                        time.sleep(0.5)
                        return
                
                # 정확히 일치하는 것 없으면 부분 일치 시도
                for item in category_items:
                    if category_name.lower() in item.text.lower():
                        parent = item.find_element(By.XPATH, "./ancestor::label")
                        parent.click()
                        logger.info(f"Selected category (partial match): {item.text}")
                        time.sleep(0.5)
                        return
                        
                logger.warning(f"Category '{category_name}' not found in list")
                
            except Exception as e:
                logger.warning(f"Category selection error: {e}")
                
        except TimeoutException:
            logger.warning("Category dropdown not found")
        except Exception as e:
            logger.warning(f"Category selection failed: {e}")

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
