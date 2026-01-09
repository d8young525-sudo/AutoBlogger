"""
정보성 글쓰기 탭 - 블로그 포스팅 자동 생성 기능
UX 개선: 드롭다운/직접입력 상호배타, AI 추천 상태표시, 이미지 생성 옵션
v3.3.0: 썸네일/본문 삽화 분리, TEXT/MARKDOWN/HTML 옵션 복원
"""
import requests
import markdown
import re
import base64
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, 
                               QComboBox, QLineEdit, QPushButton, QRadioButton, 
                               QButtonGroup, QLabel, QMessageBox, QScrollArea, 
                               QListWidget, QListWidgetItem, QTextEdit, QTabWidget, QCheckBox,
                               QAbstractItemView, QFrame, QSpinBox, QGridLayout)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QPixmap, QImage

BACKEND_URL = "https://generate-blog-post-yahp6ia25q-du.a.run.app"


class AnalysisWorker(QThread):
    """주제 분석 워커 스레드"""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, topic):
        super().__init__()
        self.topic = topic

    def run(self):
        try:
            response = requests.post(BACKEND_URL, json={"mode": "analyze", "topic": self.topic}, timeout=60)
            if response.status_code == 200:
                self.finished.emit(response.json())
            else:
                self.error.emit(f"분석 실패 ({response.status_code}): {response.text}")
        except Exception as e:
            self.error.emit(f"통신 오류: {str(e)}")


class RecommendWorker(QThread):
    """주제 추천 워커 스레드"""
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, category):
        super().__init__()
        self.category = category

    def run(self):
        try:
            response = requests.post(BACKEND_URL, json={"mode": "recommend", "category": self.category}, timeout=60)
            if response.status_code == 200:
                result = response.json()
                self.finished.emit(result.get("topics", []))
            else:
                self.error.emit(f"추천 실패 ({response.status_code}): {response.text}")
        except Exception as e:
            self.error.emit(f"통신 오류: {str(e)}")


class ImageGenerateWorker(QThread):
    """이미지 생성 워커 스레드"""
    finished = Signal(list)  # [(image_data, base64_str), ...]
    progress = Signal(int, int)  # current, total
    error = Signal(str)
    
    def __init__(self, topic: str, count: int, auth_token: str, image_type: str = "thumbnail"):
        super().__init__()
        self.topic = topic
        self.count = count
        self.auth_token = auth_token
        self.image_type = image_type  # "thumbnail" or "illustration"
    
    def run(self):
        try:
            results = []
            
            for i in range(self.count):
                self.progress.emit(i + 1, self.count)
                
                headers = {"Authorization": f"Bearer {self.auth_token}"}
                
                # 이미지 타입에 따른 프롬프트 스타일 설정
                if self.image_type == "thumbnail":
                    style = "블로그 대표 썸네일, 텍스트 없이, 주제를 잘 나타내는 시각적 이미지"
                else:  # illustration
                    style = "블로그 본문 삽화, 텍스트 없이, 심플하고 깔끔한 일러스트레이션"
                
                payload = {
                    "mode": "generate_image",
                    "prompt": self.topic,
                    "style": style
                }
                
                response = requests.post(
                    BACKEND_URL, 
                    json=payload, 
                    headers=headers,
                    timeout=120
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") and data.get("image_base64"):
                        results.append(data["image_base64"])
                elif response.status_code == 403:
                    self.error.emit("이미지 생성 권한이 없거나 한도를 초과했습니다.")
                    return
                else:
                    self.error.emit(f"이미지 생성 실패: {response.status_code}")
                    return
            
            self.finished.emit(results)
            
        except Exception as e:
            self.error.emit(f"이미지 생성 오류: {str(e)}")


class InfoTab(QWidget):
    """정보성 글쓰기 탭"""
    start_signal = Signal(dict) 
    log_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.recommend_worker = None
        self.analysis_worker = None
        self.thumbnail_worker = None
        self.illustration_worker = None
        self.thumbnail_images = []  # 썸네일 base64 리스트
        self.illustration_images = []  # 삽화 base64 리스트
        self.auth_token = ""
        self.init_ui()

    def set_auth_token(self, token: str):
        """인증 토큰 설정"""
        self.auth_token = token

    def init_ui(self):
        main_layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)

        # 1. 주제 기획
        group_topic = QGroupBox("1. 주제 기획")
        topic_layout = QVBoxLayout()
        
        # === 카테고리 선택 방식 ===
        self.radio_use_category = QRadioButton("📂 카테고리에서 AI 추천 받기")
        self.radio_use_category.setChecked(True)
        self.radio_use_category.toggled.connect(self.toggle_topic_mode)
        topic_layout.addWidget(self.radio_use_category)
        
        # 카테고리 선택 영역
        self.category_frame = QFrame()
        category_layout = QVBoxLayout(self.category_frame)
        category_layout.setContentsMargins(20, 0, 0, 0)
        
        form_cat = QFormLayout()
        self.combo_cat = QComboBox()
        self.combo_cat.setEditable(True)
        self.combo_cat.addItems([
            "차량 관리 상식", "자동차 보험/사고처리", "리스/렌트/할부 금융", 
            "교통법규/범칙금", "자동차 여행 코스", "전기차 라이프", "중고차 거래 팁"
        ])
        form_cat.addRow("카테고리:", self.combo_cat)
        category_layout.addLayout(form_cat)
        
        self.btn_recommend = QPushButton("✨ AI 추천 주제 받기")
        self.btn_recommend.clicked.connect(self.get_recommendations)
        self.btn_recommend.setStyleSheet("background-color: #5D5D5D; color: white; padding: 8px;")
        category_layout.addWidget(self.btn_recommend)
        
        # 추천 주제 표시 영역
        self.topic_area = QScrollArea()
        self.topic_area.setWidgetResizable(True)
        self.topic_area.setMinimumHeight(180) 
        self.topic_widget = QWidget()
        self.topic_group = QButtonGroup()
        self.topic_layout_inner = QVBoxLayout(self.topic_widget)
        self.topic_layout_inner.setAlignment(Qt.AlignTop)
        self.topic_area.setWidget(self.topic_widget)
        
        category_layout.addWidget(QLabel("추천 주제 선택:"))
        category_layout.addWidget(self.topic_area)
        
        topic_layout.addWidget(self.category_frame)
        
        # === 직접 입력 방식 ===
        self.radio_use_manual = QRadioButton("✏️ 주제 직접 입력하기")
        self.radio_use_manual.toggled.connect(self.toggle_topic_mode)
        topic_layout.addWidget(self.radio_use_manual)
        
        # 직접 입력 영역
        self.manual_frame = QFrame()
        manual_layout = QVBoxLayout(self.manual_frame)
        manual_layout.setContentsMargins(20, 0, 0, 0)
        
        self.manual_topic = QLineEdit()
        self.manual_topic.setPlaceholderText("주제를 직접 입력하세요 (예: 전기차 충전 요금 비교)")
        self.manual_topic.setEnabled(False)  # 초기에는 비활성화
        manual_layout.addWidget(self.manual_topic)
        
        topic_layout.addWidget(self.manual_frame)
        
        group_topic.setLayout(topic_layout)
        layout.addWidget(group_topic)

        # 2. 스타일 설정
        group_opt = QGroupBox("2. 스타일 설정")
        form_opt = QFormLayout()
        self.combo_tone = QComboBox()
        self.combo_tone.addItems([
            "친근한 이웃 (해요체)", "신뢰감 있는 전문가 (하십시오체)", 
            "유머러스하고 재치있는 (드립+텐션업)", "감성적인 에세이 스타일",
            "냉철한 팩트 전달/뉴스 스타일"
        ])
        self.combo_len = QComboBox()
        self.combo_len.addItems(["보통 (1,500자)", "길게 (2,000자)", "아주 길게 (2,500자)"])
        self.combo_emoji = QComboBox()
        self.combo_emoji.addItems(["사용 안 함 (텍스트만)", "조금 사용 (강조용)", "많이 사용 (화려하게)"])
        
        form_opt.addRow("글 말투:", self.combo_tone)
        form_opt.addRow("분량:", self.combo_len)
        form_opt.addRow("이모지:", self.combo_emoji)
        group_opt.setLayout(form_opt)
        layout.addWidget(group_opt)

        # 3. 세부 설정 (접을 수 있음)
        self.group_adv = QGroupBox("3. 세부 설정 (선택)")
        self.group_adv.setCheckable(True)
        self.group_adv.setChecked(False)
        adv_layout = QVBoxLayout()
        
        self.btn_analyze = QPushButton("🔍 주제 분석하기 (타겟/질문 추출)")
        self.btn_analyze.clicked.connect(self.run_analysis)
        self.btn_analyze.setStyleSheet("background-color: #4A90E2; color: white; padding: 10px; font-weight: bold;")
        adv_layout.addWidget(self.btn_analyze)
        
        # 타겟 독자 - 라디오버튼을 왼쪽에 배치하여 가시성 향상
        adv_layout.addWidget(QLabel("🎯 타깃 독자 (1개만 선택):"))
        self.target_group = QButtonGroup()
        self.target_widget = QWidget()
        self.target_layout = QVBoxLayout(self.target_widget)
        self.target_layout.setAlignment(Qt.AlignTop)
        self.target_layout.setContentsMargins(0, 0, 0, 0)
        
        target_scroll = QScrollArea()
        target_scroll.setWidgetResizable(True)
        target_scroll.setMinimumHeight(100)
        target_scroll.setMaximumHeight(120)
        target_scroll.setWidget(self.target_widget)
        adv_layout.addWidget(target_scroll)
        
        adv_layout.addWidget(QLabel("❓ 예상 질문 (선택):"))
        self.list_questions = QListWidget()
        self.list_questions.setMinimumHeight(120)
        adv_layout.addWidget(self.list_questions)
        
        adv_layout.addWidget(QLabel("📌 핵심 정보 요약:"))
        self.txt_summary = QTextEdit()
        self.txt_summary.setMinimumHeight(80)
        adv_layout.addWidget(self.txt_summary)
        
        adv_layout.addWidget(QLabel("💡 나만의 인사이트 (직접 입력):"))
        self.txt_insight = QTextEdit()
        self.txt_insight.setMinimumHeight(80)
        adv_layout.addWidget(self.txt_insight)
        
        self.group_adv.setLayout(adv_layout)
        layout.addWidget(self.group_adv)

        # 4. 이미지 생성 (썸네일 + 본문 삽화 분리)
        group_image = QGroupBox("4. 이미지 생성 (선택)")
        group_image.setCheckable(True)
        group_image.setChecked(False)
        image_layout = QVBoxLayout()
        
        # 4-1. 썸네일 이미지
        thumb_frame = QFrame()
        thumb_frame.setStyleSheet("background-color: #f8f8f8; border-radius: 5px; padding: 5px;")
        thumb_layout = QVBoxLayout(thumb_frame)
        
        self.chk_thumbnail = QCheckBox("🖼️ 대표 썸네일 이미지 생성")
        self.chk_thumbnail.setStyleSheet("font-weight: bold;")
        thumb_layout.addWidget(self.chk_thumbnail)
        
        thumb_desc = QLabel("• 글 상단에 표시되는 대표 이미지 (1장)")
        thumb_desc.setStyleSheet("color: #666; font-size: 11px; margin-left: 20px;")
        thumb_layout.addWidget(thumb_desc)
        
        # 썸네일 미리보기
        self.thumbnail_preview = QLabel()
        self.thumbnail_preview.setFixedSize(200, 120)
        self.thumbnail_preview.setStyleSheet("border: 1px dashed #ccc; background-color: #fff;")
        self.thumbnail_preview.setAlignment(Qt.AlignCenter)
        self.thumbnail_preview.setText("썸네일 미리보기")
        thumb_layout.addWidget(self.thumbnail_preview)
        
        self.chk_use_thumbnail = QCheckBox("✅ 이 썸네일 사용")
        self.chk_use_thumbnail.setEnabled(False)
        thumb_layout.addWidget(self.chk_use_thumbnail)
        
        image_layout.addWidget(thumb_frame)
        
        # 4-2. 본문 삽화 이미지
        illust_frame = QFrame()
        illust_frame.setStyleSheet("background-color: #f8f8f8; border-radius: 5px; padding: 5px;")
        illust_layout = QVBoxLayout(illust_frame)
        
        illust_header = QHBoxLayout()
        self.chk_illustration = QCheckBox("🎨 본문 삽화 이미지 생성")
        self.chk_illustration.setStyleSheet("font-weight: bold;")
        illust_header.addWidget(self.chk_illustration)
        
        illust_header.addWidget(QLabel("생성 수:"))
        self.spin_illust_count = QSpinBox()
        self.spin_illust_count.setRange(0, 4)
        self.spin_illust_count.setValue(2)
        self.spin_illust_count.setFixedWidth(60)
        illust_header.addWidget(self.spin_illust_count)
        illust_header.addStretch()
        illust_layout.addLayout(illust_header)
        
        illust_desc = QLabel("• 글 중간에 삽입되는 삽화 이미지 (0~4장)")
        illust_desc.setStyleSheet("color: #666; font-size: 11px; margin-left: 20px;")
        illust_layout.addWidget(illust_desc)
        
        # 삽화 미리보기 영역
        self.illust_preview_layout = QGridLayout()
        illust_layout.addLayout(self.illust_preview_layout)
        
        # 삽화 체크박스들
        self.illust_checkboxes = []
        self.illust_checkbox_layout = QHBoxLayout()
        illust_layout.addLayout(self.illust_checkbox_layout)
        
        image_layout.addWidget(illust_frame)
        
        # 이미지 생성 버튼
        self.btn_gen_images = QPushButton("🖼️ 선택한 이미지 생성하기")
        self.btn_gen_images.clicked.connect(self.generate_images)
        self.btn_gen_images.setStyleSheet("background-color: #9B59B6; color: white; padding: 10px; font-weight: bold;")
        image_layout.addWidget(self.btn_gen_images)
        
        # 이미지 안내
        img_notice = QLabel("💡 AI가 주제에 맞는 이미지를 생성합니다. 글씨가 없는 깔끔한 이미지입니다.")
        img_notice.setStyleSheet("color: #666; font-size: 11px;")
        image_layout.addWidget(img_notice)
        
        group_image.setLayout(image_layout)
        layout.addWidget(group_image)
        self.group_image = group_image

        # 5. 출력 스타일 설정 (복원)
        group_output = QGroupBox("5. 출력 스타일 설정")
        output_layout = QVBoxLayout()
        
        # 출력 형식 탭
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
        
        self.output_tabs.addTab(text_widget, "📄 Text 설정")
        
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
        
        self.output_tabs.addTab(md_widget, "📝 Markdown 설정")
        
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
        
        self.output_tabs.addTab(html_widget, "🌐 HTML 설정")
        
        output_layout.addWidget(self.output_tabs)
        group_output.setLayout(output_layout)
        layout.addWidget(group_output)

        # 6. 실행 버튼
        btn_layout = QHBoxLayout()
        self.btn_gen_only = QPushButton("🔍 원고 생성만 (미리보기)")
        self.btn_gen_only.setStyleSheet("background-color: #5D5D5D; color: white; font-weight: bold; padding: 12px;")
        self.btn_gen_only.clicked.connect(lambda: self.request_start(action="generate"))
        self.btn_full_auto = QPushButton("🚀 생성 + 바로 발행")
        self.btn_full_auto.setStyleSheet("background-color: #03C75A; color: white; font-weight: bold; padding: 12px;")
        self.btn_full_auto.clicked.connect(lambda: self.request_start(action="full"))
        btn_layout.addWidget(self.btn_gen_only)
        btn_layout.addWidget(self.btn_full_auto)
        layout.addLayout(btn_layout)

        # 7. 결과 뷰어 (탭으로 TEXT/MARKDOWN/HTML 표시)
        layout.addWidget(QLabel("📝 생성된 글 미리보기"))
        self.result_tabs = QTabWidget()
        
        self.view_text = QTextEdit()
        self.view_text.setPlaceholderText("TEXT 형식 결과가 여기에 표시됩니다.")
        self.result_tabs.addTab(self.view_text, "📄 Text")
        
        self.view_markdown = QTextEdit()
        self.view_markdown.setPlaceholderText("Markdown 형식 결과가 여기에 표시됩니다.")
        self.result_tabs.addTab(self.view_markdown, "📝 Markdown")
        
        self.view_html = QTextEdit()
        self.view_html.setPlaceholderText("HTML 형식 결과가 여기에 표시됩니다.")
        self.result_tabs.addTab(self.view_html, "🌐 HTML")
        
        self.result_tabs.setMinimumHeight(350)
        layout.addWidget(self.result_tabs)

        # 하단 발행 버튼
        self.btn_publish_now = QPushButton("📤 현재 내용으로 발행하기")
        self.btn_publish_now.setStyleSheet("background-color: #4A90E2; color: white; font-weight: bold; padding: 15px; font-size: 16px;")
        self.btn_publish_now.clicked.connect(lambda: self.request_start(action="publish_only"))
        self.btn_publish_now.setEnabled(False)
        layout.addWidget(self.btn_publish_now)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

    def toggle_topic_mode(self):
        """주제 입력 모드 토글 (카테고리/직접입력 상호배타)"""
        use_category = self.radio_use_category.isChecked()
        
        self.combo_cat.setEnabled(use_category)
        self.btn_recommend.setEnabled(use_category)
        self.topic_area.setEnabled(use_category)
        self.manual_topic.setEnabled(not use_category)
        
        if use_category:
            self.category_frame.setStyleSheet("")
            self.manual_frame.setStyleSheet("color: #999;")
        else:
            self.category_frame.setStyleSheet("color: #999;")
            self.manual_frame.setStyleSheet("")

    def get_selected_topic(self):
        """선택된 주제 반환"""
        if self.radio_use_manual.isChecked():
            return self.manual_topic.text().strip()
        
        selected_btn = self.topic_group.checkedButton()
        if selected_btn:
            return selected_btn.text()
        return None

    def get_recommendations(self):
        """AI 추천 주제 받기"""
        category = self.combo_cat.currentText()
        self.log_signal.emit(f"🤖 '{category}' 관련 주제를 생각 중입니다...")
        
        self.btn_recommend.setEnabled(False)
        self.btn_recommend.setText("⏳ 주제 생성 중...")
        self.btn_recommend.setStyleSheet("background-color: #888; color: white; padding: 8px;")
        
        for i in reversed(range(self.topic_layout_inner.count())): 
            widget = self.topic_layout_inner.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        self.recommend_worker = RecommendWorker(category)
        self.recommend_worker.finished.connect(self.on_recommend_finished)
        self.recommend_worker.error.connect(self.on_recommend_error)
        self.recommend_worker.start()

    def on_recommend_finished(self, topics: list):
        """추천 완료 처리"""
        self.btn_recommend.setEnabled(True)
        self.btn_recommend.setText("✅ 주제 생성 완료! (다시 받기)")
        self.btn_recommend.setStyleSheet("background-color: #27AE60; color: white; padding: 8px;")
        
        for t in topics:
            rb = QRadioButton(t)
            rb.setStyleSheet("font-size: 13px; padding: 5px;")
            self.topic_layout_inner.addWidget(rb)
            self.topic_group.addButton(rb)
            
        self.log_signal.emit(f"✅ {len(topics)}개의 주제가 추천되었습니다.")

    def on_recommend_error(self, error_msg: str):
        """추천 에러 처리"""
        self.btn_recommend.setEnabled(True)
        self.btn_recommend.setText("✨ AI 추천 주제 받기")
        self.btn_recommend.setStyleSheet("background-color: #5D5D5D; color: white; padding: 8px;")
        self.log_signal.emit(f"❌ {error_msg}")

    def run_analysis(self):
        """주제 분석 실행"""
        topic = self.get_selected_topic()
        if not topic:
            QMessageBox.warning(self, "경고", "먼저 주제를 선택하거나 입력해주세요.")
            return
            
        self.log_signal.emit(f"🔍 '{topic}' 주제를 심층 분석 중입니다...")
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.setText("⏳ 분석 중...")
        
        self.analysis_worker = AnalysisWorker(topic)
        self.analysis_worker.finished.connect(self.on_analysis_finished)
        self.analysis_worker.error.connect(self.on_analysis_error)
        self.analysis_worker.start()

    def on_analysis_finished(self, data):
        """분석 완료 처리"""
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText("🔍 주제 분석하기 (타겟/질문 추출)")
        
        for i in reversed(range(self.target_layout.count())):
            widget = self.target_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        self.list_questions.clear()
        
        targets = data.get("targets", [])
        questions = data.get("questions", [])
        key_points = data.get("key_points", [])
        
        for t in targets:
            rb = QRadioButton(f"  {t}")
            rb.setStyleSheet("font-size: 13px; padding: 3px 5px;")
            self.target_layout.addWidget(rb)
            self.target_group.addButton(rb)
            
        if self.target_group.buttons():
            self.target_group.buttons()[0].setChecked(True)
            
        for q in questions:
            item = QListWidgetItem(q)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.list_questions.addItem(item)
            
        summary_text = "\n".join([f"• {p}" for p in key_points])
        self.txt_summary.setText(summary_text)
        
        self.log_signal.emit("✅ 분석 완료! 타깃과 질문을 선택해주세요.")

    def on_analysis_error(self, error_msg: str):
        """분석 에러 처리"""
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText("🔍 주제 분석하기 (타겟/질문 추출)")
        self.log_signal.emit(f"❌ {error_msg}")

    def generate_images(self):
        """AI 이미지 생성 (썸네일 + 삽화)"""
        topic = self.get_selected_topic()
        if not topic:
            QMessageBox.warning(self, "경고", "먼저 주제를 선택하거나 입력해주세요.")
            return
        
        if not self.auth_token:
            QMessageBox.warning(self, "인증 필요", "이미지 생성은 로그인이 필요합니다.")
            return
        
        gen_thumbnail = self.chk_thumbnail.isChecked()
        gen_illust = self.chk_illustration.isChecked()
        illust_count = self.spin_illust_count.value() if gen_illust else 0
        
        if not gen_thumbnail and illust_count == 0:
            QMessageBox.warning(self, "경고", "생성할 이미지를 선택해주세요.")
            return
        
        self.btn_gen_images.setEnabled(False)
        self.clear_image_previews()
        
        # 썸네일 생성
        if gen_thumbnail:
            self.btn_gen_images.setText("⏳ 썸네일 생성 중...")
            self.thumbnail_worker = ImageGenerateWorker(topic, 1, self.auth_token, "thumbnail")
            self.thumbnail_worker.finished.connect(self.on_thumbnail_finished)
            self.thumbnail_worker.error.connect(self.on_image_error)
            self.thumbnail_worker.start()
            self.log_signal.emit(f"🖼️ '{topic}' 썸네일 이미지 생성 중...")
        
        # 삽화 생성
        if illust_count > 0:
            if gen_thumbnail:
                # 썸네일 완료 후 삽화 생성하도록 대기
                self._pending_illust = (topic, illust_count)
            else:
                self._start_illustration_generation(topic, illust_count)

    def _start_illustration_generation(self, topic: str, count: int):
        """삽화 이미지 생성 시작"""
        self.btn_gen_images.setText(f"⏳ 삽화 생성 중... (0/{count})")
        self.illustration_worker = ImageGenerateWorker(topic, count, self.auth_token, "illustration")
        self.illustration_worker.progress.connect(self.on_illust_progress)
        self.illustration_worker.finished.connect(self.on_illustrations_finished)
        self.illustration_worker.error.connect(self.on_image_error)
        self.illustration_worker.start()
        self.log_signal.emit(f"🎨 '{topic}' 본문 삽화 {count}장 생성 중...")

    def on_thumbnail_finished(self, images: list):
        """썸네일 생성 완료"""
        if images:
            self.thumbnail_images = images
            img_base64 = images[0]
            
            try:
                img_data = base64.b64decode(img_base64)
                qimg = QImage.fromData(img_data)
                pixmap = QPixmap.fromImage(qimg)
                scaled = pixmap.scaled(200, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.thumbnail_preview.setPixmap(scaled)
                self.chk_use_thumbnail.setEnabled(True)
                self.chk_use_thumbnail.setChecked(True)
            except:
                self.thumbnail_preview.setText("로드 실패")
            
            self.log_signal.emit("✅ 썸네일 이미지 생성 완료!")
        
        # 대기 중인 삽화 생성 시작
        if hasattr(self, '_pending_illust') and self._pending_illust:
            topic, count = self._pending_illust
            self._pending_illust = None
            self._start_illustration_generation(topic, count)
        else:
            self.btn_gen_images.setEnabled(True)
            self.btn_gen_images.setText("🖼️ 선택한 이미지 생성하기")

    def on_illust_progress(self, current: int, total: int):
        """삽화 생성 진행률"""
        self.btn_gen_images.setText(f"⏳ 삽화 생성 중... ({current}/{total})")

    def on_illustrations_finished(self, images: list):
        """삽화 생성 완료"""
        self.btn_gen_images.setEnabled(True)
        self.btn_gen_images.setText("🖼️ 선택한 이미지 생성하기")
        
        self.illustration_images = images
        
        # 삽화 미리보기 및 체크박스 표시
        for i, img_base64 in enumerate(images):
            row = i // 2
            col = i % 2
            
            # 미리보기 + 체크박스 컨테이너
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(5, 5, 5, 5)
            
            # 미리보기 라벨
            preview = QLabel()
            preview.setFixedSize(150, 100)
            preview.setStyleSheet("border: 1px solid #ddd;")
            
            try:
                img_data = base64.b64decode(img_base64)
                qimg = QImage.fromData(img_data)
                pixmap = QPixmap.fromImage(qimg)
                scaled = pixmap.scaled(150, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                preview.setPixmap(scaled)
            except:
                preview.setText("로드 실패")
            
            container_layout.addWidget(preview)
            
            # 체크박스
            chk = QCheckBox(f"삽화 {i+1} 삽입")
            chk.setChecked(True)
            self.illust_checkboxes.append(chk)
            container_layout.addWidget(chk)
            
            self.illust_preview_layout.addWidget(container, row, col)
        
        self.log_signal.emit(f"✅ {len(images)}개의 삽화 이미지가 생성되었습니다.")

    def on_image_error(self, error_msg: str):
        """이미지 생성 에러"""
        self.btn_gen_images.setEnabled(True)
        self.btn_gen_images.setText("🖼️ 선택한 이미지 생성하기")
        self.log_signal.emit(f"❌ {error_msg}")
        self._pending_illust = None

    def clear_image_previews(self):
        """이미지 미리보기 클리어"""
        # 썸네일 클리어
        self.thumbnail_preview.clear()
        self.thumbnail_preview.setText("썸네일 미리보기")
        self.chk_use_thumbnail.setChecked(False)
        self.chk_use_thumbnail.setEnabled(False)
        self.thumbnail_images = []
        
        # 삽화 클리어
        while self.illust_preview_layout.count():
            item = self.illust_preview_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.illust_checkboxes = []
        self.illustration_images = []
        self._pending_illust = None

    def get_output_style_settings(self) -> dict:
        """출력 스타일 설정값 가져오기"""
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

    def get_selected_images(self) -> dict:
        """선택된 이미지들 반환"""
        result = {
            "thumbnail": None,
            "illustrations": []
        }
        
        # 썸네일
        if self.chk_use_thumbnail.isChecked() and self.thumbnail_images:
            result["thumbnail"] = self.thumbnail_images[0]
        
        # 삽화
        for i, chk in enumerate(self.illust_checkboxes):
            if chk.isChecked() and i < len(self.illustration_images):
                result["illustrations"].append(self.illustration_images[i])
        
        return result

    def request_start(self, action="full"):
        """작업 시작 요청"""
        if action == "publish_only":
            # 현재 탭에서 내용 가져오기
            current_tab = self.result_tabs.currentIndex()
            if current_tab == 0:
                current_content = self.view_text.toPlainText()
            elif current_tab == 1:
                current_content = self.view_markdown.toPlainText()
            else:
                current_content = self.view_html.toPlainText()
            
            if not current_content:
                QMessageBox.warning(self, "경고", "발행할 내용이 없습니다.")
                return
            lines = current_content.split('\n')
            title = "무제"
            content = current_content
            if len(lines) > 0 and (lines[0].startswith("제목:") or lines[0].startswith("# ")):
                title = lines[0].replace("제목:", "").replace("# ", "").strip()
                content = "\n".join(lines[1:]).strip()
            data = {"action": action, "title": title, "content": content}
            self.start_signal.emit(data)
            return

        topic = self.get_selected_topic()
        if not topic:
            QMessageBox.warning(self, "경고", "주제가 없습니다.")
            return

        targets = []
        selected_target = self.target_group.checkedButton()
        if selected_target:
            targets = [selected_target.text().strip()]
            
        questions = [self.list_questions.item(i).text() 
                     for i in range(self.list_questions.count()) 
                     if self.list_questions.item(i).checkState() == Qt.Checked]

        # 선택된 이미지 포함
        selected_images = self.get_selected_images() if self.group_image.isChecked() else {"thumbnail": None, "illustrations": []}
        
        # 출력 스타일 설정
        output_style = self.get_output_style_settings()

        data = {
            "action": action, "mode": "info", "topic": topic,
            "tone": self.combo_tone.currentText(), "length": self.combo_len.currentText(),
            "emoji_level": self.combo_emoji.currentText(), "targets": targets,
            "questions": questions, "summary": self.txt_summary.toPlainText(),
            "insight": self.txt_insight.toPlainText(),
            "images": selected_images,  # {"thumbnail": base64 or None, "illustrations": [base64, ...]}
            "output_style": output_style  # 출력 스타일 설정
        }
        self.start_signal.emit(data)

    def update_result_view(self, result_data):
        """결과 뷰어 업데이트"""
        title = result_data.get("title", "제목 없음")
        content = result_data.get("content", "") or result_data.get("content_text", "")
        
        # TEXT 형식
        text_result = f"제목: {title}\n\n{'=' * 50}\n\n{content}"
        self.view_text.setText(text_result)
        
        # MARKDOWN 형식
        md_result = f"# {title}\n\n{content}"
        self.view_markdown.setText(md_result)
        
        # HTML 형식
        html_result = f"<h1>{title}</h1>\n\n{content.replace(chr(10), '<br>')}"
        self.view_html.setText(html_result)
        
        self.btn_publish_now.setEnabled(True)
        self.log_signal.emit("✨ 글 생성 완료! 내용을 확인하고 필요시 수정 후 발행하세요.")
