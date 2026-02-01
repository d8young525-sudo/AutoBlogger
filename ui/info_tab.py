"""
정보성 글쓰기 탭 - 세로 스크롤 레이아웃
섹션 1: 주제 선택
섹션 2: 세부 설정 + 원고 생성
섹션 3: 미리보기 + 발행
"""
import requests
import re
import base64
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                               QComboBox, QLineEdit, QPushButton, QRadioButton,
                               QButtonGroup, QLabel, QMessageBox, QScrollArea,
                               QListWidget, QListWidgetItem, QTextEdit,
                               QFrame, QDateTimeEdit)
from PySide6.QtCore import Qt, Signal, QThread, QDateTime, QTimer
from PySide6.QtGui import QPixmap, QImage

from config import Config
from core.post_history import is_duplicate_topic, get_stats
from core.hashtag_generator import HashtagWorker, extract_tags_local

BACKEND_URL = Config.BACKEND_URL


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
    """이미지 생성 워커 스레드 (썸네일만)"""
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, prompt: str, auth_token: str):
        super().__init__()
        self.prompt = prompt
        self.auth_token = auth_token

    def run(self):
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            payload = {
                "mode": "generate_image",
                "prompt": self.prompt,
                "style": "블로그 대표 썸네일, 텍스트 없이, 주제를 잘 나타내는 시각적 이미지"
            }
            response = requests.post(BACKEND_URL, json=payload, headers=headers, timeout=120)
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("image_base64"):
                    self.finished.emit([data["image_base64"]])
                else:
                    self.error.emit("이미지 생성에 실패했습니다.")
            elif response.status_code == 403:
                self.error.emit("이미지 생성 권한이 없거나 한도를 초과했습니다.")
            else:
                self.error.emit(f"이미지 생성 실패: {response.status_code}")
        except Exception as e:
            self.error.emit(f"이미지 생성 오류: {str(e)}")


class InfoTab(QWidget):
    """정보성 글쓰기 탭 - 세로 스크롤 레이아웃"""
    start_signal = Signal(dict)
    log_signal = Signal(str)

    def __init__(self, writing_settings_tab=None):
        super().__init__()
        self.writing_settings_tab = writing_settings_tab
        self.recommend_worker = None
        self.keyword_recommend_worker = None
        self.analysis_worker = None
        self.thumbnail_worker = None
        self.thumbnail_image = None
        self.auth_token = ""
        self.generated_content = ""
        self.generated_title = ""
        self.hashtag_worker = None
        self.schedule_timer = None
        self.current_topic_for_thumbnail = ""
        self.thumbnail_regenerate_count = 0
        self.analysis_done = False

        self.init_ui()

    def set_auth_token(self, token: str):
        self.auth_token = token

    # ============================================================
    # UI 구성
    # ============================================================

    def _make_section(self, title: str, icon: str = "") -> tuple:
        """섹션 카드 프레임 생성"""
        frame = QFrame()
        frame.setObjectName("sectionCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        header = QLabel(f"{icon}  {title}" if icon else title)
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        line = QFrame()
        line.setFixedHeight(1)
        line.setObjectName("sectionDivider")
        layout.addWidget(line)

        return frame, layout

    def init_ui(self):
        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        # QScrollArea global style already in styles.py

        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setSpacing(14)
        self.content_layout.setContentsMargins(8, 8, 8, 8)

        self._build_section_topic()
        self._build_section_detail()
        self._build_section_preview()

        self.content_layout.addStretch()
        self.scroll.setWidget(content)
        outer.addWidget(self.scroll)
        self.setLayout(outer)

    # ============================================================
    # 섹션 1: 주제 선택
    # ============================================================

    def _build_section_topic(self):
        frame, layout = self._make_section("주제 선택", "1")

        # 카드형 좌우 배치
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        self.topic_mode_group = QButtonGroup()

        # 좌측 카드: 카테고리
        left_card = QFrame()
        left_card.setCursor(Qt.PointingHandCursor)
        left_card.mousePressEvent = lambda e: self.radio_use_category.setChecked(True)
        left_card.setObjectName("cardSelected")
        left_layout = QVBoxLayout(left_card)

        self.radio_use_category = QRadioButton("카테고리에서 주제 생성")
        self.radio_use_category.setChecked(True)
        self.radio_use_category.toggled.connect(self.toggle_topic_mode)
        self.topic_mode_group.addButton(self.radio_use_category, 0)
        left_layout.addWidget(self.radio_use_category)

        self.combo_cat = QComboBox()
        self.combo_cat.setEditable(True)
        self.combo_cat.addItems([
            "차량 관리 상식", "자동차 보험/사고처리", "리스/렌트/할부 금융",
            "교통법규/범칙금", "자동차 여행 코스", "전기차 라이프", "중고차 거래 팁",
            "신차 구매 가이드", "자동차 세금/등록/명의이전", "초보운전 팁",
            "수입차 유지관리", "자동차 용품/액세서리"
        ])
        left_layout.addWidget(self.combo_cat)
        cards_row.addWidget(left_card, 1)

        # 우측 카드: 키워드
        right_card = QFrame()
        right_card.setCursor(Qt.PointingHandCursor)
        right_card.mousePressEvent = lambda e: self.radio_use_keyword.setChecked(True)
        right_card.setObjectName("cardUnselected")
        right_layout = QVBoxLayout(right_card)

        self.radio_use_keyword = QRadioButton("키워드 기반 주제 생성")
        self.radio_use_keyword.toggled.connect(self.toggle_topic_mode)
        self.topic_mode_group.addButton(self.radio_use_keyword, 1)
        right_layout.addWidget(self.radio_use_keyword)

        self.manual_topic = QLineEdit()
        self.manual_topic.setPlaceholderText("키워드 입력 (예: 전기차 충전)")
        self.manual_topic.setEnabled(False)
        right_layout.addWidget(self.manual_topic)
        cards_row.addWidget(right_card, 1)

        self.left_card = left_card
        self.right_card = right_card
        layout.addLayout(cards_row)

        # 주제 생성 버튼
        self.btn_generate_topic = QPushButton("주제 생성하기")
        self.btn_generate_topic.setObjectName("primaryButton")
        self.btn_generate_topic.clicked.connect(self.generate_topics)
        layout.addWidget(self.btn_generate_topic)

        # 생성된 주제 선택 영역
        self.lbl_topic_result = QLabel("생성된 주제 선택:")
        layout.addWidget(self.lbl_topic_result)

        self.topic_widget = QWidget()
        self.topic_group = QButtonGroup()
        self.topic_layout_inner = QVBoxLayout(self.topic_widget)
        self.topic_layout_inner.setAlignment(Qt.AlignTop)
        self.topic_layout_inner.setContentsMargins(0, 0, 0, 0)

        self.topic_placeholder = QLabel("주제 생성 버튼을 눌러 AI 추천 주제를 받아보세요.")
        self.topic_placeholder.setObjectName("mutedLabel")
        self.topic_placeholder.setAlignment(Qt.AlignCenter)
        self.topic_layout_inner.addWidget(self.topic_placeholder)

        layout.addWidget(self.topic_widget)

        # 주제 분석 버튼
        self.btn_analyze = QPushButton("주제 분석하기")
        self.btn_analyze.setObjectName("infoButton")
        self.btn_analyze.clicked.connect(self.run_analysis)
        self.btn_analyze.setEnabled(False)
        layout.addWidget(self.btn_analyze)

        self.content_layout.addWidget(frame)

    # ============================================================
    # 섹션 2: 세부 설정 + 원고 생성
    # ============================================================

    def _build_section_detail(self):
        self.detail_section, layout = self._make_section("세부 설정", "2")
        self.detail_section.setEnabled(False)

        # 타깃 독자
        layout.addWidget(QLabel("타깃 독자 (1개만 선택):"))
        self.target_group = QButtonGroup()
        self.target_widget = QWidget()
        self.target_layout = QVBoxLayout(self.target_widget)
        self.target_layout.setAlignment(Qt.AlignTop)
        self.target_layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self.target_widget)

        # 핵심 정보 요약
        layout.addWidget(QLabel("핵심 정보 요약:"))
        self.txt_summary = QTextEdit()
        self.txt_summary.setMinimumHeight(120)
        layout.addWidget(self.txt_summary)

        # 예상 질문
        layout.addWidget(QLabel("예상 질문 (선택):"))
        self.list_questions = QListWidget()
        self.list_questions.setMinimumHeight(160)
        layout.addWidget(self.list_questions)

        # 나만의 인사이트
        layout.addWidget(QLabel("나만의 인사이트 (직접 입력):"))
        self.txt_insight = QTextEdit()
        self.txt_insight.setMinimumHeight(80)
        layout.addWidget(self.txt_insight)

        # 썸네일 미리보기
        thumb_row = QHBoxLayout()
        self.thumbnail_preview = QLabel()
        self.thumbnail_preview.setFixedSize(150, 90)
        self.thumbnail_preview.setObjectName("thumbnailPreview")
        self.thumbnail_preview.setAlignment(Qt.AlignCenter)
        self.thumbnail_preview.setText("썸네일 대기중...")
        thumb_row.addWidget(self.thumbnail_preview)

        thumb_btn_col = QVBoxLayout()
        self.btn_regenerate_thumbnail = QPushButton("다른 이미지로")
        self.btn_regenerate_thumbnail.setObjectName("accentButton")
        self.btn_regenerate_thumbnail.clicked.connect(self.regenerate_thumbnail)
        self.btn_regenerate_thumbnail.setEnabled(False)
        thumb_btn_col.addWidget(self.btn_regenerate_thumbnail)
        self.lbl_regenerate_count = QLabel("재생성: 0회")
        self.lbl_regenerate_count.setObjectName("mutedLabel")
        thumb_btn_col.addWidget(self.lbl_regenerate_count)
        thumb_btn_col.addStretch()
        thumb_row.addLayout(thumb_btn_col)
        thumb_row.addStretch()
        layout.addLayout(thumb_row)

        # 원고 생성 버튼
        self.btn_generate = QPushButton("원고 생성")
        self.btn_generate.setObjectName("primaryButton")
        self.btn_generate.clicked.connect(self.request_generate)
        layout.addWidget(self.btn_generate)

        self.content_layout.addWidget(self.detail_section)

    # ============================================================
    # 섹션 3: 미리보기 + 발행
    # ============================================================

    def _build_section_preview(self):
        self.preview_section, layout = self._make_section("미리보기 · 발행", "3")
        self.preview_section.setEnabled(False)

        # 미리보기
        layout.addWidget(QLabel("생성된 글 미리보기"))
        self.view_text = QTextEdit()
        self.view_text.setPlaceholderText("원고가 여기에 표시됩니다.")
        self.view_text.setMinimumHeight(300)
        layout.addWidget(self.view_text)

        # 해시태그
        tags_row = QHBoxLayout()
        tags_row.addWidget(QLabel("해시태그:"))
        self.txt_tags = QLineEdit()
        self.txt_tags.setPlaceholderText("자동 생성됩니다 (쉼표 구분)")
        tags_row.addWidget(self.txt_tags)
        self.btn_regenerate_tags = QPushButton("재생성")
        self.btn_regenerate_tags.setObjectName("accentButton")
        self.btn_regenerate_tags.clicked.connect(self.regenerate_tags)
        self.btn_regenerate_tags.setEnabled(False)
        tags_row.addWidget(self.btn_regenerate_tags)
        layout.addLayout(tags_row)

        # 즉시 발행
        publish_row = QHBoxLayout()
        publish_row.addStretch()
        self.btn_publish = QPushButton("즉시 발행")
        self.btn_publish.setObjectName("primaryButton")
        self.btn_publish.clicked.connect(self.request_publish)
        self.btn_publish.setEnabled(False)
        publish_row.addWidget(self.btn_publish)
        layout.addLayout(publish_row)

        # 예약 발행
        schedule_row = QHBoxLayout()
        schedule_row.addWidget(QLabel("예약:"))
        self.dt_schedule = QDateTimeEdit()
        self.dt_schedule.setCalendarPopup(True)
        self.dt_schedule.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        self.dt_schedule.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_schedule.setMinimumDateTime(QDateTime.currentDateTime())
        schedule_row.addWidget(self.dt_schedule)

        self.btn_schedule = QPushButton("예약 발행")
        self.btn_schedule.setObjectName("secondaryButton")
        self.btn_schedule.clicked.connect(self.schedule_publish)
        self.btn_schedule.setEnabled(False)
        schedule_row.addWidget(self.btn_schedule)

        self.btn_cancel_schedule = QPushButton("예약 취소")
        self.btn_cancel_schedule.setObjectName("dangerButton")
        self.btn_cancel_schedule.clicked.connect(self.cancel_scheduled_publish)
        self.btn_cancel_schedule.hide()
        schedule_row.addWidget(self.btn_cancel_schedule)
        layout.addLayout(schedule_row)

        self.lbl_schedule_status = QLabel("")
        self.lbl_schedule_status.setObjectName("scheduleInactive")
        layout.addWidget(self.lbl_schedule_status)

        schedule_info = QLabel("예약 발행은 앱 실행 중에만 동작합니다.")
        schedule_info.setObjectName("mutedLabel")
        layout.addWidget(schedule_info)

        self.content_layout.addWidget(self.preview_section)

    # ============================================================
    # Topic mode toggle
    # ============================================================

    def toggle_topic_mode(self):
        if self.radio_use_category.isChecked():
            self.left_card.setObjectName("cardSelected")
            self.right_card.setObjectName("cardUnselected")
            self.combo_cat.setEnabled(True)
            self.manual_topic.setEnabled(False)
        else:
            self.left_card.setObjectName("cardUnselected")
            self.right_card.setObjectName("cardSelected")
            self.combo_cat.setEnabled(False)
            self.manual_topic.setEnabled(True)
        # Force QSS re-evaluation after objectName change
        for w in (self.left_card, self.right_card):
            w.style().unpolish(w)
            w.style().polish(w)

    # ============================================================
    # Topic generation & selection
    # ============================================================

    def get_selected_topic(self):
        selected_btn = self.topic_group.checkedButton()
        if selected_btn:
            return selected_btn.text()
        return None

    def generate_topics(self):
        if self.radio_use_category.isChecked():
            self.get_recommendations()
        else:
            self.get_keyword_recommendations()

    def get_keyword_recommendations(self):
        keyword = self.manual_topic.text().strip()
        if not keyword:
            QMessageBox.warning(self, "경고", "키워드를 입력해주세요.")
            return
        self.log_signal.emit(f"'{keyword}' 키워드로 관련 주제를 분석 중입니다...")
        self.btn_generate_topic.setEnabled(False)
        self.btn_generate_topic.setText("주제 분석 중...")
        self._clear_topic_list()
        self.keyword_recommend_worker = RecommendWorker(keyword)
        self.keyword_recommend_worker.finished.connect(self.on_keyword_recommend_finished)
        self.keyword_recommend_worker.error.connect(self.on_keyword_recommend_error)
        self.keyword_recommend_worker.start()

    def on_keyword_recommend_finished(self, topics: list):
        self._reset_generate_button()
        self._populate_topics(topics)
        self.log_signal.emit(f"{len(topics)}개의 관련 주제가 추천되었습니다.")

    def on_keyword_recommend_error(self, error_msg: str):
        self._reset_generate_button()
        self.log_signal.emit(f"{error_msg}")

    def get_recommendations(self):
        category = self.combo_cat.currentText()
        self.log_signal.emit(f"'{category}' 관련 최신 트렌드를 분석 중입니다...")
        self.btn_generate_topic.setEnabled(False)
        self.btn_generate_topic.setText("트렌드 분석 중...")
        self._clear_topic_list()
        self.recommend_worker = RecommendWorker(category)
        self.recommend_worker.finished.connect(self.on_recommend_finished)
        self.recommend_worker.error.connect(self.on_recommend_error)
        self.recommend_worker.start()

    def _clear_topic_list(self):
        for i in reversed(range(self.topic_layout_inner.count())):
            widget = self.topic_layout_inner.itemAt(i).widget()
            if widget:
                widget.setParent(None)

    def _reset_generate_button(self):
        self.btn_generate_topic.setEnabled(True)
        self.btn_generate_topic.setText("주제 생성하기")

    def _populate_topics(self, topics: list):
        for t in topics:
            rb = QRadioButton(t)
            rb.setObjectName("topicRadio")
            rb.toggled.connect(self.on_topic_changed)
            self.topic_layout_inner.addWidget(rb)
            self.topic_group.addButton(rb)

    def on_recommend_finished(self, topics: list):
        self._reset_generate_button()
        self._populate_topics(topics)
        self.log_signal.emit(f"{len(topics)}개의 트렌드 주제가 추천되었습니다.")

    def on_topic_changed(self, checked: bool):
        if checked:
            self.btn_analyze.setEnabled(True)
            new_topic = self.get_selected_topic()
            if new_topic and new_topic != self.current_topic_for_thumbnail:
                self.thumbnail_image = None
                self.thumbnail_preview.setText("주제 선택 후 자동 생성됩니다")
                self.btn_regenerate_thumbnail.setEnabled(False)
                self.current_topic_for_thumbnail = new_topic
                self.thumbnail_regenerate_count = 0
                self.update_regenerate_count_label()

    def on_recommend_error(self, error_msg: str):
        self._reset_generate_button()
        self.log_signal.emit(f"{error_msg}")

    # ============================================================
    # Analysis
    # ============================================================

    def run_analysis(self):
        topic = self.get_selected_topic()
        if not topic:
            QMessageBox.warning(self, "경고", "먼저 주제를 선택해주세요.")
            return
        self.log_signal.emit(f"'{topic}' 주제를 심층 분석 중입니다...")
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.setText("주제 분석 중...")

        self.analysis_worker = AnalysisWorker(topic)
        self.analysis_worker.finished.connect(self.on_analysis_finished)
        self.analysis_worker.error.connect(self.on_analysis_error)
        self.analysis_worker.start()

        if self.writing_settings_tab and self.writing_settings_tab.is_auto_thumbnail_enabled():
            self.generate_thumbnail_auto()

    def on_analysis_finished(self, data):
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText("주제 분석하기")
        self.analysis_done = True

        # 세부 설정 섹션 활성화
        self.detail_section.setEnabled(True)

        # Clear old targets
        for i in reversed(range(self.target_layout.count())):
            widget = self.target_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self.list_questions.clear()

        targets = data.get("targets", [])
        questions = data.get("questions", [])
        key_points = data.get("key_points", [])

        for t in targets:
            rb = QRadioButton(self._clean_to_plain_text(t))
            rb.setObjectName("topicRadio")
            self.target_layout.addWidget(rb)
            self.target_group.addButton(rb)

        if self.target_group.buttons():
            self.target_group.buttons()[0].setChecked(True)

        for q in questions:
            item = QListWidgetItem(self._clean_to_plain_text(q))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.list_questions.addItem(item)

        summary_text = "\n".join([f"• {self._clean_to_plain_text(p)}" for p in key_points])
        self.txt_summary.setText(summary_text)

        self.log_signal.emit("분석 완료! 세부 설정을 확인하고 원고를 생성하세요.")

        # 세부 설정 섹션으로 스크롤
        QTimer.singleShot(100, lambda: self.scroll.ensureWidgetVisible(self.detail_section))

    def on_analysis_error(self, error_msg: str):
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText("주제 분석하기")
        self.log_signal.emit(f"{error_msg}")

    # ============================================================
    # Thumbnail
    # ============================================================

    def generate_thumbnail_auto(self):
        if not self.auth_token:
            self.thumbnail_preview.setText("로그인 필요")
            return
        topic = self.get_selected_topic()
        if not topic:
            self.thumbnail_preview.setText("주제를 선택하세요")
            return
        self.thumbnail_preview.setText("생성 중...")
        self.btn_regenerate_thumbnail.setEnabled(False)
        self.log_signal.emit(f"'{topic}' 주제로 썸네일 생성 중...")
        self.thumbnail_worker = ImageGenerateWorker(topic, self.auth_token)
        self.thumbnail_worker.finished.connect(self.on_thumbnail_finished)
        self.thumbnail_worker.error.connect(self.on_thumbnail_error)
        self.thumbnail_worker.start()

    def regenerate_thumbnail(self):
        self.thumbnail_regenerate_count += 1
        self.update_regenerate_count_label()
        self.generate_thumbnail_auto()

    def update_regenerate_count_label(self):
        self.lbl_regenerate_count.setText(f"재생성: {self.thumbnail_regenerate_count}회")

    def on_thumbnail_finished(self, images: list):
        self.btn_regenerate_thumbnail.setEnabled(True)
        if images:
            self.thumbnail_image = images[0]
            try:
                img_data = base64.b64decode(self.thumbnail_image)
                qimg = QImage.fromData(img_data)
                pixmap = QPixmap.fromImage(qimg)
                scaled = pixmap.scaled(150, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.thumbnail_preview.setPixmap(scaled)
            except:
                self.thumbnail_preview.setText("로드 실패")
            self.log_signal.emit("썸네일 생성 완료!")

    def on_thumbnail_error(self, error_msg: str):
        self.btn_regenerate_thumbnail.setEnabled(True)
        self.thumbnail_preview.setText("생성 실패")
        self.log_signal.emit(f"썸네일 생성 실패: {error_msg}")

    # ============================================================
    # Generate content
    # ============================================================

    def request_generate(self):
        topic = self.get_selected_topic()
        if not topic:
            QMessageBox.warning(self, "경고", "주제를 선택해주세요.")
            return

        if not self.analysis_done:
            QMessageBox.warning(self, "안내", "먼저 주제를 분석해주세요.")
            return

        self.btn_generate.setEnabled(False)
        self.btn_generate.setText("생성 중...")

        tone = "친근한 이웃 (해요체)"
        length = "보통 (1,500자)"
        if self.writing_settings_tab:
            tone = self.writing_settings_tab.get_default_tone()
            length = self.writing_settings_tab.get_default_length()

        targets = []
        selected_target = self.target_group.checkedButton()
        if selected_target:
            targets = [selected_target.text().strip()]

        questions = [self.list_questions.item(i).text()
                     for i in range(self.list_questions.count())
                     if self.list_questions.item(i).checkState() == Qt.Checked]

        naver_style_settings = {}
        post_structure = "default"
        structure_params = {}
        if self.writing_settings_tab:
            naver_style_settings = self.writing_settings_tab.get_naver_editor_style_settings()
            post_structure = self.writing_settings_tab.get_post_structure()
            if hasattr(self.writing_settings_tab, 'get_structure_params'):
                structure_params = self.writing_settings_tab.get_structure_params()

        data = {
            "action": "generate",
            "mode": "info",
            "topic": topic,
            "tone": tone,
            "length": length,
            "targets": targets,
            "questions": questions,
            "summary": self.txt_summary.toPlainText(),
            "insight": self.txt_insight.toPlainText(),
            "naver_style": naver_style_settings,
            "post_structure": post_structure,
            "structure_params": structure_params,
        }
        self.start_signal.emit(data)

    # ============================================================
    # Publish
    # ============================================================

    def request_publish(self):
        current_content = self.view_text.toPlainText()
        if not current_content:
            QMessageBox.warning(self, "경고", "발행할 내용이 없습니다.")
            return

        lines = current_content.split('\n')
        title = self.generated_title or "무제"
        content = current_content

        if len(lines) > 0 and (lines[0].startswith("제목:") or lines[0].startswith("# ")):
            title = lines[0].replace("제목:", "").replace("# ", "").strip()
            content = "\n".join(lines[1:]).strip()

        category = ""
        if self.writing_settings_tab:
            category = self.writing_settings_tab.get_info_category()

        thumbnail = self.thumbnail_image if self.thumbnail_image else None
        tags = self.txt_tags.text().strip()

        data = {
            "action": "publish_only",
            "title": title,
            "content": content,
            "category": category,
            "tags": tags,
            "images": {"thumbnail": thumbnail, "illustrations": []}
        }
        self.start_signal.emit(data)

    # ============================================================
    # Hashtags
    # ============================================================

    def _auto_generate_tags(self):
        if not self.generated_content:
            return
        tags = extract_tags_local(self.generated_title or "", self.generated_content)
        if tags:
            self.txt_tags.setText(", ".join(tags))
            self.btn_regenerate_tags.setEnabled(True)
            self.log_signal.emit(f"해시태그 {len(tags)}개 자동 생성 완료")

    def regenerate_tags(self):
        if not self.generated_content:
            return
        self.btn_regenerate_tags.setEnabled(False)
        self.btn_regenerate_tags.setText("생성 중...")
        self.hashtag_worker = HashtagWorker(
            self.generated_title or "", self.generated_content, self.auth_token
        )
        self.hashtag_worker.finished.connect(self._on_tags_generated)
        self.hashtag_worker.error.connect(self._on_tags_error)
        self.hashtag_worker.start()

    def _on_tags_generated(self, tags: list):
        self.btn_regenerate_tags.setEnabled(True)
        self.btn_regenerate_tags.setText("재생성")
        if tags:
            self.txt_tags.setText(", ".join(tags))
            self.log_signal.emit(f"해시태그 {len(tags)}개 생성 완료")

    def _on_tags_error(self, error_msg: str):
        self.btn_regenerate_tags.setEnabled(True)
        self.btn_regenerate_tags.setText("재생성")
        self.log_signal.emit(f"해시태그 생성 실패: {error_msg}")

    # ============================================================
    # Schedule
    # ============================================================

    def schedule_publish(self):
        target_dt = self.dt_schedule.dateTime()
        now = QDateTime.currentDateTime()
        if target_dt <= now:
            QMessageBox.warning(self, "경고", "예약 시간은 현재 시간 이후여야 합니다.")
            return
        delay_ms = now.msecsTo(target_dt)
        self.schedule_timer = QTimer(self)
        self.schedule_timer.setSingleShot(True)
        self.schedule_timer.timeout.connect(self._execute_scheduled_publish)
        self.schedule_timer.start(delay_ms)
        self.lbl_schedule_status.setText(f"예약됨: {target_dt.toString('yyyy-MM-dd HH:mm')}")
        self.lbl_schedule_status.setObjectName("scheduleActive")
        self.lbl_schedule_status.style().unpolish(self.lbl_schedule_status)
        self.lbl_schedule_status.style().polish(self.lbl_schedule_status)
        self.btn_schedule.hide()
        self.btn_cancel_schedule.show()
        self.btn_publish.setEnabled(False)
        self.dt_schedule.setEnabled(False)
        self.log_signal.emit(f"예약 발행 설정됨: {target_dt.toString('yyyy-MM-dd HH:mm')}")

    def _execute_scheduled_publish(self):
        self.schedule_timer = None
        self.lbl_schedule_status.setText("예약 시간 도달! 발행 중...")
        self.btn_cancel_schedule.hide()
        self.btn_schedule.show()
        self.dt_schedule.setEnabled(True)
        self.log_signal.emit("예약 시간 도달 - 자동 발행을 시작합니다.")
        self.request_publish()

    def cancel_scheduled_publish(self):
        if self.schedule_timer:
            self.schedule_timer.stop()
            self.schedule_timer = None
        self.lbl_schedule_status.setText("예약이 취소되었습니다.")
        self.lbl_schedule_status.setObjectName("scheduleInactive")
        self.lbl_schedule_status.style().unpolish(self.lbl_schedule_status)
        self.lbl_schedule_status.style().polish(self.lbl_schedule_status)
        self.btn_cancel_schedule.hide()
        self.btn_schedule.show()
        self.btn_publish.setEnabled(True)
        self.dt_schedule.setEnabled(True)
        self.log_signal.emit("예약 발행이 취소되었습니다.")

    # ============================================================
    # Result view
    # ============================================================

    def update_result_view(self, result_data):
        title = result_data.get("title", "제목 없음")
        content = result_data.get("content_text", "") or result_data.get("content", "")

        if not content and "blocks" in result_data:
            blocks = result_data["blocks"]
            lines = []
            for block in blocks:
                btype = block.get("type", "paragraph")
                if btype == "heading":
                    lines.append(f"\n【{block.get('text', '')}】\n")
                elif btype == "paragraph":
                    lines.append(block.get("text", ""))
                elif btype == "list":
                    for item in block.get("items", []):
                        lines.append(f"  - {item}")
                elif btype == "quotation":
                    lines.append(f"\n「{block.get('text', '')}」\n")
                elif btype == "divider":
                    lines.append("\n━━━━━━━━━━━━━━━━━━━━\n")
                elif btype == "image_placeholder":
                    desc = block.get("description", "이미지")
                    lines.append(f"\n[📷 {desc}]\n")
            content = "\n".join(lines)

        if content and content.strip().startswith("{"):
            try:
                import json
                parsed = json.loads(content)
                content = parsed.get("content_text", "") or parsed.get("content", content)
            except:
                pass

        content = self._clean_to_plain_text(content)
        self.generated_content = content
        self.generated_title = title

        display_text = f"제목: {title}\n\n{'━' * 50}\n\n{content}"
        self.view_text.setText(display_text)

        self.btn_generate.setEnabled(True)
        self.btn_generate.setText("원고 생성")
        self.btn_publish.setEnabled(True)
        self.btn_schedule.setEnabled(True)
        self.dt_schedule.setMinimumDateTime(QDateTime.currentDateTime())

        # 미리보기 섹션 활성화 및 스크롤
        self.preview_section.setEnabled(True)
        QTimer.singleShot(100, lambda: self.scroll.ensureWidgetVisible(self.preview_section))

        self.log_signal.emit("글 생성 완료!")
        self._auto_generate_tags()

    def _clean_to_plain_text(self, content: str) -> str:
        if not content:
            return content
        content = re.sub(r'<[^>]+>', '', content)
        content = re.sub(r'^#{1,3}\s*(.+)$', r'【\1】', content, flags=re.MULTILINE)
        content = re.sub(r'\*\*(.+?)\*\*', r'\1', content)
        content = re.sub(r'__(.+?)__', r'\1', content)
        content = re.sub(r'(?<!\w)\*([^*]+)\*(?!\w)', r'\1', content)
        content = re.sub(r'(?<!\w)_([^_]+)_(?!\w)', r'\1', content)
        content = re.sub(r'^>\s*', '', content, flags=re.MULTILINE)
        content = re.sub(r'```[\s\S]*?```', '', content)
        content = re.sub(r'`([^`]+)`', r'\1', content)
        content = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', content)
        content = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', content)
        content = re.sub(r'\n{3,}', '\n\n', content)
        return content.strip()

    def reset_generate_button(self):
        self.btn_generate.setEnabled(True)
        self.btn_generate.setText("원고 생성")

    def cleanup_workers(self):
        for worker in [self.recommend_worker, self.keyword_recommend_worker,
                       self.analysis_worker, self.thumbnail_worker]:
            if worker and worker.isRunning():
                worker.quit()
                worker.wait(1000)
