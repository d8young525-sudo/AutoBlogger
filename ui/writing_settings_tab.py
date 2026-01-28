"""
글쓰기 환경설정 탭 - 블로그 글쓰기 관련 설정 관리
v3.5.0: 글쓰기 관련 설정을 별도 탭으로 분리
- 탭별 블로그 카테고리 설정 (정보성글쓰기, 출고후기)
- 스타일 설정 (톤, 분량)
- 출력 스타일 설정 (TEXT/Markdown/HTML)
- 썸네일 이미지 생성 설정
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout, 
    QLineEdit, QPushButton, QMessageBox,
    QHBoxLayout, QLabel, QComboBox,
    QTabWidget, QScrollArea, QCheckBox, QRadioButton, QButtonGroup
)
from PySide6.QtCore import QSettings, Signal


class WritingSettingsTab(QWidget):
    """글쓰기 환경설정 탭"""
    
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
        
        # ========== 1. 탭별 블로그 카테고리 설정 ==========
        group_category = QGroupBox("블로그 카테고리 설정")
        category_layout = QVBoxLayout()
        
        category_desc = QLabel("각 탭에서 생성되는 컨텐츠가 업로드될 블로그 카테고리를 미리 설정합니다.\n실제 블로그에 등록된 카테고리명과 정확히 일치해야 합니다.")
        category_desc.setStyleSheet("color: #888; font-size: 12px; margin-bottom: 10px;")
        category_desc.setWordWrap(True)
        category_layout.addWidget(category_desc)
        
        cat_form = QFormLayout()
        
        # 정보성 글쓰기 카테고리
        self.input_info_category = QLineEdit()
        self.input_info_category.setPlaceholderText("예: 자동차정보/유용한팁")
        cat_form.addRow("정보성 글쓰기:", self.input_info_category)
        
        # 출고후기 카테고리
        self.input_delivery_category = QLineEdit()
        self.input_delivery_category.setPlaceholderText("예: 출고후기/고객이야기")
        cat_form.addRow("출고후기:", self.input_delivery_category)
        
        category_layout.addLayout(cat_form)
        
        category_notice = QLabel("카테고리명은 대/소분류 포함 전체 경로로 입력하세요 (예: 자동차/유지관리)")
        category_notice.setStyleSheet("color: #888; font-size: 11px; margin-top: 5px;")
        category_layout.addWidget(category_notice)
        
        group_category.setLayout(category_layout)
        layout.addWidget(group_category)
        
        # ========== 2. 스타일 설정 ==========
        group_style = QGroupBox("기본 작성 스타일")
        style_layout = QVBoxLayout()
        
        style_desc = QLabel("글 생성 시 기본으로 적용될 작성 스타일을 설정합니다.")
        style_desc.setStyleSheet("color: #888; font-size: 12px;")
        style_layout.addWidget(style_desc)
        
        style_form = QFormLayout()
        
        # 글 말투
        self.combo_default_tone = QComboBox()
        self.combo_default_tone.addItems([
            "친근한 이웃 (해요체)", 
            "신뢰감 있는 전문가 (하십시오체)", 
            "유머러스하고 재치있는 (드립+텐션업)", 
            "감성적인 에세이 스타일",
            "냉철한 팩트 전달/뉴스 스타일"
        ])
        style_form.addRow("글 말투:", self.combo_default_tone)
        
        # 분량
        self.combo_default_length = QComboBox()
        self.combo_default_length.addItems([
            "보통 (1,500자)", 
            "길게 (2,000자)", 
            "아주 길게 (2,500자)"
        ])
        style_form.addRow("기본 분량:", self.combo_default_length)
        
        style_layout.addLayout(style_form)
        group_style.setLayout(style_layout)
        layout.addWidget(group_style)
        
        # ========== 3. 썸네일 이미지 설정 ==========
        group_thumbnail = QGroupBox("썸네일 이미지 설정")
        thumb_layout = QVBoxLayout()
        
        thumb_desc = QLabel("원고 생성 후 대표 썸네일 이미지 생성 관련 설정입니다.")
        thumb_desc.setStyleSheet("color: #888; font-size: 12px;")
        thumb_layout.addWidget(thumb_desc)
        
        self.chk_auto_thumbnail = QCheckBox("원고 생성 후 자동으로 썸네일 생성")
        self.chk_auto_thumbnail.setChecked(True)
        thumb_layout.addWidget(self.chk_auto_thumbnail)
        
        thumb_notice = QLabel("썸네일은 주제를 기반으로 AI가 자동 생성합니다.")
        thumb_notice.setStyleSheet("color: #888; font-size: 11px;")
        thumb_layout.addWidget(thumb_notice)
        
        group_thumbnail.setLayout(thumb_layout)
        layout.addWidget(group_thumbnail)
        
        # ========== 4. 네이버 에디터 서식 설정 ==========
        group_naver_style = QGroupBox("네이버 에디터 서식 설정")
        naver_style_layout = QVBoxLayout()
        
        naver_desc = QLabel("네이버 블로그 에디터에 적용할 서식을 설정합니다.\nJSON 생성 시 이 설정값이 자동 적용됩니다.")
        naver_desc.setStyleSheet("color: #888; font-size: 12px; margin-bottom: 10px;")
        naver_desc.setWordWrap(True)
        naver_style_layout.addWidget(naver_desc)
        
        # 4-1. 폰트 설정
        font_group = QGroupBox("폰트 설정")
        font_layout = QFormLayout()
        
        self.combo_naver_font = QComboBox()
        self.combo_naver_font.addItems([
            "기본서체 (시스템)",
            "나눔고딕",
            "나눔명조",
            "나눔바른고딕",
            "나눔스퀘어",
            "마루부리",
            "다시시작해 (손글씨)",
            "바른히피 (손글씨)",
            "우리딸손글씨"
        ])
        self.combo_naver_font.setCurrentIndex(1)  # 나눔고딕 기본
        font_layout.addRow("본문 폰트:", self.combo_naver_font)
        
        self.combo_naver_fontsize = QComboBox()
        self.combo_naver_fontsize.addItems([
            "9pt (매우 작게)", 
            "10pt (작게)", 
            "11pt (약간 작게)", 
            "13pt (보통)", 
            "15pt (기본) - 권장", 
            "18pt (크게)", 
            "24pt (매우 크게)", 
            "32pt (제목용)"
        ])
        self.combo_naver_fontsize.setCurrentIndex(4)  # 15pt 기본
        font_layout.addRow("글자 크기:", self.combo_naver_fontsize)
        
        self.combo_naver_lineheight = QComboBox()
        self.combo_naver_lineheight.addItems([
            "1.5 (좁게)", "1.8 (보통) - 기본", "2.0 (넓게)", "2.5 (매우 넓게)"
        ])
        self.combo_naver_lineheight.setCurrentIndex(1)
        font_layout.addRow("줄 간격:", self.combo_naver_lineheight)
        
        font_group.setLayout(font_layout)
        naver_style_layout.addWidget(font_group)
        
        # 4-2. 소제목 설정
        heading_group = QGroupBox("소제목 설정")
        heading_layout = QFormLayout()
        
        self.combo_heading_style = QComboBox()
        self.combo_heading_style.addItems([
            "글자 크기만 키움 (18pt)",
            "글자 크기 + 굵게 (18pt + Bold)",
            "글자 크기 더 크게 (24pt)",
            "글자 크기 더 크게 + 굵게 (24pt + Bold)"
        ])
        heading_layout.addRow("소제목 스타일:", self.combo_heading_style)
        
        self.combo_heading_color = QComboBox()
        self.combo_heading_color.addItems([
            "검정 (기본)",
            "네이버 그린 (#03C75A)",
            "블루 (#4A90E2)",
            "다크 그레이 (#333333)"
        ])
        heading_layout.addRow("소제목 색상:", self.combo_heading_color)
        
        heading_group.setLayout(heading_layout)
        naver_style_layout.addWidget(heading_group)
        
        # 4-3. 인용구 설정
        quote_group = QGroupBox("인용구 설정")
        quote_layout = QFormLayout()
        
        self.combo_quote_style = QComboBox()
        self.combo_quote_style.addItems([
            "기본 (quotation_line) - 왼쪽 세로선",
            "말풍선 (quotation_bubble) - 말풍선 모양",
            "모서리 (quotation_corner) - 모서리 꽃음표",
            "밑줄 (quotation_underline) - 하단 밑줄",
            "포스트잇 (quotation_postit) - 메모지 스타일"
        ])
        quote_layout.addRow("인용구 모양:", self.combo_quote_style)
        
        quote_group.setLayout(quote_layout)
        naver_style_layout.addWidget(quote_group)
        
        # 4-4. 구분선 설정
        divider_group = QGroupBox("─ 구분선 설정")
        divider_layout = QFormLayout()
        
        self.combo_divider_style = QComboBox()
        self.combo_divider_style.addItems([
            "기본 실선 (line1)",
            "점선 (line2)",
            "이중선 (line3)",
            "굵은 실선 (line4)",
            "파선 (line5)",
            "점선 + 실선 (line6)",
            "장식선 (line7)"
        ])
        divider_layout.addRow("구분선 모양:", self.combo_divider_style)
        
        divider_group.setLayout(divider_layout)
        naver_style_layout.addWidget(divider_group)
        
        # 4-5. 텍스트 서식 설정
        text_format_group = QGroupBox("텍스트 서식")
        text_format_layout = QVBoxLayout()
        
        # 강조 표현 체크박스
        emphasis_row = QHBoxLayout()
        self.chk_bold = QCheckBox("굵게 (Bold)")
        self.chk_bold.setChecked(True)
        self.chk_italic = QCheckBox("기울임 (Italic)")
        self.chk_underline = QCheckBox("밑줄 (Underline)")
        self.chk_strikethrough = QCheckBox("취소선")
        
        emphasis_row.addWidget(QLabel("강조 표현:"))
        emphasis_row.addWidget(self.chk_bold)
        emphasis_row.addWidget(self.chk_italic)
        emphasis_row.addWidget(self.chk_underline)
        emphasis_row.addWidget(self.chk_strikethrough)
        emphasis_row.addStretch()
        text_format_layout.addLayout(emphasis_row)
        
        # 강조 색상
        color_form = QFormLayout()
        self.combo_emphasis_color = QComboBox()
        self.combo_emphasis_color.addItems([
            "없음 (기본 검정)",
            "네이버 그린 (#03C75A)",
            "블루 (#4A90E2)",
            "오렌지 (#F39C12)",
            "빨강 (#E74C3C)"
        ])
        color_form.addRow("강조 글자색:", self.combo_emphasis_color)
        
        self.combo_highlight_color = QComboBox()
        self.combo_highlight_color.addItems([
            "없음",
            "노란색 형광펜",
            "연두색 형광펜",
            "연분홍 형광펜"
        ])
        color_form.addRow("배경 강조색:", self.combo_highlight_color)
        text_format_layout.addLayout(color_form)
        
        text_format_group.setLayout(text_format_layout)
        naver_style_layout.addWidget(text_format_group)
        
        # 4-6. 정렬 설정
        align_group = QGroupBox("≡ 정렬 설정")
        align_layout = QHBoxLayout()
        
        self.radio_align_left = QRadioButton("왼쪽 정렬")
        self.radio_align_left.setChecked(True)
        self.radio_align_center = QRadioButton("가운데 정렬")
        self.radio_align_right = QRadioButton("오른쪽 정렬")
        
        self.align_button_group = QButtonGroup()
        self.align_button_group.addButton(self.radio_align_left, 0)
        self.align_button_group.addButton(self.radio_align_center, 1)
        self.align_button_group.addButton(self.radio_align_right, 2)
        
        align_layout.addWidget(self.radio_align_left)
        align_layout.addWidget(self.radio_align_center)
        align_layout.addWidget(self.radio_align_right)
        align_layout.addStretch()
        
        align_group.setLayout(align_layout)
        naver_style_layout.addWidget(align_group)
        
        # 4-7. 스티커 설정 (이모지 대체)
        sticker_group = QGroupBox("스티커 설정 (이모지 대체)")
        sticker_layout = QVBoxLayout()
        
        sticker_desc = QLabel("글 생성 시 이모지 대신 네이버 에디터 기본 스티커를 사용합니다.")
        sticker_desc.setStyleSheet("color: #888; font-size: 12px;")
        sticker_desc.setWordWrap(True)
        sticker_layout.addWidget(sticker_desc)
        
        sticker_form = QFormLayout()
        
        self.combo_sticker_pack = QComboBox()
        self.combo_sticker_pack.addItems([
            "기본 스티커 (심플)",
            "라인프렌즈 (브라운/코니)",
            "이모티콘 스타일",
            "귀여운 동물 스티커",
            "감정 표현 스티커"
        ])
        sticker_form.addRow("스티커 팩:", self.combo_sticker_pack)
        
        self.combo_sticker_frequency = QComboBox()
        self.combo_sticker_frequency.addItems([
            "사용 안함",
            "적게 (소제목에만)",
            "보통 (소제목 + 강조)",
            "많이 (문단마다)"
        ])
        self.combo_sticker_frequency.setCurrentIndex(2)  # 보통이 기본
        sticker_form.addRow("사용 빈도:", self.combo_sticker_frequency)
        
        sticker_layout.addLayout(sticker_form)
        
        sticker_group.setLayout(sticker_layout)
        naver_style_layout.addWidget(sticker_group)
        
        group_naver_style.setLayout(naver_style_layout)
        layout.addWidget(group_naver_style)
        
        # ========== 저장 버튼 ==========
        self.btn_save = QPushButton("글쓰기 설정 저장")
        self.btn_save.setObjectName("primaryButton")
        self.btn_save.clicked.connect(self.save_settings)
        layout.addWidget(self.btn_save)
        
        layout.addStretch()
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)
        
        # 저장된 설정 로드
        self.load_settings()
    
    def load_settings(self):
        """저장된 설정 로드"""
        # 카테고리 설정
        self.input_info_category.setText(
            self.settings.value("writing/info_category", ""))
        self.input_delivery_category.setText(
            self.settings.value("writing/delivery_category", ""))
        
        # 기본 스타일
        self.combo_default_tone.setCurrentIndex(
            self.settings.value("writing/default_tone", 0, type=int))
        self.combo_default_length.setCurrentIndex(
            self.settings.value("writing/default_length", 0, type=int))
        
        # 썸네일 설정
        self.chk_auto_thumbnail.setChecked(
            self.settings.value("writing/auto_thumbnail", True, type=bool))
        
        # 네이버 에디터 서식 설정
        self._load_naver_style_settings()
    
    def _load_naver_style_settings(self):
        """네이버 에디터 서식 설정 로드"""
        # 폰트 설정
        self.combo_naver_font.setCurrentIndex(
            self.settings.value("writing/naver_font", 0, type=int))
        self.combo_naver_fontsize.setCurrentIndex(
            self.settings.value("writing/naver_fontsize", 2, type=int))
        self.combo_naver_lineheight.setCurrentIndex(
            self.settings.value("writing/naver_lineheight", 1, type=int))
        
        # 소제목 설정
        self.combo_heading_style.setCurrentIndex(
            self.settings.value("writing/heading_style", 0, type=int))
        self.combo_heading_color.setCurrentIndex(
            self.settings.value("writing/heading_color", 0, type=int))
        
        # 인용구 설정
        self.combo_quote_style.setCurrentIndex(
            self.settings.value("writing/quote_style", 0, type=int))
        
        # 구분선 설정
        self.combo_divider_style.setCurrentIndex(
            self.settings.value("writing/divider_style", 0, type=int))
        
        # 텍스트 서식
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
        
        # 정렬 설정
        align_index = self.settings.value("writing/text_align", 0, type=int)
        if align_index == 0:
            self.radio_align_left.setChecked(True)
        elif align_index == 1:
            self.radio_align_center.setChecked(True)
        else:
            self.radio_align_right.setChecked(True)
        
        # 스티커 설정
        self.combo_sticker_pack.setCurrentIndex(
            self.settings.value("writing/sticker_pack", 0, type=int))
        self.combo_sticker_frequency.setCurrentIndex(
            self.settings.value("writing/sticker_frequency", 2, type=int))  # 기본: 보통
    
    def save_settings(self):
        """설정 저장"""
        # 카테고리 설정
        self.settings.setValue("writing/info_category", 
                               self.input_info_category.text().strip())
        self.settings.setValue("writing/delivery_category", 
                               self.input_delivery_category.text().strip())
        
        # 기본 스타일
        self.settings.setValue("writing/default_tone", 
                               self.combo_default_tone.currentIndex())
        self.settings.setValue("writing/default_length", 
                               self.combo_default_length.currentIndex())
        
        # 썸네일 설정
        self.settings.setValue("writing/auto_thumbnail", 
                               self.chk_auto_thumbnail.isChecked())
        
        # 네이버 에디터 서식 설정
        self._save_naver_style_settings()
        
        self.settings_changed.emit()
        QMessageBox.information(self, "완료", "글쓰기 설정이 저장되었습니다.")
    
    def _save_naver_style_settings(self):
        """네이버 에디터 서식 설정 저장"""
        # 폰트 설정
        self.settings.setValue("writing/naver_font", 
                               self.combo_naver_font.currentIndex())
        self.settings.setValue("writing/naver_fontsize", 
                               self.combo_naver_fontsize.currentIndex())
        self.settings.setValue("writing/naver_lineheight", 
                               self.combo_naver_lineheight.currentIndex())
        
        # 소제목 설정
        self.settings.setValue("writing/heading_style", 
                               self.combo_heading_style.currentIndex())
        self.settings.setValue("writing/heading_color", 
                               self.combo_heading_color.currentIndex())
        
        # 인용구 설정
        self.settings.setValue("writing/quote_style", 
                               self.combo_quote_style.currentIndex())
        
        # 구분선 설정
        self.settings.setValue("writing/divider_style", 
                               self.combo_divider_style.currentIndex())
        
        # 텍스트 서식
        self.settings.setValue("writing/text_bold", self.chk_bold.isChecked())
        self.settings.setValue("writing/text_italic", self.chk_italic.isChecked())
        self.settings.setValue("writing/text_underline", self.chk_underline.isChecked())
        self.settings.setValue("writing/text_strikethrough", self.chk_strikethrough.isChecked())
        
        self.settings.setValue("writing/emphasis_color", 
                               self.combo_emphasis_color.currentIndex())
        self.settings.setValue("writing/highlight_color", 
                               self.combo_highlight_color.currentIndex())
        
        # 정렬 설정
        self.settings.setValue("writing/text_align", 
                               self.align_button_group.checkedId())
        
        # 스티커 설정
        self.settings.setValue("writing/sticker_pack", 
                               self.combo_sticker_pack.currentIndex())
        self.settings.setValue("writing/sticker_frequency", 
                               self.combo_sticker_frequency.currentIndex())
    
    # ========== 외부에서 호출하는 Getter 메서드들 ==========
    
    def get_info_category(self) -> str:
        """정보성 글쓰기 카테고리 반환"""
        return self.input_info_category.text().strip()
    
    def get_delivery_category(self) -> str:
        """출고후기 카테고리 반환"""
        return self.input_delivery_category.text().strip()
    
    def get_default_tone(self) -> str:
        """기본 톤 반환"""
        return self.combo_default_tone.currentText()
    
    def get_default_tone_index(self) -> int:
        """기본 톤 인덱스 반환"""
        return self.combo_default_tone.currentIndex()
    
    def get_default_length(self) -> str:
        """기본 분량 반환"""
        return self.combo_default_length.currentText()
    
    def get_default_length_index(self) -> int:
        """기본 분량 인덱스 반환"""
        return self.combo_default_length.currentIndex()
    
    def is_auto_thumbnail_enabled(self) -> bool:
        """자동 썸네일 생성 여부"""
        return self.chk_auto_thumbnail.isChecked()
    
    def get_naver_editor_style_settings(self) -> dict:
        """네이버 에디터 서식 설정값 반환 (JSON 생성 시 사용)"""
        # 폰트 매핑 (실제 네이버 블로그 에디터 기준)
        font_map = {
            0: "system",           # 기본서체
            1: "nanumgothic",      # 나눔고딕
            2: "nanummyeongjo",    # 나눔명조
            3: "nanumbarungothic", # 나눔바른고딕
            4: "nanumsquare",      # 나눔스퀘어
            5: "maruburi",         # 마루부리
            6: "dasisijakae",      # 다시시작해
            7: "barenhipi",        # 바른히피
            8: "uridalsonglssi"    # 우리딸손글씨
        }
        
        fontsize_map = {
            0: "se-fs9", 1: "se-fs10", 2: "se-fs11",
            3: "se-fs13", 4: "se-fs15", 5: "se-fs18",
            6: "se-fs24", 7: "se-fs32"
        }
        
        lineheight_map = {0: 1.5, 1: 1.8, 2: 2.0, 3: 2.5}
        
        # 소제목 크기/볼드 매핑
        heading_size_map = {0: "se-fs18", 1: "se-fs18", 2: "se-fs24", 3: "se-fs24"}
        heading_bold_map = {0: False, 1: True, 2: False, 3: True}
        
        heading_color_map = {
            0: None,  # 기본 검정
            1: "#03C75A",  # 네이버 그린
            2: "#4A90E2",  # 블루
            3: "#333333"   # 다크 그레이
        }
        
        # 인용구 스타일 매핑
        quote_style_map = {
            0: "quotation_line",
            1: "quotation_bubble",
            2: "quotation_corner", 
            3: "quotation_underline",
            4: "quotation_postit"
        }
        
        # 구분선 스타일 매핑
        divider_style_map = {
            0: "line1", 1: "line2", 2: "line3", 3: "line4",
            4: "line5", 5: "line6", 6: "line7"
        }
        
        # 강조 색상 매핑
        emphasis_color_map = {
            0: None,  # 기본 검정
            1: "#03C75A",  # 네이버 그린
            2: "#4A90E2",  # 블루
            3: "#F39C12",  # 오렌지
            4: "#E74C3C"   # 빨강
        }
        
        highlight_color_map = {
            0: None,
            1: "#FFFF00",  # 노란색
            2: "#90EE90",  # 연두색
            3: "#FFB6C1"   # 연분홍
        }
        
        # 정렬 매핑
        align_map = {0: "left", 1: "center", 2: "right"}
        
        return {
            "font": {
                "family": font_map.get(self.combo_naver_font.currentIndex(), "se-ff-nanumgothic"),
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
                "enabled": self.combo_sticker_frequency.currentIndex() > 0,  # 0 = 사용안함
                "pack": self.combo_sticker_pack.currentIndex(),
                "packName": self.combo_sticker_pack.currentText(),
                "frequency": self.combo_sticker_frequency.currentIndex(),
                "frequencyName": self.combo_sticker_frequency.currentText()
            }
        }
    
    def get_sticker_settings(self) -> dict:
        """스티커 설정값 반환"""
        freq_idx = self.combo_sticker_frequency.currentIndex()
        return {
            "enabled": freq_idx > 0,  # 0 = 사용안함
            "pack": self.combo_sticker_pack.currentIndex(),
            "packName": self.combo_sticker_pack.currentText(),
            "frequency": freq_idx,
            "frequencyName": self.combo_sticker_frequency.currentText()
        }
