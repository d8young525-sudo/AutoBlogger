#!/usr/bin/env python3
"""
Auto Blogger Pro - 자동 블로그 포스팅 도구
GUI 및 CLI 모드 지원
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
            QVBoxLayout, QTabWidget, QTextEdit, QLabel
        )
        from PySide6.QtCore import Slot, QSettings
        
        from ui.info_tab import InfoTab
        from ui.settings_tab import SettingsTab
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

            main_widget = QWidget()
            self.setCentralWidget(main_widget)
            layout = QVBoxLayout(main_widget)

            # Tab widget
            self.tabs = QTabWidget()
            
            self.tab_info = InfoTab()
            self.tab_settings = SettingsTab()
            
            self.tabs.addTab(self.tab_info, "📝 정보성 글쓰기")
            self.tabs.addTab(QWidget(), "🚗 출고 후기 (준비중)")
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

        def start_automation(self, data):
            """Start automation worker"""
            user_id = self.settings.value("id", "")
            user_pw = self.settings.value("pw", "")
            
            if not user_id or not user_pw:
                self.update_log("❌ 오류: 설정 탭에서 ID/PW를 먼저 저장해주세요.")
                self.tabs.setCurrentIndex(2)
                return

            settings_dict = {
                "id": user_id, 
                "pw": user_pw,
                "intro": self.settings.value("intro", ""),
                "outro": self.settings.value("outro", "")
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
