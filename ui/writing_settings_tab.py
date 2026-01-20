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
    QTabWidget, QScrollArea, QCheckBox, QRadioButton, QButtonGroup,
    QFileDialog
)
from PySide6.QtCore import QSettings, Signal
import os


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
        
        # 썸네일 저장 경로 설정
        path_layout = QHBoxLayout()
        path_label = QLabel("썸네일 저장 경로:")
        path_layout.addWidget(path_label)
        
        self.input_thumbnail_path = QLineEdit()
        self.input_thumbnail_path.setPlaceholderText("예: C:\\Users\\Pictures\\blog_thumbnails")
        path_layout.addWidget(self.input_thumbnail_path)
        
        self.btn_browse_path = QPushButton("📁")
        self.btn_browse_path.setFixedWidth(40)
        self.btn_browse_path.clicked.connect(self._browse_thumbnail_path)
        path_layout.addWidget(self.btn_browse_path)
        
        thumb_layout.addLayout(path_layout)
        
        # 자동 등록 옵션
        self.chk_auto_upload_thumbnail = QCheckBox("생성 후 자동으로 대표 이미지 등록")
        self.chk_auto_upload_thumbnail.setChecked(True)
        thumb_layout.addWidget(self.chk_auto_upload_thumbnail)
        
        thumb_notice = QLabel("💡 썸네일은 주제를 기반으로 AI가 자동 생성하며, 지정된 경로에 저장됩니다.")
        thumb_notice.setStyleSheet("color: #888; font-size: 11px;")
        thumb_layout.addWidget(thumb_notice)
        
        group_thumbnail.setLayout(thumb_layout)
        layout.addWidget(group_thumbnail)
        
        # ========== 4. 출력 스타일 설정 (텍스트 전용) ==========
        group_output = QGroupBox("🎨 출력 스타일 설정")
        output_layout = QVBoxLayout()
        
        output_desc = QLabel("생성되는 글의 텍스트 스타일을 설정합니다.\n네이버 블로그 에디터에 맞춰 순수 텍스트 형식으로 생성됩니다.")
        output_desc.setStyleSheet("color: #666; font-size: 11px;")
        output_layout.addWidget(output_desc)
        
        text_form = QFormLayout()
        
        # 소제목 스타일
        self.combo_text_heading = QComboBox()
        self.combo_text_heading.addItems([
            "【 】 대괄호", 
            "▶ 화살표", 
            "● 원형 불릿", 
            "■ 사각형", 
            "★ 별표",
            "— 대시",
            "본문과 동일 (구분 없음)"
        ])
        text_form.addRow("소제목 스타일:", self.combo_text_heading)
        
        # 강조 표현
        self.combo_text_emphasis = QComboBox()
        self.combo_text_emphasis.addItems([
            "「강조」 꺽쇠괄호", 
            "'강조' 작은따옴표", 
            "\"강조\" 큰따옴표",
            "*강조* 별표",
            "강조 없음 (일반 텍스트)"
        ])
        text_form.addRow("강조 표현:", self.combo_text_emphasis)
        
        # 구분선
        self.combo_text_divider = QComboBox()
        self.combo_text_divider.addItems([
            "━━━━━━━━ (실선)", 
            "- - - - - - - - (점선)", 
            "════════ (이중선)", 
            "빈 줄 2개",
            "구분선 없음"
        ])
        text_form.addRow("구분선:", self.combo_text_divider)
        
        # 문단 간격
        self.combo_text_spacing = QComboBox()
        self.combo_text_spacing.addItems([
            "기본 (빈 줄 1개)", 
            "넓게 (빈 줄 2개)", 
            "좁게 (줄바꿈만)"
        ])
        text_form.addRow("문단 간격:", self.combo_text_spacing)
        
        # Q&A 스타일
        self.combo_text_qa = QComboBox()
        self.combo_text_qa.addItems([
            "Q. 질문 / A. 답변",
            "❓ 질문 / ✔️ 답변",
            "▶ 질문 / → 답변",
            "일반 문단 (구분 없음)"
        ])
        text_form.addRow("Q&A 스타일:", self.combo_text_qa)
        
        # 목록 기호
        self.combo_text_list = QComboBox()
        self.combo_text_list.addItems([
            "• 불릿 기호",
            "- 하이픈",
            "▸ 삼각형",
            "1. 2. 3. 숫자",
            "① ② ③ 원문자"
        ])
        text_form.addRow("목록 기호:", self.combo_text_list)
        
        output_layout.addLayout(text_form)
        
        output_notice = QLabel("💡 설정한 스타일은 AI 글 생성 시 자동으로 적용됩니다.")
        output_notice.setStyleSheet("color: #888; font-size: 11px; margin-top: 10px;")
        output_layout.addWidget(output_notice)
        
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
        
        # 썸네일 저장 경로 (기본값: 바탕화면)
        default_path = os.path.join(os.path.expanduser("~"), "Desktop", "blog_thumbnails")
        self.input_thumbnail_path.setText(
            self.settings.value("writing/thumbnail_path", default_path))
        
        # 자동 등록 설정
        self.chk_auto_upload_thumbnail.setChecked(
            self.settings.value("writing/auto_upload_thumbnail", True, type=bool))
        
        # 출력 스타일 설정
        self._load_output_style_settings()
    
    def _load_output_style_settings(self):
        """출력 스타일 설정 로드 (텍스트 전용)"""
        self.combo_text_heading.setCurrentIndex(
            self.settings.value("writing/style_text_heading", 0, type=int))
        self.combo_text_emphasis.setCurrentIndex(
            self.settings.value("writing/style_text_emphasis", 0, type=int))
        self.combo_text_divider.setCurrentIndex(
            self.settings.value("writing/style_text_divider", 0, type=int))
        self.combo_text_spacing.setCurrentIndex(
            self.settings.value("writing/style_text_spacing", 0, type=int))
        self.combo_text_qa.setCurrentIndex(
            self.settings.value("writing/style_text_qa", 0, type=int))
        self.combo_text_list.setCurrentIndex(
            self.settings.value("writing/style_text_list", 0, type=int))
    
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
        self.settings.setValue("writing/thumbnail_path",
                               self.input_thumbnail_path.text().strip())
        self.settings.setValue("writing/auto_upload_thumbnail",
                               self.chk_auto_upload_thumbnail.isChecked())
        
        # 출력 스타일 설정
        self._save_output_style_settings()
        
        self.settings_changed.emit()
        QMessageBox.information(self, "완료", "글쓰기 설정이 저장되었습니다.")
    
    def _save_output_style_settings(self):
        """출력 스타일 설정 저장 (텍스트 전용)"""
        self.settings.setValue("writing/style_text_heading", 
                               self.combo_text_heading.currentIndex())
        self.settings.setValue("writing/style_text_emphasis", 
                               self.combo_text_emphasis.currentIndex())
        self.settings.setValue("writing/style_text_divider", 
                               self.combo_text_divider.currentIndex())
        self.settings.setValue("writing/style_text_spacing", 
                               self.combo_text_spacing.currentIndex())
        self.settings.setValue("writing/style_text_qa", 
                               self.combo_text_qa.currentIndex())
        self.settings.setValue("writing/style_text_list", 
                               self.combo_text_list.currentIndex())
    
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
    
    def get_thumbnail_path(self) -> str:
        """썸네일 저장 경로 반환"""
        path = self.input_thumbnail_path.text().strip()
        if not path:
            path = os.path.join(os.path.expanduser("~"), "Desktop", "blog_thumbnails")
        return path
    
    def is_auto_upload_thumbnail_enabled(self) -> bool:
        """자동 대표 이미지 등록 여부"""
        return self.chk_auto_upload_thumbnail.isChecked()
    
    def _browse_thumbnail_path(self):
        """썸네일 저장 경로 선택 다이얼로그"""
        current_path = self.input_thumbnail_path.text().strip()
        if not current_path or not os.path.exists(current_path):
            current_path = os.path.expanduser("~")
        
        folder = QFileDialog.getExistingDirectory(
            self, "썸네일 저장 폴더 선택", current_path
        )
        if folder:
            self.input_thumbnail_path.setText(folder)
    
    def get_output_style_settings(self) -> dict:
        """출력 스타일 설정값 반환 (텍스트 전용)"""
        return {
            "heading": self.combo_text_heading.currentText(),
            "emphasis": self.combo_text_emphasis.currentText(),
            "divider": self.combo_text_divider.currentText(),
            "spacing": self.combo_text_spacing.currentText(),
            "qa": self.combo_text_qa.currentText(),
            "list": self.combo_text_list.currentText(),
        }
