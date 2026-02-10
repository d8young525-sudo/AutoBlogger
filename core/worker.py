"""
Automation Worker Module
백그라운드 작업 처리를 위한 Worker Thread
"""
import base64
import json
import logging
import tempfile
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

import requests
from PySide6.QtCore import QThread, Signal

from automation import NaverBlogBot
from config import Config
from core.content_converter import ContentConverter
from core.image_generator import GeminiImageGenerator
from core.post_history import add_post

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
                self.log_signal.emit("원고 생성 완료!")
                self.progress_signal.emit(100)
                self.finished_signal.emit()
                return

            # Full automation: generate and publish
            if action == "full":
                self.data['title'] = res_data.get('title', '')
                # API 응답 키가 content 또는 content_text일 수 있음
                self.data['content'] = res_data.get('content', '') or res_data.get('content_text', '')
                # API 응답의 blocks 직접 전달
                if 'blocks' in res_data:
                    self.data['blocks'] = res_data['blocks']
                
                if not self.data['content']:
                    self.log_signal.emit("생성된 본문 내용이 없습니다.")
                    self.finished_signal.emit()
                    return
                    
                self.log_signal.emit("발행 프로세스 시작...")
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
        self.log_signal.emit(f"AI 글 작성 요청 중... (주제: {topic})")
        
        # Build emoji instruction
        emoji_level = self.data.get('emoji_level', '')
        if "조금" in emoji_level:
            emoji_inst = "적절히 사용"
        elif "많이" in emoji_level:
            emoji_inst = "풍부하게 사용"
        else:
            emoji_inst = "이모지 사용 안 함"

        # 네이버 에디터 서식 설정 가져오기
        naver_style = self.data.get('naver_style', {})
        
        # Build request payload
        prompt_payload = {
            "mode": "write",
            "topic": topic,
            "targets": self.data.get('targets', []),
            "questions": self.data.get('questions', []),
            "summary": self.data.get('summary', ''),
            "insight": self.data.get('insight', ''),
            "tone": self.data.get('tone', '친근한 이웃 (해요체)'),
            "length": self.data.get('length', '보통 (1,500자)'),
            "emoji_level": emoji_inst,
            "intro": self.settings.get('intro', ''),
            "outro": self.settings.get('outro', ''),
            "prompt": f"""
                타겟: {", ".join(self.data.get('targets', []))}
                질문: {" / ".join(self.data.get('questions', []))}
                요약: {self.data.get('summary', '')}
                인사이트: {self.data.get('insight', '')}
                말투: {self.data.get('tone', '친근한 이웃 (해요체)')}
                분량: {self.data.get('length', '보통 (1,500자)')}
                이모지: {emoji_inst}
                인사말: {self.settings.get('intro', '')}
                맺음말: {self.settings.get('outro', '')}
            """,
            "style_options": str(self.data.get('style_options', {})),
            "naver_style": naver_style,
            "structure_style": self.data.get('post_structure', 'default'),
            "structure_params": self.data.get('structure_params', {})
        }

        try:
            response = requests.post(
                Config.BACKEND_URL, 
                json=prompt_payload, 
                timeout=Config.API_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                self.log_signal.emit("AI 글 생성 완료!")
                return result
            else:
                error_msg = f"서버 에러 ({response.status_code}): {response.text[:200]}"
                self.log_signal.emit(f"{error_msg}")
                logger.error(error_msg)
                return None

        except requests.Timeout:
            self.log_signal.emit("서버 응답 시간 초과 (3분)")
            return None
        except requests.ConnectionError:
            self.log_signal.emit("서버 연결 실패 - 네트워크를 확인하세요")
            return None
        except Exception as e:
            self.log_signal.emit(f"통신 오류: {str(e)}")
            logger.error(f"API request failed: {e}")
            return None

    def _run_publish_only(self):
        """Execute blog publishing"""
        title = self.data.get('title', '')
        content = self.data.get('content', '')
        category = self.data.get('category', '') or self.settings.get('default_category', '')
        
        if not title or not content:
            self.log_signal.emit("발행할 내용이 없습니다.")
            return

        user_id = self.settings.get('id', '')
        user_pw = self.settings.get('pw', '')
        
        if not user_id or not user_pw:
            self.log_signal.emit("네이버 계정 정보가 없습니다. 설정 탭에서 입력해주세요.")
            return

        # Create bot instance with context manager for proper cleanup
        self.bot = NaverBlogBot()
        
        # 카테고리 설정
        if category:
            self.bot.set_category(category)
            self.log_signal.emit(f"카테고리: {category}")
        
        try:
            # Step 1: Start browser
            self.log_signal.emit("브라우저 실행 중...")
            self.progress_signal.emit(60)
            
            success, msg = self.bot.start_browser()
            if not success:
                self.log_signal.emit(f"브라우저 실행 실패: {msg}")
                return
            
            if self._is_cancelled:
                return
            
            # Step 2: Login
            self.log_signal.emit("로그인 시도...")
            self.progress_signal.emit(70)
            
            success, msg = self.bot.login(user_id, user_pw)
            if not success:
                self.log_signal.emit(f"로그인 실패: {msg}")
                return
            
            if self._is_cancelled:
                return
            
            # Step 3: Navigate to editor
            self.log_signal.emit("글쓰기 페이지 진입...")
            self.progress_signal.emit(80)
            
            success, msg = self.bot.go_to_editor()
            if not success:
                self.log_signal.emit(f"에디터 진입 실패: {msg}")
                return
            
            if self._is_cancelled:
                return

            # Step 3.5: 대표 이미지(썸네일) 업로드
            thumbnail_path = None
            images_data = self.data.get('images', {})
            thumbnail_b64 = images_data.get('thumbnail')
            if thumbnail_b64:
                self.log_signal.emit("대표 이미지 업로드 중...")
                thumbnail_path = self._save_thumbnail_temp(thumbnail_b64)
                if thumbnail_path:
                    success, msg = self.bot.upload_cover_image(thumbnail_path)
                    if success:
                        self.log_signal.emit("대표 이미지 업로드 완료")
                    else:
                        self.log_signal.emit(f"대표 이미지 업로드 실패: {msg}")

            if self._is_cancelled:
                self._cleanup_thumbnail(thumbnail_path)
                return

            # Step 3.6: 본문 이미지 생성
            image_paths = {}
            naver_style = self.data.get('naver_style', {})
            blocks = self.data.get('blocks', None)
            if not blocks:
                blocks = self._text_to_blocks(content)

            if blocks:
                # 인용구 필터링: 실제 인용문만 quotation 유지
                blocks = self._filter_quotation_blocks(blocks)
                image_paths = self._generate_content_images(blocks)

            if self._is_cancelled:
                self._cleanup_temp_images(image_paths)
                return

            # Step 4: 콘텐츠 작성 (DOM 방식 - blocks 기반 서식 적용)
            self.log_signal.emit("콘텐츠 작성 중 (서식 적용)...")
            self.progress_signal.emit(85)

            # 디버그용 JSON 저장 (서식 적용 추적)
            tags = self.data.get('tags', '')
            self._save_debug_json(title, blocks, naver_style, tags)

            if blocks:
                self.log_signal.emit(f"블록 변환 완료 ({len(blocks)}개 블록)")
                success, msg = self.bot.write_content_with_blocks(title, blocks, image_paths=image_paths, naver_style=naver_style)
            else:
                self.log_signal.emit("블록 변환 실패, 텍스트 방식으로 작성...")
                success, msg = self.bot.write_content(title, content)
            
            if not success:
                self.log_signal.emit(f"작성 실패: {msg}")
                return
            
            if self._is_cancelled:
                return
            
            if self._is_cancelled:
                return

            # Step 5: 발행 (태그는 발행 팝업 내에서 입력)
            tags = self.data.get('tags', '')
            self.log_signal.emit("발행 중...")
            self.progress_signal.emit(95)

            success, msg = self.bot.publish_post(category=category, tags=tags)
            if success:
                self.log_signal.emit("발행 완료!")
                self.progress_signal.emit(100)
                self._record_publish(title, content, category)
            else:
                self.log_signal.emit(f"발행 실패: {msg}")
                
        except Exception as e:
            self.log_signal.emit(f"치명적 오류: {str(e)}")
            logger.error(f"Publishing failed: {e}")
        finally:
            # Cleanup - close browser and temp images
            self._cleanup_temp_images(image_paths)
            self._cleanup_thumbnail(thumbnail_path)
            if self.bot:
                self.bot.close()
                self.bot = None

    def _generate_content_images(self, blocks: list) -> dict:
        """
        blocks에서 image_placeholder를 찾아 최대 3개 이미지 생성.
        Returns: {block_index: file_path} 매핑
        """
        import random

        structure_params = self.data.get('structure_params', {})
        structure_mode = structure_params.get('mode', 'auto')

        if structure_mode == 'auto':
            # 자동 모드: 1~3개 랜덤
            max_images = random.randint(1, 3)
            self.log_signal.emit(f"자동 모드: 본문 이미지 {max_images}개 생성 예정")
        else:
            # 수동 모드: 설정값 사용
            max_images = min(structure_params.get('image_count', 2), 3)

        if max_images <= 0:
            return {}

        # image_placeholder 블록 인덱스 수집
        placeholders = []
        for i, block in enumerate(blocks):
            if block.get('type') == 'image_placeholder':
                placeholders.append((i, block.get('description', '')))

        if not placeholders:
            return {}

        # 균등 간격으로 max_images개 선택
        if len(placeholders) <= max_images:
            selected = placeholders
        else:
            step = len(placeholders) / max_images
            selected = [placeholders[int(step * j)] for j in range(max_images)]

        self.log_signal.emit(f"본문 이미지 생성 중 ({len(selected)}개)...")

        generator = GeminiImageGenerator()
        if not generator.is_available():
            self.log_signal.emit("이미지 생성 API 키 미설정, 이미지 생략")
            return {}

        image_paths = {}
        topic = self.data.get('topic', '')

        for idx, (block_idx, description) in enumerate(selected):
            if self._is_cancelled:
                break

            prompt = f"{topic} - {description}" if description else topic
            self.log_signal.emit(f"  이미지 {idx + 1}/{len(selected)} 생성 중...")

            try:
                tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                tmp.close()

                success, msg, img_bytes = generator.generate_blog_image(
                    topic=prompt,
                    style="본문 삽화",
                    output_path=tmp.name,
                    aspect_ratio="16:9"
                )

                if success and img_bytes:
                    image_paths[block_idx] = tmp.name
                    logger.info(f"Content image {idx + 1} generated: {tmp.name}")
                else:
                    os.unlink(tmp.name)
                    logger.warning(f"Content image {idx + 1} failed: {msg}")

            except Exception as e:
                logger.error(f"Content image generation error: {e}")

        if image_paths:
            self.log_signal.emit(f"본문 이미지 {len(image_paths)}개 생성 완료")
        return image_paths

    def _cleanup_temp_images(self, image_paths: dict):
        """임시 이미지 파일 정리"""
        for path in image_paths.values():
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except Exception:
                pass

    def _save_thumbnail_temp(self, thumbnail_b64: str) -> Optional[str]:
        """
        base64 썸네일 이미지를 임시 파일로 저장

        Args:
            thumbnail_b64: base64 인코딩된 이미지 데이터

        Returns:
            임시 파일 경로 또는 None
        """
        try:
            # base64 디코딩
            img_data = base64.b64decode(thumbnail_b64)

            # 임시 파일 생성
            temp_dir = tempfile.gettempdir()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_path = os.path.join(temp_dir, f"thumbnail_{timestamp}.png")

            with open(temp_path, 'wb') as f:
                f.write(img_data)

            logger.info(f"Thumbnail saved to temp: {temp_path}")
            return temp_path

        except Exception as e:
            logger.error(f"Failed to save thumbnail: {e}")
            return None

    def _cleanup_thumbnail(self, thumbnail_path: Optional[str]):
        """썸네일 임시 파일 정리"""
        if thumbnail_path:
            try:
                if os.path.exists(thumbnail_path):
                    os.unlink(thumbnail_path)
            except Exception:
                pass

    def _text_to_blocks(self, content: str) -> list:
        """
        텍스트를 blocks 배열로 변환 (DOM 방식 서식 적용용)
        
        Returns:
            list of block dicts: [{"type": "heading", "text": "..."}, ...]
        """
        try:
            converter = ContentConverter()
            parsed = converter.parse_text_content(content)
            
            blocks = []
            for section in parsed.get("sections", []):
                # 소제목
                heading = section.get("heading", "")
                if heading:
                    blocks.append({"type": "heading", "text": heading, "level": 2})
                
                # 섹션 내용
                for item in section.get("content", []):
                    item_type = item.get("type", "paragraph")
                    item_text = item.get("text", "")
                    
                    if item_type == "paragraph":
                        if item_text.strip():
                            blocks.append({"type": "paragraph", "text": item_text})
                    elif item_type == "question":
                        blocks.append({"type": "quotation", "text": f"Q. {item_text}"})
                    elif item_type == "answer":
                        blocks.append({"type": "paragraph", "text": f"A. {item_text}"})
                    elif item_type == "list_item":
                        # 연속된 리스트 아이템은 하나의 list 블록으로 모음
                        if blocks and blocks[-1].get("type") == "list":
                            blocks[-1]["items"].append(item_text)
                        else:
                            blocks.append({"type": "list", "style": "bullet", "items": [item_text]})
                    elif item_type == "divider":
                        blocks.append({"type": "divider"})
                    else:
                        if item_text.strip():
                            blocks.append({"type": "paragraph", "text": item_text})
            
            logger.info(f"Converted text to {len(blocks)} blocks")
            return blocks
            
        except Exception as e:
            logger.warning(f"Failed to convert text to blocks: {e}")
            return []

    def _filter_quotation_blocks(self, blocks: list) -> list:
        """
        실제 인용문만 quotation으로 유지, 장식용 인용은 paragraph로 변환.

        인용문 판별 기준:
        - "~라고 말했다/밝혔다/전했다" 등 인용 표현
        - "~에 따르면" 출처 표현
        - 따옴표로 시작/끝나는 문장
        """
        import re

        # 실제 인용문 패턴
        quote_patterns = [
            r'.*라고\s*(말했|밝혔|전했|설명했|강조했|덧붙였)',
            r'.*에\s*따르면',
            r'.*출처[:：]',
            r'^["\'].*["\']$',  # 따옴표로 감싸진 문장
            r'^「.*」$',  # 겹낫표
            r'^『.*』$',  # 겹화살괄호
        ]

        filtered = []
        for block in blocks:
            if block.get("type") == "quotation":
                text = block.get("text", "").strip()

                # 실제 인용문인지 확인
                is_real_quote = any(re.search(p, text) for p in quote_patterns)

                if is_real_quote:
                    # 실제 인용문은 그대로 유지
                    filtered.append(block)
                else:
                    # 장식용 인용은 paragraph + 강조 이모지로 변환
                    # 「」 기호 제거
                    clean_text = text.strip("「」『』")
                    filtered.append({
                        "type": "paragraph",
                        "text": clean_text if clean_text else text
                    })
                    logger.debug(f"Quotation converted to paragraph: {text[:30]}")
            else:
                filtered.append(block)

        return filtered

    def _save_debug_json(self, title: str, blocks: list, naver_style: dict, tags: str = ""):
        """디버그용 JSON 저장 - 전체 설정값 포함"""
        try:
            debug_dir = Path("logs/debug")
            debug_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = "".join(c for c in title[:20] if c.isalnum() or c in " _-가-힣").strip()
            filename = f"{timestamp}_{safe_title}.json"

            # 전체 설정값 수집
            settings = {
                "topic": self.data.get("topic", ""),
                "mode": self.data.get("mode", "info"),
                "tone": self.data.get("tone", ""),
                "length": self.data.get("length", ""),
                "emoji_level": self.data.get("emoji_level", ""),
                "category": self.data.get("category", ""),
                "targets": self.data.get("targets", []),
                "questions": self.data.get("questions", []),
                "summary": self.data.get("summary", ""),
                "insight": self.data.get("insight", ""),
                "intro": self.settings.get("intro", ""),
                "outro": self.settings.get("outro", ""),
                "post_structure": self.data.get("post_structure", "default"),
                "structure_params": self.data.get("structure_params", {})
            }

            data = {
                "timestamp": timestamp,
                "title": title,
                "tags": tags,
                "blocks": blocks,
                "block_count": len(blocks) if blocks else 0,
                "block_types": [b.get("type") for b in blocks] if blocks else [],
                "naver_style": naver_style,
                "settings": settings
            }

            filepath = debug_dir / filename
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"Debug JSON saved: {filepath}")
            self.log_signal.emit(f"디버그 JSON 저장: {filename}")

        except Exception as e:
            logger.warning(f"Failed to save debug JSON: {e}")

    def _record_publish(self, title: str, content: str, category: str):
        """발행 성공 시 이력 기록"""
        try:
            topic = self.data.get("topic", "")
            mode = self.data.get("mode", "info")
            tags = self.data.get("tags", "")
            add_post(
                title=title,
                topic=topic,
                category=category,
                mode=mode,
                content_preview=content[:200] if content else "",
                tags=tags
            )
        except Exception as e:
            logger.warning(f"Failed to record post history: {e}")
