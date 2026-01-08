#!/usr/bin/env python3
"""
Auto Blogger Pro - 자동 블로그 포스팅 도구
GUI 및 CLI 모드 지원
Firebase Auth 로그인 기능 포함
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
        from ui.delivery_tab import DeliveryTab
        from ui.login_dialog import LoginDialog, UserInfoWidget
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

            main_widget = QWidget()
            self.setCentralWidget(main_widget)
            layout = QVBoxLayout(main_widget)

            # 상단 로그인 상태 바
            login_bar = QHBoxLayout()
            self.lbl_login_status = QLabel("🔒 로그인이 필요합니다")
            self.lbl_login_status.setStyleSheet("color: #E74C3C; font-weight: bold;")
            self.btn_login = QPushButton("🔐 로그인")
            self.btn_login.setStyleSheet("background-color: #03C75A; color: white; padding: 5px 15px;")
            self.btn_login.clicked.connect(self.show_login_dialog)
            
            login_bar.addWidget(self.lbl_login_status)
            login_bar.addStretch()
            login_bar.addWidget(self.btn_login)
            layout.addLayout(login_bar)

            # Tab widget
            self.tabs = QTabWidget()
            
            self.tab_info = InfoTab()
            self.tab_delivery = DeliveryTab()
            self.tab_settings = SettingsTab()
            self.tab_user = UserInfoWidget()
            
            self.tabs.addTab(self.tab_info, "📝 정보성 글쓰기")
            self.tabs.addTab(self.tab_delivery, "🚗 출고 후기")
            self.tabs.addTab(self.tab_settings, "⚙️ 환경 설정")
            self.tabs.addTab(self.tab_user, "👤 내 정보")
            
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
            
            self.tab_user.logout_signal.connect(self.on_logout)
            
            # 저장된 로그인 확인
            self.check_saved_login()

        def check_saved_login(self):
            """저장된 로그인 정보 확인"""
            saved_token = self.settings.value("auth_token", "")
            saved_email = self.settings.value("auth_email", "")
            
            if saved_token and saved_email:
                self.id_token = saved_token
                self.current_user = {"email": saved_email}
                self.update_login_status(saved_email)
                self.fetch_user_info()

        def show_login_dialog(self):
            """로그인 다이얼로그 표시"""
            api_key = Config.FIREBASE_API_KEY
            
            if not api_key:
                QMessageBox.warning(
                    self, 
                    "설정 필요", 
                    "Firebase API 키가 설정되지 않았습니다.\n\n"
                    "환경변수 FIREBASE_API_KEY를 설정하거나\n"
                    "config.py에서 직접 설정해주세요."
                )
                return
            
            dialog = LoginDialog(self, api_key=api_key)
            dialog.login_success.connect(self.on_login_success)
            dialog.exec()

        def on_login_success(self, user_data: dict):
            """로그인 성공 처리"""
            self.current_user = user_data
            self.id_token = user_data.get("id_token", "")
            
            email = user_data.get("email", "")
            self.update_login_status(email)
            self.update_log(f"✅ 로그인 성공: {email}")
            
            # 사용자 정보 조회
            self.fetch_user_info()

        def update_login_status(self, email: str):
            """로그인 상태 UI 업데이트"""
            self.lbl_login_status.setText(f"✅ {email}")
            self.lbl_login_status.setStyleSheet("color: #27AE60; font-weight: bold;")
            self.btn_login.setText("🔄 계정 전환")

        def on_logout(self):
            """로그아웃 처리"""
            self.current_user = None
            self.id_token = None
            self.lbl_login_status.setText("🔒 로그인이 필요합니다")
            self.lbl_login_status.setStyleSheet("color: #E74C3C; font-weight: bold;")
            self.btn_login.setText("🔐 로그인")
            self.update_log("🚪 로그아웃 되었습니다.")

        def fetch_user_info(self):
            """서버에서 사용자 정보 조회"""
            if not self.id_token:
                return
            
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
                    user_info = response.json()
                    self.tab_user.update_user_info(user_info)
                elif response.status_code == 401:
                    # 토큰 만료
                    self.update_log("⚠️ 로그인이 만료되었습니다. 다시 로그인해주세요.")
                    self.on_logout()
                    
            except Exception as e:
                logger.error(f"Failed to fetch user info: {e}")

        def start_automation(self, data):
            """Start automation worker"""
            user_id = self.settings.value("id", "")
            user_pw = self.settings.value("pw", "")
            
            # 발행 기능은 네이버 계정 필요
            if data.get("action") in ["publish_only", "full"]:
                if not user_id or not user_pw:
                    self.update_log("❌ 오류: 설정 탭에서 네이버 ID/PW를 먼저 저장해주세요.")
                    self.tabs.setCurrentIndex(2)
                    return

            settings_dict = {
                "id": user_id, 
                "pw": user_pw,
                "intro": self.settings.value("intro", ""),
                "outro": self.settings.value("outro", ""),
                "auth_token": self.id_token or ""
            }

            # Create and start worker
            self.worker = AutomationWorker(data, settings_dict)
            self.worker.log_signal.connect(self.update_log)
            self.worker.result_signal.connect(self.tab_info.update_result_view)
            self.worker.error_signal.connect(self.update_log)
            self.worker.start()

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
