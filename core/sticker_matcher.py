"""
스티커 문맥 매칭 모듈
텍스트에서 감정 키워드를 추출하고 sticker_map.json에서 적합한 스티커를 선택합니다.
"""
import json
import logging
import random
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).parent.parent / "assets" / "stickers"

# 한국어 감정 키워드 사전
EMOTION_KEYWORDS = {
    "happy": [
        "기쁜", "좋은", "즐거운", "행복", "축하", "감사", "추천", "최고",
        "만족", "편리", "효과", "장점", "좋아", "괜찮", "훌륭", "완벽"
    ],
    "sad": [
        "슬픈", "아쉬운", "힘든", "걱정", "불안", "우울", "안타까운",
        "아쉽", "단점", "부족", "실망"
    ],
    "surprised": [
        "놀라운", "대박", "충격", "신기", "의외", "깜짝", "놀랍",
        "엄청", "어마어마", "상상이상"
    ],
    "angry": [
        "화나는", "짜증", "불만", "주의", "위험", "경고", "조심",
        "금지", "절대", "심각"
    ],
    "love": [
        "사랑", "예쁜", "좋아하", "매력", "인기", "귀여운", "아름다운",
        "멋진", "세련", "디자인"
    ],
    "thinking": [
        "고민", "비교", "선택", "참고", "팁", "방법", "어떻게",
        "알아보", "확인", "체크", "포인트", "핵심", "중요"
    ],
    "greeting": [
        "안녕", "반가", "소개", "시작", "오늘", "여러분", "처음"
    ],
    "goodbye": [
        "마무리", "정리", "요약", "결론", "끝", "이상으로", "마치",
        "도움이", "되셨", "감사합니다"
    ],
    "excited": [
        "신나", "기대", "두근", "설레", "흥미", "재미", "꿀팁",
        "강추", "필수", "꼭"
    ],
    "tired": [
        "피곤", "지친", "힘들", "어려운", "복잡", "번거로운", "귀찮"
    ],
    "neutral": []
}


class StickerMatcher:
    """텍스트 문맥에 맞는 스티커를 선택하는 매처"""

    def __init__(self, pack_name: Optional[str] = None):
        """
        Args:
            pack_name: 사용할 스티커 팩 이름 (None이면 첫 번째 팩)
        """
        self._sticker_map = None
        self._pack_name = pack_name
        self._used_indices = set()  # 중복 삽입 방지

    @property
    def sticker_map(self) -> dict:
        if self._sticker_map is None:
            self._sticker_map = self._load_sticker_map()
        return self._sticker_map

    def is_available(self) -> bool:
        """sticker_map.json이 존재하고 유효한지 확인"""
        return bool(self.sticker_map.get("packs"))

    def get_available_packs(self) -> list:
        """사용 가능한 팩 이름 목록"""
        return list(self.sticker_map.get("packs", {}).keys())

    def match_sticker(self, text: str) -> Optional[Tuple[str, int]]:
        """
        텍스트 문맥에 맞는 스티커를 선택.

        Args:
            text: 분석할 텍스트 (heading이나 paragraph)

        Returns:
            (pack_name, sticker_index) 또는 None
        """
        if not self.is_available():
            return None

        # 사용할 팩 결정
        packs = self.sticker_map["packs"]
        pack_name = self._pack_name if self._pack_name in packs else next(iter(packs), None)
        if not pack_name:
            return None

        pack = packs[pack_name]
        stickers = pack.get("stickers", [])
        if not stickers:
            return None

        # 텍스트에서 감정 추출
        emotion = self._detect_emotion(text)

        # 해당 감정에 맞는 스티커 필터링
        matching = [
            s for s in stickers
            if emotion in s.get("emotions", []) and s["index"] not in self._used_indices
        ]

        # 매칭되는 게 없으면 전체에서 미사용 스티커 선택
        if not matching:
            matching = [s for s in stickers if s["index"] not in self._used_indices]

        # 그래도 없으면 (전부 사용됨) 리셋
        if not matching:
            self._used_indices.clear()
            matching = stickers

        if not matching:
            return None

        selected = random.choice(matching)
        self._used_indices.add(selected["index"])
        logger.info(f"Sticker matched: pack={pack_name}, idx={selected['index']}, emotion={emotion}, text={text[:30]}")
        return (pack_name, selected["index"])

    def _detect_emotion(self, text: str) -> str:
        """텍스트에서 가장 매칭되는 감정 카테고리 반환"""
        scores = {}
        text_lower = text.lower()

        for emotion, keywords in EMOTION_KEYWORDS.items():
            if not keywords:
                continue
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[emotion] = score

        if scores:
            return max(scores, key=scores.get)
        return "neutral"

    def _load_sticker_map(self) -> dict:
        """sticker_map.json 로드"""
        map_path = ASSETS_DIR / "sticker_map.json"
        if not map_path.exists():
            logger.warning(f"sticker_map.json 없음: {map_path}")
            return {}

        try:
            with open(map_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"sticker_map.json 로드 실패: {e}")
            return {}
