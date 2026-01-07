import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QTabWidget, QTextEdit, QLabel)
from PySide6.QtCore import Slot, QSettings

# 모듈 import
from ui.info_tab import InfoTab
from ui.settings_tab import SettingsTab
from core.worker import AutomationWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto Blogger Pro (v3.0 Modular)")
        self.resize(700, 1000)
        self.settings = QSettings("MySoft", "NaverBlogBot")

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # 탭 구성
        self.tabs = QTabWidget()
        
        self.tab_info = InfoTab()
        self.tab_settings = SettingsTab()
        
        self.tabs.addTab(self.tab_info, "📝 정보성 글쓰기")
        self.tabs.addTab(QWidget(), "🚗 출고 후기 (준비중)")
        self.tabs.addTab(self.tab_settings, "⚙️ 환경 설정")
        
        layout.addWidget(self.tabs)

        # 로그창
        layout.addWidget(QLabel("📋 시스템 로그"))
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(150)
        layout.addWidget(self.log_area)

        # 시그널 연결
        self.tab_info.start_signal.connect(self.start_automation)
        self.tab_info.log_signal.connect(self.update_log)

    def start_automation(self, data):
        # 설정값 로드
        user_id = self.settings.value("id", "")
        user_pw = self.settings.value("pw", "")
        
        if not user_id or not user_pw:
            self.update_log("❌ 오류: 설정 탭에서 ID/PW를 먼저 저장해주세요.")
            self.tabs.setCurrentIndex(2)
            return

        settings_dict = {
            "id": user_id, "pw": user_pw,
            "intro": self.settings.value("intro", ""),
            "outro": self.settings.value("outro", "")
        }

        # 작업자 시작
        self.worker = AutomationWorker(data, settings_dict)
        self.worker.log_signal.connect(self.update_log)
        self.worker.result_signal.connect(self.tab_info.update_result_view)
        self.worker.start()

    @Slot(str)
    def update_log(self, msg):
        self.log_area.append(msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
