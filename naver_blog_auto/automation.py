"""
Naver Blog Automation Module
네이버 블로그 자동 포스팅 - SmartEditor One 대응

최종 수정: 2026-01-18
- 최신 네이버 에디터 DOM 구조 대응
- 다중 셀렉터 폴백 전략 적용
- 에러 복구 로직 강화
"""
import time
import logging
import platform
from typing import Tuple, Optional

try:
    import pyperclip
except ImportError:
    pyperclip = None

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    ElementNotInteractableException,
    StaleElementReferenceException
)

logger = logging.getLogger(__name__)


class NaverBlogBot:
    """
    네이버 블로그 자동 포스팅 봇
    SmartEditor One 에디터 대응
    """
    
    # 네이버 URL 상수
    NAVER_LOGIN_URL = "https://nid.naver.com/nidlogin.login"
    NAVER_MAIN_URL = "https://www.naver.com"
    NAVER_BLOG_SECTION_URL = "https://section.blog.naver.com/"
    NAVER_BLOG_WRITE_URL = "https://blog.naver.com/GoBlogWrite.naver"
    
    # SmartEditor One 셀렉터 (다중 폴백)
    SELECTORS = {
        # 제목 입력 영역
        'title': [
            "//span[contains(@class, 'se-placeholder') and text()='제목']",
            "//span[contains(@class, 'se-placeholder') and contains(text(), '제목')]",
            "//p[contains(@class, 'se-title-text')]",
            ".se-title-text",
            "[data-placeholder='제목']",
        ],
        # 본문 입력 영역  
        'content': [
            "//span[contains(@class, 'se-placeholder') and contains(text(), '글감과 함께')]",
            "//span[contains(@class, 'se-placeholder') and contains(text(), '본문')]",
            "//p[contains(@class, 'se-text-paragraph')]",
            ".se-text-paragraph",
            ".se-component-content",
        ],
        # 발행 버튼 (1차 - 상단)
        'publish_btn_1': [
            "button[data-click-area='tpb.publish']",
            ".publish_btn__Y5lEP",
            "//button[contains(text(), '발행')]",
            "//button[contains(@class, 'publish')]",
        ],
        # 발행 버튼 (2차 - 최종 확인)
        'publish_btn_final': [
            "button[data-testid='seOnePublishBtn']",
            ".confirm_btn__Dv2lV",
            "//button[contains(text(), '발행')]",
        ],
        # 팝업 닫기 버튼
        'popup_cancel': [
            "button.se-popup-button-cancel",
            ".se-popup-button-cancel",
            "//button[contains(@class, 'cancel')]",
        ],
        # 도움말 패널 닫기
        'help_close': [
            "button.se-help-panel-close-button",
            ".se-help-panel-close-button",
        ],
    }
    
    def __init__(self, headless: bool = False, timeout: int = 15):
        """
        초기화
        
        Args:
            headless: 헤드리스 모드 여부
            timeout: 기본 대기 시간(초)
        """
        self.driver = None
        self.wait = None
        self.headless = headless
        self.timeout = timeout
        self._is_mac = platform.system() == 'Darwin'

    def start_browser(self):
        """브라우저 실행 (자동화 탐지 우회 설정 포함)"""
        options = webdriver.ChromeOptions()
        
        # 자동화 탐지 우회 설정
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("detach", True)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # 헤드리스 모드
        if self.headless:
            options.add_argument("--headless=new")
        
        # 안정성 옵션
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        # User-Agent 설정 (최신 Chrome 버전으로)
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        try:
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()), 
                options=options
            )
            self.wait = WebDriverWait(self.driver, self.timeout)
            self.driver.set_window_size(1920, 1080)
            
            # navigator.webdriver 속성 제거
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            
            logger.info("브라우저 실행 완료")
            
        except Exception as e:
            logger.error(f"브라우저 실행 실패: {e}")
            raise

    def clipboard_input(self, user_input: str) -> bool:
        """
        클립보드를 이용한 입력 (로그인 캡챠 우회용)
        
        Args:
            user_input: 입력할 텍스트
            
        Returns:
            성공 여부
        """
        if pyperclip is None:
            logger.warning("pyperclip이 설치되지 않음. 직접 입력 시도.")
            return False
        
        try:
            pyperclip.copy(user_input)
            
            # 맥/윈도우 구분하여 붙여넣기
            if self._is_mac:
                ActionChains(self.driver).key_down(Keys.COMMAND).send_keys('v').key_up(Keys.COMMAND).perform()
            else:
                ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
            
            time.sleep(0.5)
            return True
            
        except Exception as e:
            logger.error(f"클립보드 입력 실패: {e}")
            return False
    
    def _find_element_with_fallback(self, selectors: list, timeout: int = None) -> Optional[any]:
        """
        다중 셀렉터로 요소 찾기 (폴백 전략)
        
        Args:
            selectors: 셀렉터 목록 (XPath 또는 CSS)
            timeout: 대기 시간
            
        Returns:
            찾은 요소 또는 None
        """
        timeout = timeout or self.timeout
        
        for selector in selectors:
            try:
                # XPath인지 CSS 셀렉터인지 판별
                if selector.startswith("//") or selector.startswith("("):
                    by = By.XPATH
                else:
                    by = By.CSS_SELECTOR
                
                element = WebDriverWait(self.driver, timeout / len(selectors)).until(
                    EC.presence_of_element_located((by, selector))
                )
                logger.debug(f"요소 발견: {selector}")
                return element
                
            except (TimeoutException, NoSuchElementException):
                continue
            except Exception as e:
                logger.debug(f"셀렉터 {selector} 실패: {e}")
                continue
        
        return None
    
    def _click_element_safely(self, element) -> bool:
        """
        요소 안전하게 클릭 (여러 방법 시도)
        """
        try:
            # 방법 1: 일반 클릭
            element.click()
            return True
        except ElementNotInteractableException:
            pass
        except Exception:
            pass
        
        try:
            # 방법 2: JavaScript 클릭
            self.driver.execute_script("arguments[0].click();", element)
            return True
        except Exception:
            pass
        
        try:
            # 방법 3: ActionChains 클릭
            ActionChains(self.driver).move_to_element(element).click().perform()
            return True
        except Exception as e:
            logger.error(f"클릭 실패: {e}")
            return False

    def login(self, user_id: str, user_pw: str) -> Tuple[bool, str]:
        """
        네이버 로그인
        
        Args:
            user_id: 네이버 아이디
            user_pw: 네이버 비밀번호
            
        Returns:
            (성공 여부, 메시지)
        """
        if not self.driver:
            return False, "브라우저가 실행되지 않았습니다."

        try:
            # 1. 로그인 페이지 이동
            self.driver.get(self.NAVER_LOGIN_URL)
            time.sleep(2)

            # 2. 아이디 입력
            id_input = self.wait.until(EC.element_to_be_clickable((By.ID, "id")))
            id_input.click()
            time.sleep(0.3)
            
            # 클립보드 입력 시도, 실패 시 직접 입력
            if not self.clipboard_input(user_id):
                id_input.clear()
                id_input.send_keys(user_id)
            
            time.sleep(0.5)

            # 3. 비밀번호 입력
            pw_input = self.driver.find_element(By.ID, "pw")
            pw_input.click()
            time.sleep(0.3)
            
            if not self.clipboard_input(user_pw):
                pw_input.clear()
                pw_input.send_keys(user_pw)
            
            time.sleep(0.5)

            # 4. 로그인 버튼 클릭
            login_btn = self.driver.find_element(By.ID, "log.login")
            login_btn.click()
            
            time.sleep(3)
            
            # 5. 로그인 결과 확인
            current_url = self.driver.current_url
            
            # 캡챠/2차 인증 체크
            if "captcha" in current_url.lower():
                return False, "캡챠 인증이 필요합니다. 수동으로 완료해주세요."
            
            if "device" in current_url.lower() or "otp" in current_url.lower():
                return False, "2차 인증이 필요합니다. 수동으로 완료해주세요."
            
            # 로그인 성공 확인 (메인 페이지 또는 마이페이지로 이동)
            if "nid.naver.com" not in current_url or "login" not in current_url.lower():
                logger.info("네이버 로그인 성공")
                return True, "로그인 성공"
            
            return False, "로그인 실패 - 아이디/비밀번호를 확인해주세요."

        except TimeoutException:
            return False, "로그인 페이지 로딩 시간 초과"
        except Exception as e:
            logger.error(f"로그인 오류: {e}")
            return False, f"로그인 중 오류 발생: {str(e)}"

    def go_to_editor(self) -> Tuple[bool, str]:
        """
        블로그 글쓰기 에디터로 이동
        메인 -> 블로그 -> 글쓰기 순서로 이동
        
        Returns:
            (성공 여부, 메시지)
        """
        try:
            # 1. 네이버 메인 이동
            self.driver.get(self.NAVER_MAIN_URL)
            time.sleep(2)

            # 2. 블로그 서비스로 이동 (여러 방법 시도)
            blog_entered = False
            
            # 방법 1: 메인 페이지 블로그 링크
            try:
                blog_link = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, "a.link_service[href*='blog.naver.com'], a[href*='blog.naver.com']")
                    )
                )
                blog_link.click()
                blog_entered = True
            except:
                pass
            
            # 방법 2: 직접 URL 이동
            if not blog_entered:
                self.driver.get(self.NAVER_BLOG_SECTION_URL)
            
            time.sleep(2)
            
            # 새 탭이 열렸을 수 있으므로 처리
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[-1])

            # 3. 글쓰기 버튼 클릭 (여러 셀렉터 시도)
            write_btn = None
            write_selectors = [
                "a[href*='GoBlogWrite.naver']",
                ".btn_write",
                "//a[contains(text(), '글쓰기')]",
                "//button[contains(text(), '글쓰기')]",
            ]
            
            for selector in write_selectors:
                try:
                    if selector.startswith("//"):
                        write_btn = WebDriverWait(self.driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                    else:
                        write_btn = WebDriverWait(self.driver, 3).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                    break
                except:
                    continue
            
            if write_btn:
                self._click_element_safely(write_btn)
            else:
                # 직접 글쓰기 URL로 이동
                self.driver.get(self.NAVER_BLOG_WRITE_URL)
            
            time.sleep(3)

            # 4. 새 창으로 열렸으면 전환
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[-1])
            
            # 5. iframe 진입 시도 (있을 경우)
            self._switch_to_editor_frame()

            # 6. 팝업/도움말 닫기
            self._close_popups()

            logger.info("에디터 진입 성공")
            return True, "에디터 진입 성공"

        except Exception as e:
            logger.error(f"에디터 진입 실패: {e}")
            return False, f"에디터 진입 실패: {str(e)}"
    
    def _switch_to_editor_frame(self):
        """에디터 iframe으로 전환 (존재하는 경우)"""
        frame_names = ["mainFrame", "se2_iframe", "editor_frame"]
        
        for frame_name in frame_names:
            try:
                self.driver.switch_to.frame(frame_name)
                logger.debug(f"iframe 전환 성공: {frame_name}")
                return True
            except:
                continue
        
        # iframe이 없으면 기본 컨텍스트 유지
        try:
            self.driver.switch_to.default_content()
        except:
            pass
        
        return False
    
    def _close_popups(self):
        """에디터 진입 시 나타나는 팝업들 닫기"""
        # 1. 작성 중인 글 복구 팝업 닫기
        popup_cancel = self._find_element_with_fallback(
            self.SELECTORS['popup_cancel'], timeout=3
        )
        if popup_cancel:
            self._click_element_safely(popup_cancel)
            time.sleep(0.5)
        
        # 2. 도움말 패널 닫기
        help_close = self._find_element_with_fallback(
            self.SELECTORS['help_close'], timeout=2
        )
        if help_close:
            self._click_element_safely(help_close)
            time.sleep(0.5)

    def write_content(self, title_text: str, content_text: str) -> Tuple[bool, str]:
        """
        제목 및 본문 작성
        
        Args:
            title_text: 블로그 제목
            content_text: 블로그 본문 내용
            
        Returns:
            (성공 여부, 메시지)
        """
        try:
            # 1. 제목 입력
            logger.info("제목 입력 시도 중...")
            title_success = self._input_title(title_text)
            
            if not title_success:
                return False, "제목 입력 실패 - 제목 영역을 찾을 수 없습니다."
            
            time.sleep(1)

            # 2. 본문 입력
            logger.info("본문 입력 시도 중...")
            content_success = self._input_content(content_text)
            
            if not content_success:
                return False, "본문 입력 실패 - 본문 영역을 찾을 수 없습니다."
            
            time.sleep(1)
            
            logger.info("글 작성 완료")
            return True, "본문 작성 완료"

        except Exception as e:
            # 디버깅용 스크린샷
            try:
                self.driver.save_screenshot("write_error.png")
                logger.info("에러 스크린샷 저장: write_error.png")
            except:
                pass
            
            logger.error(f"글 작성 실패: {e}")
            return False, f"글 작성 실패: {str(e)}"
    
    def _input_title(self, title_text: str) -> bool:
        """
        제목 영역에 텍스트 입력
        여러 셀렉터와 입력 방식을 시도
        """
        # 방법 1: placeholder 클릭 후 입력
        title_element = self._find_element_with_fallback(self.SELECTORS['title'])
        
        if title_element:
            try:
                self._click_element_safely(title_element)
                time.sleep(0.3)
                
                # 클립보드 입력 시도
                if self.clipboard_input(title_text):
                    return True
                
                # 직접 입력 시도
                ActionChains(self.driver).send_keys(title_text).perform()
                return True
                
            except Exception as e:
                logger.debug(f"제목 입력 방법 1 실패: {e}")
        
        # 방법 2: 부모 요소(se-title-text) 직접 접근
        try:
            title_area = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".se-title-text, .se-text-paragraph-title"))
            )
            self._click_element_safely(title_area)
            time.sleep(0.3)
            
            if self.clipboard_input(title_text):
                return True
            
            ActionChains(self.driver).send_keys(title_text).perform()
            return True
            
        except Exception as e:
            logger.debug(f"제목 입력 방법 2 실패: {e}")
        
        # 방법 3: JavaScript로 직접 값 설정
        try:
            self.driver.execute_script("""
                var titleEl = document.querySelector('.se-title-text, [class*="title"] p');
                if (titleEl) {
                    titleEl.textContent = arguments[0];
                    titleEl.dispatchEvent(new Event('input', { bubbles: true }));
                    return true;
                }
                return false;
            """, title_text)
            return True
        except Exception as e:
            logger.debug(f"제목 입력 방법 3 실패: {e}")
        
        return False
    
    def _input_content(self, content_text: str) -> bool:
        """
        본문 영역에 텍스트 입력
        여러 셀렉터와 입력 방식을 시도
        """
        # 방법 1: placeholder 클릭 후 입력
        content_element = self._find_element_with_fallback(self.SELECTORS['content'])
        
        if content_element:
            try:
                self._click_element_safely(content_element)
                time.sleep(0.3)
                
                # 클립보드 입력
                if self.clipboard_input(content_text):
                    return True
                
                # 직접 타이핑
                ActionChains(self.driver).send_keys(content_text).perform()
                return True
                
            except Exception as e:
                logger.debug(f"본문 입력 방법 1 실패: {e}")
        
        # 방법 2: 본문 영역 직접 클릭
        try:
            # 에디터 본문 영역 찾기
            content_selectors = [
                ".se-component-content",
                ".se-text-paragraph",
                ".se-section-text",
                "[contenteditable='true']",
            ]
            
            for selector in content_selectors:
                try:
                    content_area = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    self._click_element_safely(content_area)
                    time.sleep(0.3)
                    
                    if self.clipboard_input(content_text):
                        return True
                    
                    ActionChains(self.driver).send_keys(content_text).perform()
                    return True
                except:
                    continue
                    
        except Exception as e:
            logger.debug(f"본문 입력 방법 2 실패: {e}")
        
        # 방법 3: JavaScript로 직접 삽입
        try:
            result = self.driver.execute_script("""
                // 본문 영역 찾기
                var contentEl = document.querySelector('.se-component-content, .se-text-paragraph, [contenteditable="true"]');
                if (contentEl) {
                    // HTML 줄바꿈 처리
                    var htmlContent = arguments[0].replace(/\n/g, '<br>');
                    contentEl.innerHTML = htmlContent;
                    contentEl.dispatchEvent(new Event('input', { bubbles: true }));
                    return true;
                }
                return false;
            """, content_text)
            
            if result:
                return True
                
        except Exception as e:
            logger.debug(f"본문 입력 방법 3 실패: {e}")
        
        return False

    def publish_post(self) -> Tuple[bool, str]:
        """
        발행 버튼 클릭 및 최종 발행
        
        Returns:
            (성공 여부, 메시지)
        """
        try:
            # 1. 상단 발행 버튼 클릭
            logger.info("상단 발행 버튼 클릭 시도...")
            publish_btn_1 = self._find_element_with_fallback(self.SELECTORS['publish_btn_1'])
            
            if not publish_btn_1:
                return False, "발행 버튼을 찾을 수 없습니다."
            
            self._click_element_safely(publish_btn_1)
            time.sleep(2)  # 발행 설정 팝업 로딩 대기

            # 2. '현재' 발행으로 설정 (예약 발행이 아닌 즉시 발행)
            try:
                now_radio_selectors = [
                    "#radio_time1",
                    "input[name='publishTime'][value='now']",
                    "//label[contains(text(), '현재')]",
                ]
                
                for selector in now_radio_selectors:
                    try:
                        if selector.startswith("//"):
                            now_radio = self.driver.find_element(By.XPATH, selector)
                        else:
                            now_radio = self.driver.find_element(By.CSS_SELECTOR, selector)
                        
                        self.driver.execute_script("arguments[0].click();", now_radio)
                        time.sleep(0.3)
                        break
                    except:
                        continue
            except Exception as e:
                logger.debug(f"현재 발행 라디오 버튼 선택 실패 (무시): {e}")

            # 3. 최종 발행 버튼 클릭
            logger.info("최종 발행 버튼 클릭 시도...")
            final_publish_btn = self._find_element_with_fallback(
                self.SELECTORS['publish_btn_final'], timeout=10
            )
            
            if not final_publish_btn:
                # 대체 방법: 모든 발행 버튼 중 활성화된 것 클릭
                try:
                    final_publish_btn = self.wait.until(
                        EC.element_to_be_clickable(
                            (By.XPATH, "//button[contains(text(), '발행') and not(@disabled)]")
                        )
                    )
                except:
                    return False, "최종 발행 버튼을 찾을 수 없습니다."
            
            self._click_element_safely(final_publish_btn)
            time.sleep(3)  # 발행 처리 대기
            
            # 4. 발행 결과 확인
            current_url = self.driver.current_url
            
            # 발행 성공 시 보통 포스트 URL로 이동
            if "post" in current_url.lower() or "logNo" in current_url:
                logger.info(f"포스팅 발행 완료: {current_url}")
                return True, f"포스팅 발행 완료\nURL: {current_url}"
            
            logger.info("포스팅 발행 완료")
            return True, "포스팅 발행 완료"

        except TimeoutException:
            return False, "발행 버튼 대기 시간 초과"
        except Exception as e:
            logger.error(f"발행 실패: {e}")
            return False, f"발행 실패: {str(e)}"
    
    def get_current_url(self) -> str:
        """현재 페이지 URL 반환"""
        try:
            return self.driver.current_url
        except:
            return ""
    
    def take_screenshot(self, filename: str = "screenshot.png") -> bool:
        """스크린샷 저장"""
        try:
            self.driver.save_screenshot(filename)
            logger.info(f"스크린샷 저장: {filename}")
            return True
        except Exception as e:
            logger.error(f"스크린샷 저장 실패: {e}")
            return False

    def close(self):
        """브라우저 종료"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("브라우저 종료")
            except Exception as e:
                logger.error(f"브라우저 종료 오류: {e}")
            finally:
                self.driver = None
                self.wait = None
    
    def __enter__(self):
        """Context manager 진입"""
        self.start_browser()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager 종료"""
        self.close()
