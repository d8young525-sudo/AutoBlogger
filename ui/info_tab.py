"""
정보성 글쓰기 탭 - 블로그 포스팅 자동 생성 기능
v3.3.3: TEXT 우선 생성 구조, 네이버 에디터 HTML 지원
"""
import requests
import markdown
import re
import base64
from core.content_converter import ContentConverter
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
    finished = Signal(list)  # [base64_str, ...]
    progress = Signal(int, int)  # current, total
    error = Signal(str)
    
    def __init__(self, prompts: list, auth_token: str, image_type: str = "thumbnail"):
        super().__init__()
        self.prompts = prompts  # 여러 프롬프트 지원
        self.auth_token = auth_token
        self.image_type = image_type
    
    def run(self):
        try:
            results = []
            total = len(self.prompts)
            
            for i, prompt in enumerate(self.prompts):
                self.progress.emit(i + 1, total)
                
                headers = {"Authorization": f"Bearer {self.auth_token}"}
                
                # 이미지 타입에 따른 스타일 설정
                if self.image_type == "thumbnail":
                    style = "블로그 대표 썸네일, 텍스트 없이, 주제를 잘 나타내는 시각적 이미지"
                else:  # illustration
                    style = "블로그 본문 삽화, 텍스트 없이, 심플하고 깔끔한 일러스트레이션"
                
                payload = {
                    "mode": "generate_image",
                    "prompt": prompt,
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


class IllustrationPromptWorker(QThread):
    """본문 기반 삽화 프롬프트 생성 워커"""
    finished = Signal(dict)  # {"prompts": [...], "positions": [...]}
    error = Signal(str)
    
    def __init__(self, content: str, count: int):
        super().__init__()
        self.content = content
        self.count = count
    
    def run(self):
        try:
            response = requests.post(
                BACKEND_URL, 
                json={
                    "mode": "generate_illustration_prompts",
                    "content": self.content,
                    "count": self.count
                }, 
                timeout=60
            )
            if response.status_code == 200:
                self.finished.emit(response.json())
            else:
                self.error.emit(f"프롬프트 생성 실패 ({response.status_code}): {response.text}")
        except Exception as e:
            self.error.emit(f"통신 오류: {str(e)}")


class InfoTab(QWidget):
    """정보성 글쓰기 탭"""
    start_signal = Signal(dict) 
    log_signal = Signal(str)

    def __init__(self, settings_tab=None):
        super().__init__()
        self.settings_tab = settings_tab  # 환경설정 탭 참조 (출력 스타일 가져오기용)
        self.recommend_worker = None
        self.analysis_worker = None
        self.thumbnail_worker = None
        self.illustration_worker = None
        self.prompt_worker = None
        self.thumbnail_images = []
        self.illustration_images = []
        self.illustration_prompts = []
        self.auth_token = ""
        self.generated_content = ""  # 생성된 본문 저장
        self.generated_title = ""  # 생성된 제목 저장
        self._pending_illust_count = 0
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
        
        self.btn_recommend = QPushButton("✨ AI 추천 주제 받기 (실시간 트렌드 반영)")
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
        self.manual_topic.setEnabled(False)
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

        # 출력 스타일 안내 (환경설정에서 관리)
        style_notice = QLabel("💡 출력 스타일 (Text/Markdown/HTML)은 [환경 설정] 탭에서 관리됩니다.")
        style_notice.setStyleSheet("color: #666; font-size: 11px; padding: 5px; background-color: #f8f8f8; border-radius: 4px;")
        layout.addWidget(style_notice)

        # 3. 세부 설정 (접을 수 있음)
        self.group_adv = QGroupBox("3. 세부 설정 (선택)")
        self.group_adv.setCheckable(True)
        self.group_adv.setChecked(False)
        adv_layout = QVBoxLayout()
        
        self.btn_analyze = QPushButton("🔍 주제 분석하기 (타겟/질문 추출)")
        self.btn_analyze.clicked.connect(self.run_analysis)
        self.btn_analyze.setStyleSheet("background-color: #4A90E2; color: white; padding: 10px; font-weight: bold;")
        adv_layout.addWidget(self.btn_analyze)
        
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

        # 4. 실행 버튼 (원고 생성)
        btn_layout = QHBoxLayout()
        self.btn_gen_only = QPushButton("🔍 원고 생성 (미리보기)")
        self.btn_gen_only.setStyleSheet("background-color: #5D5D5D; color: white; font-weight: bold; padding: 12px;")
        self.btn_gen_only.clicked.connect(lambda: self.request_start(action="generate"))
        self.btn_full_auto = QPushButton("🚀 생성 + 바로 발행")
        self.btn_full_auto.setStyleSheet("background-color: #03C75A; color: white; font-weight: bold; padding: 12px;")
        self.btn_full_auto.clicked.connect(lambda: self.request_start(action="full"))
        btn_layout.addWidget(self.btn_gen_only)
        btn_layout.addWidget(self.btn_full_auto)
        layout.addLayout(btn_layout)

        # 5. 결과 뷰어
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
        
        self.result_tabs.setMinimumHeight(300)
        layout.addWidget(self.result_tabs)

        # 6. 이미지 생성 (원고 생성 후 활성화)
        self.group_image = QGroupBox("4. 이미지 생성 (원고 생성 후 활성화)")
        self.group_image.setEnabled(False)
        image_layout = QVBoxLayout()
        
        # 7-1. 썸네일 이미지
        thumb_frame = QFrame()
        thumb_frame.setStyleSheet("background-color: #f8f8f8; border-radius: 5px; padding: 5px;")
        thumb_layout = QVBoxLayout(thumb_frame)
        
        self.chk_thumbnail = QCheckBox("🖼️ 대표 썸네일 이미지 생성 (1장)")
        self.chk_thumbnail.setStyleSheet("font-weight: bold;")
        self.chk_thumbnail.setChecked(True)
        thumb_layout.addWidget(self.chk_thumbnail)
        
        # 썸네일 미리보기
        thumb_preview_row = QHBoxLayout()
        self.thumbnail_preview = QLabel()
        self.thumbnail_preview.setFixedSize(200, 120)
        self.thumbnail_preview.setStyleSheet("border: 1px dashed #ccc; background-color: #fff;")
        self.thumbnail_preview.setAlignment(Qt.AlignCenter)
        self.thumbnail_preview.setText("썸네일 미리보기")
        thumb_preview_row.addWidget(self.thumbnail_preview)
        thumb_preview_row.addStretch()
        thumb_layout.addLayout(thumb_preview_row)
        
        self.chk_use_thumbnail = QCheckBox("✅ 이 썸네일 사용")
        self.chk_use_thumbnail.setEnabled(False)
        thumb_layout.addWidget(self.chk_use_thumbnail)
        
        image_layout.addWidget(thumb_frame)
        
        # 7-2. 본문 삽화 이미지 (본문 기반 자동 생성)
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
        
        illust_desc = QLabel("💡 원고 내용을 분석하여 본문에 어울리는 삽화를 자동 생성합니다.")
        illust_desc.setStyleSheet("color: #666; font-size: 11px; margin-left: 20px;")
        illust_layout.addWidget(illust_desc)
        
        # 삽화 미리보기 영역
        self.illust_preview_layout = QGridLayout()
        illust_layout.addLayout(self.illust_preview_layout)
        
        # 삽화 체크박스들
        self.illust_checkboxes = []
        
        image_layout.addWidget(illust_frame)
        
        # 이미지 생성 버튼
        self.btn_gen_images = QPushButton("🖼️ 이미지 생성하기")
        self.btn_gen_images.clicked.connect(self.generate_images)
        self.btn_gen_images.setStyleSheet("background-color: #9B59B6; color: white; padding: 10px; font-weight: bold;")
        image_layout.addWidget(self.btn_gen_images)
        
        self.group_image.setLayout(image_layout)
        layout.addWidget(self.group_image)

        # 7. 최종 발행 버튼
        self.btn_publish_now = QPushButton("📤 현재 내용으로 발행하기")
        self.btn_publish_now.setStyleSheet("background-color: #4A90E2; color: white; font-weight: bold; padding: 15px; font-size: 16px;")
        self.btn_publish_now.clicked.connect(lambda: self.request_start(action="publish_only"))
        self.btn_publish_now.setEnabled(False)
        layout.addWidget(self.btn_publish_now)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

    def toggle_topic_mode(self):
        """주제 입력 모드 토글"""
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
        """AI 추천 주제 받기 (Grounding 적용)"""
        category = self.combo_cat.currentText()
        self.log_signal.emit(f"🤖 '{category}' 관련 최신 트렌드를 분석 중입니다...")
        
        self.btn_recommend.setEnabled(False)
        self.btn_recommend.setText("⏳ 트렌드 분석 중...")
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
        """추천 완료"""
        self.btn_recommend.setEnabled(True)
        self.btn_recommend.setText("✅ 추천 완료! (다시 받기)")
        self.btn_recommend.setStyleSheet("background-color: #27AE60; color: white; padding: 8px;")
        
        for t in topics:
            rb = QRadioButton(t)
            rb.setStyleSheet("font-size: 13px; padding: 5px;")
            self.topic_layout_inner.addWidget(rb)
            self.topic_group.addButton(rb)
            
        self.log_signal.emit(f"✅ {len(topics)}개의 트렌드 주제가 추천되었습니다.")

    def on_recommend_error(self, error_msg: str):
        """추천 에러"""
        self.btn_recommend.setEnabled(True)
        self.btn_recommend.setText("✨ AI 추천 주제 받기 (실시간 트렌드 반영)")
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
        """분석 완료"""
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
        """분석 에러"""
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText("🔍 주제 분석하기 (타겟/질문 추출)")
        self.log_signal.emit(f"❌ {error_msg}")

    def generate_images(self):
        """이미지 생성 (원고 기반)"""
        if not self.generated_content:
            QMessageBox.warning(self, "경고", "먼저 원고를 생성해주세요.")
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
            topic = self.get_selected_topic() or "블로그 글"
            self.btn_gen_images.setText("⏳ 썸네일 생성 중...")
            self.thumbnail_worker = ImageGenerateWorker([topic], self.auth_token, "thumbnail")
            self.thumbnail_worker.finished.connect(self.on_thumbnail_finished)
            self.thumbnail_worker.error.connect(self.on_image_error)
            self.thumbnail_worker.start()
            self.log_signal.emit(f"🖼️ 썸네일 이미지 생성 중...")
        
        # 삽화 생성 (본문 기반 프롬프트 먼저 생성)
        if illust_count > 0:
            if gen_thumbnail:
                self._pending_illust_count = illust_count
            else:
                self._start_illustration_generation(illust_count)

    def _start_illustration_generation(self, count: int):
        """삽화 프롬프트 생성 시작"""
        self.btn_gen_images.setText("⏳ 본문 분석 중...")
        self.log_signal.emit(f"🎨 본문을 분석하여 삽화 프롬프트 생성 중...")
        
        self.prompt_worker = IllustrationPromptWorker(self.generated_content, count)
        self.prompt_worker.finished.connect(self.on_prompts_finished)
        self.prompt_worker.error.connect(self.on_image_error)
        self.prompt_worker.start()

    def on_prompts_finished(self, data: dict):
        """삽화 프롬프트 생성 완료"""
        self.illustration_prompts = data.get("prompts", [])
        
        if not self.illustration_prompts:
            self.on_image_error("삽화 프롬프트 생성에 실패했습니다.")
            return
        
        self.log_signal.emit(f"📝 {len(self.illustration_prompts)}개의 삽화 프롬프트가 생성되었습니다. 이미지 생성 중...")
        
        # 이제 실제 이미지 생성
        self.btn_gen_images.setText(f"⏳ 삽화 생성 중... (0/{len(self.illustration_prompts)})")
        self.illustration_worker = ImageGenerateWorker(self.illustration_prompts, self.auth_token, "illustration")
        self.illustration_worker.progress.connect(self.on_illust_progress)
        self.illustration_worker.finished.connect(self.on_illustrations_finished)
        self.illustration_worker.error.connect(self.on_image_error)
        self.illustration_worker.start()

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
        if hasattr(self, '_pending_illust_count') and self._pending_illust_count > 0:
            count = self._pending_illust_count
            self._pending_illust_count = 0
            self._start_illustration_generation(count)
        else:
            self.btn_gen_images.setEnabled(True)
            self.btn_gen_images.setText("🖼️ 이미지 생성하기")

    def on_illust_progress(self, current: int, total: int):
        """삽화 생성 진행률"""
        self.btn_gen_images.setText(f"⏳ 삽화 생성 중... ({current}/{total})")

    def on_illustrations_finished(self, images: list):
        """삽화 생성 완료"""
        self.btn_gen_images.setEnabled(True)
        self.btn_gen_images.setText("🖼️ 이미지 생성하기")
        
        self.illustration_images = images
        
        # 삽화 미리보기 표시
        for i, img_base64 in enumerate(images):
            row = i // 2
            col = i % 2
            
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(5, 5, 5, 5)
            
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
            
            chk = QCheckBox(f"삽화 {i+1} 삽입")
            chk.setChecked(True)
            self.illust_checkboxes.append(chk)
            container_layout.addWidget(chk)
            
            self.illust_preview_layout.addWidget(container, row, col)
        
        self.log_signal.emit(f"✅ {len(images)}개의 삽화 이미지가 생성되었습니다.")
        
        # 이미지 HTML 코드 업데이트
        self._update_content_with_images()

    def on_image_error(self, error_msg: str):
        """이미지 생성 에러"""
        self.btn_gen_images.setEnabled(True)
        self.btn_gen_images.setText("🖼️ 이미지 생성하기")
        self.log_signal.emit(f"❌ {error_msg}")
        self._pending_illust_count = 0

    def clear_image_previews(self):
        """이미지 미리보기 클리어"""
        self.thumbnail_preview.clear()
        self.thumbnail_preview.setText("썸네일 미리보기")
        self.chk_use_thumbnail.setChecked(False)
        self.chk_use_thumbnail.setEnabled(False)
        self.thumbnail_images = []
        
        while self.illust_preview_layout.count():
            item = self.illust_preview_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.illust_checkboxes = []
        self.illustration_images = []
        self._pending_illust_count = 0

    def get_output_style_settings(self) -> dict:
        """출력 스타일 설정값 (환경설정 탭에서 가져옴)"""
        if self.settings_tab:
            return self.settings_tab.get_output_style_settings()
        # 기본값 (settings_tab이 연결되지 않은 경우)
        return {
            "text": {
                "heading": "【 】 대괄호",
                "emphasis": "** 별표 **",
                "divider": "━━━━━━ (실선)",
                "spacing": "기본 (1줄)",
            },
            "markdown": {
                "heading": "## H2 사용",
                "list": "- 하이픈",
                "qa": "> 인용문 스타일",
                "narrative": "짧은 문장 (모바일 최적화)",
            },
            "html": {
                "title": "<h2> 태그",
                "qa": "<blockquote> 인용",
                "color": "네이버 그린 (#03C75A)",
                "font": "기본 (시스템)",
                "box": "배경색 박스",
            }
        }
    
    def get_default_category(self) -> str:
        """기본 카테고리 가져오기 (환경설정 탭에서)"""
        if self.settings_tab:
            return self.settings_tab.get_default_category()
        return ""

    def get_selected_images(self) -> dict:
        """선택된 이미지들 반환"""
        result = {"thumbnail": None, "illustrations": []}
        
        if self.chk_use_thumbnail.isChecked() and self.thumbnail_images:
            result["thumbnail"] = self.thumbnail_images[0]
        
        for i, chk in enumerate(self.illust_checkboxes):
            if chk.isChecked() and i < len(self.illustration_images):
                result["illustrations"].append(self.illustration_images[i])
        
        return result

    def request_start(self, action="full"):
        """작업 시작 요청"""
        if action == "publish_only":
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
            
            # 이미지 포함
            selected_images = self.get_selected_images()
            data = {
                "action": action, 
                "title": title, 
                "content": content, 
                "images": selected_images,
                "category": self.get_default_category()  # 카테고리 정보 추가
            }
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

        output_style = self.get_output_style_settings()

        data = {
            "action": action, "mode": "info", "topic": topic,
            "tone": self.combo_tone.currentText(), "length": self.combo_len.currentText(),
            "emoji_level": self.combo_emoji.currentText(), "targets": targets,
            "questions": questions, "summary": self.txt_summary.toPlainText(),
            "insight": self.txt_insight.toPlainText(),
            "output_style": output_style,
            "images": self.get_selected_images(),
            "category": self.get_default_category()  # 카테고리 정보 추가
        }
        self.start_signal.emit(data)

    def generate_image_html(self, img_base64: str, alt_text: str = "이미지", is_thumbnail: bool = False) -> str:
        """이미지 base64를 HTML 태그로 변환"""
        if is_thumbnail:
            # 썸네일용 HTML (네이버 블로그 배경 이미지 스타일)
            return f'''<div style="width:100%; max-width:800px; margin:20px auto;">
<img src="data:image/png;base64,{img_base64}" alt="{alt_text}" style="width:100%; height:auto; border-radius:8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
</div>'''
        else:
            # 삽화용 HTML
            return f'''<div style="text-align:center; margin:30px 0;">
<img src="data:image/png;base64,{img_base64}" alt="{alt_text}" style="max-width:600px; width:100%; height:auto; border-radius:4px;">
</div>'''

    def _update_content_with_images(self):
        """이미지가 삽입된 컨텐츠 업데이트"""
        if not self.generated_content:
            return
        
        # 현재 HTML 컨텐츠 가져오기
        current_html = self.view_html.toPlainText()
        
        # 썸네일 HTML 생성
        thumbnail_html = ""
        if self.chk_use_thumbnail.isChecked() and self.thumbnail_images:
            thumbnail_html = self.generate_image_html(self.thumbnail_images[0], "대표 이미지", True)
        
        # 삽화 HTML 생성
        illust_htmls = []
        for i, chk in enumerate(self.illust_checkboxes):
            if chk.isChecked() and i < len(self.illustration_images):
                illust_htmls.append(self.generate_image_html(
                    self.illustration_images[i], 
                    f"삽화 {i+1}"
                ))
        
        # HTML에 이미지 삽입
        if thumbnail_html or illust_htmls:
            # 제목 추출
            lines = current_html.split('\n')
            title_line = lines[0] if lines else ""
            body = '\n'.join(lines[1:]) if len(lines) > 1 else current_html
            
            # 썸네일은 제목 바로 다음에
            if thumbnail_html:
                body = thumbnail_html + "\n\n" + body
            
            # 삽화는 본문 중간에 균등 배치
            if illust_htmls:
                paragraphs = body.split('\n\n')
                total_p = len(paragraphs)
                
                if total_p > len(illust_htmls):
                    # 균등 배치
                    interval = total_p // (len(illust_htmls) + 1)
                    for i, img_html in enumerate(illust_htmls):
                        insert_pos = (i + 1) * interval
                        if insert_pos < len(paragraphs):
                            paragraphs.insert(insert_pos + i, img_html)
                    body = '\n\n'.join(paragraphs)
                else:
                    # 문단이 적으면 끝에 추가
                    body = body + '\n\n' + '\n\n'.join(illust_htmls)
            
            # 업데이트된 HTML
            updated_html = title_line + '\n\n' + body
            self.view_html.setText(updated_html)
            
            self.log_signal.emit("📸 이미지가 HTML에 삽입되었습니다. HTML 탭에서 확인하세요.")

    def update_result_view(self, result_data):
        """결과 뷰어 업데이트 - TEXT 기반 변환 사용"""
        title = result_data.get("title", "제목 없음")
        content = result_data.get("content", "") or result_data.get("content_text", "")
        
        # 생성된 본문 저장 (이미지 생성용)
        self.generated_content = content
        self.generated_title = title
        
        # 스타일 설정 가져오기
        style_settings = self.get_output_style_settings()
        
        # ContentConverter를 사용하여 TEXT → Markdown/HTML 변환
        converter = ContentConverter(style_settings)
        converted = converter.convert_all(content, title)
        
        # TEXT 형식 (스타일 적용)
        self.view_text.setText(converted["text"])
        
        # MARKDOWN 형식
        self.view_markdown.setText(converted["markdown"])
        
        # HTML 형식 (네이버 블로그 스타일, 이모지 제거)
        clean_html = self._remove_emojis(converted["html_naver"])
        self.view_html.setText(clean_html)
        
        # 이미지 생성 섹션 활성화
        self.group_image.setEnabled(True)
        self.group_image.setTitle("4. 이미지 생성 (본문 기반)")
        
        self.btn_publish_now.setEnabled(True)
        self.log_signal.emit("✨ 글 생성 완료! 이제 이미지를 생성하거나 바로 발행할 수 있습니다.")

    def _remove_emojis(self, text: str) -> str:
        """텍스트에서 이모지 제거"""
        import re
        # 이모지 패턴 (유니코드 범위)
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"  # emoticons
            u"\U0001F300-\U0001F5FF"  # symbols & pictographs
            u"\U0001F680-\U0001F6FF"  # transport & map symbols
            u"\U0001F1E0-\U0001F1FF"  # flags
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)
        return emoji_pattern.sub('', text)
