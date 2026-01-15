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
        group_category = QGroupBox("📁 블로그 카테고리 설정")
        category_layout = QVBoxLayout()
        
        category_desc = QLabel("각 탭에서 생성되는 컨텐츠가 업로드될 블로그 카테고리를 미리 설정합니다.\n실제 블로그에 등록된 카테고리명과 정확히 일치해야 합니다.")
        category_desc.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 10px;")
        category_desc.setWordWrap(True)
        category_layout.addWidget(category_desc)
        
        cat_form = QFormLayout()
        
        # 정보성 글쓰기 카테고리
        self.input_info_category = QLineEdit()
        self.input_info_category.setPlaceholderText("예: 자동차정보/유용한팁")
        cat_form.addRow("📝 정보성 글쓰기:", self.input_info_category)
        
        # 출고후기 카테고리
        self.input_delivery_category = QLineEdit()
        self.input_delivery_category.setPlaceholderText("예: 출고후기/고객이야기")
        cat_form.addRow("🚗 출고후기:", self.input_delivery_category)
        
        category_layout.addLayout(cat_form)
        
        category_notice = QLabel("💡 카테고리명은 대/소분류 포함 전체 경로로 입력하세요 (예: 자동차/유지관리)")
        category_notice.setStyleSheet("color: #888; font-size: 11px; margin-top: 5px;")
        category_layout.addWidget(category_notice)
        
        group_category.setLayout(category_layout)
        layout.addWidget(group_category)
        
        # ========== 2. 스타일 설정 ==========
        group_style = QGroupBox("✍️ 기본 작성 스타일")
        style_layout = QVBoxLayout()
        
        style_desc = QLabel("글 생성 시 기본으로 적용될 작성 스타일을 설정합니다.")
        style_desc.setStyleSheet("color: #666; font-size: 11px;")
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
        group_thumbnail = QGroupBox("🖼️ 썸네일 이미지 설정")
        thumb_layout = QVBoxLayout()
        
        thumb_desc = QLabel("원고 생성 후 대표 썸네일 이미지 생성 관련 설정입니다.")
        thumb_desc.setStyleSheet("color: #666; font-size: 11px;")
        thumb_layout.addWidget(thumb_desc)
        
        self.chk_auto_thumbnail = QCheckBox("원고 생성 후 자동으로 썸네일 생성")
        self.chk_auto_thumbnail.setChecked(True)
        thumb_layout.addWidget(self.chk_auto_thumbnail)
        
        thumb_notice = QLabel("💡 썸네일은 주제를 기반으로 AI가 자동 생성합니다.")
        thumb_notice.setStyleSheet("color: #888; font-size: 11px;")
        thumb_layout.addWidget(thumb_notice)
        
        group_thumbnail.setLayout(thumb_layout)
        layout.addWidget(group_thumbnail)
        
        # ========== 4. 출력 스타일 설정 ==========
        group_output = QGroupBox("🎨 출력 스타일 설정")
        output_layout = QVBoxLayout()
        
        output_desc = QLabel("생성되는 글의 포맷별 스타일을 설정합니다.")
        output_desc.setStyleSheet("color: #666; font-size: 11px;")
        output_layout.addWidget(output_desc)
        
        self.output_tabs = QTabWidget()
        
        # TEXT 설정 탭
        text_widget = QWidget()
        text_layout = QFormLayout(text_widget)
        
        self.combo_text_heading = QComboBox()
        self.combo_text_heading.addItems(["【 】 대괄호", "▶ 화살표", "● 원형", "■ 사각형", "※ 꽃표"])
        text_layout.addRow("소제목 스타일:", self.combo_text_heading)
        
        self.combo_text_emphasis = QComboBox()
        self.combo_text_emphasis.addItems(["** 별표 **", "「 」 꺽쇠", "★ ~ ★", "밑줄 ___"])
        text_layout.addRow("강조 표현:", self.combo_text_emphasis)
        
        self.combo_text_divider = QComboBox()
        self.combo_text_divider.addItems(["━━━━━━ (실선)", "- - - - - (점선)", "═══════ (이중선)", "빈 줄만"])
        text_layout.addRow("구분선:", self.combo_text_divider)
        
        self.combo_text_spacing = QComboBox()
        self.combo_text_spacing.addItems(["기본 (1줄)", "넓게 (2줄)", "좁게 (줄바꿈만)"])
        text_layout.addRow("문단 간격:", self.combo_text_spacing)
        
        self.output_tabs.addTab(text_widget, "📄 Text")
        
        # MARKDOWN 설정 탭
        md_widget = QWidget()
        md_layout = QFormLayout(md_widget)
        
        self.combo_md_heading = QComboBox()
        self.combo_md_heading.addItems(["## H2 사용", "### H3 사용", "**굵게** 사용"])
        md_layout.addRow("헤딩 레벨:", self.combo_md_heading)
        
        self.combo_md_list = QComboBox()
        self.combo_md_list.addItems(["- 하이픈", "* 별표", "1. 숫자"])
        md_layout.addRow("목록 기호:", self.combo_md_list)
        
        self.combo_md_qa = QComboBox()
        self.combo_md_qa.addItems(["> 인용문 스타일", "**Q:** 굵게 스타일", "### Q: 헤딩 스타일"])
        md_layout.addRow("Q&A 표현:", self.combo_md_qa)
        
        self.combo_md_narrative = QComboBox()
        self.combo_md_narrative.addItems(["짧은 문장 (모바일 최적화)", "긴 문장 (PC 최적화)"])
        md_layout.addRow("서술 방식:", self.combo_md_narrative)
        
        self.output_tabs.addTab(md_widget, "📝 Markdown")
        
        # HTML 설정 탭
        html_widget = QWidget()
        html_layout = QFormLayout(html_widget)
        
        self.combo_html_title = QComboBox()
        self.combo_html_title.addItems(["<h2> 태그", "<h3> 태그", "<strong> 굵게만"])
        html_layout.addRow("제목 스타일:", self.combo_html_title)
        
        self.combo_html_qa = QComboBox()
        self.combo_html_qa.addItems(["<blockquote> 인용", "<div class='qa'> 커스텀", "<details> 접기형"])
        html_layout.addRow("Q&A 스타일:", self.combo_html_qa)
        
        self.combo_html_color = QComboBox()
        self.combo_html_color.addItems(["네이버 그린 (#03C75A)", "블루 (#4A90E2)", "오렌지 (#F39C12)", "그레이 (#666)"])
        html_layout.addRow("테마 컬러:", self.combo_html_color)
        
        self.combo_html_font = QComboBox()
        self.combo_html_font.addItems(["기본 (시스템)", "나눔고딕", "맑은 고딕"])
        html_layout.addRow("본문 폰트:", self.combo_html_font)
        
        self.combo_html_box = QComboBox()
        self.combo_html_box.addItems(["배경색 박스", "테두리 박스", "없음"])
        html_layout.addRow("강조 박스:", self.combo_html_box)
        
        self.output_tabs.addTab(html_widget, "🌐 HTML")
        
        output_layout.addWidget(self.output_tabs)
        group_output.setLayout(output_layout)
        layout.addWidget(group_output)
        
        # ========== 저장 버튼 ==========
        self.btn_save = QPushButton("💾 글쓰기 설정 저장")
        self.btn_save.clicked.connect(self.save_settings)
        self.btn_save.setStyleSheet("""
            background-color: #03C75A; 
            color: white; 
            padding: 12px; 
            font-weight: bold;
            font-size: 14px;
        """)
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
        
        # 출력 스타일 설정
        self._load_output_style_settings()
    
    def _load_output_style_settings(self):
        """출력 스타일 설정 로드"""
        # Text 설정
        self.combo_text_heading.setCurrentIndex(
            self.settings.value("writing/style_text_heading", 0, type=int))
        self.combo_text_emphasis.setCurrentIndex(
            self.settings.value("writing/style_text_emphasis", 0, type=int))
        self.combo_text_divider.setCurrentIndex(
            self.settings.value("writing/style_text_divider", 0, type=int))
        self.combo_text_spacing.setCurrentIndex(
            self.settings.value("writing/style_text_spacing", 0, type=int))
        
        # Markdown 설정
        self.combo_md_heading.setCurrentIndex(
            self.settings.value("writing/style_md_heading", 0, type=int))
        self.combo_md_list.setCurrentIndex(
            self.settings.value("writing/style_md_list", 0, type=int))
        self.combo_md_qa.setCurrentIndex(
            self.settings.value("writing/style_md_qa", 0, type=int))
        self.combo_md_narrative.setCurrentIndex(
            self.settings.value("writing/style_md_narrative", 0, type=int))
        
        # HTML 설정
        self.combo_html_title.setCurrentIndex(
            self.settings.value("writing/style_html_title", 0, type=int))
        self.combo_html_qa.setCurrentIndex(
            self.settings.value("writing/style_html_qa", 0, type=int))
        self.combo_html_color.setCurrentIndex(
            self.settings.value("writing/style_html_color", 0, type=int))
        self.combo_html_font.setCurrentIndex(
            self.settings.value("writing/style_html_font", 0, type=int))
        self.combo_html_box.setCurrentIndex(
            self.settings.value("writing/style_html_box", 0, type=int))
    
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
        
        # 출력 스타일 설정
        self._save_output_style_settings()
        
        self.settings_changed.emit()
        QMessageBox.information(self, "완료", "글쓰기 설정이 저장되었습니다.")
    
    def _save_output_style_settings(self):
        """출력 스타일 설정 저장"""
        # Text 설정
        self.settings.setValue("writing/style_text_heading", 
                               self.combo_text_heading.currentIndex())
        self.settings.setValue("writing/style_text_emphasis", 
                               self.combo_text_emphasis.currentIndex())
        self.settings.setValue("writing/style_text_divider", 
                               self.combo_text_divider.currentIndex())
        self.settings.setValue("writing/style_text_spacing", 
                               self.combo_text_spacing.currentIndex())
        
        # Markdown 설정
        self.settings.setValue("writing/style_md_heading", 
                               self.combo_md_heading.currentIndex())
        self.settings.setValue("writing/style_md_list", 
                               self.combo_md_list.currentIndex())
        self.settings.setValue("writing/style_md_qa", 
                               self.combo_md_qa.currentIndex())
        self.settings.setValue("writing/style_md_narrative", 
                               self.combo_md_narrative.currentIndex())
        
        # HTML 설정
        self.settings.setValue("writing/style_html_title", 
                               self.combo_html_title.currentIndex())
        self.settings.setValue("writing/style_html_qa", 
                               self.combo_html_qa.currentIndex())
        self.settings.setValue("writing/style_html_color", 
                               self.combo_html_color.currentIndex())
        self.settings.setValue("writing/style_html_font", 
                               self.combo_html_font.currentIndex())
        self.settings.setValue("writing/style_html_box", 
                               self.combo_html_box.currentIndex())
    
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
    
    def get_output_style_settings(self) -> dict:
        """출력 스타일 설정값 반환"""
        return {
            "text": {
                "heading": self.combo_text_heading.currentText(),
                "emphasis": self.combo_text_emphasis.currentText(),
                "divider": self.combo_text_divider.currentText(),
                "spacing": self.combo_text_spacing.currentText(),
            },
            "markdown": {
                "heading": self.combo_md_heading.currentText(),
                "list": self.combo_md_list.currentText(),
                "qa": self.combo_md_qa.currentText(),
                "narrative": self.combo_md_narrative.currentText(),
            },
            "html": {
                "title": self.combo_html_title.currentText(),
                "qa": self.combo_html_qa.currentText(),
                "color": self.combo_html_color.currentText(),
                "font": self.combo_html_font.currentText(),
                "box": self.combo_html_box.currentText(),
            }
        }
