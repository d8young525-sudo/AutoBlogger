"""
통합 설정 탭 - 계정, 글쓰기 스타일, 포스팅 구조, 네이버 서식, 카테고리, 데이터 관리
기존 settings_tab.py + writing_settings_tab.py 통합
"""
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout,
    QLineEdit, QTextEdit, QPushButton, QMessageBox,
    QHBoxLayout, QLabel, QComboBox, QCheckBox, QRadioButton,
    QButtonGroup, QScrollArea, QFileDialog, QSpinBox
)
from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QPixmap

from ui.styles import GREEN_BUTTON_STYLE, NEUTRAL_BUTTON_STYLE


class UnifiedSettingsTab(QWidget):
    """통합 설정 탭"""

    settings_changed = Signal()

    def __init__(self):
        super().__init__()
        self.settings = QSettings("MySoft", "NaverBlogBot")
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)

        # ========== 1. 계정 설정 ==========
        self._create_account_section(layout)

        # ========== 2. 글쓰기 기본 스타일 ==========
        self._create_style_section(layout)

        # ========== 3. 포스팅 구조 ==========
        self._create_structure_section(layout)

        # ========== 4. 네이버 에디터 서식 ==========
        self._create_naver_style_section(layout)

        # ========== 5. 카테고리 설정 ==========
        self._create_category_section(layout)

        # ========== 저장 버튼 ==========
        self.btn_save = QPushButton("설정 저장")
        self.btn_save.setStyleSheet(GREEN_BUTTON_STYLE)
        self.btn_save.clicked.connect(self.save_settings)
        layout.addWidget(self.btn_save)

        layout.addStretch()

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

        self.load_settings()

    # ============================================================
    # Helpers
    # ============================================================

    def _form_label(self, text: str) -> QLabel:
        """고정 너비 폼 라벨 생성 (정렬 통일)"""
        lbl = QLabel(text)
        lbl.setMinimumWidth(120)
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return lbl

    def _make_form(self) -> QFormLayout:
        """통일된 QFormLayout 생성"""
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        return form

    def _label_above(self, text: str) -> QLabel:
        """label-above 패턴용 라벨"""
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        return lbl

    def _two_col(self, l1, w1, l2, w2):
        """2열 그리드: 라벨 위 + 위젯"""
        row = QHBoxLayout()
        row.setSpacing(16)
        for label, widget in [(l1, w1), (l2, w2)]:
            col = QVBoxLayout()
            col.setSpacing(4)
            col.addWidget(self._label_above(label))
            col.addWidget(widget)
            row.addLayout(col, 1)
        return row

    # ============================================================
    # Section builders
    # ============================================================

    def _create_account_section(self, layout):
        group = QGroupBox("계정 설정")
        vlayout = QVBoxLayout()
        vlayout.setSpacing(12)

        desc = QLabel("네이버 계정은 블로그 자동 발행에만 사용됩니다.")
        desc.setEnabled(False)
        vlayout.addWidget(desc)

        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText("네이버 아이디")
        self.input_pw = QLineEdit()
        self.input_pw.setEchoMode(QLineEdit.Password)
        self.input_pw.setPlaceholderText("네이버 비밀번호")

        vlayout.addWidget(self._label_above("네이버 ID"))
        vlayout.addWidget(self.input_id)
        vlayout.addWidget(self._label_above("네이버 PW"))
        vlayout.addWidget(self.input_pw)

        group.setLayout(vlayout)
        layout.addWidget(group)

    def _create_style_section(self, layout):
        group = QGroupBox("글쓰기 기본 스타일")
        vlayout = QVBoxLayout()
        vlayout.setSpacing(16)

        # 글 말투 + 기본 분량: 2열 배치
        self.combo_default_tone = QComboBox()
        self.combo_default_tone.addItems([
            "친근한 이웃 (해요체)",
            "신뢰감 있는 전문가 (하십시오체)",
            "유머러스하고 재치있는 (드립+텐션업)",
            "감성적인 에세이 스타일",
            "냉철한 팩트 전달/뉴스 스타일"
        ])

        self.combo_default_length = QComboBox()
        self.combo_default_length.addItems([
            "보통 (1,500자)",
            "길게 (2,000자)",
            "아주 길게 (2,500자)"
        ])

        vlayout.addLayout(self._two_col(
            "글 문투", self.combo_default_tone,
            "기본 분량", self.combo_default_length
        ))

        # 고정 인사말
        vlayout.addWidget(QLabel("고정 인사말 (글 시작 부분):"))
        self.input_intro = QTextEdit()
        self.input_intro.setMaximumHeight(80)
        self.input_intro.setPlaceholderText("예: 안녕하세요, 자동차 전문 상담사 OOO입니다!")
        vlayout.addWidget(self.input_intro)

        # 고정 맺음말
        vlayout.addWidget(QLabel("고정 맺음말 (글 마무리 부분):"))
        self.input_outro = QTextEdit()
        self.input_outro.setMaximumHeight(80)
        self.input_outro.setPlaceholderText("예: 차량 구매 상담은 언제든 연락주세요!")
        vlayout.addWidget(self.input_outro)

        # 명함 이미지
        vlayout.addWidget(QLabel("명함/연락처 이미지 (선택):"))
        image_row = QHBoxLayout()

        self.lbl_image_preview = QLabel()
        self.lbl_image_preview.setFixedSize(150, 90)
        self.lbl_image_preview.setAlignment(Qt.AlignCenter)
        image_row.addWidget(self.lbl_image_preview)

        btn_col = QVBoxLayout()
        self.btn_select_image = QPushButton("이미지 선택")
        self.btn_select_image.setStyleSheet(NEUTRAL_BUTTON_STYLE)
        self.btn_select_image.clicked.connect(self.select_outro_image)
        btn_col.addWidget(self.btn_select_image)

        self.btn_clear_image = QPushButton("삭제")
        self.btn_clear_image.setStyleSheet(NEUTRAL_BUTTON_STYLE)
        self.btn_clear_image.clicked.connect(self.clear_outro_image)
        btn_col.addWidget(self.btn_clear_image)
        btn_col.addStretch()
        image_row.addLayout(btn_col)
        image_row.addStretch()

        vlayout.addLayout(image_row)

        self.lbl_image_path = QLabel("")
        vlayout.addWidget(self.lbl_image_path)

        group.setLayout(vlayout)
        layout.addWidget(group)

    def _create_structure_section(self, layout):
        group = QGroupBox("포스팅 구조")
        vlayout = QVBoxLayout()
        vlayout.setSpacing(12)

        # 자동/수동 모드 선택
        vlayout.addWidget(self._label_above("구조 모드"))
        mode_row = QHBoxLayout()
        self.radio_structure_auto = QRadioButton("자동 (권장)")
        self.radio_structure_auto.setChecked(True)
        self.radio_structure_auto.setToolTip("AI가 글 흐름에 맞게 자유롭게 구성")
        self.radio_structure_manual = QRadioButton("수동")
        self.radio_structure_manual.setToolTip("구조를 직접 지정 (강제 적용)")

        self.structure_mode_group = QButtonGroup()
        self.structure_mode_group.addButton(self.radio_structure_auto, 0)
        self.structure_mode_group.addButton(self.radio_structure_manual, 1)
        self.structure_mode_group.idToggled.connect(self._on_structure_mode_changed)

        mode_row.addWidget(self.radio_structure_auto)
        mode_row.addWidget(self.radio_structure_manual)
        mode_row.addStretch()
        vlayout.addLayout(mode_row)

        # 수동 설정 컨테이너
        self.manual_structure_widget = QWidget()
        manual_layout = QVBoxLayout(self.manual_structure_widget)
        manual_layout.setContentsMargins(0, 10, 0, 0)

        desc = QLabel("수동 모드: AI에게 구조를 강제합니다.")
        desc.setEnabled(False)
        desc.setWordWrap(True)
        manual_layout.addWidget(desc)

        # 소제목/인용구/이미지 수: 3열 배치
        self.spin_heading_count = QSpinBox()
        self.spin_heading_count.setRange(3, 6)
        self.spin_heading_count.setValue(4)
        self.spin_heading_count.setToolTip("소제목(h2) 개수를 강제 지정")

        self.spin_quotation_count = QSpinBox()
        self.spin_quotation_count.setRange(0, 4)
        self.spin_quotation_count.setValue(2)
        self.spin_quotation_count.setToolTip("인용구 블록 개수를 강제 지정")

        self.spin_image_count = QSpinBox()
        self.spin_image_count.setRange(0, 3)
        self.spin_image_count.setValue(2)
        self.spin_image_count.setToolTip("본문에 삽입할 AI 생성 이미지 수 (0=없음, 최대 3개)")

        three_col = QHBoxLayout()
        three_col.setSpacing(16)
        for label, widget in [("소제목 개수", self.spin_heading_count),
                              ("인용구 개수", self.spin_quotation_count),
                              ("본문 이미지 수", self.spin_image_count)]:
            col = QVBoxLayout()
            col.setSpacing(4)
            col.addWidget(self._label_above(label))
            col.addWidget(widget)
            three_col.addLayout(col, 1)
        manual_layout.addLayout(three_col)

        # 마무리 스타일
        manual_layout.addWidget(self._label_above("마무리 스타일"))
        self.combo_ending_style = QComboBox()
        self.combo_ending_style.addItems(["요약", "질문 유도", "CTA (행동 유도)"])
        manual_layout.addWidget(self.combo_ending_style)

        vlayout.addWidget(self.manual_structure_widget)

        # 초기 상태: 자동 모드이므로 수동 설정 비활성화
        self.manual_structure_widget.setEnabled(False)

        group.setLayout(vlayout)
        layout.addWidget(group)

    def _create_naver_style_section(self, layout):
        group = QGroupBox("네이버 에디터 서식 설정")
        vlayout = QVBoxLayout()
        vlayout.setSpacing(16)

        # 폰트 + 글자 크기: 2열
        self.combo_naver_font = QComboBox()
        self.combo_naver_font.addItems([
            "기본서체 (시스템)", "나눔고딕", "나눔명조", "나눔바른고딕",
            "나눔스퀘어", "마루부리", "다시시작해 (손글씨)",
            "바른히피 (손글씨)", "우리딸손글씨"
        ])
        self.combo_naver_font.setCurrentIndex(1)

        self.combo_naver_fontsize = QComboBox()
        self.combo_naver_fontsize.addItems([
            "11pt", "13pt", "15pt (권장)", "16pt", "19pt", "24pt", "28pt", "30pt"
        ])
        self.combo_naver_fontsize.setCurrentIndex(2)

        vlayout.addLayout(self._two_col(
            "본문 폰트", self.combo_naver_font,
            "글자 크기", self.combo_naver_fontsize
        ))

        # 줄 간격 + 소제목 스타일: 2열
        self.combo_naver_lineheight = QComboBox()
        self.combo_naver_lineheight.addItems(["1.5 (좁게)", "1.8 (기본)", "2.0 (넓게)", "2.5 (매우 넓게)"])
        self.combo_naver_lineheight.setCurrentIndex(1)

        self.combo_heading_style = QComboBox()
        self.combo_heading_style.addItems([
            "19pt", "19pt + Bold", "24pt", "24pt + Bold"
        ])

        vlayout.addLayout(self._two_col(
            "줄 간격", self.combo_naver_lineheight,
            "소제목 스타일", self.combo_heading_style
        ))

        # 소제목 색상 + 인용구 모양: 2열
        self.combo_heading_color = QComboBox()
        self.combo_heading_color.addItems([
            "검정 (기본)", "그린 (#54b800)", "블루 (#0078cb)", "레드 (#ff0010)"
        ])

        self.combo_quote_style = QComboBox()
        self.combo_quote_style.addItems([
            "왼쪽 세로선", "말풍선", "모서리 꽃음표", "하단 밑줄", "포스트잇"
        ])

        vlayout.addLayout(self._two_col(
            "소제목 색상", self.combo_heading_color,
            "인용구 모양", self.combo_quote_style
        ))

        # 구분선 모양 (1열)
        vlayout.addWidget(self._label_above("구분선 모양"))
        self.combo_divider_style = QComboBox()
        self.combo_divider_style.addItems([
            "기본 실선", "점선", "이중선", "굵은 실선", "파선", "점선+실선", "장식선"
        ])
        vlayout.addWidget(self.combo_divider_style)

        # 텍스트 서식: 강조
        vlayout.addWidget(self._label_above("강조"))
        emphasis_row = QHBoxLayout()
        self.chk_bold = QCheckBox("Bold")
        self.chk_bold.setChecked(True)
        self.chk_italic = QCheckBox("Italic")
        self.chk_underline = QCheckBox("Underline")
        self.chk_strikethrough = QCheckBox("취소선")
        emphasis_row.addWidget(self.chk_bold)
        emphasis_row.addWidget(self.chk_italic)
        emphasis_row.addWidget(self.chk_underline)
        emphasis_row.addWidget(self.chk_strikethrough)
        emphasis_row.addStretch()
        vlayout.addLayout(emphasis_row)

        # 강조 글자색 + 배경 강조색: 2열
        self.combo_emphasis_color = QComboBox()
        self.combo_emphasis_color.addItems([
            "없음 (기본 검정)", "그린 (#54b800)", "블루 (#0078cb)", "오렌지 (#ff9300)", "레드 (#ff0010)"
        ])

        self.combo_highlight_color = QComboBox()
        self.combo_highlight_color.addItems([
            "없음",
            "노란색 (#fff593)",
            "연두색 (#e3fdc8)",
            "연분홍 (#ffb7de)"
        ])

        vlayout.addLayout(self._two_col(
            "강조 글자색", self.combo_emphasis_color,
            "배경 강조색", self.combo_highlight_color
        ))

        # 정렬
        vlayout.addWidget(self._label_above("정렬"))
        align_row = QHBoxLayout()
        self.radio_align_left = QRadioButton("왼쪽")
        self.radio_align_left.setChecked(True)
        self.radio_align_center = QRadioButton("가운데")
        self.radio_align_right = QRadioButton("오른쪽")
        self.align_button_group = QButtonGroup()
        self.align_button_group.addButton(self.radio_align_left, 0)
        self.align_button_group.addButton(self.radio_align_center, 1)
        self.align_button_group.addButton(self.radio_align_right, 2)
        align_row.addWidget(self.radio_align_left)
        align_row.addWidget(self.radio_align_center)
        align_row.addWidget(self.radio_align_right)
        align_row.addStretch()
        vlayout.addLayout(align_row)

        # 스티커 팩 + 스티커 빈도: 2열
        self.combo_sticker_pack = QComboBox()
        self._load_sticker_packs()

        self.combo_sticker_frequency = QComboBox()
        self.combo_sticker_frequency.addItems(["사용 안함", "적게", "보통", "많이"])
        self.combo_sticker_frequency.setCurrentIndex(2)

        vlayout.addLayout(self._two_col(
            "스티커 팩", self.combo_sticker_pack,
            "스티커 빈도", self.combo_sticker_frequency
        ))

        group.setLayout(vlayout)
        layout.addWidget(group)

    def _create_category_section(self, layout):
        group = QGroupBox("카테고리 설정")
        vlayout = QVBoxLayout()
        vlayout.setSpacing(12)

        desc = QLabel("실제 블로그에 등록된 카테고리명과 정확히 일치해야 합니다.")
        desc.setEnabled(False)
        desc.setWordWrap(True)
        vlayout.addWidget(desc)

        vlayout.addWidget(self._label_above("정보성 글쓰기"))
        self.input_info_category = QLineEdit()
        self.input_info_category.setPlaceholderText("예: 자동차정보/유용한팁")
        vlayout.addWidget(self.input_info_category)

        vlayout.addWidget(self._label_above("출고후기"))
        self.input_delivery_category = QLineEdit()
        self.input_delivery_category.setPlaceholderText("예: 출고후기/고객이야기")
        vlayout.addWidget(self.input_delivery_category)

        group.setLayout(vlayout)
        layout.addWidget(group)

    # ============================================================
    # Structure mode logic
    # ============================================================

    def _on_structure_mode_changed(self, button_id: int, checked: bool):
        """자동/수동 모드 전환 시 수동 설정 위젯 활성화/비활성화"""
        if checked:
            is_manual = (button_id == 1)  # 1 = 수동 모드
            self.manual_structure_widget.setEnabled(is_manual)

    # ============================================================
    # Image helpers
    # ============================================================

    def select_outro_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "명함/연락처 이미지 선택", "",
            "이미지 파일 (*.png *.jpg *.jpeg *.bmp *.gif);;모든 파일 (*.*)"
        )
        if file_path:
            if self._load_image_preview(file_path):
                self.settings.setValue("outro_image", file_path)
                self.lbl_image_path.setText(os.path.basename(file_path))

    def clear_outro_image(self):
        self.settings.remove("outro_image")
        self.lbl_image_preview.setText("이미지 없음")
        self.lbl_image_preview.setPixmap(QPixmap())
        self.lbl_image_path.setText("")

    def _load_image_preview(self, file_path: str) -> bool:
        try:
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                self.lbl_image_preview.setText("로드 실패")
                return False
            scaled = pixmap.scaled(150, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.lbl_image_preview.setPixmap(scaled)
            return True
        except Exception:
            self.lbl_image_preview.setText("로드 실패")
            return False

    # ============================================================
    # Save / Load
    # ============================================================

    def save_settings(self):
        # 계정
        self.settings.setValue("id", self.input_id.text())
        self.settings.setValue("pw", self.input_pw.text())
        self.settings.setValue("intro", self.input_intro.toPlainText())
        self.settings.setValue("outro", self.input_outro.toPlainText())

        # 스타일
        self.settings.setValue("writing/default_tone", self.combo_default_tone.currentIndex())
        self.settings.setValue("writing/default_length", self.combo_default_length.currentIndex())

        # 구조
        self.settings.setValue("writing/structure_mode", self.structure_mode_group.checkedId())
        self.settings.setValue("writing/heading_count", self.spin_heading_count.value())
        self.settings.setValue("writing/quotation_count", self.spin_quotation_count.value())
        self.settings.setValue("writing/image_count", self.spin_image_count.value())
        self.settings.setValue("writing/ending_style", self.combo_ending_style.currentIndex())

        # 카테고리
        self.settings.setValue("writing/info_category", self.input_info_category.text().strip())
        self.settings.setValue("writing/delivery_category", self.input_delivery_category.text().strip())

        # 네이버 에디터 서식
        self._save_naver_style_settings()

        self.settings_changed.emit()
        QMessageBox.information(self, "완료", "설정이 저장되었습니다.")

    def _save_naver_style_settings(self):
        self.settings.setValue("writing/naver_font", self.combo_naver_font.currentIndex())
        self.settings.setValue("writing/naver_fontsize", self.combo_naver_fontsize.currentIndex())
        self.settings.setValue("writing/naver_lineheight", self.combo_naver_lineheight.currentIndex())
        self.settings.setValue("writing/heading_style", self.combo_heading_style.currentIndex())
        self.settings.setValue("writing/heading_color", self.combo_heading_color.currentIndex())
        self.settings.setValue("writing/quote_style", self.combo_quote_style.currentIndex())
        self.settings.setValue("writing/divider_style", self.combo_divider_style.currentIndex())
        self.settings.setValue("writing/text_bold", self.chk_bold.isChecked())
        self.settings.setValue("writing/text_italic", self.chk_italic.isChecked())
        self.settings.setValue("writing/text_underline", self.chk_underline.isChecked())
        self.settings.setValue("writing/text_strikethrough", self.chk_strikethrough.isChecked())
        self.settings.setValue("writing/emphasis_color", self.combo_emphasis_color.currentIndex())
        self.settings.setValue("writing/highlight_color", self.combo_highlight_color.currentIndex())
        self.settings.setValue("writing/text_align", self.align_button_group.checkedId())
        self.settings.setValue("writing/sticker_pack", self.combo_sticker_pack.currentIndex())
        self.settings.setValue("writing/sticker_frequency", self.combo_sticker_frequency.currentIndex())

    def load_settings(self):
        # 계정
        self.input_id.setText(self.settings.value("id", ""))
        self.input_pw.setText(self.settings.value("pw", ""))
        self.input_intro.setText(self.settings.value("intro", ""))
        self.input_outro.setText(self.settings.value("outro", ""))

        # 명함 이미지
        outro_image = self.settings.value("outro_image", "")
        if outro_image and os.path.exists(outro_image):
            self._load_image_preview(outro_image)
            self.lbl_image_path.setText(os.path.basename(outro_image))
        else:
            self.lbl_image_preview.setText("이미지 없음")

        # 스타일
        self.combo_default_tone.setCurrentIndex(
            self.settings.value("writing/default_tone", 0, type=int))
        self.combo_default_length.setCurrentIndex(
            self.settings.value("writing/default_length", 0, type=int))

        # 구조
        structure_mode = self.settings.value("writing/structure_mode", 0, type=int)
        if structure_mode == 1:
            self.radio_structure_manual.setChecked(True)
            self.manual_structure_widget.setEnabled(True)
        else:
            self.radio_structure_auto.setChecked(True)
            self.manual_structure_widget.setEnabled(False)
        self.spin_heading_count.setValue(
            self.settings.value("writing/heading_count", 4, type=int))
        self.spin_quotation_count.setValue(
            self.settings.value("writing/quotation_count", 2, type=int))
        self.spin_image_count.setValue(
            self.settings.value("writing/image_count", 2, type=int))
        self.combo_ending_style.setCurrentIndex(
            self.settings.value("writing/ending_style", 0, type=int))

        # 카테고리
        self.input_info_category.setText(
            self.settings.value("writing/info_category", ""))
        self.input_delivery_category.setText(
            self.settings.value("writing/delivery_category", ""))

        # 네이버 에디터 서식
        self._load_naver_style_settings()

    def _load_naver_style_settings(self):
        self.combo_naver_font.setCurrentIndex(
            self.settings.value("writing/naver_font", 1, type=int))
        self.combo_naver_fontsize.setCurrentIndex(
            self.settings.value("writing/naver_fontsize", 4, type=int))
        self.combo_naver_lineheight.setCurrentIndex(
            self.settings.value("writing/naver_lineheight", 1, type=int))
        self.combo_heading_style.setCurrentIndex(
            self.settings.value("writing/heading_style", 0, type=int))
        self.combo_heading_color.setCurrentIndex(
            self.settings.value("writing/heading_color", 0, type=int))
        self.combo_quote_style.setCurrentIndex(
            self.settings.value("writing/quote_style", 0, type=int))
        self.combo_divider_style.setCurrentIndex(
            self.settings.value("writing/divider_style", 0, type=int))
        self.chk_bold.setChecked(
            self.settings.value("writing/text_bold", True, type=bool))
        self.chk_italic.setChecked(
            self.settings.value("writing/text_italic", False, type=bool))
        self.chk_underline.setChecked(
            self.settings.value("writing/text_underline", False, type=bool))
        self.chk_strikethrough.setChecked(
            self.settings.value("writing/text_strikethrough", False, type=bool))
        self.combo_emphasis_color.setCurrentIndex(
            self.settings.value("writing/emphasis_color", 0, type=int))
        self.combo_highlight_color.setCurrentIndex(
            self.settings.value("writing/highlight_color", 0, type=int))
        align_index = self.settings.value("writing/text_align", 0, type=int)
        if align_index == 0:
            self.radio_align_left.setChecked(True)
        elif align_index == 1:
            self.radio_align_center.setChecked(True)
        else:
            self.radio_align_right.setChecked(True)
        self.combo_sticker_pack.setCurrentIndex(
            self.settings.value("writing/sticker_pack", 0, type=int))
        self.combo_sticker_frequency.setCurrentIndex(
            self.settings.value("writing/sticker_frequency", 2, type=int))

    # ============================================================
    # Getter methods (compatible with WritingSettingsTab + SettingsTab)
    # ============================================================

    def get_naver_id(self) -> str:
        return self.input_id.text()

    def get_naver_pw(self) -> str:
        return self.input_pw.text()

    def get_intro(self) -> str:
        return self.input_intro.toPlainText()

    def get_outro(self) -> str:
        return self.input_outro.toPlainText()

    def get_outro_image_path(self) -> str:
        return self.settings.value("outro_image", "")

    def get_info_category(self) -> str:
        return self.input_info_category.text().strip()

    def get_delivery_category(self) -> str:
        return self.input_delivery_category.text().strip()

    def get_default_tone(self) -> str:
        return self.combo_default_tone.currentText()

    def get_default_tone_index(self) -> int:
        return self.combo_default_tone.currentIndex()

    def get_default_length(self) -> str:
        return self.combo_default_length.currentText()

    def get_default_length_index(self) -> int:
        return self.combo_default_length.currentIndex()

    def get_post_structure(self) -> str:
        """자동/수동 모드 반환"""
        return "manual" if self.radio_structure_manual.isChecked() else "auto"

    def get_structure_params(self) -> dict:
        """자동/수동 모드에 따라 구조 파라미터 반환"""
        if self.radio_structure_auto.isChecked():
            return {"mode": "auto"}
        return {
            "mode": "manual",
            "heading_count": self.spin_heading_count.value(),
            "quotation_count": self.spin_quotation_count.value(),
            "image_count": self.spin_image_count.value(),
            "ending_style": self.combo_ending_style.currentText()
        }

    def is_auto_thumbnail_enabled(self) -> bool:
        return True  # 항상 썸네일 생성

    def get_sticker_settings(self) -> dict:
        freq_idx = self.combo_sticker_frequency.currentIndex()
        # userData에서 pack_id 가져오기 (없으면 currentText 사용)
        pack_id = self.combo_sticker_pack.currentData() or self.combo_sticker_pack.currentText()
        return {
            "enabled": freq_idx > 0,
            "pack": self.combo_sticker_pack.currentIndex(),
            "packName": pack_id,  # 내부 ID 사용 (cafe_001 등)
            "frequency": freq_idx,
            "frequencyName": self.combo_sticker_frequency.currentText()
        }

    def _load_sticker_packs(self):
        """sticker_map.json에서 팩 목록을 로드하여 콤보박스에 추가 (미리보기 이미지 포함)"""
        import json
        from pathlib import Path
        from PySide6.QtGui import QIcon, QPixmap
        from PySide6.QtCore import QSize

        map_path = Path(__file__).parent.parent / "assets" / "stickers" / "sticker_map.json"
        stickers_dir = Path(__file__).parent.parent / "assets" / "stickers"
        self._sticker_pack_map = {}  # display_name -> pack_id 매핑

        # 콤보박스 설정: 이미지만 표시 (텍스트 없음)
        self.combo_sticker_pack.setIconSize(QSize(40, 40))
        self.combo_sticker_pack.setMinimumWidth(70)

        if map_path.exists():
            try:
                with open(map_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                packs = data.get("packs", {})
                if packs:
                    for pack_id, pack_info in packs.items():
                        display_name = pack_info.get("display_name", pack_id)

                        # 미리보기 이미지 로드 (sticker_0.png) - 텍스트 없이 아이콘만
                        preview_path = stickers_dir / pack_id / "sticker_0.png"
                        if preview_path.exists():
                            icon = QIcon(str(preview_path))
                            self.combo_sticker_pack.addItem(icon, "", userData=pack_id)
                        else:
                            # 이미지 없으면 pack_id 표시 (fallback)
                            self.combo_sticker_pack.addItem(pack_id, userData=pack_id)

                        self._sticker_pack_map[display_name] = pack_id
                    return
            except Exception:
                pass

        # sticker_map.json이 없으면 기본값
        self.combo_sticker_pack.addItem("기본", userData="default")

    def get_naver_editor_style_settings(self) -> dict:
        font_map = {
            0: "system", 1: "nanumgothic", 2: "nanummyeongjo",
            3: "nanumbarungothic", 4: "nanumsquare", 5: "maruburi",
            6: "dasisijakae", 7: "barenhipi", 8: "uridalsonglssi"
        }
        # 네이버 에디터 실제 유효 크기: 11, 13, 15, 16, 19, 24, 28, 30, 34, 38
        fontsize_map = {
            0: "se-fs11", 1: "se-fs13", 2: "se-fs15",
            3: "se-fs16", 4: "se-fs19", 5: "se-fs24",
            6: "se-fs28", 7: "se-fs30"
        }
        lineheight_map = {0: 1.5, 1: 1.8, 2: 2.0, 3: 2.5}
        # 소제목 크기: fs18 없음 → fs19 사용
        heading_size_map = {0: "se-fs19", 1: "se-fs19", 2: "se-fs24", 3: "se-fs24"}
        heading_bold_map = {0: False, 1: True, 2: False, 3: True}
        # 네이버 팔레트 실제 색상
        heading_color_map = {0: None, 1: "#54b800", 2: "#0078cb", 3: "#ff0010"}
        quote_style_map = {
            0: "quotation_line", 1: "quotation_bubble", 2: "quotation_corner",
            3: "quotation_underline", 4: "quotation_postit"
        }
        divider_style_map = {0: "line1", 1: "line2", 2: "line3", 3: "line4", 4: "line5", 5: "line6", 6: "line7"}
        # 네이버 팔레트 실제 색상
        emphasis_color_map = {0: None, 1: "#54b800", 2: "#0078cb", 3: "#ff9300", 4: "#ff0010"}
        # 네이버 팔레트 실제 형광펜 색상
        highlight_color_map = {0: None, 1: "#fff593", 2: "#e3fdc8", 3: "#ffb7de"}
        align_map = {0: "left", 1: "center", 2: "right"}

        return {
            "font": {
                "family": font_map.get(self.combo_naver_font.currentIndex(), "nanumgothic"),
                "size": fontsize_map.get(self.combo_naver_fontsize.currentIndex(), "se-fs15"),
                "lineHeight": lineheight_map.get(self.combo_naver_lineheight.currentIndex(), 1.8)
            },
            "heading": {
                "size": heading_size_map.get(self.combo_heading_style.currentIndex(), "se-fs18"),
                "bold": heading_bold_map.get(self.combo_heading_style.currentIndex(), False),
                "color": heading_color_map.get(self.combo_heading_color.currentIndex())
            },
            "quotation": {
                "style": quote_style_map.get(self.combo_quote_style.currentIndex(), "quotation_line")
            },
            "divider": {
                "style": divider_style_map.get(self.combo_divider_style.currentIndex(), "line1")
            },
            "emphasis": {
                "bold": self.chk_bold.isChecked(),
                "italic": self.chk_italic.isChecked(),
                "underline": self.chk_underline.isChecked(),
                "strikethrough": self.chk_strikethrough.isChecked(),
                "color": emphasis_color_map.get(self.combo_emphasis_color.currentIndex()),
                "highlightColor": highlight_color_map.get(self.combo_highlight_color.currentIndex())
            },
            "align": align_map.get(self.align_button_group.checkedId(), "left"),
            "sticker": {
                "enabled": self.combo_sticker_frequency.currentIndex() > 0,
                "pack": self.combo_sticker_pack.currentIndex(),
                "packName": self.combo_sticker_pack.currentData() or self.combo_sticker_pack.currentText(),  # 내부 ID
                "frequency": self.combo_sticker_frequency.currentIndex(),
                "frequencyName": self.combo_sticker_frequency.currentText()
            }
        }
