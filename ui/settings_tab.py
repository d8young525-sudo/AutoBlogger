"""
환경 설정 탭 - 네이버 계정, 고정 인사말/맺음말, 명함 이미지, 출력 스타일, 
               이모티콘 그룹, 이미지 생성 설정
v3.4.0: 이모티콘 그룹 선택, 이미지 생성 옵션 추가
"""
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout, 
    QLineEdit, QTextEdit, QPushButton, QMessageBox,
    QHBoxLayout, QLabel, QFileDialog, QComboBox,
    QTabWidget, QScrollArea, QListWidget, QListWidgetItem,
    QAbstractItemView, QCheckBox, QRadioButton, QButtonGroup
)
from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QPixmap


class SettingsTab(QWidget):
    """환경 설정 탭"""
    
    # 설정 변경 시그널 (다른 탭에서 사용)
    settings_changed = Signal()
    
    def __init__(self):
        super().__init__()
        self.settings = QSettings("MySoft", "NaverBlogBot")
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        
        # 스크롤 영역 추가
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        
        # ========== 1. 네이버 계정 설정 ==========
        group_account = QGroupBox("🔐 네이버 계정 (블로그 발행용)")
        account_form = QFormLayout()
        
        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText("네이버 아이디")
        self.input_pw = QLineEdit()
        self.input_pw.setEchoMode(QLineEdit.Password)
        self.input_pw.setPlaceholderText("네이버 비밀번호")
        
        account_form.addRow("네이버 ID:", self.input_id)
        account_form.addRow("네이버 PW:", self.input_pw)
        
        account_notice = QLabel("⚠️ 네이버 계정은 블로그 자동 발행에만 사용됩니다.")
        account_notice.setStyleSheet("color: #888; font-size: 11px;")
        account_form.addRow("", account_notice)
        
        group_account.setLayout(account_form)
        layout.addWidget(group_account)
        
        # ========== 2. 블로그 카테고리 설정 ==========
        group_category = QGroupBox("📁 블로그 카테고리 설정")
        category_layout = QVBoxLayout()
        
        category_desc = QLabel("블로그에 등록된 카테고리명을 입력하면 발행 시 자동으로 선택됩니다.")
        category_desc.setStyleSheet("color: #666; font-size: 11px;")
        category_layout.addWidget(category_desc)
        
        # 카테고리 입력
        cat_form = QFormLayout()
        
        self.input_category = QLineEdit()
        self.input_category.setPlaceholderText("예: 자동차/차량관리")
        cat_form.addRow("기본 카테고리:", self.input_category)
        
        category_layout.addLayout(cat_form)
        
        # 카테고리 목록 관리
        category_layout.addWidget(QLabel("📋 자주 사용하는 카테고리 목록:"))
        
        self.list_categories = QListWidget()
        self.list_categories.setMaximumHeight(100)
        self.list_categories.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_categories.itemDoubleClicked.connect(self._on_category_double_click)
        category_layout.addWidget(self.list_categories)
        
        cat_btn_layout = QHBoxLayout()
        
        self.input_new_category = QLineEdit()
        self.input_new_category.setPlaceholderText("새 카테고리 입력")
        cat_btn_layout.addWidget(self.input_new_category)
        
        btn_add_cat = QPushButton("➕ 추가")
        btn_add_cat.clicked.connect(self._add_category)
        btn_add_cat.setStyleSheet("padding: 5px 10px;")
        cat_btn_layout.addWidget(btn_add_cat)
        
        btn_del_cat = QPushButton("🗑️ 삭제")
        btn_del_cat.clicked.connect(self._delete_category)
        btn_del_cat.setStyleSheet("padding: 5px 10px;")
        cat_btn_layout.addWidget(btn_del_cat)
        
        category_layout.addLayout(cat_btn_layout)
        
        cat_notice = QLabel("💡 더블클릭하면 기본 카테고리로 설정됩니다.")
        cat_notice.setStyleSheet("color: #888; font-size: 11px;")
        category_layout.addWidget(cat_notice)
        
        group_category.setLayout(category_layout)
        layout.addWidget(group_category)
        
        # ========== 3. 고정 인사말 ==========
        group_intro = QGroupBox("👋 고정 인사말 (글 시작 부분)")
        intro_layout = QVBoxLayout()
        
        self.input_intro = QTextEdit()
        self.input_intro.setMaximumHeight(80)
        self.input_intro.setPlaceholderText("예: 안녕하세요, 자동차 전문 상담사 OOO입니다!")
        intro_layout.addWidget(self.input_intro)
        
        group_intro.setLayout(intro_layout)
        layout.addWidget(group_intro)
        
        # ========== 4. 고정 맺음말 + 명함 이미지 ==========
        group_outro = QGroupBox("🤝 고정 맺음말 (글 마무리 부분)")
        outro_layout = QVBoxLayout()
        
        self.input_outro = QTextEdit()
        self.input_outro.setMaximumHeight(80)
        self.input_outro.setPlaceholderText("예: 차량 구매 상담은 언제든 연락주세요! 감사합니다 😊")
        outro_layout.addWidget(self.input_outro)
        
        # 명함 이미지 섹션
        outro_layout.addWidget(QLabel("📇 명함/연락처 이미지 (선택):"))
        
        image_layout = QHBoxLayout()
        
        # 이미지 미리보기
        self.lbl_image_preview = QLabel()
        self.lbl_image_preview.setFixedSize(150, 90)
        self.lbl_image_preview.setStyleSheet("border: 1px solid #ddd; background-color: #f9f9f9;")
        self.lbl_image_preview.setAlignment(Qt.AlignCenter)
        image_layout.addWidget(self.lbl_image_preview)
        
        # 이미지 버튼들
        btn_image_layout = QVBoxLayout()
        
        self.btn_select_image = QPushButton("📁 이미지 선택")
        self.btn_select_image.clicked.connect(self.select_outro_image)
        self.btn_select_image.setStyleSheet("padding: 8px;")
        btn_image_layout.addWidget(self.btn_select_image)
        
        self.btn_clear_image = QPushButton("🗑️ 삭제")
        self.btn_clear_image.clicked.connect(self.clear_outro_image)
        self.btn_clear_image.setStyleSheet("padding: 8px;")
        btn_image_layout.addWidget(self.btn_clear_image)
        
        btn_image_layout.addStretch()
        image_layout.addLayout(btn_image_layout)
        image_layout.addStretch()
        
        outro_layout.addLayout(image_layout)
        
        # 이미지 경로 표시
        self.lbl_image_path = QLabel("")
        self.lbl_image_path.setStyleSheet("color: #666; font-size: 11px;")
        outro_layout.addWidget(self.lbl_image_path)
        
        image_notice = QLabel("💡 지원 형식: JPG, JPEG, PNG, BMP, GIF")
        image_notice.setStyleSheet("color: #888; font-size: 11px;")
        outro_layout.addWidget(image_notice)
        
        group_outro.setLayout(outro_layout)
        layout.addWidget(group_outro)
        
        # ========== 5. 이모티콘 설정 (NEW) ==========
        group_emoticon = QGroupBox("😊 이모티콘 설정")
        emoticon_layout = QVBoxLayout()
        
        emoticon_desc = QLabel("생성되는 글에 사용할 이모티콘 그룹을 선택하세요.")
        emoticon_desc.setStyleSheet("color: #666; font-size: 11px;")
        emoticon_layout.addWidget(emoticon_desc)
        
        # 이모티콘 그룹 체크박스들
        self.emoticon_checkboxes = {}
        emoticon_groups = [
            ("basic", "기본 이모지", "👍 ❤️ ⭐ ✅ 💡"),
            ("business", "비즈니스", "📈 💰 🤝 📋 🎯"),
            ("car", "자동차", "🚗 ⛽ 🔑 🛣️ 🚦"),
            ("food", "음식/맛집", "🍽️ ☕ 🍕 😋 ⭐"),
            ("travel", "여행", "✈️ 🏨 📷 🗺️ 🧳"),
            ("expression", "표정/감정", "😊 🤔 😎 🤩 😍"),
            ("decoration", "꾸미기", "✨ 🎉 🏆 🔥 👑"),
        ]
        
        for group_id, group_name, preview in emoticon_groups:
            chk = QCheckBox(f"{group_name} ({preview})")
            chk.setChecked(group_id in ["basic", "decoration"])  # 기본 선택
            self.emoticon_checkboxes[group_id] = chk
            emoticon_layout.addWidget(chk)
        
        group_emoticon.setLayout(emoticon_layout)
        layout.addWidget(group_emoticon)
        
        # ========== 6. 이미지 생성 설정 (NEW) ==========
        group_image_gen = QGroupBox("🖼️ 이미지 생성 설정")
        image_gen_layout = QVBoxLayout()
        
        image_gen_desc = QLabel("AI 이미지 생성 관련 기본 설정입니다.")
        image_gen_desc.setStyleSheet("color: #666; font-size: 11px;")
        image_gen_layout.addWidget(image_gen_desc)
        
        # 썸네일 설정
        image_gen_layout.addWidget(QLabel("📷 대표 썸네일 이미지:"))
        
        self.radio_thumb_ai = QRadioButton("AI 자동 생성")
        self.radio_thumb_ai.setChecked(True)
        self.radio_thumb_none = QRadioButton("생성 안 함")
        
        self.thumb_group = QButtonGroup()
        self.thumb_group.addButton(self.radio_thumb_ai)
        self.thumb_group.addButton(self.radio_thumb_none)
        
        thumb_row = QHBoxLayout()
        thumb_row.addWidget(self.radio_thumb_ai)
        thumb_row.addWidget(self.radio_thumb_none)
        thumb_row.addStretch()
        image_gen_layout.addLayout(thumb_row)
        
        # 본문 삽화 설정
        image_gen_layout.addWidget(QLabel("🎨 본문 삽화 이미지:"))
        
        self.radio_illust_ai = QRadioButton("AI 자동 생성")
        self.radio_illust_none = QRadioButton("생성 안 함 (권장)")
        self.radio_illust_none.setChecked(True)
        
        self.illust_group = QButtonGroup()
        self.illust_group.addButton(self.radio_illust_ai)
        self.illust_group.addButton(self.radio_illust_none)
        
        illust_row = QHBoxLayout()
        illust_row.addWidget(self.radio_illust_ai)
        illust_row.addWidget(self.radio_illust_none)
        illust_row.addStretch()
        image_gen_layout.addLayout(illust_row)
        
        illust_notice = QLabel("💡 본문 삽화는 주제에 따라 품질 차이가 크므로 필요시만 사용을 권장합니다.")
        illust_notice.setStyleSheet("color: #888; font-size: 11px;")
        illust_notice.setWordWrap(True)
        image_gen_layout.addWidget(illust_notice)
        
        group_image_gen.setLayout(image_gen_layout)
        layout.addWidget(group_image_gen)
        
        # ========== 7. 출력 스타일 설정 ==========
        group_output = QGroupBox("🎨 출력 스타일 설정")
        output_layout = QVBoxLayout()
        
        output_desc = QLabel("생성되는 글의 기본 스타일을 설정합니다. 자주 변경하지 않는 설정입니다.")
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
        self.btn_save = QPushButton("💾 모든 설정 저장")
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
        # 계정 정보
        self.input_id.setText(self.settings.value("id", ""))
        self.input_pw.setText(self.settings.value("pw", ""))
        self.input_intro.setText(self.settings.value("intro", ""))
        self.input_outro.setText(self.settings.value("outro", ""))
        
        # 카테고리 설정
        self.input_category.setText(self.settings.value("default_category", ""))
        categories = self.settings.value("category_list", [])
        if categories:
            for cat in categories:
                self.list_categories.addItem(cat)
        
        # 명함 이미지 로드
        outro_image = self.settings.value("outro_image", "")
        if outro_image and os.path.exists(outro_image):
            self.load_image_preview(outro_image)
            self.lbl_image_path.setText(f"📎 {os.path.basename(outro_image)}")
        else:
            self.lbl_image_preview.setText("이미지 없음")
        
        # 이모티콘 그룹 설정
        selected_emoticons = self.settings.value("emoticon_groups", ["basic", "decoration"])
        for group_id, chk in self.emoticon_checkboxes.items():
            chk.setChecked(group_id in selected_emoticons)
        
        # 이미지 생성 설정
        thumb_mode = self.settings.value("thumbnail_mode", "ai")
        self.radio_thumb_ai.setChecked(thumb_mode == "ai")
        self.radio_thumb_none.setChecked(thumb_mode != "ai")
        
        illust_mode = self.settings.value("illustration_mode", "none")
        self.radio_illust_ai.setChecked(illust_mode == "ai")
        self.radio_illust_none.setChecked(illust_mode != "ai")
        
        # 출력 스타일 설정 로드
        self._load_output_style_settings()
    
    def _load_output_style_settings(self):
        """출력 스타일 설정 로드"""
        # Text 설정
        self.combo_text_heading.setCurrentIndex(
            self.settings.value("style_text_heading", 0, type=int))
        self.combo_text_emphasis.setCurrentIndex(
            self.settings.value("style_text_emphasis", 0, type=int))
        self.combo_text_divider.setCurrentIndex(
            self.settings.value("style_text_divider", 0, type=int))
        self.combo_text_spacing.setCurrentIndex(
            self.settings.value("style_text_spacing", 0, type=int))
        
        # Markdown 설정
        self.combo_md_heading.setCurrentIndex(
            self.settings.value("style_md_heading", 0, type=int))
        self.combo_md_list.setCurrentIndex(
            self.settings.value("style_md_list", 0, type=int))
        self.combo_md_qa.setCurrentIndex(
            self.settings.value("style_md_qa", 0, type=int))
        self.combo_md_narrative.setCurrentIndex(
            self.settings.value("style_md_narrative", 0, type=int))
        
        # HTML 설정
        self.combo_html_title.setCurrentIndex(
            self.settings.value("style_html_title", 0, type=int))
        self.combo_html_qa.setCurrentIndex(
            self.settings.value("style_html_qa", 0, type=int))
        self.combo_html_color.setCurrentIndex(
            self.settings.value("style_html_color", 0, type=int))
        self.combo_html_font.setCurrentIndex(
            self.settings.value("style_html_font", 0, type=int))
        self.combo_html_box.setCurrentIndex(
            self.settings.value("style_html_box", 0, type=int))
    
    def _save_output_style_settings(self):
        """출력 스타일 설정 저장"""
        # Text 설정
        self.settings.setValue("style_text_heading", self.combo_text_heading.currentIndex())
        self.settings.setValue("style_text_emphasis", self.combo_text_emphasis.currentIndex())
        self.settings.setValue("style_text_divider", self.combo_text_divider.currentIndex())
        self.settings.setValue("style_text_spacing", self.combo_text_spacing.currentIndex())
        
        # Markdown 설정
        self.settings.setValue("style_md_heading", self.combo_md_heading.currentIndex())
        self.settings.setValue("style_md_list", self.combo_md_list.currentIndex())
        self.settings.setValue("style_md_qa", self.combo_md_qa.currentIndex())
        self.settings.setValue("style_md_narrative", self.combo_md_narrative.currentIndex())
        
        # HTML 설정
        self.settings.setValue("style_html_title", self.combo_html_title.currentIndex())
        self.settings.setValue("style_html_qa", self.combo_html_qa.currentIndex())
        self.settings.setValue("style_html_color", self.combo_html_color.currentIndex())
        self.settings.setValue("style_html_font", self.combo_html_font.currentIndex())
        self.settings.setValue("style_html_box", self.combo_html_box.currentIndex())
    
    def get_output_style_settings(self) -> dict:
        """출력 스타일 설정값 반환 (다른 탭에서 사용)"""
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
    
    def get_default_category(self) -> str:
        """기본 카테고리 반환"""
        return self.input_category.text().strip()
    
    def get_category_list(self) -> list:
        """카테고리 목록 반환"""
        categories = []
        for i in range(self.list_categories.count()):
            categories.append(self.list_categories.item(i).text())
        return categories
    
    def get_selected_emoticon_groups(self) -> list:
        """선택된 이모티콘 그룹 반환"""
        groups = []
        for group_id, chk in self.emoticon_checkboxes.items():
            if chk.isChecked():
                groups.append(group_id)
        return groups
    
    def get_image_settings(self) -> dict:
        """이미지 생성 설정 반환"""
        return {
            "thumbnail_mode": "ai" if self.radio_thumb_ai.isChecked() else "none",
            "illustration_mode": "ai" if self.radio_illust_ai.isChecked() else "none",
        }
    
    def _add_category(self):
        """카테고리 추가"""
        new_cat = self.input_new_category.text().strip()
        if new_cat:
            # 중복 확인
            for i in range(self.list_categories.count()):
                if self.list_categories.item(i).text() == new_cat:
                    QMessageBox.warning(self, "알림", "이미 존재하는 카테고리입니다.")
                    return
            
            self.list_categories.addItem(new_cat)
            self.input_new_category.clear()
    
    def _delete_category(self):
        """선택된 카테고리 삭제"""
        current_item = self.list_categories.currentItem()
        if current_item:
            self.list_categories.takeItem(self.list_categories.row(current_item))
    
    def _on_category_double_click(self, item):
        """카테고리 더블클릭 시 기본 카테고리로 설정"""
        self.input_category.setText(item.text())
        QMessageBox.information(self, "설정 완료", f"'{item.text()}' 카테고리가 기본값으로 설정되었습니다.")
    
    def select_outro_image(self):
        """명함 이미지 선택"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "명함/연락처 이미지 선택",
            "",
            "이미지 파일 (*.png *.jpg *.jpeg *.bmp *.gif);;모든 파일 (*.*)"
        )
        
        if file_path:
            if self.load_image_preview(file_path):
                self.settings.setValue("outro_image", file_path)
                self.lbl_image_path.setText(f"📎 {os.path.basename(file_path)}")
                QMessageBox.information(self, "완료", "명함 이미지가 설정되었습니다.")
    
    def load_image_preview(self, file_path: str) -> bool:
        """이미지 미리보기 로드"""
        try:
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                self.lbl_image_preview.setText("로드 실패")
                return False
            
            # 미리보기 크기에 맞게 조정
            scaled = pixmap.scaled(
                150, 90, 
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.lbl_image_preview.setPixmap(scaled)
            return True
        except Exception as e:
            self.lbl_image_preview.setText("로드 실패")
            return False
    
    def clear_outro_image(self):
        """명함 이미지 삭제"""
        self.settings.remove("outro_image")
        self.lbl_image_preview.setText("이미지 없음")
        self.lbl_image_preview.setPixmap(QPixmap())
        self.lbl_image_path.setText("")
        QMessageBox.information(self, "완료", "명함 이미지가 삭제되었습니다.")
    
    def save_settings(self):
        """모든 설정 저장"""
        # 계정 정보
        self.settings.setValue("id", self.input_id.text())
        self.settings.setValue("pw", self.input_pw.text())
        self.settings.setValue("intro", self.input_intro.toPlainText())
        self.settings.setValue("outro", self.input_outro.toPlainText())
        
        # 카테고리 설정
        self.settings.setValue("default_category", self.input_category.text().strip())
        self.settings.setValue("category_list", self.get_category_list())
        
        # 이모티콘 그룹 설정
        self.settings.setValue("emoticon_groups", self.get_selected_emoticon_groups())
        
        # 이미지 생성 설정
        self.settings.setValue("thumbnail_mode", "ai" if self.radio_thumb_ai.isChecked() else "none")
        self.settings.setValue("illustration_mode", "ai" if self.radio_illust_ai.isChecked() else "none")
        
        # 출력 스타일 설정
        self._save_output_style_settings()
        
        # 변경 알림
        self.settings_changed.emit()
        
        QMessageBox.information(self, "완료", "모든 설정이 저장되었습니다.")
