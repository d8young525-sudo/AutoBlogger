"""
Naver Blog Automation Module
네이버 블로그 자동 포스팅 봇
v3.6.3: 팝업 처리 최적화 및 에디터 안정화
- 팝업 처리: WebDriverWait → find_elements 즉시 체크 (5초 대기 제거)
- 에디터 포커스 안정화
- 불필요한 대기 시간 단축
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
            
            # 비밀번호 저장 팝업 완전 차단 (강화된 설정)
            prefs = {
                # 비밀번호 관련 완전 비활성화
                "credentials_enable_service": False,
                "profile.password_manager_enabled": False,
                "profile.password_manager_leak_detection": False,
                
                # 자동완성 비활성화
                "autofill.profile_enabled": False,
                "autofill.address_enabled": False,
                "autofill.credit_card_enabled": False,
                
                # 알림 및 팝업 차단
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_setting_values.popups": 2,
                
                # 저장 프롬프트 비활성화
                "profile.password_manager.auto_signin_enabled": False,
                
                # 번역 팝업 비활성화
                "translate_enabled": False,
                "translate.enabled": False,
            }
            options.add_experimental_option("prefs", prefs)
            
            # 추가 Chrome 플래그로 비밀번호 관리 비활성화
            options.add_argument("--disable-save-password-bubble")
            options.add_argument("--password-store=basic")
            options.add_argument("--disable-infobars")
            
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
            logger.info("Navigated to GoBlogWrite.naver, waiting for page load...")
            time.sleep(5)  # 에디터 로드 대기 시간 늘림
            
            # Step 3: URL 확인
            current_url = self.driver.current_url
            logger.info(f"Current URL: {current_url}")
            
            # 로그인 페이지로 리다이렉트 됐는지 확인
            if "nidlogin" in current_url or "nid.naver.com" in current_url:
                logger.error("Redirected to login page - session may have expired")
                return False, "로그인 세션 만료"
            
            if "blog.naver.com" not in current_url:
                return False, f"Unexpected URL: {current_url}"
            
            # Step 4: mainFrame으로 전환
            logger.info("Attempting to switch to mainFrame...")
            if not self._switch_to_editor_frame():
                logger.warning("Could not switch to mainFrame, but continuing...")
            
            # Step 5: 팝업 처리 (간소화)
            self._handle_popups()
            
            logger.info("Editor page ready")
            return True, "Editor loaded"
            
        except Exception as e:
            logger.error(f"Failed to load editor: {e}")
            return False, f"Editor error: {str(e)}"

    def _switch_to_editor_frame(self) -> bool:
        """
        에디터가 있는 mainFrame iframe으로 전환
        
        네이버 블로그 에디터는 #mainFrame iframe 안에 있음
        
        Returns:
            True if successfully switched to editor frame
        """
        try:
            # 먼저 기본 컨텍스트로
            self.driver.switch_to.default_content()
            
            # mainFrame으로 전환 시도
            try:
                # 방법 1: name으로 찾기
                self.driver.switch_to.frame("mainFrame")
                logger.info("Switched to mainFrame by name")
                return True
            except Exception as e:
                logger.debug(f"Switch by name failed: {e}")
            
            try:
                # 방법 2: id로 찾기
                self.driver.switch_to.default_content()
                iframe = self.driver.find_element(By.ID, "mainFrame")
                self.driver.switch_to.frame(iframe)
                logger.info("Switched to mainFrame by ID")
                return True
            except Exception as e:
                logger.debug(f"Switch by ID failed: {e}")
            
            try:
                # 방법 3: CSS 셀렉터로 찾기
                self.driver.switch_to.default_content()
                iframe = self.driver.find_element(By.CSS_SELECTOR, "iframe#mainFrame, iframe[name='mainFrame']")
                self.driver.switch_to.frame(iframe)
                logger.info("Switched to mainFrame by CSS selector")
                return True
            except Exception as e:
                logger.debug(f"Switch by CSS failed: {e}")
            
            try:
                # 방법 4: 첫 번째 iframe으로 시도
                self.driver.switch_to.default_content()
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                logger.info(f"Found {len(iframes)} iframes")
                if iframes:
                    self.driver.switch_to.frame(iframes[0])
                    logger.info("Switched to first iframe")
                    return True
            except Exception as e:
                logger.debug(f"Switch to first iframe failed: {e}")
            
            logger.warning("Could not switch to any editor frame")
            return False
            
        except Exception as e:
            logger.error(f"Error switching to editor frame: {e}")
            return False

    def _handle_popups(self):
        """팝업들 처리 (드래프트 팝업, 도움말 패널 등) - 빠른 체크 방식"""
        
        # 드래프트 팝업 처리 (즉시 체크, 대기 없음)
        try:
            # find_elements는 없으면 빈 리스트 반환 (예외 없음, 대기 없음)
            cancel_btns = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "button.se-popup-button-cancel"
            )
            if cancel_btns and cancel_btns[0].is_displayed():
                cancel_btns[0].click()
                logger.info("Closed draft popup")
                time.sleep(0.3)
            else:
                logger.info("No draft popup")
        except Exception as e:
            logger.debug(f"Draft popup check: {e}")
        
        # 도움말 패널 처리 (즉시 체크, 대기 없음)
        try:
            help_btns = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "button.se-help-panel-close-button"
            )
            if help_btns and help_btns[0].is_displayed():
                help_btns[0].click()
                logger.info("Closed help panel")
                time.sleep(0.3)
            else:
                logger.info("No help panel")
        except Exception as e:
            logger.debug(f"Help panel check: {e}")

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
            logger.info("=== write_content() 시작 ===")
            
            # mainFrame으로 전환
            logger.info("Switching to mainFrame for writing...")
            if not self._switch_to_editor_frame():
                logger.error("Failed to switch to mainFrame")
                return False, "Failed to switch to editor frame"
            
            # 에디터가 완전히 로드될 때까지 잠시 대기
            time.sleep(1)
            
            # 에디터 요소 확인
            logger.info("Checking for editor elements...")
            self._log_editor_state()
            
            # 에디터 영역 안정화를 위해 body 클릭
            try:
                self.driver.find_element(By.CSS_SELECTOR, ".se-component-content").click()
                time.sleep(0.3)
            except:
                pass
            
            # Step 1: 제목 입력
            logger.info(f"Inputting title: {title[:30]}...")
            title_success = self._input_title(title)
            if not title_success:
                logger.error("Title input failed")
                return False, "Failed to input title"
            logger.info("Title input SUCCESS")
            
            time.sleep(0.5)
            
            # Step 2: 본문 입력
            logger.info(f"Inputting content ({len(content)} chars)...")
            content_success = self._input_content(content)
            if not content_success:
                logger.error("Content input failed")
                return False, "Failed to input content"
            logger.info("Content input SUCCESS")
            
            time.sleep(1)
            
            logger.info("=== write_content() 완료 ===")
            return True, "Content written"
            
        except Exception as e:
            logger.error(f"write_content error: {e}")
            return False, f"Write error: {str(e)}"

    def _log_editor_state(self):
        """디버깅용: 현재 에디터 상태 로깅"""
        try:
            # 에디터 관련 요소 존재 여부
            selectors_to_check = [
                (".se-section-documentTitle", "제목 섹션"),
                (".se-section-text", "본문 섹션"),
                (".se-placeholder", "placeholder"),
            ]
            
            for selector, name in selectors_to_check:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    logger.info(f"  {name}: {len(elements)} found")
                except:
                    logger.info(f"  {name}: error")
            
        except Exception as e:
            logger.error(f"_log_editor_state error: {e}")

    def _input_title(self, title: str) -> bool:
        """제목 입력"""
        try:
            # 방법 0: 가장 안정적인 execCommand 방식 (먼저 시도)
            try:
                logger.info("  Trying execCommand method (most reliable)...")
                result = self.driver.execute_script("""
                    // 제목 영역 찾기
                    var titleSection = document.querySelector('.se-section-documentTitle');
                    if (!titleSection) {
                        console.log('No title section found');
                        return false;
                    }
                    
                    // 편집 가능한 요소 찾기
                    var editableArea = titleSection.querySelector('p.se-text-paragraph') ||
                                       titleSection.querySelector('[contenteditable="true"]') ||
                                       titleSection.querySelector('.se-title-text');
                    
                    if (!editableArea) {
                        console.log('No editable area found');
                        return false;
                    }
                    
                    // 포커스
                    editableArea.focus();
                    editableArea.click();
                    
                    // placeholder 숨기기
                    var placeholder = titleSection.querySelector('.se-placeholder');
                    if (placeholder) {
                        placeholder.style.display = 'none';
                    }
                    
                    // 기존 텍스트 선택 및 삭제
                    document.execCommand('selectAll', false, null);
                    document.execCommand('delete', false, null);
                    
                    // 텍스트 삽입
                    document.execCommand('insertText', false, arguments[0]);
                    
                    // 이벤트 발생
                    editableArea.dispatchEvent(new Event('input', {bubbles: true}));
                    editableArea.dispatchEvent(new Event('change', {bubbles: true}));
                    
                    return true;
                """, title)
                
                if result:
                    logger.info("  Title: execCommand method SUCCESS")
                    return True
            except Exception as e:
                logger.debug(f"  Title execCommand failed: {e}")
            
            # 방법 1: placeholder 클릭
            try:
                logger.info("  Trying placeholder method...")
                title_placeholder = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((
                        By.CSS_SELECTOR,
                        ".se-section-documentTitle .se-placeholder, .se-title-text .se-placeholder"
                    ))
                )
                title_placeholder.click()
                time.sleep(0.5)
                
                if PYPERCLIP_AVAILABLE:
                    pyperclip.copy(title)
                    ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                else:
                    ActionChains(self.driver).send_keys(title).perform()
                
                logger.info("  Title: placeholder method SUCCESS")
                return True
            except Exception as e:
                logger.debug(f"  Title placeholder failed: {e}")
            
            # 방법 2: p 태그 클릭
            try:
                logger.info("  Trying paragraph method...")
                title_para = self.driver.find_element(
                    By.CSS_SELECTOR,
                    ".se-section-documentTitle p.se-text-paragraph, .se-title-text p.se-text-paragraph"
                )
                title_para.click()
                time.sleep(0.5)
                
                if PYPERCLIP_AVAILABLE:
                    pyperclip.copy(title)
                    ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                else:
                    ActionChains(self.driver).send_keys(title).perform()
                
                logger.info("  Title: paragraph method SUCCESS")
                return True
            except Exception as e:
                logger.debug(f"  Title paragraph failed: {e}")
            
            # 방법 3: JavaScript
            try:
                logger.info("  Trying JavaScript method...")
                result = self.driver.execute_script("""
                    var titleArea = document.querySelector('.se-section-documentTitle p.se-text-paragraph') ||
                                   document.querySelector('.se-title-text p.se-text-paragraph');
                    if (titleArea) {
                        titleArea.click();
                        var placeholder = titleArea.querySelector('span.se-placeholder');
                        if (placeholder) placeholder.style.display = 'none';
                        
                        var textSpan = titleArea.querySelector('span.__se-node');
                        if (!textSpan) {
                            textSpan = document.createElement('span');
                            textSpan.className = '__se-node';
                            titleArea.appendChild(textSpan);
                        }
                        textSpan.textContent = arguments[0];
                        titleArea.dispatchEvent(new Event('input', {bubbles: true}));
                        return true;
                    }
                    return false;
                """, title)
                
                if result:
                    logger.info("  Title: JavaScript method SUCCESS")
                    return True
            except Exception as e:
                logger.debug(f"  Title JavaScript failed: {e}")
            
            # 방법 4: Tab 키
            try:
                logger.info("  Trying Tab method...")
                body = self.driver.find_element(By.TAG_NAME, "body")
                body.click()
                time.sleep(0.3)
                ActionChains(self.driver).send_keys(Keys.TAB).perform()
                time.sleep(0.3)
                
                if PYPERCLIP_AVAILABLE:
                    pyperclip.copy(title)
                    ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                else:
                    ActionChains(self.driver).send_keys(title).perform()
                
                logger.info("  Title: Tab method SUCCESS")
                return True
            except Exception as e:
                logger.debug(f"  Title Tab failed: {e}")
            
            logger.error("All title methods failed")
            return False
            
        except Exception as e:
            logger.error(f"_input_title error: {e}")
            return False

    def _input_content(self, content: str) -> bool:
        """본문 입력"""
        try:
            # 방법 0: 가장 안정적인 execCommand 방식 (먼저 시도)
            try:
                logger.info("  Trying execCommand method (most reliable)...")
                result = self.driver.execute_script("""
                    // 본문 영역 찾기
                    var textSection = document.querySelector('.se-section-text');
                    if (!textSection) {
                        console.log('No text section found');
                        return false;
                    }
                    
                    // 편집 가능한 요소 찾기
                    var editableArea = textSection.querySelector('p.se-text-paragraph') ||
                                       textSection.querySelector('[contenteditable="true"]');
                    
                    if (!editableArea) {
                        console.log('No editable area found');
                        return false;
                    }
                    
                    // 포커스
                    editableArea.focus();
                    editableArea.click();
                    
                    // placeholder 숨기기
                    var placeholder = textSection.querySelector('.se-placeholder');
                    if (placeholder) {
                        placeholder.style.display = 'none';
                    }
                    
                    // 기존 텍스트 선택 및 삭제
                    document.execCommand('selectAll', false, null);
                    document.execCommand('delete', false, null);
                    
                    // 텍스트 삽입
                    document.execCommand('insertText', false, arguments[0]);
                    
                    // 이벤트 발생
                    editableArea.dispatchEvent(new Event('input', {bubbles: true}));
                    editableArea.dispatchEvent(new Event('change', {bubbles: true}));
                    
                    return true;
                """, content)
                
                if result:
                    logger.info("  Content: execCommand method SUCCESS")
                    return True
            except Exception as e:
                logger.debug(f"  Content execCommand failed: {e}")
            
            # 방법 1: placeholder 클릭
            try:
                logger.info("  Trying placeholder method...")
                content_placeholder = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((
                        By.CSS_SELECTOR,
                        ".se-section-text .se-placeholder"
                    ))
                )
                content_placeholder.click()
                time.sleep(0.5)
                
                if PYPERCLIP_AVAILABLE:
                    pyperclip.copy(content)
                    ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                else:
                    ActionChains(self.driver).send_keys(content).perform()
                
                logger.info("  Content: placeholder method SUCCESS")
                return True
            except Exception as e:
                logger.debug(f"  Content placeholder failed: {e}")
            
            # 방법 2: p 태그 클릭
            try:
                logger.info("  Trying paragraph method...")
                content_para = self.driver.find_element(
                    By.CSS_SELECTOR,
                    ".se-section-text p.se-text-paragraph"
                )
                content_para.click()
                time.sleep(0.5)
                
                if PYPERCLIP_AVAILABLE:
                    pyperclip.copy(content)
                    ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                else:
                    ActionChains(self.driver).send_keys(content).perform()
                
                logger.info("  Content: paragraph method SUCCESS")
                return True
            except Exception as e:
                logger.debug(f"  Content paragraph failed: {e}")
            
            # 방법 3: JavaScript
            try:
                logger.info("  Trying JavaScript method...")
                result = self.driver.execute_script("""
                    var contentArea = document.querySelector('.se-section-text p.se-text-paragraph');
                    if (contentArea) {
                        contentArea.click();
                        var placeholder = contentArea.querySelector('span.se-placeholder');
                        if (placeholder) placeholder.style.display = 'none';
                        
                        var textSpan = contentArea.querySelector('span.__se-node');
                        if (!textSpan) {
                            textSpan = document.createElement('span');
                            textSpan.className = '__se-node se-fs15';
                            contentArea.insertBefore(textSpan, contentArea.firstChild);
                        }
                        textSpan.textContent = arguments[0];
                        contentArea.dispatchEvent(new Event('input', {bubbles: true}));
                        return true;
                    }
                    return false;
                """, content)
                
                if result:
                    logger.info("  Content: JavaScript method SUCCESS")
                    return True
            except Exception as e:
                logger.debug(f"  Content JavaScript failed: {e}")
            
            # 방법 4: Tab 키
            try:
                logger.info("  Trying Tab method...")
                ActionChains(self.driver).send_keys(Keys.TAB).perform()
                time.sleep(0.3)
                
                if PYPERCLIP_AVAILABLE:
                    pyperclip.copy(content)
                    ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                else:
                    ActionChains(self.driver).send_keys(content).perform()
                
                logger.info("  Content: Tab method SUCCESS")
                return True
            except Exception as e:
                logger.debug(f"  Content Tab failed: {e}")
            
            logger.error("All content methods failed")
            return False
            
        except Exception as e:
            logger.error(f"_input_content error: {e}")
            return False

    def publish_post(self, category: str = "") -> Tuple[bool, str]:
        """
        Publish the blog post
        
        Args:
            category: 발행할 카테고리명 (선택사항)
        """
        if not self.driver:
            return False, "Browser not started"
        
        target_category = category or self.category
            
        try:
            logger.info("Publishing post...")
            
            # mainFrame 안에서 발행
            self._switch_to_editor_frame()
            
            # Step 1: 발행 버튼 클릭
            publish_btn = self.wait.until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR, 
                    "button.publish_btn__m9KHH, button[data-click-area='tpb.publish']"
                ))
            )
            publish_btn.click()
            time.sleep(1.5)
            
            # Step 2: 카테고리 선택
            if target_category:
                self._select_category(target_category)
            
            # Step 3: 즉시 발행
            try:
                immediate_radio = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "label[for='radio_time1'], input#radio_time1"
                )
                immediate_radio.click()
                time.sleep(0.5)
            except:
                try:
                    self.driver.execute_script("document.getElementById('radio_time1').click();")
                except:
                    pass
            
            # Step 4: 최종 발행
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
        """카테고리 선택"""
        try:
            logger.info(f"Selecting category: {category_name}")
            
            category_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR,
                    "span.text__sraQE[data-testid^='categoryItemText'], .category_btn, [class*='category']"
                ))
            )
            category_btn.click()
            time.sleep(1)
            
            category_items = self.driver.find_elements(
                By.CSS_SELECTOR,
                "span.text__sraQE[data-testid^='categoryItemText']"
            )
            
            for item in category_items:
                if category_name in item.text or item.text in category_name:
                    parent = item.find_element(By.XPATH, "./ancestor::label")
                    parent.click()
                    logger.info(f"Selected category: {item.text}")
                    time.sleep(0.5)
                    return
                        
            logger.warning(f"Category '{category_name}' not found")
                
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
