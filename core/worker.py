"""
Automation Worker Module
백그라운드 작업 처리를 위한 Worker Thread
v3.8.0: blocks 기반 에디터 조작 지원 추가
"""
import logging
from typing import Dict, Any, Optional

import requests
from PySide6.QtCore import QThread, Signal

from automation import NaverBlogBot
from config import Config

logger = logging.getLogger(__name__)


class AutomationWorker(QThread):
    """Background worker for blog automation tasks"""
    
    log_signal = Signal(str)
    result_signal = Signal(dict)
    finished_signal = Signal()
    error_signal = Signal(str)
    progress_signal = Signal(int)

    def __init__(self, data: Dict[str, Any], settings: Dict[str, str]):
        """
        Initialize worker
        
        Args:
            data: Task data including topic, action, etc.
            settings: User settings including credentials
        """
        super().__init__()
        self.data = data
        self.settings = settings
        self.bot: Optional[NaverBlogBot] = None
        self._is_cancelled = False

    def cancel(self):
        """Cancel the current operation"""
        self._is_cancelled = True
        if self.bot:
            self.bot.close()

    def run(self):
        """Main worker execution"""
        try:
            action = self.data.get('action', 'full')
            
            # Publish only mode
            if action == "publish_only":
                self._run_publish_only()
                return

            # Generate content
            self.progress_signal.emit(10)
            res_data = self._run_generation()
            
            if not res_data or self._is_cancelled:
                self.finished_signal.emit()
                return

            # Emit result for UI update
            self.result_signal.emit(res_data)
            self.progress_signal.emit(50)
            
            if action == "generate":
                self.log_signal.emit("✅ 원고 생성 완료! [결과 뷰어] 탭에서 확인하세요.")
                self.progress_signal.emit(100)
                self.finished_signal.emit()
                return

            # Full automation: generate and publish
            if action == "full":
                self.data['title'] = res_data.get('title', '')
                # API 응답 키가 content 또는 content_text일 수 있음
                self.data['content'] = res_data.get('content', '') or res_data.get('content_text', '')
                # blocks 데이터 전달 (Selenium 에디터 조작용)
                self.data['blocks'] = res_data.get('blocks', [])
                
                if not self.data['content']:
                    self.log_signal.emit("❌ 생성된 본문 내용이 없습니다.")
                    self.finished_signal.emit()
                    return
                    
                self.log_signal.emit("📤 발행 프로세스 시작...")
                self._run_publish_only()
                
        except Exception as e:
            logger.error(f"Worker error: {e}")
            self.error_signal.emit(f"작업 중 오류 발생: {str(e)}")
        finally:
            self.progress_signal.emit(100)
            self.finished_signal.emit()

    def _run_generation(self) -> Optional[Dict[str, Any]]:
        """
        Request content generation from backend API
        
        Returns:
            Generated content data or None on failure
        """
        topic = self.data.get('topic', '')
        self.log_signal.emit(f"🚀 AI 글 작성 요청 중... (주제: {topic})")
        
        # Build emoji instruction
        emoji_level = self.data.get('emoji_level', '')
        if "조금" in emoji_level:
            emoji_inst = "적절히 사용"
        elif "많이" in emoji_level:
            emoji_inst = "풍부하게 사용"
        else:
            emoji_inst = "이모지 사용 안 함"

        # 스타일 옵션 가져오기
        style_options = self.data.get('style_options', {})
        
        # Build request payload (API 스펙에 맞게)
        prompt_payload = {
            "mode": "write",
            "topic": topic,
            "targets": self.data.get('targets', []),
            "questions": self.data.get('questions', []),
            "summary": self.data.get('summary', ''),
            "insight": self.data.get('insight', ''),
            "tone": self.data.get('tone', '친근한 이웃 (해요체)'),
            "length": self.data.get('length', '보통 (1,500자)'),
            "emoji_level": self.data.get('emoji_level', '사용 안 함'),
            "intro": self.settings.get('intro', ''),
            "outro": self.settings.get('outro', ''),
            "output_style": style_options,  # 출력 스타일 설정
        }

        try:
            response = requests.post(
                Config.BACKEND_URL, 
                json=prompt_payload, 
                timeout=Config.API_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                self.log_signal.emit("✅ AI 글 생성 완료!")
                return result
            else:
                error_msg = f"서버 에러 ({response.status_code}): {response.text[:200]}"
                self.log_signal.emit(f"❌ {error_msg}")
                logger.error(error_msg)
                return None
                
        except requests.Timeout:
            self.log_signal.emit("❌ 서버 응답 시간 초과 (3분)")
            return None
        except requests.ConnectionError:
            self.log_signal.emit("❌ 서버 연결 실패 - 네트워크를 확인하세요")
            return None
        except Exception as e:
            self.log_signal.emit(f"❌ 통신 오류: {str(e)}")
            logger.error(f"API request failed: {e}")
            return None

    def _run_publish_only(self):
        """Execute blog publishing"""
        title = self.data.get('title', '')
        content = self.data.get('content', '')
        blocks = self.data.get('blocks', [])  # 구조화된 블록 데이터
        category = self.data.get('category', '') or self.settings.get('default_category', '')
        
        if not title or not content:
            self.log_signal.emit("❌ 발행할 내용이 없습니다.")
            return

        user_id = self.settings.get('id', '')
        user_pw = self.settings.get('pw', '')
        
        if not user_id or not user_pw:
            self.log_signal.emit("❌ 네이버 계정 정보가 없습니다. 설정 탭에서 입력해주세요.")
            return

        # Create bot instance with context manager for proper cleanup
        self.bot = NaverBlogBot()
        
        # 카테고리 설정
        if category:
            self.bot.set_category(category)
            self.log_signal.emit(f"📁 카테고리: {category}")
        
        try:
            # Step 1: Start browser
            self.log_signal.emit("🚀 브라우저 실행 중...")
            self.progress_signal.emit(60)
            
            success, msg = self.bot.start_browser()
            if not success:
                self.log_signal.emit(f"❌ 브라우저 실행 실패: {msg}")
                return
            
            if self._is_cancelled:
                return
            
            # Step 2: Login
            self.log_signal.emit("🔑 로그인 시도...")
            self.progress_signal.emit(70)
            
            success, msg = self.bot.login(user_id, user_pw)
            if not success:
                self.log_signal.emit(f"❌ 로그인 실패: {msg}")
                return
            
            if self._is_cancelled:
                return
            
            # Step 3: Navigate to editor
            self.log_signal.emit("📝 글쓰기 페이지 진입...")
            self.progress_signal.emit(80)
            
            success, msg = self.bot.go_to_editor()
            if not success:
                self.log_signal.emit(f"❌ 에디터 진입 실패: {msg}")
                return
            
            if self._is_cancelled:
                return
            
            # Step 4: Write content (blocks 또는 plain text)
            self.log_signal.emit("✍️ 본문 작성 중...")
            self.progress_signal.emit(85)
            
            # blocks가 있고 유효하면 에디터 도구를 사용하여 서식 적용
            if blocks and isinstance(blocks, list) and len(blocks) > 0:
                self.log_signal.emit(f"🎨 서식 적용 모드: {len(blocks)}개 블록")
                success, msg = self.bot.write_content_with_blocks(title, blocks)
            else:
                # 기존 방식: 평문 붙여넣기
                self.log_signal.emit("📝 일반 텍스트 모드")
                success, msg = self.bot.write_content(title, content)
            
            if not success:
                self.log_signal.emit(f"❌ 작성 실패: {msg}")
                return
            
            if self._is_cancelled:
                return
            
            # Step 4.5: Upload cover image (if provided)
            thumbnail_path = self.data.get('thumbnail_path', '')
            if thumbnail_path:
                self.log_signal.emit("🖼️ 대표 이미지 등록 중...")
                self.progress_signal.emit(90)
                
                success, msg = self.bot.upload_cover_image(thumbnail_path)
                if success:
                    self.log_signal.emit("✅ 대표 이미지 등록 완료!")
                else:
                    self.log_signal.emit(f"⚠️ 대표 이미지 등록 실패: {msg}")
                    # 이미지 실패해도 발행은 계속 진행
            
            if self._is_cancelled:
                return
            
            # Step 5: Publish (with category)
            self.log_signal.emit("📤 발행 중...")
            self.progress_signal.emit(95)
            
            success, msg = self.bot.publish_post(category=category)
            if success:
                self.log_signal.emit("🎉 발행 완료!")
                self.progress_signal.emit(100)
            else:
                self.log_signal.emit(f"❌ 발행 실패: {msg}")
                
        except Exception as e:
            self.log_signal.emit(f"💥 치명적 오류: {str(e)}")
            logger.error(f"Publishing failed: {e}")
        finally:
            # Cleanup - close browser
            if self.bot:
                self.bot.close()
                self.bot = None
