"""
Auto Blogger Pro - UI 스타일 테마
qt-material 기반 + 개별 위젯 인라인 스타일
"""

# 버튼 인라인 스타일 (개별 위젯에 setStyleSheet로 적용)
GREEN_BUTTON_STYLE = """
    QPushButton {
        background-color: #03C75A;
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        padding: 12px 24px;
        font-size: 14px;
        font-weight: 600;
    }
    QPushButton:hover {
        background-color: #00B050;
    }
    QPushButton:pressed {
        background-color: #009944;
    }
    QPushButton:disabled {
        background-color: #CCCCCC;
        color: #888888;
    }
"""

# 카드 인라인 스타일 (정보성글쓰기탭 모드 선택용)
CARD_SELECTED_STYLE = """
    .QFrame {
        border: 2px solid #4A90D9;
        border-radius: 8px;
        background-color: #FFFFFF;
    }
"""

CARD_UNSELECTED_STYLE = """
    .QFrame {
        border: 1px solid #E0E0E0;
        border-radius: 8px;
        background-color: #FFFFFF;
    }
"""

NEUTRAL_BUTTON_STYLE = """
    QPushButton {
        background-color: #f0f0f0;
        color: #333333;
        border: 1px solid #cccccc;
        border-radius: 4px;
        padding: 8px 16px;
    }
    QPushButton:hover {
        background-color: #e0e0e0;
        border-color: #aaaaaa;
    }
    QPushButton:pressed {
        background-color: #d0d0d0;
    }
"""

RED_BUTTON_STYLE = """
    QPushButton {
        background-color: #FF5252;
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 600;
    }
    QPushButton:hover {
        background-color: #E04848;
    }
    QPushButton:pressed {
        background-color: #CC3E3E;
    }
"""
