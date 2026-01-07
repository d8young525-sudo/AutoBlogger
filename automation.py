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
        options = webdriver.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("detach", True)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        self.wait = WebDriverWait(self.driver, 15)
        self.driver.set_window_size(1280, 900)

    def clipboard_input(self, user_input):
        pyperclip.copy(user_input)
        ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
        time.sleep(0.5)

    def login(self, user_id, user_pw):
        if not self.driver: return False, "Browser not started"
        try:
            self.driver.get("https://nid.naver.com/nidlogin.login")
            time.sleep(2)
            id_input = self.wait.until(EC.element_to_be_clickable((By.ID, "id")))
            id_input.click()
            self.clipboard_input(user_id)
            pw_input = self.driver.find_element(By.ID, "pw")
            pw_input.click()
            self.clipboard_input(user_pw)
            self.driver.find_element(By.ID, "log.login").click()
            time.sleep(2)
            return True, "Login success"
        except Exception as e: return False, str(e)

    def go_to_editor(self):
        try:
            # 바로 에디터 URL로 이동
            self.driver.get("https://blog.naver.com/PostWriteForm.naver?wtype=post")
            time.sleep(3)
            
            # 팝업 닫기 (작성중인 글 등)
            try:
                cancel_btn = WebDriverWait(self.driver, 3).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.se-popup-button-cancel")))
                cancel_btn.click()
            except: pass
            
            # 도움말 닫기
            try:
                help_btn = WebDriverWait(self.driver, 2).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.se-help-panel-close-button")))
                help_btn.click()
            except: pass
            
            return True, "Editor loaded"
        except Exception as e: return False, str(e)

    def write_content(self, title, content):
        try:
            title_area = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(@class, 'se-placeholder') and text()='제목']")))
            title_area.click()
            self.clipboard_input(title)
            time.sleep(1)
            
            content_area = self.driver.find_element(By.XPATH, "//span[contains(@class, 'se-placeholder') and contains(text(), '글감과')]")
            content_area.click()
            self.clipboard_input(content)
            time.sleep(2)
            return True, "Content written"
        except Exception as e: return False, str(e)

    def publish_post(self):
        try:
            # 1차 발행 버튼
            self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-click-area='tpb.publish']"))).click()
            time.sleep(1.5)
            
            # 현재 발행 강제 선택 (JS 사용)
            try:
                self.driver.execute_script("document.getElementById('radio_time1').click();")
            except: pass
            
            # 2차 최종 발행
            self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='seOnePublishBtn']"))).click()
            return True, "Published"
        except Exception as e: return False, str(e)
