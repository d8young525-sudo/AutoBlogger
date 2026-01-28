"""
Auto Blogger Pro - UI 스타일 테마
모던하고 프로페셔널한 QSS 테마
"""

# ============================================================
# Color Constants - Coral/Orange Theme
# ============================================================
PRIMARY = "#FF6B6B"
PRIMARY_LIGHT = "#FF8E8E"
PRIMARY_DARK = "#E04E4E"
PRIMARY_HOVER = "#FF5252"

ACCENT = "#FF8E53"
ACCENT_HOVER = "#F07A3F"

BG_MAIN = "#FFF8F6"
BG_CARD = "#FFFFFF"
BG_INPUT = "#FFFAF8"
BG_SIDEBAR = "#FFF0EC"

TEXT_PRIMARY = "#2D2D3A"
TEXT_SECONDARY = "#5A5A6E"
TEXT_MUTED = "#9A9AB0"
TEXT_WHITE = "#FFFFFF"

BORDER_LIGHT = "#FFE0D6"
BORDER_MEDIUM = "#FFCBBE"
BORDER_FOCUS = PRIMARY

DANGER = "#E53E3E"
DANGER_HOVER = "#C53030"
WARNING = "#F6AD55"
SUCCESS = "#48BB78"
INFO = "#4299E1"


def get_app_stylesheet() -> str:
    """메인 앱 글로벌 스타일시트"""
    return f"""
    /* ============================================ */
    /* Global Base                                  */
    /* ============================================ */
    QMainWindow, QWidget {{
        background-color: {BG_MAIN};
        color: {TEXT_PRIMARY};
        font-family: "Malgun Gothic", "맑은 고딕", sans-serif;
        font-size: 13px;
    }}

    /* ============================================ */
    /* Tab Widget                                   */
    /* ============================================ */
    QTabWidget::pane {{
        border: 1px solid {BORDER_LIGHT};
        border-top: 2px solid {PRIMARY};
        background-color: {BG_CARD};
        border-radius: 0 0 4px 4px;
    }}

    QTabBar::tab {{
        background-color: {BG_SIDEBAR};
        color: {TEXT_SECONDARY};
        border: 1px solid {BORDER_LIGHT};
        border-bottom: none;
        padding: 8px 18px;
        margin-right: 2px;
        border-radius: 4px 4px 0 0;
        font-size: 13px;
        min-width: 80px;
    }}

    QTabBar::tab:selected {{
        background-color: {BG_CARD};
        color: {PRIMARY_DARK};
        font-weight: bold;
        border-bottom: 2px solid {PRIMARY};
    }}

    QTabBar::tab:hover:!selected {{
        background-color: #FFF0EC;
        color: {TEXT_PRIMARY};
    }}

    /* ============================================ */
    /* Buttons                                      */
    /* ============================================ */
    QPushButton {{
        background-color: {BG_CARD};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_MEDIUM};
        border-radius: 6px;
        padding: 8px 16px;
        font-size: 13px;
        min-height: 20px;
    }}

    QPushButton:hover {{
        background-color: #F0F0F0;
        border-color: {PRIMARY_LIGHT};
    }}

    QPushButton:pressed {{
        background-color: #E0E0E0;
    }}

    QPushButton:disabled {{
        background-color: #F0F0F0;
        color: {TEXT_MUTED};
        border-color: {BORDER_LIGHT};
    }}

    /* Primary action buttons */
    QPushButton[objectName="primaryButton"],
    QPushButton#primaryButton {{
        background-color: {PRIMARY};
        color: {TEXT_WHITE};
        border: none;
        font-weight: bold;
        padding: 12px 24px;
        font-size: 14px;
    }}

    QPushButton[objectName="primaryButton"]:hover,
    QPushButton#primaryButton:hover {{
        background-color: {PRIMARY_HOVER};
    }}

    QPushButton[objectName="primaryButton"]:pressed,
    QPushButton#primaryButton:pressed {{
        background-color: {PRIMARY_DARK};
    }}

    QPushButton[objectName="primaryButton"]:disabled,
    QPushButton#primaryButton:disabled {{
        background-color: #A0A0A0;
        color: #D0D0D0;
    }}

    /* Danger buttons */
    QPushButton[objectName="dangerButton"],
    QPushButton#dangerButton {{
        background-color: {DANGER};
        color: {TEXT_WHITE};
        border: none;
        font-weight: bold;
    }}

    QPushButton[objectName="dangerButton"]:hover,
    QPushButton#dangerButton:hover {{
        background-color: {DANGER_HOVER};
    }}

    /* Secondary / outline buttons */
    QPushButton[objectName="secondaryButton"],
    QPushButton#secondaryButton {{
        background-color: transparent;
        color: {PRIMARY};
        border: 1px solid {PRIMARY};
        font-weight: bold;
    }}

    QPushButton[objectName="secondaryButton"]:hover,
    QPushButton#secondaryButton:hover {{
        background-color: #FFF0EC;
    }}

    /* Accent buttons */
    QPushButton[objectName="accentButton"],
    QPushButton#accentButton {{
        background-color: {ACCENT};
        color: {TEXT_PRIMARY};
        border: none;
        font-weight: bold;
    }}

    QPushButton[objectName="accentButton"]:hover,
    QPushButton#accentButton:hover {{
        background-color: {ACCENT_HOVER};
    }}

    /* Info buttons */
    QPushButton[objectName="infoButton"],
    QPushButton#infoButton {{
        background-color: {INFO};
        color: {TEXT_WHITE};
        border: none;
        font-weight: bold;
    }}

    QPushButton[objectName="infoButton"]:hover,
    QPushButton#infoButton:hover {{
        background-color: #3182CE;
    }}

    /* Link-style buttons (no border) */
    QPushButton[objectName="linkButton"],
    QPushButton#linkButton {{
        background-color: transparent;
        color: {INFO};
        border: none;
        text-decoration: underline;
        padding: 4px 8px;
    }}

    QPushButton[objectName="linkButton"]:hover,
    QPushButton#linkButton:hover {{
        color: {PRIMARY};
    }}

    /* ============================================ */
    /* Input Fields                                 */
    /* ============================================ */
    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: {BG_INPUT};
        border: 1px solid {BORDER_LIGHT};
        border-radius: 6px;
        padding: 8px 12px;
        color: {TEXT_PRIMARY};
        font-size: 13px;
        selection-background-color: {PRIMARY_LIGHT};
        selection-color: {TEXT_WHITE};
    }}

    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border: 1px solid {PRIMARY};
        background-color: {BG_CARD};
    }}

    QLineEdit:disabled, QTextEdit:disabled {{
        background-color: #EEEEEE;
        color: {TEXT_MUTED};
    }}

    /* ============================================ */
    /* ComboBox                                     */
    /* ============================================ */
    QComboBox {{
        background-color: {BG_INPUT};
        border: 1px solid {BORDER_LIGHT};
        border-radius: 6px;
        padding: 6px 12px;
        color: {TEXT_PRIMARY};
        font-size: 13px;
        min-height: 22px;
    }}

    QComboBox:focus {{
        border: 1px solid {PRIMARY};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}

    QComboBox::down-arrow {{
        width: 10px;
        height: 10px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {BG_CARD};
        border: 1px solid {BORDER_LIGHT};
        selection-background-color: #FFF0EC;
        selection-color: {PRIMARY_DARK};
        padding: 4px;
    }}

    QComboBox:disabled {{
        background-color: #EEEEEE;
        color: {TEXT_MUTED};
    }}

    /* ============================================ */
    /* Group Box                                    */
    /* ============================================ */
    QGroupBox {{
        background-color: {BG_CARD};
        border: 1px solid {BORDER_LIGHT};
        border-radius: 8px;
        margin-top: 16px;
        padding: 16px 12px 12px 12px;
        font-weight: bold;
        font-size: 13px;
        color: {TEXT_PRIMARY};
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        padding: 0 8px;
        background-color: {BG_CARD};
        color: {PRIMARY_DARK};
    }}

    /* ============================================ */
    /* Scroll Area & Scrollbar                      */
    /* ============================================ */
    QScrollArea {{
        border: none;
        background-color: transparent;
    }}

    QScrollBar:vertical {{
        background-color: transparent;
        width: 8px;
        margin: 0;
    }}

    QScrollBar::handle:vertical {{
        background-color: #C0C0C0;
        border-radius: 4px;
        min-height: 30px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: #A0A0A0;
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    QScrollBar:horizontal {{
        background-color: transparent;
        height: 8px;
    }}

    QScrollBar::handle:horizontal {{
        background-color: #C0C0C0;
        border-radius: 4px;
        min-width: 30px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background-color: #A0A0A0;
    }}

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}

    /* ============================================ */
    /* List Widget                                  */
    /* ============================================ */
    QListWidget {{
        background-color: {BG_INPUT};
        border: 1px solid {BORDER_LIGHT};
        border-radius: 6px;
        padding: 4px;
    }}

    QListWidget::item {{
        padding: 6px 8px;
        border-radius: 4px;
    }}

    QListWidget::item:hover {{
        background-color: #FFF0EC;
    }}

    QListWidget::item:selected {{
        background-color: {PRIMARY_LIGHT};
        color: {TEXT_WHITE};
    }}

    /* ============================================ */
    /* Radio Button & Checkbox                      */
    /* ============================================ */
    QRadioButton, QCheckBox {{
        spacing: 8px;
        color: {TEXT_PRIMARY};
        font-size: 13px;
    }}

    QRadioButton::indicator, QCheckBox::indicator {{
        width: 16px;
        height: 16px;
    }}

    QRadioButton::indicator:checked {{
        background-color: {PRIMARY};
        border: 2px solid {PRIMARY};
        border-radius: 9px;
    }}

    QRadioButton::indicator:unchecked {{
        background-color: {BG_CARD};
        border: 2px solid {BORDER_MEDIUM};
        border-radius: 9px;
    }}

    QCheckBox::indicator:checked {{
        background-color: {PRIMARY};
        border: 2px solid {PRIMARY};
        border-radius: 3px;
    }}

    QCheckBox::indicator:unchecked {{
        background-color: {BG_CARD};
        border: 2px solid {BORDER_MEDIUM};
        border-radius: 3px;
    }}

    /* ============================================ */
    /* Labels                                       */
    /* ============================================ */
    QLabel {{
        color: {TEXT_PRIMARY};
        font-size: 13px;
    }}

    /* ============================================ */
    /* Progress Bar                                 */
    /* ============================================ */
    QProgressBar {{
        background-color: #E0E0E0;
        border: none;
        border-radius: 4px;
        text-align: center;
        height: 8px;
    }}

    QProgressBar::chunk {{
        background-color: {PRIMARY};
        border-radius: 4px;
    }}

    /* ============================================ */
    /* Frame                                        */
    /* ============================================ */
    QFrame {{
        border: none;
    }}

    /* ============================================ */
    /* SpinBox                                      */
    /* ============================================ */
    QSpinBox {{
        background-color: {BG_INPUT};
        border: 1px solid {BORDER_LIGHT};
        border-radius: 6px;
        padding: 6px 12px;
        color: {TEXT_PRIMARY};
    }}

    QSpinBox:focus {{
        border: 1px solid {PRIMARY};
    }}

    /* ============================================ */
    /* ToolTip                                      */
    /* ============================================ */
    QToolTip {{
        background-color: {TEXT_PRIMARY};
        color: {TEXT_WHITE};
        border: none;
        padding: 6px 10px;
        border-radius: 4px;
        font-size: 12px;
    }}
    """


def get_login_dialog_stylesheet() -> str:
    """로그인 다이얼로그 전용 스타일시트"""
    return f"""
    QDialog {{
        background-color: {BG_CARD};
    }}

    QTabWidget::pane {{
        border: none;
        background-color: {BG_CARD};
    }}

    QTabBar::tab {{
        background-color: transparent;
        color: {TEXT_MUTED};
        border: none;
        border-bottom: 2px solid transparent;
        padding: 10px 20px;
        font-size: 13px;
        font-weight: bold;
    }}

    QTabBar::tab:selected {{
        color: {PRIMARY_DARK};
        border-bottom: 2px solid {PRIMARY};
    }}

    QTabBar::tab:hover:!selected {{
        color: {TEXT_PRIMARY};
    }}

    QLineEdit {{
        background-color: {BG_INPUT};
        border: 1px solid {BORDER_LIGHT};
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 14px;
    }}

    QLineEdit:focus {{
        border: 1px solid {PRIMARY};
        background-color: {BG_CARD};
    }}
    """
