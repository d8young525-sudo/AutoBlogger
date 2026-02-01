"""
Hashtag Generator
주제/본문 분석을 통한 해시태그 자동 생성
Gemini + Google Search grounding → 백엔드 AI → 로컬 키워드 추출 순으로 폴백
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


def _generate_via_gemini_grounding(title: str, content: str, max_tags: int = 10) -> List[str]:
    """Gemini + Google Search grounding으로 트렌드 반영 해시태그 생성"""
    api_key = Config.GEMINI_API_KEY
    if not api_key:
        return []

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        prompt = (
            f"네이버 블로그 해시태그를 생성해주세요.\n\n"
            f"제목: {title}\n"
            f"본문 요약: {content[:800]}\n\n"
            f"조건:\n"
            f"- 네이버 블로그에서 실제 검색량이 높은 태그 위주로 {max_tags}개\n"
            f"- 주제 직접 관련 태그 5개 + 연관 트렌드/롱테일 태그 5개\n"
            f"- 너무 광범위한 태그(일상, 블로그 등) 제외\n"
            f"- 2~6글자 한글 태그\n"
            f"- 쉼표로 구분, # 기호 없이 태그만 한 줄로 출력\n"
            f"- 다른 설명 없이 태그만 출력"
        )

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.7,
            ),
        )

        text = response.text.strip()
        tags = [t.strip().replace("#", "") for t in text.split(",")]
        tags = [t for t in tags if t and 2 <= len(t) <= 20]
        if len(tags) >= 3:
            return tags[:max_tags]
        return []

    except Exception as e:
        logger.warning(f"Gemini grounding hashtag failed: {e}")
        return []


class HashtagWorker(QThread):
    """해시태그 생성 워커: Gemini grounding → 백엔드 AI → 로컬 추출"""
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, title: str, content: str, auth_token: str = ""):
        super().__init__()
        self.title = title
        self.content = content
        self.auth_token = auth_token

    def run(self):
        try:
            # 1순위: Gemini + Google Search grounding
            tags = _generate_via_gemini_grounding(self.title, self.content)
            if tags:
                logger.info(f"Hashtags generated via Gemini grounding: {tags}")
                self.finished.emit(tags)
                return

            # 2순위: 백엔드 AI
            if self.auth_token:
                tags = self._generate_via_ai()
                if tags:
                    self.finished.emit(tags)
                    return

            # 3순위: 로컬 추출
            tags = extract_tags_local(self.title, self.content)
            self.finished.emit(tags)

        except Exception as e:
            logger.error(f"Hashtag generation error: {e}")
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
                if content_text:
                    tags = [t.strip().replace("#", "") for t in content_text.split(",")]
                    tags = [t for t in tags if t and len(t) >= 2]
                    if tags:
                        return tags[:10]

            return []

        except Exception as e:
            logger.warning(f"AI hashtag generation failed: {e}")
            return []
