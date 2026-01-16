"""
Naver Blog Automation Module
네이버 블로그 자동 포스팅 봇
v3.5.4: 글쓰기 에디터 제목/본문 입력 개선, 도움말 패널 처리 강화
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
            
            # Step 4: 도움말 패널 닫기 (여러 번 시도)
            self._close_help_panel()
            time.sleep(1)
            self._close_help_panel()  # 한번 더 시도
            
            # Step 5: 에디터 로드 확인 (실제 네이버 에디터 구조에 맞게)
            try:
                # 에디터의 제목 영역 확인 - 실제 클래스: se-section-documentTitle, se-title-text
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR, 
                        ".se-section-documentTitle, .se-title-text, .se-text-paragraph"
                    ))
                )
                logger.info("Editor loaded successfully")
                return True, "Editor loaded"
            except TimeoutException:
                # URL 확인 - 다양한 패턴 체크
                current_url = self.driver.current_url
                if any(pattern in current_url for pattern in ["Redirect=Write", "PostWriteForm", "GoBlogWrite"]):
                    logger.info(f"Editor loaded (URL verified): {current_url}")
                    return True, "Editor loaded (URL verified)"
                
                # 추가: 에디터 iframe이나 다른 요소 확인
                try:
                    # placeholder "제목" 텍스트로 확인
                    self.driver.find_element(
                        By.XPATH,
                        "//span[contains(@class, 'se-placeholder') and text()='제목']"
                    )
                    logger.info("Editor loaded (placeholder found)")
                    return True, "Editor loaded (placeholder found)"
                except:
                    pass
                
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

    def _close_help_panel(self):
        """
        도움말 패널이 있으면 닫기
        여러 방법으로 시도
        """
        try:
            # 방법 1: CSS 셀렉터로 닫기 버튼 찾기
            help_close_btn = WebDriverWait(self.driver, 3).until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR, 
                    "button.se-help-panel-close-button"
                ))
            )
            help_close_btn.click()
            logger.info("Closed help panel (CSS selector)")
            time.sleep(0.5)
            return
        except TimeoutException:
            pass
        except Exception as e:
            logger.debug(f"Help panel close attempt 1: {e}")
        
        try:
            # 방법 2: 도움말 컨테이너 내 닫기 버튼 찾기
            help_container = self.driver.find_element(
                By.CSS_SELECTOR, 
                "div.se-help-container"
            )
            if help_container:
                close_btn = help_container.find_element(
                    By.CSS_SELECTOR,
                    "button.se-help-panel-close-button"
                )
                close_btn.click()
                logger.info("Closed help panel (container method)")
                time.sleep(0.5)
                return
        except NoSuchElementException:
            pass
        except Exception as e:
            logger.debug(f"Help panel close attempt 2: {e}")
        
        try:
            # 방법 3: JavaScript로 닫기 버튼 클릭
            self.driver.execute_script("""
                var closeBtn = document.querySelector('button.se-help-panel-close-button');
                if (closeBtn) {
                    closeBtn.click();
                    return true;
                }
                return false;
            """)
            logger.info("Closed help panel (JavaScript)")
            time.sleep(0.5)
            return
        except Exception as e:
            logger.debug(f"Help panel close attempt 3: {e}")
        
        try:
            # 방법 4: 도움말 패널 자체를 숨기기
            self.driver.execute_script("""
                var helpContainer = document.querySelector('div.se-help-container');
                if (helpContainer) {
                    helpContainer.style.display = 'none';
                    return true;
                }
                return false;
            """)
            logger.info("Hidden help panel (JavaScript hide)")
            time.sleep(0.5)
        except Exception as e:
            logger.debug(f"Help panel close attempt 4: {e}")
        
        # 도움말 패널이 없으면 정상 진행
        logger.info("No help panel found or already closed")

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
            
            # 먼저 도움말 패널 닫기 (혹시 남아있으면)
            self._close_help_panel()
            time.sleep(1)
            
            # Step 1: 제목 입력
            title_success = self._input_title(title)
            if not title_success:
                return False, "Failed to input title"
            
            time.sleep(1)
            
            # Step 2: 본문 입력
            content_success = self._input_content(content)
            if not content_success:
                return False, "Failed to input content"
            
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

    def _input_title(self, title: str) -> bool:
        """
        제목 입력
        
        네이버 에디터 제목 영역 실제 구조:
        <div class="se-section se-section-documentTitle ...">
            <div class="se-module se-module-text ... se-title-text ...">
                <p class="se-text-paragraph ...">
                    <span class="se-placeholder __se_placeholder se-fs32">제목</span>
                </p>
            </div>
        </div>
        """
        try:
            logger.info("Inputting title...")
            
            # 방법 1: 제목 placeholder 클릭 (실제 구조: se-section-documentTitle 내의 se-placeholder)
            try:
                title_placeholder = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((
                        By.CSS_SELECTOR,
                        ".se-section-documentTitle .se-placeholder, .se-title-text .se-placeholder"
                    ))
                )
                title_placeholder.click()
                time.sleep(0.5)
                
                # 제목 입력
                if PYPERCLIP_AVAILABLE:
                    pyperclip.copy(title)
                    ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                else:
                    ActionChains(self.driver).send_keys(title).perform()
                
                logger.info("Title input success (placeholder method)")
                return True
            except Exception as e:
                logger.debug(f"Title placeholder method failed: {e}")
            
            # 방법 2: 제목 영역의 p 태그 클릭 (실제 구조)
            try:
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
                
                logger.info("Title input success (paragraph method)")
                return True
            except Exception as e:
                logger.debug(f"Title paragraph method failed: {e}")
            
            # 방법 3: JavaScript로 직접 입력 (실제 구조에 맞게)
            try:
                result = self.driver.execute_script("""
                    // 제목 영역 찾기 (실제 구조: se-section-documentTitle 또는 se-title-text)
                    var titleArea = document.querySelector('.se-section-documentTitle p.se-text-paragraph') ||
                                   document.querySelector('.se-title-text p.se-text-paragraph');
                    if (titleArea) {
                        // 클릭하여 포커스
                        titleArea.click();
                        
                        // placeholder 제거
                        var placeholder = titleArea.querySelector('span.se-placeholder');
                        if (placeholder) {
                            placeholder.style.display = 'none';
                        }
                        
                        // 기존 span 찾거나 새로 생성
                        var textSpan = titleArea.querySelector('span.__se-node');
                        if (!textSpan) {
                            textSpan = document.createElement('span');
                            textSpan.className = '__se-node';
                            titleArea.appendChild(textSpan);
                        }
                        textSpan.textContent = arguments[0];
                        
                        // 입력 이벤트 발생
                        titleArea.dispatchEvent(new Event('input', {bubbles: true}));
                        titleArea.dispatchEvent(new Event('change', {bubbles: true}));
                        titleArea.dispatchEvent(new Event('keyup', {bubbles: true}));
                        return true;
                    }
                    return false;
                """, title)
                
                if result:
                    logger.info("Title input success (JavaScript method)")
                    return True
            except Exception as e:
                logger.debug(f"Title JavaScript method failed: {e}")
            
            # 방법 4: Tab 키로 제목 영역 이동 후 입력
            try:
                # 페이지 클릭 후 Tab으로 제목 영역 이동
                body = self.driver.find_element(By.TAG_NAME, "body")
                body.click()
                time.sleep(0.3)
                
                # Tab 키로 제목으로 이동
                ActionChains(self.driver).send_keys(Keys.TAB).perform()
                time.sleep(0.3)
                
                if PYPERCLIP_AVAILABLE:
                    pyperclip.copy(title)
                    ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                else:
                    ActionChains(self.driver).send_keys(title).perform()
                
                logger.info("Title input success (Tab method)")
                return True
            except Exception as e:
                logger.debug(f"Title Tab method failed: {e}")
            
            logger.error("All title input methods failed")
            return False
            
        except Exception as e:
            logger.error(f"Title input error: {e}")
            return False

    def _input_content(self, content: str) -> bool:
        """
        본문 입력
        
        네이버 에디터 본문 영역 실제 구조:
        <div class="se-section se-section-text ...">  <!-- 본문은 se-section-text -->
            <div class="se-module se-module-text __se-unit ...">
                <p class="se-text-paragraph ...">
                    <span class="__se-node se-fs15">...</span>
                    <span class="se-placeholder __se_placeholder se-fs15">글감과 함께...</span>
                </p>
            </div>
        </div>
        """
        try:
            logger.info("Inputting content...")
            
            # 방법 1: 본문 placeholder 클릭 (실제 구조: se-section-text 내의 se-placeholder)
            try:
                content_placeholder = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((
                        By.CSS_SELECTOR,
                        ".se-section-text .se-placeholder, .se-section-text span.__se_placeholder"
                    ))
                )
                content_placeholder.click()
                time.sleep(0.5)
                
                # 본문 입력
                if PYPERCLIP_AVAILABLE:
                    pyperclip.copy(content)
                    ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                else:
                    ActionChains(self.driver).send_keys(content).perform()
                
                logger.info("Content input success (placeholder method)")
                return True
            except Exception as e:
                logger.debug(f"Content placeholder method failed: {e}")
            
            # 방법 2: 본문 영역 직접 찾기 (se-section-text 내의 p 태그)
            try:
                # se-section-text 내의 se-text-paragraph 찾기 (제목 영역 se-section-documentTitle 제외)
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
                
                logger.info("Content input success (paragraph method)")
                return True
            except Exception as e:
                logger.debug(f"Content paragraph method failed: {e}")
            
            # 방법 3: JavaScript로 직접 입력 (실제 구조: se-section-text)
            try:
                result = self.driver.execute_script("""
                    // 본문 영역 찾기 (se-section-text 내의 p 태그)
                    var contentArea = document.querySelector('.se-section-text p.se-text-paragraph');
                    
                    if (contentArea) {
                        // 클릭하여 포커스
                        contentArea.click();
                        
                        // placeholder 숨기기
                        var placeholder = contentArea.querySelector('span.se-placeholder, span.__se_placeholder');
                        if (placeholder) {
                            placeholder.style.display = 'none';
                        }
                        
                        // 기존 __se-node span 찾거나 새로 생성
                        var textSpan = contentArea.querySelector('span.__se-node');
                        if (!textSpan) {
                            textSpan = document.createElement('span');
                            textSpan.className = '__se-node se-fs15';
                            contentArea.insertBefore(textSpan, contentArea.firstChild);
                        }
                        textSpan.textContent = arguments[0];
                        
                        // 이벤트 발생
                        contentArea.dispatchEvent(new Event('input', {bubbles: true}));
                        contentArea.dispatchEvent(new Event('change', {bubbles: true}));
                        contentArea.dispatchEvent(new Event('keyup', {bubbles: true}));
                        return true;
                    }
                    return false;
                """, content)
                
                if result:
                    logger.info("Content input success (JavaScript method)")
                    return True
            except Exception as e:
                logger.debug(f"Content JavaScript method failed: {e}")
            
            # 방법 4: Tab 키로 본문 영역 이동 후 입력
            try:
                # 제목 입력 후 Tab으로 본문으로 이동
                ActionChains(self.driver).send_keys(Keys.TAB).perform()
                time.sleep(0.3)
                
                if PYPERCLIP_AVAILABLE:
                    pyperclip.copy(content)
                    ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                else:
                    ActionChains(self.driver).send_keys(content).perform()
                
                logger.info("Content input success (Tab method)")
                return True
            except Exception as e:
                logger.debug(f"Content Tab method failed: {e}")
            
            # 방법 5: 에디터 본문 영역 클릭 후 입력
            try:
                # 에디터 메인 영역 클릭
                editor_main = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "div.se-content, div[class*='editor-content'], main.se-viewer"
                )
                editor_main.click()
                time.sleep(0.5)
                
                if PYPERCLIP_AVAILABLE:
                    pyperclip.copy(content)
                    ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                else:
                    ActionChains(self.driver).send_keys(content).perform()
                
                logger.info("Content input success (editor area method)")
                return True
            except Exception as e:
                logger.debug(f"Content editor area method failed: {e}")
            
            logger.error("All content input methods failed")
            return False
            
        except Exception as e:
            logger.error(f"Content input error: {e}")
            return False

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
