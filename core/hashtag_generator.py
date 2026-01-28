"""
Hashtag Generator
주제/본문 분석을 통한 해시태그 자동 생성
백엔드 AI API를 사용하거나, 로컬 키워드 추출로 폴백
"""
import re
import logging
from typing import List
from collections import Counter

import requests
from PySide6.QtCore import QThread, Signal

from config import Config

logger = logging.getLogger(__name__)


def extract_tags_local(title: str, content: str, max_tags: int = 10) -> List[str]:
    """
    로컬 키워드 추출 기반 해시태그 생성 (AI 없이).
    
    한글 명사/키워드를 빈도 기반으로 추출합니다.
    """
    text = f"{title} {content}"
    
    # 한글 2글자 이상 단어 추출
    words = re.findall(r'[가-힣]{2,}', text)
    
    # 불용어 제거
    stopwords = {
        "하는", "있는", "되는", "이는", "그는", "것은", "에서", "으로",
        "하고", "있고", "되고", "에게", "부터", "까지", "이다", "합니다",
        "있습니다", "됩니다", "것입니다", "대한", "통해", "위해", "따라",
        "경우", "때문", "이후", "이전", "사이", "관련", "포함", "기준",
        "정도", "이상", "이하", "그리고", "하지만", "그래서", "때문에",
        "그러나", "또한", "즉", "바로", "정말", "매우", "아주", "특히",
        "해요", "할까요", "인데요", "거든요", "같아요", "볼까요",
    }
    
    filtered = [w for w in words if w not in stopwords and len(w) >= 2]
    
    # 빈도 기반 상위 키워드
    counter = Counter(filtered)
    top_words = [word for word, _ in counter.most_common(max_tags * 2)]
    
    # 제목 키워드 우선 포함
    title_words = re.findall(r'[가-힣]{2,}', title)
    title_keywords = [w for w in title_words if w not in stopwords]
    
    # 제목 키워드 + 빈도 키워드 합치기 (중복 제거)
    result = []
    seen = set()
    for w in title_keywords + top_words:
        if w not in seen:
            result.append(w)
            seen.add(w)
        if len(result) >= max_tags:
            break
    
    return result


class HashtagWorker(QThread):
    """AI 기반 해시태그 생성 워커"""
    finished = Signal(list)
    error = Signal(str)
    
    def __init__(self, title: str, content: str, auth_token: str = ""):
        super().__init__()
        self.title = title
        self.content = content
        self.auth_token = auth_token
    
    def run(self):
        try:
            # AI 백엔드에 태그 생성 요청 시도
            if self.auth_token:
                tags = self._generate_via_ai()
                if tags:
                    self.finished.emit(tags)
                    return
            
            # Fallback: 로컬 추출
            tags = extract_tags_local(self.title, self.content)
            self.finished.emit(tags)
            
        except Exception as e:
            logger.error(f"Hashtag generation error: {e}")
            # 에러 시에도 로컬 추출 시도
            try:
                tags = extract_tags_local(self.title, self.content)
                self.finished.emit(tags)
            except Exception:
                self.error.emit(f"해시태그 생성 실패: {str(e)}")
    
    def _generate_via_ai(self) -> List[str]:
        """백엔드 AI로 태그 생성"""
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            payload = {
                "mode": "write",
                "topic": self.title,
                "prompt": (
                    f"아래 블로그 글에 대한 네이버 블로그 해시태그를 10개 생성해주세요.\n"
                    f"태그만 쉼표로 구분하여 한 줄로 출력하세요. # 기호는 빼고 단어만.\n\n"
                    f"제목: {self.title}\n"
                    f"본문(앞부분): {self.content[:500]}"
                )
            }
            
            response = requests.post(
                Config.BACKEND_URL,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                content_text = data.get("content_text", "") or data.get("content", "")
                # 쉼표 구분 태그 파싱
                if content_text:
                    tags = [t.strip().replace("#", "") for t in content_text.split(",")]
                    tags = [t for t in tags if t and len(t) >= 2]
                    if tags:
                        return tags[:10]
            
            return []
            
        except Exception as e:
            logger.warning(f"AI hashtag generation failed: {e}")
            return []
