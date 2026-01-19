"""
Naver Blog Automation Module
네이버 블로그 자동 포스팅 봇
v3.6.1: 발행 버튼이 iframe 안에 있음 - default_content 호출 제거
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
        self._has_iframe = False  # 에디터 타입 (True=구 에디터, False=새 에디터)
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
            
            # ====================================================
            # 🔧 팝업 비활성화 설정 (비밀번호 저장, 알림 등)
            # ====================================================
            prefs = {
                # 비밀번호 저장 팝업 비활성화
                "credentials_enable_service": False,
                "profile.password_manager_enabled": False,
                
                # 알림 팝업 비활성화
                "profile.default_content_setting_values.notifications": 2,
                
                # 자동완성 비활성화
                "autofill.profile_enabled": False,
                "autofill.credit_card_enabled": False,
                
                # 번역 팝업 비활성화
                "translate_whitelists": {},
                "translate": {"enabled": False},
                
                # 기본 브라우저 설정 팝업 비활성화
                "browser.default_browser_setting_enabled": False,
            }
            options.add_experimental_option("prefs", prefs)
            
            # Stability settings
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            
            # 추가 팝업/알림 비활성화
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-popup-blocking")
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
        
        플로우: 블로그 메인 -> 글쓰기 에디터 진입
        
        주의: 네이버 에디터는 2가지 버전이 있음
        1. 새 에디터 (PostWriteForm.naver) - iframe 없음
        2. 구 에디터 (GoBlogWrite.naver + mainFrame) - iframe 있음
        """
        if not self.driver:
            return False, "Browser not started"
            
        try:
            logger.info("Navigating to editor...")
            
            # Step 1: 블로그 메인으로 이동
            self.driver.get("https://blog.naver.com")
            time.sleep(2)
            
            # Step 2: 글쓰기 에디터로 직접 이동
            self.driver.get("https://blog.naver.com/GoBlogWrite.naver")
            time.sleep(3)
            
            # Step 3: "작성 중인 글이 있습니다" 팝업 처리
            self._handle_draft_popup()
            
            # Step 4: 에디터 타입 확인 (iframe 있는지 없는지)
            self._check_editor_type()
            
            # Step 5: 에디터 로드 확인
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR, 
                        ".se-placeholder, .se-text-paragraph"
                    ))
                )
                editor_type = "new (no iframe)" if not self._has_iframe else "old (with iframe)"
                logger.info(f"Editor loaded successfully - {editor_type}")
                return True, "Editor loaded"
            except TimeoutException:
                # URL로 확인
                if "PostWriteForm" in self.driver.current_url or "GoBlogWrite" in self.driver.current_url:
                    return True, "Editor loaded (URL verified)"
                return False, "Editor elements not found"
            
        except TimeoutException:
            return False, "Editor load timeout"
        except Exception as e:
            logger.error(f"Failed to load editor: {e}")
            return False, f"Editor error: {str(e)}"
    
    def _check_editor_type(self):
        """
        에디터 타입 확인 (iframe 유무)
        새 에디터: PostWriteForm.naver - iframe 없음
        구 에디터: mainFrame iframe 있음
        """
        try:
            # mainFrame 존재 여부 확인
            iframe = WebDriverWait(self.driver, 3).until(
                EC.presence_of_element_located((By.ID, "mainFrame"))
            )
            self.driver.switch_to.frame(iframe)
            self._has_iframe = True
            logger.info("Detected old editor with mainFrame iframe")
        except TimeoutException:
            # iframe 없음 = 새 에디터
            self._has_iframe = False
            logger.info("Detected new editor without iframe")

    def _handle_draft_popup(self):
        """
        "작성 중인 글이 있습니다" 팝업 처리
        취소 버튼을 클릭하여 새 글 작성
        
        주의: 새 에디터는 iframe이 없으므로 직접 처리
        """
        # 먼저 메인 페이지에서 팝업 확인 (새 에디터)
        try:
            cancel_btn = WebDriverWait(self.driver, 3).until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR, 
                    "button.se-popup-button.se-popup-button-cancel, button.se-popup-button-cancel"
                ))
            )
            cancel_btn.click()
            logger.info("Closed draft popup - starting fresh")
            time.sleep(1)
            return
        except TimeoutException:
            pass
        
        # iframe 안에 팝업이 있을 수 있음 (구 에디터)
        try:
            self.driver.switch_to.default_content()
            iframe = WebDriverWait(self.driver, 3).until(
                EC.presence_of_element_located((By.ID, "mainFrame"))
            )
            self.driver.switch_to.frame(iframe)
            logger.info("Switched to mainFrame for popup handling")
            
            cancel_btn = WebDriverWait(self.driver, 3).until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR, 
                    "button.se-popup-button.se-popup-button-cancel, button.se-popup-button-cancel"
                ))
            )
            cancel_btn.click()
            logger.info("Closed draft popup in iframe")
            time.sleep(1)
            
            # 다시 default로 복귀
            self.driver.switch_to.default_content()
        except TimeoutException:
            logger.info("No draft popup found")
        except Exception as e:
            logger.warning(f"Draft popup handling: {e}")
        
        # 도움말 패널 닫기
        self._close_help_panel()

    def _close_help_panel(self):
        """
        도움말 패널이 있으면 닫기
        도움말 패널이 발행 버튼을 가리고 있어서 반드시 닫아야 함!
        
        셀렉터: button.se-help-panel-close-button > span.se-blind("닫기")
        """
        # 여러 번 시도 (패널이 늦게 나타날 수 있음)
        for attempt in range(3):
            try:
                # 방법 1: 직접 셀렉터로 찾기
                help_close_btn = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((
                        By.CSS_SELECTOR, 
                        "button.se-help-panel-close-button"
                    ))
                )
                help_close_btn.click()
                logger.info("Closed help panel")
                time.sleep(0.5)
                return  # 성공하면 종료
            except TimeoutException:
                # 도움말 패널이 없으면 정상 진행
                if attempt == 0:
                    logger.info("No help panel found (attempt 1)")
                break
            except Exception as e:
                logger.warning(f"Help panel handling attempt {attempt + 1}: {e}")
                time.sleep(0.5)
        
        # 방법 2: JavaScript로 강제 닫기 시도
        try:
            self.driver.execute_script("""
                var closeBtn = document.querySelector('button.se-help-panel-close-button');
                if (closeBtn) {
                    closeBtn.click();
                    console.log('Help panel closed via JS');
                }
            """)
        except Exception as e:
            logger.debug(f"JS help panel close: {e}")

    def _ensure_in_editor(self):
        """
        에디터 영역에 있는지 확인
        새 에디터: iframe 없이 직접 접근
        구 에디터: mainFrame iframe 내부로 전환
        """
        try:
            # 에디터 요소 확인
            self.driver.find_element(By.CSS_SELECTOR, ".se-placeholder, .se-component")
            return True
        except NoSuchElementException:
            # 새 에디터인 경우 (iframe 없음) - 이미 접근 가능
            if hasattr(self, '_has_iframe') and not self._has_iframe:
                logger.info("New editor - no iframe needed")
                return True
            
            # 구 에디터인 경우 - iframe으로 전환 시도
            try:
                self.driver.switch_to.default_content()
                iframe = self.driver.find_element(By.ID, "mainFrame")
                self.driver.switch_to.frame(iframe)
                logger.info("Switched to mainFrame iframe")
                return True
            except Exception as e:
                logger.warning(f"Could not switch to iframe: {e}")
                return True  # 새 에디터일 수 있으므로 진행

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
            
            # Step 0: 에디터 영역 확인
            self._ensure_in_editor()
            
            # Step 1: 제목 입력
            # 제목 placeholder 클릭 (.se-fs32 = 32px 폰트 = 제목)
            try:
                title_area = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((
                        By.CSS_SELECTOR, 
                        "span.se-placeholder.se-fs32"
                    ))
                )
                title_area.click()
                logger.info("Clicked title placeholder")
            except TimeoutException:
                # 대안: 제목 텍스트로 찾기
                try:
                    title_area = self.driver.find_element(
                        By.XPATH, 
                        "//span[contains(@class, 'se-placeholder') and text()='제목']"
                    )
                    title_area.click()
                    logger.info("Clicked title placeholder (by text)")
                except:
                    # 대안 2: 제목 컴포넌트 영역 클릭
                    title_component = self.driver.find_element(
                        By.CSS_SELECTOR,
                        ".se-documentTitle .se-text-paragraph"
                    )
                    title_component.click()
                    logger.info("Clicked title component area")
            
            time.sleep(0.5)
            
            # 제목 입력
            if not self.clipboard_input(title):
                ActionChains(self.driver).send_keys(title).perform()
            
            logger.info(f"Title entered: {title[:30]}...")
            time.sleep(1)
            
            # Step 2: 본문 입력
            # 본문 placeholder 클릭 (.se-fs15 = 15px 폰트 = 본문)
            try:
                content_area = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((
                        By.CSS_SELECTOR,
                        "span.se-placeholder.se-fs15"
                    ))
                )
                content_area.click()
                logger.info("Clicked content placeholder")
            except TimeoutException:
                # 대안: 본문 텍스트로 찾기
                try:
                    content_area = self.driver.find_element(
                        By.XPATH, 
                        "//span[contains(@class, 'se-placeholder') and contains(text(), '글감과')]"
                    )
                    content_area.click()
                    logger.info("Clicked content placeholder (by text)")
                except:
                    # 대안 2: 본문 영역 직접 클릭
                    content_component = self.driver.find_element(
                        By.CSS_SELECTOR,
                        ".se-component.se-text .se-text-paragraph"
                    )
                    content_component.click()
                    logger.info("Clicked content component area")
            
            time.sleep(0.5)
            
            # 본문 입력
            if not self.clipboard_input(content):
                ActionChains(self.driver).send_keys(content).perform()
            
            logger.info(f"Content entered: {len(content)} characters")
            time.sleep(2)
            
            logger.info("Content written successfully")
            return True, "Content written"
            
        except TimeoutException:
            return False, "Content area not found - editor may not be loaded"
        except NoSuchElementException as e:
            logger.error(f"Editor elements not found: {e}")
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
        1. 메인 프레임으로 전환 (발행 버튼은 iframe 밖에 있음)
        2. 발행 버튼 클릭 -> 발행 팝업 열림
        3. 발행 팝업 내에서:
           - 카테고리 선택 (있으면)
           - 공개 설정 확인
           - 즉시 발행 선택
        4. 최종 발행 버튼 클릭
        """
        if not self.driver:
            return False, "Browser not started"
        
        # 카테고리 설정 (인자로 전달되거나, 미리 설정된 값 사용)
        target_category = category or self.category
            
        try:
            logger.info("Publishing post...")
            
            # Step 0: 도움말 패널 닫기 (발행 버튼을 가릴 수 있음)
            self._close_help_panel()
            
            # 참고: 발행 버튼은 현재 frame 안에 있음 (default_content로 나가면 안 됨!)
            logger.info("Publish button is inside current frame - staying here")
            
            time.sleep(0.5)
            
            # Step 2: 상단 발행 버튼 클릭 -> 발행 팝업 열기
            try:
                publish_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((
                        By.CSS_SELECTOR, 
                        "button.publish_btn__m9KHH, button[data-click-area='tpb.publish'], button.se-publish-btn"
                    ))
                )
                publish_btn.click()
                logger.info("Clicked publish button - popup should open")
            except TimeoutException:
                # JavaScript로 발행 버튼 찾아서 클릭
                self.driver.execute_script("""
                    var btn = document.querySelector('button[data-click-area="tpb.publish"]') ||
                              document.querySelector('button.publish_btn__m9KHH') ||
                              document.querySelector('.publish_btn__m9KHH');
                    if (btn) btn.click();
                """)
                logger.info("Clicked publish button via JS")
            
            time.sleep(2)  # 팝업이 열리는 시간 대기
            
            # Step 3: 발행 팝업 내에서 설정
            self._handle_publish_popup(target_category)
            
            time.sleep(1)
            
            # Step 4: 최종 발행 버튼 클릭
            success = self._click_final_publish_button()
            if success:
                time.sleep(3)
                logger.info("Post published successfully")
                return True, "Published"
            else:
                return False, "Final publish button not found"
            
        except TimeoutException:
            return False, "Publish button not found"
        except Exception as e:
            logger.error(f"Publish failed: {e}")
            return False, f"Publish error: {str(e)}"

    def _handle_publish_popup(self, target_category: str = ""):
        """
        발행 팝업 내에서 카테고리 선택만 처리
        
        네이버 블로그 발행 팝업 구조:
        - 팝업 컨테이너: layer_publish__vA9PX
        - 카테고리 버튼: selectbox_button__jb1Dt
        - 공개설정: #open_public (기본값 = 전체공개) → 건드리지 않음
        - 발행시간: #radio_time1 (기본값 = 현재/즉시) → 건드리지 않음
        - 최종 발행: confirm_btn__WEaBq
        """
        try:
            # 팝업이 열렸는지 확인
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    ".layer_publish__vA9PX, .layer_content_set_publish__KDvaV, [class*='layer_publish']"
                ))
            )
            logger.info("Publish popup detected")
        except TimeoutException:
            logger.warning("Publish popup not detected, proceeding anyway")
        
        # 카테고리 선택 (설정된 카테고리가 있으면)
        # 공개설정(#open_public)과 발행시간(#radio_time1)은 기본값이 원하는 값이므로 건드리지 않음
        if target_category:
            self._select_category(target_category)

    def _click_final_publish_button(self) -> bool:
        """
        최종 발행 버튼 클릭
        
        Returns:
            True if clicked successfully
        """
        final_btn_selectors = [
            "button.confirm_btn__WEaBq",
            "button[data-testid='seOnePublishBtn']",
            "button[data-click-area='ppp.confirm']",
            ".btn_publish_confirm",
            "button.btn_confirm",
            "[class*='confirm'][class*='btn']"
        ]
        
        for selector in final_btn_selectors:
            try:
                final_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                final_btn.click()
                logger.info(f"Clicked final publish button via {selector}")
                return True
            except (TimeoutException, NoSuchElementException):
                continue
        
        # JavaScript로 시도
        try:
            self.driver.execute_script("""
                // 발행/확인 버튼 찾기
                var btn = document.querySelector('button.confirm_btn__WEaBq') ||
                          document.querySelector('button[data-testid="seOnePublishBtn"]') ||
                          document.querySelector('[data-click-area="ppp.confirm"]');
                if (btn) { btn.click(); return true; }
                
                // 텍스트로 찾기
                var buttons = document.querySelectorAll('button');
                for (var b of buttons) {
                    if (b.innerText.trim() === '발행' || b.innerText.includes('발행하기')) {
                        b.click(); return true;
                    }
                }
                return false;
            """)
            logger.info("Clicked final publish button via JS")
            return True
        except Exception as e:
            logger.error(f"Failed to click final publish button: {e}")
            return False

    def _select_category(self, category_name: str):
        """
        카테고리 선택
        
        Args:
            category_name: 선택할 카테고리명
            
        네이버 블로그 카테고리 구조 (2024 업데이트):
        - 카테고리 버튼: selectbox_button__jb1Dt (현재 선택된 카테고리 표시)
        - 드롭다운 열리면 카테고리 목록 표시
        """
        try:
            logger.info(f"Selecting category: {category_name}")
            
            # Step 1: 카테고리 드롭다운 버튼 클릭 (업데이트된 셀렉터)
            category_btn_selectors = [
                "button.selectbox_button__jb1Dt",
                ".option_category___kpJc button",
                "[class*='selectbox_button']",
                "[class*='category'] button"
            ]
            
            category_btn = None
            for selector in category_btn_selectors:
                try:
                    category_btn = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    break
                except TimeoutException:
                    continue
            
            if category_btn:
                category_btn.click()
                logger.info("Opened category dropdown")
                time.sleep(1)
            else:
                logger.warning("Category dropdown button not found")
                return
            
            # Step 2: 카테고리 목록에서 해당 카테고리 찾아서 클릭
            try:
                # 드롭다운 목록에서 카테고리 항목 찾기
                category_items = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "[class*='selectbox'] li, [class*='dropdown'] li, [class*='option'] li, ul li"
                )
                
                for item in category_items:
                    item_text = item.text.strip()
                    if not item_text:
                        continue
                    # 카테고리명 비교
                    if category_name == item_text or category_name in item_text:
                        item.click()
                        logger.info(f"Selected category: {item_text}")
                        time.sleep(0.5)
                        return
                
                # 부분 일치 시도
                for item in category_items:
                    item_text = item.text.strip()
                    if item_text and category_name.lower() in item_text.lower():
                        item.click()
                        logger.info(f"Selected category (partial match): {item_text}")
                        time.sleep(0.5)
                        return
                
                # JavaScript로 시도
                self.driver.execute_script(f"""
                    var items = document.querySelectorAll('li, [class*="option"]');
                    for (var item of items) {{
                        if (item.innerText && item.innerText.includes('{category_name}')) {{
                            item.click();
                            console.log('Selected category via JS: ' + item.innerText);
                            return;
                        }}
                    }}
                """)
                        
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
