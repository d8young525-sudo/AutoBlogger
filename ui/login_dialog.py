"""
Firebase 로그인 다이얼로그
회원가입, 로그인, 사용자 정보 관리
"""
import json
import requests
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QMessageBox,
    QTabWidget, QWidget, QGroupBox
)
from PySide6.QtCore import Signal, QSettings

# Firebase Auth REST API
FIREBASE_API_KEY = ""  # Firebase 웹 API 키 (config에서 로드)
FIREBASE_AUTH_URL = "https://identitytoolkit.googleapis.com/v1/accounts"

# 관리자 연락처 (오픈카톡)
ADMIN_CONTACT = "https://open.kakao.com/o/sgbYdyai"

# 백엔드 API URL
BACKEND_URL = os.environ.get("BACKEND_URL", "https://generate-blog-post-yahp6ia25q-du.a.run.app")


class LoginDialog(QDialog):
    """로그인/회원가입 다이얼로그"""
    
    login_success = Signal(dict)  # 로그인 성공 시 사용자 정보 전달
    
    def __init__(self, parent=None, api_key: str = ""):
        super().__init__(parent)
        self.api_key = api_key
        self.settings = QSettings("MySoft", "NaverBlogBot")
        self.current_user = None
        self.id_token = None
        
        self.setWindowTitle("🔐 로그인")
        self.setMinimumWidth(400)
        self.init_ui()
        
        # 저장된 로그인 정보 로드
        self.load_saved_credentials()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 탭 위젯 (로그인 / 회원가입)
        self.tabs = QTabWidget()
        
        # 로그인 탭
        login_tab = QWidget()
        login_layout = QVBoxLayout()
        
        login_form = QFormLayout()
        self.login_email = QLineEdit()
        self.login_email.setPlaceholderText("example@email.com")
        self.login_password = QLineEdit()
        self.login_password.setEchoMode(QLineEdit.Password)
        self.login_password.setPlaceholderText("비밀번호")
        
        login_form.addRow("이메일:", self.login_email)
        login_form.addRow("비밀번호:", self.login_password)
        login_layout.addLayout(login_form)
        
        self.btn_login = QPushButton("🔓 로그인")
        self.btn_login.setStyleSheet("background-color: #03C75A; color: white; font-weight: bold; padding: 12px;")
        self.btn_login.clicked.connect(self.do_login)
        login_layout.addWidget(self.btn_login)
        
        # 로그인 상태 저장 체크박스 대신 자동 저장
        self.login_status = QLabel("")
        self.login_status.setStyleSheet("color: #666;")
        login_layout.addWidget(self.login_status)
        
        login_tab.setLayout(login_layout)
        self.tabs.addTab(login_tab, "로그인")
        
        # 회원가입 탭
        register_tab = QWidget()
        register_layout = QVBoxLayout()
        
        register_form = QFormLayout()
        self.register_email = QLineEdit()
        self.register_email.setPlaceholderText("example@email.com")
        self.register_password = QLineEdit()
        self.register_password.setEchoMode(QLineEdit.Password)
        self.register_password.setPlaceholderText("6자 이상")
        self.register_password_confirm = QLineEdit()
        self.register_password_confirm.setEchoMode(QLineEdit.Password)
        self.register_password_confirm.setPlaceholderText("비밀번호 확인")
        
        register_form.addRow("이메일:", self.register_email)
        register_form.addRow("비밀번호:", self.register_password)
        register_form.addRow("비밀번호 확인:", self.register_password_confirm)
        register_layout.addLayout(register_form)
        
        self.btn_register = QPushButton("📝 회원가입")
        self.btn_register.setStyleSheet("background-color: #4A90E2; color: white; font-weight: bold; padding: 12px;")
        self.btn_register.clicked.connect(self.do_register)
        register_layout.addWidget(self.btn_register)
        
        register_info = QLabel("⚠️ 회원가입 후 관리자 승인이 필요합니다.")
        register_info.setStyleSheet("color: #E67E22; font-size: 12px;")
        register_layout.addWidget(register_info)
        
        # 관리자 연락처 안내
        contact_info = QLabel(f"📞 승인 문의: <a href='{ADMIN_CONTACT}'>오픈카톡</a>")
        contact_info.setStyleSheet("color: #3498DB; font-size: 12px;")
        contact_info.setOpenExternalLinks(True)
        register_layout.addWidget(contact_info)
        
        register_tab.setLayout(register_layout)
        self.tabs.addTab(register_tab, "회원가입")
        
        layout.addWidget(self.tabs)
        
        # 하단 버튼
        btn_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("취소")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def load_saved_credentials(self):
        """저장된 로그인 정보 로드"""
        saved_email = self.settings.value("auth_email", "")
        saved_token = self.settings.value("auth_token", "")
        
        if saved_email:
            self.login_email.setText(saved_email)
            self.login_status.setText(f"마지막 로그인: {saved_email}")
    
    def save_credentials(self, email: str, token: str, user_data: dict):
        """로그인 정보 저장"""
        self.settings.setValue("auth_email", email)
        self.settings.setValue("auth_token", token)
        self.settings.setValue("auth_uid", user_data.get("localId", ""))
    
    def do_login(self):
        """로그인 실행"""
        email = self.login_email.text().strip()
        password = self.login_password.text()
        
        if not email or not password:
            QMessageBox.warning(self, "입력 오류", "이메일과 비밀번호를 입력해주세요.")
            return
        
        self.btn_login.setEnabled(False)
        self.btn_login.setText("⏳ 로그인 중...")
        
        try:
            # Firebase Auth REST API 호출
            url = f"{FIREBASE_AUTH_URL}:signInWithPassword?key={self.api_key}"
            payload = {
                "email": email,
                "password": password,
                "returnSecureToken": True
            }
            
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                self.current_user = {
                    "uid": data.get("localId"),
                    "email": data.get("email"),
                    "id_token": data.get("idToken"),
                    "refresh_token": data.get("refreshToken")
                }
                self.id_token = data.get("idToken")
                
                # 로그인 정보 저장
                self.save_credentials(email, self.id_token, data)
                
                QMessageBox.information(self, "로그인 성공", f"환영합니다, {email}!")
                self.login_success.emit(self.current_user)
                self.accept()
            else:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "로그인 실패")
                
                # 에러 메시지 한글화
                error_messages = {
                    "EMAIL_NOT_FOUND": "등록되지 않은 이메일입니다.",
                    "INVALID_PASSWORD": "비밀번호가 올바르지 않습니다.",
                    "INVALID_LOGIN_CREDENTIALS": "이메일 또는 비밀번호가 올바르지 않습니다.",
                    "USER_DISABLED": "비활성화된 계정입니다.",
                    "TOO_MANY_ATTEMPTS_TRY_LATER": "너무 많은 시도. 잠시 후 다시 시도해주세요."
                }
                
                display_msg = error_messages.get(error_msg, error_msg)
                QMessageBox.warning(self, "로그인 실패", display_msg)
                
        except requests.Timeout:
            QMessageBox.warning(self, "오류", "서버 응답 시간 초과")
        except Exception as e:
            QMessageBox.warning(self, "오류", f"로그인 중 오류 발생: {str(e)}")
        finally:
            self.btn_login.setEnabled(True)
            self.btn_login.setText("🔓 로그인")
    
    def do_register(self):
        """회원가입 실행"""
        email = self.register_email.text().strip()
        password = self.register_password.text()
        password_confirm = self.register_password_confirm.text()
        
        if not email or not password:
            QMessageBox.warning(self, "입력 오류", "이메일과 비밀번호를 입력해주세요.")
            return
        
        if password != password_confirm:
            QMessageBox.warning(self, "입력 오류", "비밀번호가 일치하지 않습니다.")
            return
        
        if len(password) < 6:
            QMessageBox.warning(self, "입력 오류", "비밀번호는 6자 이상이어야 합니다.")
            return
        
        self.btn_register.setEnabled(False)
        self.btn_register.setText("⏳ 가입 중...")
        
        try:
            # Firebase Auth REST API 호출
            url = f"{FIREBASE_AUTH_URL}:signUp?key={self.api_key}"
            payload = {
                "email": email,
                "password": password,
                "returnSecureToken": True
            }
            
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Firestore에 사용자 문서 즉시 생성 (Backend API 호출)
                self._create_firestore_user(data.get("idToken"), email)
                
                QMessageBox.information(
                    self, 
                    "회원가입 완료", 
                    f"회원가입이 완료되었습니다!\n\n"
                    f"이메일: {email}\n\n"
                    f"⚠️ 서비스 이용을 위해 관리자 승인이 필요합니다.\n"
                    f"📞 오픈카톡으로 문의해주세요:\n"
                    f"{ADMIN_CONTACT}"
                )
                
                # 로그인 탭으로 전환
                self.tabs.setCurrentIndex(0)
                self.login_email.setText(email)
                
            else:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "회원가입 실패")
                
                error_messages = {
                    "EMAIL_EXISTS": "이미 등록된 이메일입니다.",
                    "WEAK_PASSWORD": "비밀번호가 너무 약합니다. 6자 이상 입력해주세요.",
                    "INVALID_EMAIL": "올바른 이메일 형식이 아닙니다."
                }
                
                display_msg = error_messages.get(error_msg, error_msg)
                QMessageBox.warning(self, "회원가입 실패", display_msg)
                
        except requests.Timeout:
            QMessageBox.warning(self, "오류", "서버 응답 시간 초과")
        except Exception as e:
            QMessageBox.warning(self, "오류", f"회원가입 중 오류 발생: {str(e)}")
        finally:
            self.btn_register.setEnabled(True)
            self.btn_register.setText("📝 회원가입")
    
    def _create_firestore_user(self, id_token: str, email: str):
        """회원가입 후 Firestore에 사용자 문서 즉시 생성"""
        try:
            # Backend API를 호출하여 user_info 모드로 사용자 문서 생성 유도
            headers = {
                "Authorization": f"Bearer {id_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "mode": "user_info"
            }
            
            response = requests.post(
                BACKEND_URL,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                print(f"Firestore 사용자 문서 생성 완료: {email}")
            else:
                print(f"Firestore 사용자 문서 생성 실패: {response.status_code}")
                
        except Exception as e:
            print(f"Firestore 문서 생성 중 오류: {e}")
    
    def get_id_token(self) -> str:
        """현재 로그인된 사용자의 ID 토큰 반환"""
        return self.id_token or ""
    
    def get_current_user(self) -> dict:
        """현재 로그인된 사용자 정보 반환"""
        return self.current_user or {}


class UserInfoWidget(QWidget):
    """사용자 정보 표시 위젯"""
    
    logout_signal = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("MySoft", "NaverBlogBot")
        self.user_data = {}
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 사용자 정보 그룹
        group = QGroupBox("👤 사용자 정보")
        group_layout = QFormLayout()
        
        self.lbl_email = QLabel("-")
        self.lbl_plan = QLabel("-")
        self.lbl_status = QLabel("-")
        self.lbl_daily_usage = QLabel("-")
        self.lbl_monthly_usage = QLabel("-")
        
        group_layout.addRow("이메일:", self.lbl_email)
        group_layout.addRow("플랜:", self.lbl_plan)
        group_layout.addRow("상태:", self.lbl_status)
        group_layout.addRow("오늘 이미지:", self.lbl_daily_usage)
        group_layout.addRow("이번 달:", self.lbl_monthly_usage)
        
        group.setLayout(group_layout)
        layout.addWidget(group)
        
        # 로그아웃 버튼
        self.btn_logout = QPushButton("🚪 로그아웃")
        self.btn_logout.setStyleSheet("background-color: #E74C3C; color: white; padding: 10px;")
        self.btn_logout.clicked.connect(self.do_logout)
        layout.addWidget(self.btn_logout)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def update_user_info(self, user_data: dict):
        """사용자 정보 업데이트"""
        self.user_data = user_data
        
        self.lbl_email.setText(user_data.get("email", "-"))
        
        is_active = user_data.get("is_active", False)
        if is_active:
            self.lbl_plan.setText("정식 사용자")
        else:
            self.lbl_plan.setText("승인 대기")
        
        is_active = user_data.get("is_active", False)
        if is_active:
            self.lbl_status.setText("✅ 활성")
            self.lbl_status.setStyleSheet("color: #27AE60; font-weight: bold;")
        else:
            self.lbl_status.setText("❌ 비활성 (결제 필요)")
            self.lbl_status.setStyleSheet("color: #E74C3C; font-weight: bold;")
        
        usage = user_data.get("usage", {})
        daily = usage.get("daily_image_count", 0)
        monthly = usage.get("monthly_image_count", 0)
        
        self.lbl_daily_usage.setText(f"{daily}장 사용")
        self.lbl_monthly_usage.setText(f"{monthly}장 사용")
    
    def do_logout(self):
        """로그아웃"""
        self.settings.remove("auth_token")
        self.settings.remove("auth_uid")
        # 이메일은 유지 (다음 로그인 편의)
        
        self.user_data = {}
        self.lbl_email.setText("-")
        self.lbl_plan.setText("-")
        self.lbl_status.setText("-")
        self.lbl_daily_usage.setText("-")
        self.lbl_monthly_usage.setText("-")
        
        self.logout_signal.emit()
        QMessageBox.information(self, "로그아웃", "로그아웃 되었습니다.")
