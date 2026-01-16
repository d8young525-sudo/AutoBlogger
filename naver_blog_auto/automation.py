import time
import pyperclip
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class NaverBlogBot:
    def __init__(self):
        self.driver = None
        self.wait = None

    def start_browser(self):
        """브라우저 실행"""
        options = webdriver.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("detach", True)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        # 윈도우/맥 환경에 맞춰 User-Agent 설정 (선택사항)
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        self.wait = WebDriverWait(self.driver, 15) # 대기 시간 넉넉히 15초
        self.driver.set_window_size(1280, 900)

    def clipboard_input(self, user_input):
        """클립보드를 이용한 입력 (로그인 캡챠 우회용)"""
        pyperclip.copy(user_input)
        # 맥/윈도우 구분 없이 Ctrl+V 시도 (맥은 Command지만, 보통 드라이버 레벨에서 제어 필요. 여기선 일반적인 Ctrl로 시도)
        # 윈도우: Keys.CONTROL, 맥: Keys.COMMAND
        # 만약 맥에서 동작 안하면 분기 처리 필요. 일단 범용적인 방식 사용.
        ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
        time.sleep(0.5)

    def login(self, user_id, user_pw):
        """네이버 로그인"""
        if not self.driver:
            return False, "브라우저가 실행되지 않았습니다."

        try:
            # 1. 로그인 페이지 직접 이동 (가장 안정적)
            self.driver.get("https://nid.naver.com/nidlogin.login")
            time.sleep(2)

            # 2. 아이디 입력
            id_input = self.wait.until(EC.element_to_be_clickable((By.ID, "id")))
            id_input.click()
            self.clipboard_input(user_id)

            # 3. 비밀번호 입력
            pw_input = self.driver.find_element(By.ID, "pw")
            pw_input.click()
            self.clipboard_input(user_pw)

            # 4. 로그인 버튼 클릭
            # id="log.login"
            login_btn = self.driver.find_element(By.ID, "log.login")
            login_btn.click()
            
            time.sleep(2)
            
            # 로그인 실패/캡챠 확인 로직 추가 가능
            # 여기서는 완료된 것으로 간주
            return True, "로그인 시도 완료"

        except Exception as e:
            return False, f"로그인 중 오류 발생: {str(e)}"

    def go_to_editor(self):
        """메인 -> 블로그 -> 글쓰기 이동"""
        try:
            # 1. 네이버 메인 이동 (로그인 상태 확인 겸)
            self.driver.get("https://www.naver.com")
            time.sleep(2)

            # 2. 블로그 서비스 링크 클릭
            # <a href="https://blog.naver.com" class="link_service" ...>
            try:
                blog_link = self.wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "a.link_service[href*='blog.naver.com']")
                ))
                blog_link.click()
            except:
                # 메인 UI가 다를 경우 바로 URL 이동
                self.driver.get("https://section.blog.naver.com/")

            time.sleep(2)
            
            # 탭이 새로 열렸을 수 있으므로 핸들링
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[-1])

            # 3. 글쓰기 버튼 클릭
            # <a ... href="https://blog.naver.com/GoBlogWrite.naver" ...>글쓰기</a>
            # class="item"이나 href 속성으로 찾기
            write_btn = self.wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "a[href*='GoBlogWrite.naver']")
            ))
            write_btn.click()
            
            time.sleep(3)

            # 4. 글쓰기 에디터는 보통 '새 창'으로 열림 -> 윈도우 전환 필수
            self.driver.switch_to.window(self.driver.window_handles[-1])
            
            # 5. iframe 진입 (SmartEditor One은 mainFrame 안에 있을 수 있음)
            try:
                self.driver.switch_to.frame("mainFrame")
            except:
                pass # iframe이 없으면 그냥 진행

            # 6. 팝업(작성 중인 글) 닫기 시도 (개선됨)
            try:
                # 팝업이 뜰 때까지 잠시 대기 (최대 3초)
                # 제공해주신 소스: <button ... class="se-popup-button se-popup-button-cancel">
                cancel_btn = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.se-popup-button-cancel"))
                )
                cancel_btn.click()
                time.sleep(1) # 팝업 닫히는 애니메이션 대기
            except:
                # 팝업이 안 뜨면 그냥 진행
                pass

            # 7. 도움말 패널(Help Panel) 닫기 (추가됨)
            try:
                # 제공해주신 소스: <button ... class="se-help-panel-close-button">
                help_close_btn = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.se-help-panel-close-button"))
                )
                help_close_btn.click()
                time.sleep(1)
            except:
                pass

            return True, "에디터 진입 성공"

        except Exception as e:
            return False, f"에디터 진입 실패: {str(e)}"

    def write_content(self, title_text, content_text):
        """제목 및 본문 작성"""
        try:
            # 1. 제목 입력
            # <span class="se-placeholder ...">제목</span> 을 찾아서 클릭
            title_placeholder = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//span[contains(@class, 'se-placeholder') and text()='제목']")
            ))
            # 부모 요소(p태그 혹은 상위 div)를 클릭해야 입력 모드가 활성화될 수 있음
            # placeholder 자체를 클릭해도 보통 동작함
            title_placeholder.click()
            time.sleep(0.5)
            
            # 제목 입력 (클립보드 방식이 안전)
            self.clipboard_input(title_text)
            time.sleep(1)

            # 2. 본문 입력
            # <span class="se-placeholder ...">글감과 함께...</span> 찾기
            # text()가 길 수 있으므로 contains 사용
            content_placeholder = self.driver.find_element(By.XPATH, "//span[contains(@class, 'se-placeholder') and contains(text(), '글감과 함께')]")
            content_placeholder.click()
            time.sleep(0.5)

            # 본문 입력
            self.clipboard_input(content_text)
            time.sleep(2)

            return True, "본문 작성 완료"

        except Exception as e:
            # 실패 시 스크린샷 저장 (디버깅용, 로컬 실행시 유용)
            # self.driver.save_screenshot("write_error.png")
            return False, f"글 작성 실패: {str(e)}"

    def publish_post(self):
        """발행 버튼 클릭 및 최종 발행"""
        try:
            # 1. 상단 발행 버튼 클릭
            # data-click-area="tpb.publish"
            publish_btn_1 = self.wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button[data-click-area='tpb.publish']")
            ))
            publish_btn_1.click()
            time.sleep(1.5) # 발행 설정 팝업이 뜨는 시간 대기

            # 2. '현재' 발행으로 설정 (안전장치 추가)
            try:
                # '현재' 라디오 버튼(id="radio_time1")을 찾아서 클릭
                # 혹시 '예약'에 체크되어 있어도 이걸 누르면 '현재'로 돌아옴
                now_radio_btn = self.driver.find_element(By.ID, "radio_time1")
                # 가끔 클릭이 안 먹힐 때를 대비해 Javascript로 강제 클릭
                self.driver.execute_script("arguments[0].click();", now_radio_btn)
                time.sleep(0.5)
            except:
                pass # 요소를 못 찾으면(구조 변경 등) 일단 패스하고 진행

            # 3. 최종 발행 버튼 클릭
            # data-testid="seOnePublishBtn"
            final_publish_btn = self.wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button[data-testid='seOnePublishBtn']")
            ))
            final_publish_btn.click()
            
            time.sleep(3) # 발행 완료 대기
            
            return True, "포스팅 발행 완료"

        except Exception as e:
            return False, f"발행 실패: {str(e)}"

    def close(self):
        if self.driver:
            self.driver.quit()
