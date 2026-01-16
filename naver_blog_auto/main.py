import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QLineEdit, QPushButton, QTextEdit, QLabel, QMessageBox)
from PySide6.QtCore import QThread, Signal, Slot
from automation import NaverBlogBot

class AutomationWorker(QThread):
    """자동화 로직을 백그라운드에서 실행하는 워커 스레드"""
    log_signal = Signal(str)  # UI로 로그 메시지를 보내는 신호
    finished_signal = Signal() # 작업 종료 신호

    def __init__(self, user_id, user_pw):
        super().__init__()
        self.user_id = user_id
        self.user_pw = user_pw
        self.bot = None

    def run(self):
        self.log_signal.emit("🚀 브라우저 시작 중...")
        self.bot = NaverBlogBot()
        
        try:
            self.bot.start_browser()
            self.log_signal.emit("✅ 브라우저 실행 완료")

            # 1. 로그인
            self.log_signal.emit("🔑 로그인 시도 중...")
            success, msg = self.bot.login(self.user_id, self.user_pw)
            if not success:
                self.log_signal.emit(f"❌ {msg}")
                return
            self.log_signal.emit(f"✅ {msg}")

            # 2. 에디터 이동
            self.log_signal.emit("📝 글쓰기 에디터로 이동 중 (메인->블로그->글쓰기)...")
            success, msg = self.bot.go_to_editor()
            if not success:
                self.log_signal.emit(f"❌ {msg}")
                return
            self.log_signal.emit(f"✅ {msg}")

            # 3. 글 작성
            self.log_signal.emit("✍️ 제목 및 본문 작성 중...")
            # 실제로는 여기서 생성형 AI가 만든 텍스트를 넣게 됩니다.
            title = "자동차 영업사원이 알려주는 겨울철 차량 관리 꿀팁"
            content = "안녕하세요. 이웃님들!\n\n오늘은 날씨가 추워지면서 배터리 방전이나 타이어 공기압 경고등으로 당황하시는 분들을 위해 겨울철 필수 차량 관리 상식을 정리해봤습니다.\n\n다들 안전운전 하시길 바랍니다!"
            
            success, msg = self.bot.write_content(title, content)
            if not success:
                self.log_signal.emit(f"❌ {msg}")
                # 작성 실패해도 브라우저 끄지 않고 유지 (디버깅용)
                return
            self.log_signal.emit(f"✅ {msg}")

            # 4. 발행
            self.log_signal.emit("📤 발행 버튼 클릭 중...")
            success, msg = self.bot.publish_post()
            if not success:
                self.log_signal.emit(f"❌ {msg}")
                return
            self.log_signal.emit(f"🎉 {msg}")

        except Exception as e:
            self.log_signal.emit(f"💥 치명적 오류 발생: {str(e)}")
        finally:
            self.finished_signal.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("네이버 블로그 포스팅 봇 v0.2")
        self.resize(400, 500)

        # UI 컴포넌트 설정
        container = QWidget()
        layout = QVBoxLayout()

        # ID 입력
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("네이버 아이디")
        layout.addWidget(QLabel("아이디:"))
        layout.addWidget(self.id_input)

        # PW 입력
        self.pw_input = QLineEdit()
        self.pw_input.setPlaceholderText("네이버 비밀번호")
        self.pw_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(QLabel("비밀번호:"))
        layout.addWidget(self.pw_input)

        # 로그창
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(QLabel("진행 로그:"))
        layout.addWidget(self.log_area)

        # 시작 버튼
        self.start_btn = QPushButton("자동 포스팅 시작")
        self.start_btn.clicked.connect(self.start_automation)
        self.start_btn.setStyleSheet("background-color: #03C75A; color: white; font-weight: bold; padding: 10px;")
        layout.addWidget(self.start_btn)

        container.setLayout(layout)
        self.setCentralWidget(container)

    def start_automation(self):
        user_id = self.id_input.text().strip()
        user_pw = self.pw_input.text().strip()

        if not user_id or not user_pw:
            QMessageBox.warning(self, "경고", "아이디와 비밀번호를 입력해주세요.")
            return

        self.start_btn.setEnabled(False) # 중복 실행 방지
        self.log_area.clear()
        
        # 워커 스레드 시작
        self.worker = AutomationWorker(user_id, user_pw)
        self.worker.log_signal.connect(self.update_log)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    @Slot(str)
    def update_log(self, msg):
        self.log_area.append(msg)

    @Slot()
    def on_finished(self):
        self.start_btn.setEnabled(True)
        QMessageBox.information(self, "완료", "작업이 종료되었습니다. 브라우저를 확인하세요.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
