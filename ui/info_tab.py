"""
정보성 글쓰기 탭 - 초간소화 버전 (v3.16.0)
주제 선택 → 발행 (세부 설정 UI 제거, 백그라운드 분석)
"""
import requests
import re
import base64
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                               QComboBox, QLineEdit, QPushButton, QRadioButton,
                               QButtonGroup, QLabel, QMessageBox, QScrollArea,
                               QFrame, QGroupBox)
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from PySide6.QtGui import QPixmap, QImage

from config import Config
from ui.styles import GREEN_BUTTON_STYLE, CARD_SELECTED_STYLE, CARD_UNSELECTED_STYLE
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
        self.generated_tags = ""  # 해시태그 저장용
        self.current_topic_for_thumbnail = ""
        self.thumbnail_regenerate_count = 0
        self.analysis_done = False
        self.generated_blocks = None  # 원본 블록 데이터 보존

        self.init_ui()

    def set_auth_token(self, token: str):
        self.auth_token = token

    # ============================================================
    # UI 구성
    # ============================================================

    def _make_section(self, title: str, icon: str = "") -> tuple:
        """섹션 카드 프레임 생성"""
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        header = QLabel(f"{icon}  {title}" if icon else title)
        layout.addWidget(header)

        line = QFrame()
        line.setFixedHeight(1)
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
        self._init_internal_data()

        self.content_layout.addStretch()
        self.scroll.setWidget(content)
        outer.addWidget(self.scroll)
        self.setLayout(outer)

    # ============================================================
    # 주제 생성 영역 (헤더 없이 바로 카드 배치)
    # ============================================================

    def _build_section_topic(self):
        self.topic_mode_group = QButtonGroup()

        # ========== 1. 카드 선택 컨테이너 (초기 상태) ==========
        self.card_container = QGroupBox("주제 생성")
        card_container_layout = QVBoxLayout(self.card_container)
        card_container_layout.setSpacing(16)

        # 카드형 좌우 배치
        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)

        # 좌측 카드: 카테고리
        left_card = QFrame()
        left_card.setStyleSheet(CARD_SELECTED_STYLE)
        left_card.setCursor(Qt.PointingHandCursor)
        left_card.mousePressEvent = lambda e: self.radio_use_category.setChecked(True)
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(12, 12, 12, 8)
        left_layout.setSpacing(18)

        lbl_left = QLabel("카테고리에서 주제 생성")
        lbl_left.setAlignment(Qt.AlignCenter)
        lbl_left.setStyleSheet("font-size: 12pt;")
        left_layout.addWidget(lbl_left)

        self.radio_use_category = QRadioButton()
        self.radio_use_category.setChecked(True)
        self.radio_use_category.toggled.connect(self.toggle_topic_mode)
        self.radio_use_category.hide()
        self.topic_mode_group.addButton(self.radio_use_category, 0)

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
        right_card.setStyleSheet(CARD_UNSELECTED_STYLE)
        right_card.setCursor(Qt.PointingHandCursor)
        right_card.mousePressEvent = lambda e: self.radio_use_keyword.setChecked(True)
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(12, 12, 12, 8)
        right_layout.setSpacing(18)

        lbl_right = QLabel("키워드 기반 주제 생성")
        lbl_right.setAlignment(Qt.AlignCenter)
        lbl_right.setStyleSheet("font-size: 12pt;")
        right_layout.addWidget(lbl_right)

        self.radio_use_keyword = QRadioButton()
        self.radio_use_keyword.toggled.connect(self.toggle_topic_mode)
        self.radio_use_keyword.hide()
        self.topic_mode_group.addButton(self.radio_use_keyword, 1)

        self.manual_topic = QLineEdit()
        self.manual_topic.setPlaceholderText("키워드 입력 (예: 전기차 충전)")
        self.manual_topic.setEnabled(False)
        right_layout.addWidget(self.manual_topic)
        cards_row.addWidget(right_card, 1)

        self.left_card = left_card
        self.right_card = right_card
        card_container_layout.addLayout(cards_row)

        # 주제 생성 버튼
        self.btn_generate_topic = QPushButton("주제 생성하기")
        self.btn_generate_topic.setStyleSheet(GREEN_BUTTON_STYLE)
        self.btn_generate_topic.clicked.connect(self.generate_topics)
        card_container_layout.addWidget(self.btn_generate_topic)

        self.content_layout.addWidget(self.card_container)

        # ========== 2. 요약 컨테이너 (주제 생성 후) ==========
        self.summary_container = QFrame()
        summary_layout = QHBoxLayout(self.summary_container)
        summary_layout.setContentsMargins(16, 12, 16, 12)

        self.lbl_summary = QLabel("")
        summary_layout.addWidget(self.lbl_summary, 1)

        self.btn_change_mode = QPushButton("변경")
        self.btn_change_mode.setCursor(Qt.PointingHandCursor)
        self.btn_change_mode.clicked.connect(self._show_card_mode)
        summary_layout.addWidget(self.btn_change_mode)

        self.summary_container.hide()  # 초기에는 숨김
        self.content_layout.addWidget(self.summary_container)

        # ========== 3. 생성된 주제 선택 영역 (초기에는 숨김) ==========
        self.topic_section = QGroupBox("주제 선택")
        topic_section_layout = QVBoxLayout(self.topic_section)
        topic_section_layout.setSpacing(12)

        self.lbl_topic_result = QLabel("생성된 주제 선택")
        topic_section_layout.addWidget(self.lbl_topic_result)

        # 주제 리스트 프레임
        self.topic_list_frame = QFrame()
        self.topic_group = QButtonGroup()
        self.topic_layout_inner = QVBoxLayout(self.topic_list_frame)
        self.topic_layout_inner.setContentsMargins(0, 0, 0, 0)
        self.topic_layout_inner.setSpacing(0)
        topic_section_layout.addWidget(self.topic_list_frame)

        # 발행 버튼
        self.btn_publish = QPushButton("발행")
        self.btn_publish.setStyleSheet(GREEN_BUTTON_STYLE)
        self.btn_publish.clicked.connect(self.request_full_publish)
        self.btn_publish.setEnabled(False)
        topic_section_layout.addWidget(self.btn_publish)

        self.topic_section.hide()  # 초기에는 숨김
        self.content_layout.addWidget(self.topic_section)

        self.btn_analyze = None

    def _show_card_mode(self):
        """카드 선택 모드로 돌아가기"""
        self.summary_container.hide()
        self.topic_section.hide()
        self.card_container.show()
        self._clear_topic_list()
        # 카드 스타일 복원
        if self.radio_use_category.isChecked():
            self.left_card.setStyleSheet(CARD_SELECTED_STYLE)
            self.right_card.setStyleSheet(CARD_UNSELECTED_STYLE)
        else:
            self.left_card.setStyleSheet(CARD_UNSELECTED_STYLE)
            self.right_card.setStyleSheet(CARD_SELECTED_STYLE)
        # 상태 초기화
        self.btn_publish.setEnabled(False)
        self.analysis_done = False
        self.thumbnail_image = None
        self.current_topic_for_thumbnail = ""

    def _show_summary_mode(self):
        """요약 모드로 전환 (주제 생성 후)"""
        # 선택된 모드에 따라 요약 텍스트 설정
        if self.radio_use_category.isChecked():
            mode_text = f"카테고리: {self.combo_cat.currentText()}"
        else:
            mode_text = f"키워드: {self.manual_topic.text()}"
        self.lbl_summary.setText(mode_text)

        self.card_container.hide()
        self.summary_container.show()
        self.topic_section.show()

    # ============================================================
    # 내부 데이터 초기화 (UI 없음 - 백그라운드 데이터만)
    # ============================================================

    def _init_internal_data(self):
        """UI 없이 내부 데이터 저장용 변수 초기화"""
        # 분석 결과 저장 (UI 표시 없음)
        self._targets = []  # 타깃 독자 리스트
        self._questions = []  # 예상 질문 리스트
        self._selected_target = None  # 선택된 타깃 (첫 번째 자동 선택)
        self._selected_questions = []  # 선택된 질문들 (첫 번째 자동 선택)
        self._pending_publish = False  # 발행 대기 플래그 (분석+썸네일 완료 대기)


    # ============================================================
    # Topic mode toggle
    # ============================================================

    def toggle_topic_mode(self):
        if self.radio_use_category.isChecked():
            self.combo_cat.setEnabled(True)
            self.manual_topic.setEnabled(False)
            self.left_card.setStyleSheet(CARD_SELECTED_STYLE)
            self.right_card.setStyleSheet(CARD_UNSELECTED_STYLE)
        else:
            self.combo_cat.setEnabled(False)
            self.manual_topic.setEnabled(True)
            self.left_card.setStyleSheet(CARD_UNSELECTED_STYLE)
            self.right_card.setStyleSheet(CARD_SELECTED_STYLE)

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
        self._show_summary_mode()
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
            rb.toggled.connect(self.on_topic_changed)
            self.topic_layout_inner.addWidget(rb)
            self.topic_group.addButton(rb)

    def on_recommend_finished(self, topics: list):
        self._reset_generate_button()
        self._populate_topics(topics)
        self._show_summary_mode()
        self.log_signal.emit(f"{len(topics)}개의 트렌드 주제가 추천되었습니다.")

    def on_topic_changed(self, checked: bool):
        if checked:
            new_topic = self.get_selected_topic()
            if new_topic and new_topic != self.current_topic_for_thumbnail:
                self.thumbnail_image = None
                self.current_topic_for_thumbnail = new_topic
                # 주제가 바뀌면 분석 결과 초기화
                self.analysis_done = False
                self._targets = []
                self._questions = []
                self._selected_target = None
                self._selected_questions = []

            # 발행 버튼 활성화 (분석은 발행 클릭 시 실행)
            self.btn_publish.setEnabled(True)

    def on_recommend_error(self, error_msg: str):
        self._reset_generate_button()
        self.log_signal.emit(f"{error_msg}")

    # ============================================================
    # Analysis
    # ============================================================

    def run_analysis(self):
        topic = self.get_selected_topic()
        if not topic:
            return
        self.log_signal.emit(f"'{topic}' 주제를 심층 분석 중입니다...")

        self.analysis_worker = AnalysisWorker(topic)
        self.analysis_worker.finished.connect(self.on_analysis_finished)
        self.analysis_worker.error.connect(self.on_analysis_error)
        self.analysis_worker.start()

    def on_analysis_finished(self, data):
        self.analysis_done = True

        # 분석 결과를 내부 데이터로 저장 (UI 표시 없음)
        targets = data.get("targets", [])
        questions = data.get("questions", [])
        key_points = data.get("key_points", [])

        self._targets = [self._clean_to_plain_text(t) for t in targets]
        self._questions = [self._clean_to_plain_text(q) for q in questions]
        self._key_points = [self._clean_to_plain_text(p) for p in key_points]

        # 첫 번째 타깃/질문 자동 선택
        self._selected_target = self._targets[0] if self._targets else None
        self._selected_questions = [self._questions[0]] if self._questions else []

        self.log_signal.emit("분석 완료!")

        # 발행 대기 중이면 발행 진행 체크
        if self._pending_publish:
            self._check_ready_to_publish()

    def on_analysis_error(self, error_msg: str):
        self.log_signal.emit(f"분석 실패: {error_msg}")
        # 발행 대기 중이면 취소하고 버튼 복원
        if self._pending_publish:
            self._pending_publish = False
            self.btn_publish.setEnabled(True)
            self.btn_publish.setText("발행")

    # ============================================================
    # Thumbnail (백그라운드 생성, UI 없음)
    # ============================================================

    def generate_thumbnail_auto(self):
        """썸네일 자동 생성 (백그라운드)"""
        if not self.auth_token:
            self.log_signal.emit("썸네일 생성 스킵: 로그인 필요")
            return
        topic = self.get_selected_topic()
        if not topic:
            return
        self.log_signal.emit(f"썸네일 생성 중...")
        self.thumbnail_worker = ImageGenerateWorker(topic, self.auth_token)
        self.thumbnail_worker.finished.connect(self.on_thumbnail_finished)
        self.thumbnail_worker.error.connect(self.on_thumbnail_error)
        self.thumbnail_worker.start()

    def on_thumbnail_finished(self, images: list):
        """썸네일 생성 완료 (내부 저장)"""
        if images:
            self.thumbnail_image = images[0]
            self.log_signal.emit("썸네일 생성 완료!")

        # 발행 대기 중이면 발행 진행 체크
        if self._pending_publish:
            self._check_ready_to_publish()

    def on_thumbnail_error(self, error_msg: str):
        self.log_signal.emit(f"썸네일 생성 실패: {error_msg}")
        # 썸네일 실패해도 발행은 진행 (썸네일 없이)
        if self._pending_publish:
            self._check_ready_to_publish()

    # ============================================================
    # Full Publish (원고 생성 + 발행 통합) - v3.17.0 흐름 변경
    # ============================================================

    def request_full_publish(self):
        """발행 버튼 클릭 - 분석 → 썸네일 → 원고 생성 + 발행"""
        topic = self.get_selected_topic()
        if not topic:
            QMessageBox.warning(self, "경고", "주제를 선택해주세요.")
            return

        self.btn_publish.setEnabled(False)
        self.btn_publish.setText("분석 중...")
        self._pending_publish = True

        # 분석이 이미 완료된 경우 (같은 주제 재발행)
        if self.analysis_done and self.thumbnail_image:
            self._do_actual_publish()
            return

        # 분석 시작
        if not self.analysis_done:
            self.run_analysis()

        # 썸네일 생성 병렬 실행 (필수)
        if not self.thumbnail_image:
            self.generate_thumbnail_auto()

        # 분석/썸네일이 이미 완료되어 있다면 바로 발행 체크
        self._check_ready_to_publish()

    def _check_ready_to_publish(self):
        """분석과 썸네일이 모두 준비되었는지 확인 후 발행 진행"""
        if not self._pending_publish:
            return

        # 분석 완료 필수
        if not self.analysis_done:
            return

        # 썸네일은 선택적 (없어도 발행 진행)
        # thumbnail_image가 None이어도 썸네일 워커가 끝났으면 진행
        # (on_thumbnail_finished/error에서 호출되므로 여기 도달하면 끝난 것)

        # 발행 진행
        self._pending_publish = False
        self.btn_publish.setText("발행 중...")
        self._do_actual_publish()

    def _do_actual_publish(self):
        """실제 발행 로직 - 원고 생성 + 발행 시그널 emit"""
        topic = self.get_selected_topic()

        tone = "친근한 이웃 (해요체)"
        length = "보통 (1,500자)"
        category = ""
        if self.writing_settings_tab:
            tone = self.writing_settings_tab.get_default_tone()
            length = self.writing_settings_tab.get_default_length()
            category = self.writing_settings_tab.get_info_category()

        # 내부 저장된 분석 데이터 사용
        targets = [self._selected_target] if self._selected_target else []
        questions = self._selected_questions if self._selected_questions else []

        naver_style_settings = {}
        post_structure = "default"
        structure_params = {}
        if self.writing_settings_tab:
            naver_style_settings = self.writing_settings_tab.get_naver_editor_style_settings()
            post_structure = self.writing_settings_tab.get_post_structure()
            if hasattr(self.writing_settings_tab, 'get_structure_params'):
                structure_params = self.writing_settings_tab.get_structure_params()

        thumbnail = self.thumbnail_image if self.thumbnail_image else None
        key_points = getattr(self, '_key_points', [])

        data = {
            "action": "full",
            "mode": "info",
            "topic": topic,
            "tone": tone,
            "length": length,
            "category": category,
            "targets": targets,
            "questions": questions,
            "key_points": key_points,
            "naver_style": naver_style_settings,
            "post_structure": post_structure,
            "structure_params": structure_params,
            "images": {"thumbnail": thumbnail, "illustrations": []}
        }
        self.start_signal.emit(data)


    # ============================================================
    # Hashtags (내부 처리 - UI 없음)
    # ============================================================

    def _auto_generate_tags(self):
        """자동 해시태그 생성 - Gemini Few-shot 사용"""
        if not self.generated_content:
            return

        self.log_signal.emit("해시태그 생성 중...")

        # HashtagWorker로 Gemini Few-shot 사용
        self.hashtag_worker = HashtagWorker(
            self.generated_title or "", self.generated_content, self.auth_token
        )
        self.hashtag_worker.finished.connect(self._on_tags_generated)
        self.hashtag_worker.error.connect(self._on_tags_error)
        self.hashtag_worker.start()

    def _on_tags_generated(self, tags: list):
        """해시태그 생성 완료 - 내부 변수에 저장"""
        if tags:
            self.generated_tags = ", ".join(tags)
            self.log_signal.emit(f"해시태그 {len(tags)}개 생성 완료: {self.generated_tags[:50]}...")
        else:
            self.generated_tags = ""
            self.log_signal.emit("해시태그 생성 실패 (빈 결과)")

    def _on_tags_error(self, error_msg: str):
        """해시태그 생성 오류 - 로컬 폴백"""
        self.log_signal.emit(f"해시태그 AI 생성 실패, 로컬 추출 시도...")
        tags = extract_tags_local(self.generated_title or "", self.generated_content)
        if tags:
            self.generated_tags = ", ".join(tags)
            self.log_signal.emit(f"해시태그 {len(tags)}개 로컬 생성: {self.generated_tags[:50]}...")
        else:
            self.generated_tags = ""


    # ============================================================
    # Result view (간소화 - 발행 버튼 리셋용)
    # ============================================================

    def update_result_view(self, result_data):
        """원고 생성 결과 처리 - 내부 데이터 저장 및 버튼 리셋"""
        try:
            title = result_data.get("title", "제목 없음")
            content = result_data.get("content_text", "") or result_data.get("content", "")

            # 원본 블록 데이터 보존
            if "blocks" in result_data and result_data["blocks"]:
                self.generated_blocks = result_data["blocks"]
            else:
                self.generated_blocks = None

            if not content and self.generated_blocks:
                blocks = self.generated_blocks
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
                        lines.append(f"\n[{desc}]\n")
                content = "\n".join(lines)

            if content and content.strip().startswith("{"):
                try:
                    import json
                    parsed = json.loads(content)
                    content = parsed.get("content_text", "") or parsed.get("content", content)
                except Exception:
                    pass

            content = self._clean_to_plain_text(content)
            self.generated_content = content
            self.generated_title = title

            # 발행 버튼 리셋
            self.btn_publish.setEnabled(True)
            self.btn_publish.setText("발행")

            self.log_signal.emit(f"원고 생성 완료: {title}")

        except Exception as e:
            self.log_signal.emit(f"원고 처리 오류: {e}")
            self.btn_publish.setEnabled(True)
            self.btn_publish.setText("발행")

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

    def reset_publish_button(self):
        """발행 버튼 리셋"""
        self.btn_publish.setEnabled(True)
        self.btn_publish.setText("발행")

    def cleanup_workers(self):
        for worker in [self.recommend_worker, self.keyword_recommend_worker,
                       self.analysis_worker, self.thumbnail_worker]:
            if worker and worker.isRunning():
                worker.quit()
                worker.wait(1000)
