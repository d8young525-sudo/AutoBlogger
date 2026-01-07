import requests
from PySide6.QtCore import QThread, Signal
from automation import NaverBlogBot

BACKEND_URL = "https://generate-blog-post-yahp6ia25q-du.a.run.app"

class AutomationWorker(QThread):
    log_signal = Signal(str)
    result_signal = Signal(dict)
    finished_signal = Signal()

    def __init__(self, data, settings):
        super().__init__()
        self.data = data
        self.settings = settings
        self.bot = None

    def run(self):
        action = self.data.get('action', 'full')
        
        # 1. 발행만 할 경우
        if action == "publish_only":
            self.run_publish_only()
            return

        # 2. 생성 요청
        res_data = self.run_generation()
        if not res_data:
            self.finished_signal.emit()
            return

        # 결과 전달 (UI 업데이트용)
        self.result_signal.emit(res_data)
        
        if action == "generate":
            self.log_signal.emit("✅ 원고 생성 완료! [결과 뷰어] 탭에서 확인하세요.")
            self.finished_signal.emit()
            return

        # 3. 전체 실행일 경우 바로 발행
        if action == "full":
            self.data['title'] = res_data.get('title', '')
            self.data['content'] = res_data.get('content_text', '') # 기본은 텍스트
            self.run_publish_only()

    def run_generation(self):
        self.log_signal.emit(f"🚀 AI 글 작성 요청 중... (주제: {self.data['topic']})")
        
        # 프롬프트 구성
        emoji_inst = "이모지 사용 안 함"
        if "조금" in self.data.get('emoji_level', ''): emoji_inst = "적절히 사용"
        elif "많이" in self.data.get('emoji_level', ''): emoji_inst = "풍부하게 사용"

        prompt_payload = {
            "mode": "write",
            "topic": self.data['topic'],
            "prompt": f"""
                타겟: {", ".join(self.data.get('targets', []))}
                질문: {" / ".join(self.data.get('questions', []))}
                요약: {self.data.get('summary', '')}
                인사이트: {self.data.get('insight', '')}
                말투: {self.data.get('tone')}
                분량: {self.data.get('length')}
                이모지: {emoji_inst}
                인사말: {self.settings.get('intro', '')}
                맺음말: {self.settings.get('outro', '')}
            """,
            "style_options": str(self.data.get('style_options', {}))
        }

        try:
            res = requests.post(BACKEND_URL, json=prompt_payload, timeout=180)
            if res.status_code == 200:
                return res.json()
            else:
                self.log_signal.emit(f"❌ 서버 에러: {res.text}")
                return None
        except Exception as e:
            self.log_signal.emit(f"❌ 통신 오류: {str(e)}")
            return None

    def run_publish_only(self):
        title = self.data.get('title', '')
        content = self.data.get('content', '')
        
        if not title or not content:
            self.log_signal.emit("❌ 발행할 내용이 없습니다.")
            self.finished_signal.emit()
            return

        self.bot = NaverBlogBot()
        self.log_signal.emit("🚀 브라우저 실행 중...")
        
        try:
            self.bot.start_browser()
            self.log_signal.emit("🔑 로그인 시도...")
            if not self.bot.login(self.settings['id'], self.settings['pw'])[0]:
                self.log_signal.emit("❌ 로그인 실패")
                return
            
            self.log_signal.emit("📝 글쓰기 진입...")
            if not self.bot.go_to_editor()[0]:
                self.log_signal.emit("❌ 에디터 진입 실패")
                return

            self.log_signal.emit("✍️ 본문 작성...")
            if not self.bot.write_content(title, content)[0]:
                self.log_signal.emit("❌ 작성 실패")
                return

            self.log_signal.emit("📤 발행 중...")
            if self.bot.publish_post()[0]:
                self.log_signal.emit("🎉 발행 완료!")
            else:
                self.log_signal.emit("❌ 발행 실패")
                
        except Exception as e:
            self.log_signal.emit(f"💥 치명적 오류: {str(e)}")
        finally:
            self.finished_signal.emit()
