#!/usr/bin/env python3
"""
Auto Blogger Pro - 자동 블로그 포스팅 도구
v3.5.0: 글쓰기 환경설정 탭 분리
GUI 및 CLI 모드 지원
Firebase Auth 로그인 필수
"""
import sys
import argparse
import logging

from config import Config

logger = logging.getLogger(__name__)


def setup_logging(debug: bool = False):
    """Configure logging"""
    level = logging.DEBUG if debug else logging.INFO
    logging.getLogger().setLevel(level)


def run_gui():
    """Run application in GUI mode"""
    try:
        from PySide6.QtWidgets import (
            QApplication, QMainWindow, QWidget, 
            QVBoxLayout, QHBoxLayout, QTabWidget, QTextEdit, QLabel,
            QPushButton, QMessageBox
        )
        from PySide6.QtCore import Slot, QSettings
        
        from ui.info_tab import InfoTab
        from ui.settings_tab import SettingsTab
        from ui.writing_settings_tab import WritingSettingsTab
        from ui.delivery_tab import DeliveryTab
        from ui.login_dialog import LoginDialog
        from core.worker import AutomationWorker
        
    except ImportError as e:
        logger.error(f"GUI import failed: {e}")
        logger.info("Install GUI dependencies: pip install PySide6")
        return 1

    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle(f"{Config.APP_NAME} (v{Config.VERSION})")
            self.resize(Config.WINDOW_WIDTH, Config.WINDOW_HEIGHT)
            self.settings = QSettings("MySoft", "NaverBlogBot")
            self.worker = None
            self.current_user = None
            self.id_token = None
            self.user_info = None

            main_widget = QWidget()
            self.setCentralWidget(main_widget)
            layout = QVBoxLayout(main_widget)

            # 상단 사용자 정보 바
            user_bar = QHBoxLayout()
            self.lbl_user_email = QLabel("🔒 로그인이 필요합니다")
            self.lbl_user_email.setStyleSheet("color: #666; font-weight: bold;")
            self.lbl_subscription = QLabel("")
            self.lbl_subscription.setStyleSheet("color: #27AE60; font-size: 12px;")
            
            self.btn_logout = QPushButton("🚪 로그아웃")
            self.btn_logout.setStyleSheet("background-color: #E74C3C; color: white; padding: 5px 10px;")
            self.btn_logout.clicked.connect(self.do_logout)
            self.btn_logout.hide()
            
            user_bar.addWidget(self.lbl_user_email)
            user_bar.addWidget(self.lbl_subscription)
            user_bar.addStretch()
            user_bar.addWidget(self.btn_logout)
            layout.addLayout(user_bar)

            # 구분선
            line = QLabel()
            line.setStyleSheet("border-bottom: 1px solid #ddd; margin: 5px 0;")
            line.setFixedHeight(2)
            layout.addWidget(line)

            # Tab widget
            self.tabs = QTabWidget()
            
            # 글쓰기 환경설정 탭 먼저 생성 (다른 탭에서 참조)
            self.tab_writing_settings = WritingSettingsTab()
            
            # 기본 환경설정 탭
            self.tab_settings = SettingsTab()
            
            # info_tab에 글쓰기 환경설정 탭 연결
            self.tab_info = InfoTab(writing_settings_tab=self.tab_writing_settings)
            self.tab_delivery = DeliveryTab()
            
            # 탭 추가 (순서 변경: 글쓰기 환경설정을 환경설정 앞에)
            self.tabs.addTab(self.tab_info, "📝 정보성 글쓰기")
            self.tabs.addTab(self.tab_delivery, "🚗 출고 후기")
            self.tabs.addTab(self.tab_writing_settings, "✍️ 글쓰기 환경설정")
            self.tabs.addTab(self.tab_settings, "⚙️ 환경 설정")
            
            layout.addWidget(self.tabs)

            # Log area
            layout.addWidget(QLabel("📋 시스템 로그"))
            self.log_area = QTextEdit()
            self.log_area.setReadOnly(True)
            self.log_area.setMaximumHeight(150)
            layout.addWidget(self.log_area)

            # Connect signals
            self.tab_info.start_signal.connect(self.start_automation)
            self.tab_info.log_signal.connect(self.update_log)
            
            self.tab_delivery.start_signal.connect(self.start_automation)
            self.tab_delivery.log_signal.connect(self.update_log)
            
            # 로그인 상태 확인 및 처리
            self.check_and_require_login()

        def check_and_require_login(self):
            """로그인 필수 확인"""
            saved_token = self.settings.value("auth_token", "")
            saved_email = self.settings.value("auth_email", "")
            
            if saved_token and saved_email:
                self.id_token = saved_token
                self.current_user = {"email": saved_email}
                
                if self.verify_and_fetch_user_info():
                    return
            
            self.show_login_required()

        def show_login_required(self):
            """로그인 필수 다이얼로그 표시"""
            api_key = Config.FIREBASE_API_KEY
            
            if not api_key:
                QMessageBox.critical(
                    self, 
                    "설정 오류", 
                    "Firebase API 키가 설정되지 않았습니다.\n프로그램을 종료합니다."
                )
                sys.exit(1)
            
            dialog = LoginDialog(self, api_key=api_key)
            dialog.login_success.connect(self.on_login_success)
            
            result = dialog.exec()
            if result == 0:
                sys.exit(0)

        def on_login_success(self, user_data: dict):
            """로그인 성공 처리"""
            self.current_user = user_data
            self.id_token = user_data.get("id_token", "")
            
            if not self.verify_and_fetch_user_info():
                QMessageBox.warning(
                    self,
                    "승인 대기",
                    "관리자 승인이 필요합니다.\n\n"
                    "📞 오픈카톡으로 문의해주세요:\n"
                    "https://open.kakao.com/o/sgbYdyai"
                )
                self.show_login_required()
                return
            
            self.update_log(f"✅ 로그인 성공: {user_data.get('email', '')}")

        def verify_and_fetch_user_info(self) -> bool:
            """서버에서 사용자 정보 확인 및 승인 여부 체크"""
            if not self.id_token:
                return False
            
            try:
                import requests
                
                headers = {"Authorization": f"Bearer {self.id_token}"}
                response = requests.post(
                    Config.BACKEND_URL,
                    json={"mode": "user_info"},
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code == 200:
                    self.user_info = response.json()
                    is_active = self.user_info.get("is_active", False)
                    
                    if is_active:
                        self.update_user_display()
                        return True
                    else:
                        return False
                        
                elif response.status_code == 401:
                    self.settings.remove("auth_token")
                    return False
                else:
                    return False
                    
            except Exception as e:
                logger.error(f"Failed to verify user: {e}")
                return False

        def update_user_display(self):
            """상단 사용자 정보 표시 업데이트"""
            if self.user_info:
                email = self.user_info.get("email", "")
                self.lbl_user_email.setText(f"✅ {email}")
                self.lbl_user_email.setStyleSheet("color: #27AE60; font-weight: bold;")
                
                is_admin = self.user_info.get("is_admin", False)
                if is_admin:
                    self.lbl_subscription.setText("👑 관리자")
                else:
                    self.lbl_subscription.setText("🎫 정식 사용자")
                
                self.btn_logout.show()
                
                # 이미지 생성용 토큰 전달
                self.tab_info.set_auth_token(self.id_token)

        def do_logout(self):
            """로그아웃 처리"""
            reply = QMessageBox.question(
                self, 
                "로그아웃", 
                "로그아웃 하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.settings.remove("auth_token")
                self.settings.remove("auth_uid")
                self.current_user = None
                self.id_token = None
                self.user_info = None
                
                self.update_log("🚪 로그아웃 되었습니다.")
                self.show_login_required()

        def start_automation(self, data):
            """Start automation worker"""
            user_id = self.settings.value("id", "")
            user_pw = self.settings.value("pw", "")
            
            # 발행 기능은 네이버 계정 필요
            if data.get("action") in ["publish_only", "full"]:
                if not user_id or not user_pw:
                    self.update_log("❌ 오류: [환경 설정] 탭에서 네이버 ID/PW를 먼저 저장해주세요.")
                    self.tabs.setCurrentIndex(3)  # 환경 설정 탭으로 이동
                    return

            # 카테고리 정보 가져오기 (글쓰기 환경설정에서)
            category = data.get("category", "")
            if not category:
                # mode에 따라 카테고리 자동 설정
                mode = data.get("mode", "")
                if mode == "info":
                    category = self.tab_writing_settings.get_info_category()
                elif mode == "delivery":
                    category = self.tab_writing_settings.get_delivery_category()
            
            settings_dict = {
                "id": user_id, 
                "pw": user_pw,
                "intro": self.settings.value("intro", ""),
                "outro": self.settings.value("outro", ""),
                "outro_image": self.settings.value("outro_image", ""),
                "auth_token": self.id_token or "",
                "default_category": category
            }

            # Create and start worker
            self.worker = AutomationWorker(data, settings_dict)
            self.worker.log_signal.connect(self.update_log)
            self.worker.result_signal.connect(self.on_worker_result)
            self.worker.error_signal.connect(self.on_worker_error)
            self.worker.start()

        def on_worker_result(self, result):
            """워커 결과 처리"""
            # 현재 탭에 따라 결과 전달
            current_tab = self.tabs.currentIndex()
            if current_tab == 0:  # 정보성 글쓰기
                self.tab_info.update_result_view(result)
            elif current_tab == 1:  # 출고 후기
                self.tab_delivery.update_result_view(result)

        def on_worker_error(self, error_msg):
            """워커 에러 처리"""
            self.update_log(f"❌ {error_msg}")
            # 버튼 상태 복원
            current_tab = self.tabs.currentIndex()
            if current_tab == 0:
                self.tab_info.reset_generate_button()

        @Slot(str)
        def update_log(self, msg):
            """Update log area"""
            self.log_area.append(msg)
        
        def closeEvent(self, event):
            """Handle window close"""
            if self.worker and self.worker.isRunning():
                self.worker.cancel()
                self.worker.wait(3000)
            event.accept()

    # Run application
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    
    logger.info(f"Starting {Config.APP_NAME} v{Config.VERSION}")
    return app.exec()


def run_cli(args):
    """Run in CLI mode"""
    print(f"\n{Config.APP_NAME} v{Config.VERSION}")
    print("=" * 40)
    
    if args.info:
        info = Config.get_info()
        for key, value in info.items():
            print(f"  {key}: {value}")
        return 0
    
    print("\nCLI mode is available for:")
    print("  - API testing")
    print("  - Headless automation")
    print("\nFor full features, run without --cli flag for GUI mode.")
    
    return 0


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description=f"{Config.APP_NAME} - Automated Blog Posting Tool"
    )
    
    parser.add_argument(
        '--cli', '-c',
        action='store_true',
        help='Run in CLI mode (no GUI)'
    )
    
    parser.add_argument(
        '--info', '-i',
        action='store_true',
        help='Show application info'
    )
    
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Enable debug mode'
    )
    
    parser.add_argument(
        '--version', '-v',
        action='version',
        version=f'{Config.APP_NAME} v{Config.VERSION}'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(debug=args.debug)
    
    # CLI mode or no GUI available
    if args.cli or args.info:
        return run_cli(args)
    
    # Check GUI availability
    if not Config.is_gui_available():
        logger.warning("GUI not available in this environment")
        logger.info("Running in CLI mode...")
        return run_cli(args)
    
    # Run GUI
    return run_gui()


if __name__ == "__main__":
    sys.exit(main())
