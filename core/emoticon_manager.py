"""
Emoticon Manager Module
네이버 블로그 이모티콘 관리 및 적용
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import re


@dataclass
class EmoticonGroup:
    """이모티콘 그룹 정보"""
    name: str
    description: str
    emoticons: Dict[str, str]  # key: 설명, value: 이모티콘


class EmoticonManager:
    """네이버 블로그 이모티콘 관리자"""
    
    # 기본 이모티콘 그룹들
    EMOTICON_GROUPS: Dict[str, EmoticonGroup] = {
        "basic": EmoticonGroup(
            name="기본 이모지",
            description="일반적인 유니코드 이모지",
            emoticons={
                "좋아요": "👍",
                "박수": "👏",
                "하트": "❤️",
                "별": "⭐",
                "체크": "✅",
                "느낌표": "❗",
                "물음표": "❓",
                "포인트": "👉",
                "전구": "💡",
                "메모": "📝",
                "폴더": "📁",
                "화살표": "➡️",
                "경고": "⚠️",
                "금지": "🚫",
                "시계": "⏰",
            }
        ),
        "business": EmoticonGroup(
            name="비즈니스",
            description="업무/전문 관련 이모지",
            emoticons={
                "차트상승": "📈",
                "차트하락": "📉",
                "돈": "💰",
                "계약": "📋",
                "악수": "🤝",
                "전화": "📞",
                "이메일": "📧",
                "노트북": "💻",
                "달력": "📅",
                "목표": "🎯",
            }
        ),
        "car": EmoticonGroup(
            name="자동차",
            description="자동차/운전 관련 이모지",
            emoticons={
                "자동차": "🚗",
                "SUV": "🚙",
                "스포츠카": "🏎️",
                "트럭": "🚚",
                "버스": "🚌",
                "주유소": "⛽",
                "충전": "🔌",
                "열쇠": "🔑",
                "도로": "🛣️",
                "신호등": "🚦",
            }
        ),
        "food": EmoticonGroup(
            name="음식/맛집",
            description="음식/요리 관련 이모지",
            emoticons={
                "레스토랑": "🍽️",
                "피자": "🍕",
                "햄버거": "🍔",
                "커피": "☕",
                "케이크": "🎂",
                "과일": "🍎",
                "요리사": "👨‍🍳",
                "맛있음": "😋",
                "별점": "⭐",
                "추천": "👌",
            }
        ),
        "travel": EmoticonGroup(
            name="여행",
            description="여행/관광 관련 이모지",
            emoticons={
                "비행기": "✈️",
                "호텔": "🏨",
                "해변": "🏖️",
                "산": "⛰️",
                "캠핑": "⛺",
                "카메라": "📷",
                "지도": "🗺️",
                "여권": "📗",
                "가방": "🧳",
                "나침반": "🧭",
            }
        ),
        "expression": EmoticonGroup(
            name="표정/감정",
            description="감정 표현 이모지",
            emoticons={
                "웃음": "😊",
                "감동": "🥹",
                "놀람": "😮",
                "생각": "🤔",
                "윙크": "😉",
                "멋짐": "😎",
                "화남": "😤",
                "슬픔": "😢",
                "신남": "🤩",
                "기대": "😍",
            }
        ),
        "symbol": EmoticonGroup(
            name="기호/아이콘",
            description="특수 기호 및 아이콘",
            emoticons={
                "체크마크": "✓",
                "엑스마크": "✗",
                "별표": "★",
                "다이아": "◆",
                "하트": "♥",
                "클로버": "♣",
                "화살표_오른쪽": "→",
                "화살표_왼쪽": "←",
                "화살표_위": "↑",
                "화살표_아래": "↓",
            }
        ),
        "decoration": EmoticonGroup(
            name="꾸미기",
            description="제목/강조 꾸미기용",
            emoticons={
                "반짝": "✨",
                "폭죽": "🎉",
                "선물": "🎁",
                "트로피": "🏆",
                "리본": "🎀",
                "꽃": "🌸",
                "무지개": "🌈",
                "불꽃": "🔥",
                "번개": "⚡",
                "크라운": "👑",
            }
        ),
    }
    
    # 키워드 → 이모티콘 자동 매핑
    KEYWORD_EMOTICON_MAP: Dict[str, str] = {
        # 일반
        "tip": "💡",
        "팁": "💡",
        "주의": "⚠️",
        "경고": "⚠️",
        "중요": "❗",
        "참고": "📌",
        "추천": "👍",
        "비추천": "👎",
        "필수": "✅",
        "확인": "✅",
        # 질문/답변
        "질문": "❓",
        "답변": "💬",
        "Q": "❓",
        "A": "💡",
        # 섹션
        "소개": "📋",
        "목차": "📑",
        "결론": "🎯",
        "요약": "📝",
        "후기": "💬",
        # 자동차
        "자동차": "🚗",
        "전기차": "🔌",
        "충전": "⚡",
        "연비": "⛽",
        "보험": "🛡️",
        # 금융
        "가격": "💰",
        "비용": "💸",
        "할인": "🏷️",
        "무료": "🆓",
    }
    
    def __init__(self, selected_groups: Optional[List[str]] = None):
        """
        Args:
            selected_groups: 사용할 이모티콘 그룹 이름 목록
        """
        self.selected_groups = selected_groups or ["basic", "symbol", "decoration"]
    
    @classmethod
    def get_available_groups(cls) -> List[Tuple[str, str, str]]:
        """사용 가능한 이모티콘 그룹 목록 반환
        
        Returns:
            [(group_id, name, description), ...]
        """
        return [
            (gid, group.name, group.description)
            for gid, group in cls.EMOTICON_GROUPS.items()
        ]
    
    @classmethod
    def get_group_emoticons(cls, group_id: str) -> Dict[str, str]:
        """특정 그룹의 이모티콘 반환"""
        group = cls.EMOTICON_GROUPS.get(group_id)
        return group.emoticons if group else {}
    
    def get_emoticon_by_keyword(self, keyword: str) -> Optional[str]:
        """키워드에 맞는 이모티콘 반환"""
        keyword_lower = keyword.lower().strip()
        return self.KEYWORD_EMOTICON_MAP.get(keyword_lower)
    
    def apply_emoticons_to_text(
        self, 
        text: str, 
        level: str = "조금"
    ) -> str:
        """텍스트에 이모티콘 적용
        
        Args:
            text: 원본 텍스트
            level: 이모티콘 레벨 ("없음", "조금", "많이")
        
        Returns:
            이모티콘이 적용된 텍스트
        """
        if level == "없음" or level == "사용 안 함 (텍스트만)":
            return self._remove_emoticons(text)
        
        lines = text.split('\n')
        result = []
        
        for line in lines:
            # 소제목 패턴 감지 및 이모티콘 추가
            heading_match = re.match(r'^(【(.+?)】|▶\s*(.+)|●\s*(.+)|■\s*(.+)|※\s*(.+))', line)
            if heading_match:
                heading_text = heading_match.group(2) or heading_match.group(3) or \
                              heading_match.group(4) or heading_match.group(5) or \
                              heading_match.group(6)
                if heading_text:
                    emoticon = self._get_emoticon_for_heading(heading_text, level)
                    if emoticon and emoticon not in line:
                        # 소제목 앞에 이모티콘 추가
                        line = re.sub(
                            r'^(【|▶|●|■|※)\s*',
                            f'{emoticon} \\1 ',
                            line
                        )
            
            # Q&A 패턴
            if re.match(r'^Q[:.:]', line) and '❓' not in line:
                line = '❓ ' + line
            elif re.match(r'^A[:.:]', line) and '💡' not in line:
                line = '💡 ' + line
            
            result.append(line)
        
        return '\n'.join(result)
    
    def _get_emoticon_for_heading(self, heading: str, level: str) -> Optional[str]:
        """소제목에 적합한 이모티콘 찾기"""
        heading_lower = heading.lower()
        
        # 키워드 매핑에서 찾기
        for keyword, emoticon in self.KEYWORD_EMOTICON_MAP.items():
            if keyword in heading_lower:
                return emoticon
        
        # 기본 이모티콘 (level에 따라)
        if level == "많이" or level == "많이 사용 (화려하게)":
            return "📌"
        
        return None
    
    def _remove_emoticons(self, text: str) -> str:
        """텍스트에서 이모지 제거"""
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            u"\U0001F1E0-\U0001F1FF"
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)
        return emoji_pattern.sub('', text)
    
    def get_emoticon_palette(self) -> Dict[str, Dict[str, str]]:
        """선택된 그룹들의 이모티콘 팔레트 반환"""
        palette = {}
        for group_id in self.selected_groups:
            if group_id in self.EMOTICON_GROUPS:
                group = self.EMOTICON_GROUPS[group_id]
                palette[group.name] = group.emoticons
        return palette


# 싱글톤 인스턴스
_emoticon_manager: Optional[EmoticonManager] = None


def get_emoticon_manager(groups: Optional[List[str]] = None) -> EmoticonManager:
    """EmoticonManager 싱글톤 반환"""
    global _emoticon_manager
    if _emoticon_manager is None or groups is not None:
        _emoticon_manager = EmoticonManager(groups)
    return _emoticon_manager


def apply_emoticons(text: str, level: str = "조금") -> str:
    """편의 함수: 텍스트에 이모티콘 적용"""
    manager = get_emoticon_manager()
    return manager.apply_emoticons_to_text(text, level)
