"""
정보성 글쓰기 탭 - 블로그 포스팅 자동 생성 기능
v3.5.1: 썸네일을 세부설정에 통합, 재생성 2회 제한
"""
import requests
import re
import base64
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, 
                               QComboBox, QLineEdit, QPushButton, QRadioButton, 
                               QButtonGroup, QLabel, QMessageBox, QScrollArea, 
                               QListWidget, QListWidgetItem, QTextEdit, QCheckBox,
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
            
            response = requests.post(
                BACKEND_URL, 
                json=payload, 
                headers=headers,
                timeout=120
            )
            
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
    """정보성 글쓰기 탭"""
    start_signal = Signal(dict) 
    log_signal = Signal(str)

    def __init__(self, writing_settings_tab=None):
        super().__init__()
        self.writing_settings_tab = writing_settings_tab  # 글쓰기 환경설정 탭 참조
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
        
        # 썸네일 재생성 횟수 추적 (주제별) - 서버 측에서 일/월 한도 관리
        self.current_topic_for_thumbnail = ""
        self.thumbnail_regenerate_count = 0
        
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

        # ========== 1. 주제 기획 ==========
        group_topic = QGroupBox("1. 주제 기획")
        topic_layout = QVBoxLayout()
        
        # ===== 카드형 좌우 배치 =====
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        self.topic_mode_group = QButtonGroup()
        
        # 좌측 카드: 카테고리에서 주제 생성
        left_card = QFrame()
        left_card.setStyleSheet("""
            QFrame { 
                border: 2px solid #FF6B6B; 
                border-radius: 8px; 
                background-color: #FFF0EC; 
                padding: 10px;
            }
        """)
        left_layout = QVBoxLayout(left_card)
        
        self.radio_use_category = QRadioButton("카테고리에서 주제 생성")
        self.radio_use_category.setChecked(True)
        self.radio_use_category.toggled.connect(self.toggle_topic_mode)
        self.radio_use_category.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.topic_mode_group.addButton(self.radio_use_category, 0)
        left_layout.addWidget(self.radio_use_category)
        
        self.combo_cat = QComboBox()
        self.combo_cat.setEditable(True)
        self.combo_cat.addItems([
            "차량 관리 상식", "자동차 보험/사고처리", "리스/렌트/할부 금융", 
            "교통법규/범칙금", "자동차 여행 코스", "전기차 라이프", "중고차 거래 팁"
        ])
        left_layout.addWidget(self.combo_cat)
        
        cards_row.addWidget(left_card, 1)  # stretch factor 1
        
        # 우측 카드: 키워드 기반 주제 생성
        right_card = QFrame()
        right_card.setStyleSheet("""
            QFrame { 
                border: 2px solid #ddd; 
                border-radius: 8px; 
                background-color: #fafafa; 
                padding: 10px;
            }
        """)
        right_layout = QVBoxLayout(right_card)
        
        self.radio_use_keyword = QRadioButton("키워드 기반 주제 생성")
        self.radio_use_keyword.toggled.connect(self.toggle_topic_mode)
        self.radio_use_keyword.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.topic_mode_group.addButton(self.radio_use_keyword, 1)
        right_layout.addWidget(self.radio_use_keyword)
        
        self.manual_topic = QLineEdit()
        self.manual_topic.setPlaceholderText("키워드 입력 (예: 전기차 충전)")
        self.manual_topic.setEnabled(False)
        self.manual_topic.setStyleSheet("background-color: #eee;")
        right_layout.addWidget(self.manual_topic)
        
        cards_row.addWidget(right_card, 1)  # stretch factor 1 (동일 비율)
        
        # 카드 참조 저장 (스타일 변경용)
        self.left_card = left_card
        self.right_card = right_card
        
        topic_layout.addLayout(cards_row)
        
        # ===== 주제 생성 버튼 (전체 너비) =====
        self.btn_generate_topic = QPushButton("주제 생성하기")
        self.btn_generate_topic.setObjectName("primaryButton")
        self.btn_generate_topic.clicked.connect(self.generate_topics)
        topic_layout.addWidget(self.btn_generate_topic)
        
        # ===== 생성된 주제 선택 영역 =====
        self.lbl_topic_result = QLabel("생성된 주제 선택:")
        self.lbl_topic_result.setStyleSheet("font-weight: bold; margin-top: 10px;")
        topic_layout.addWidget(self.lbl_topic_result)
        
        self.topic_area = QScrollArea()
        self.topic_area.setWidgetResizable(True)
        self.topic_area.setMinimumHeight(100)
        self.topic_area.setStyleSheet("QScrollArea { border: 1px solid #ddd; background-color: #fafafa; }")
        self.topic_widget = QWidget()
        self.topic_group = QButtonGroup()
        self.topic_layout_inner = QVBoxLayout(self.topic_widget)
        self.topic_layout_inner.setAlignment(Qt.AlignTop)
        
        # 초기 안내 메시지
        self.topic_placeholder = QLabel("주제 생성 버튼을 눌러 AI 추천 주제를 받아보세요.")
        self.topic_placeholder.setStyleSheet("color: #888; padding: 20px;")
        self.topic_placeholder.setAlignment(Qt.AlignCenter)
        self.topic_layout_inner.addWidget(self.topic_placeholder)
        
        self.topic_area.setWidget(self.topic_widget)
        topic_layout.addWidget(self.topic_area)
        
        # 레거시 호환용 (숨김 처리)
        self.category_frame = QFrame()
        self.category_frame.hide()
        self.keyword_frame = QFrame()
        self.keyword_frame.hide()
        self.radio_use_manual = QRadioButton()
        self.radio_use_manual.hide()
        self.manual_frame = QFrame()
        self.manual_frame.hide()
        self.keyword_topic_area = QScrollArea()
        self.keyword_topic_area.hide()
        self.keyword_topic_widget = QWidget()
        self.keyword_topic_layout_inner = QVBoxLayout(self.keyword_topic_widget)
        
        group_topic.setLayout(topic_layout)
        layout.addWidget(group_topic)

        # ========== 2. 세부 설정 (항상 표시) ==========
        group_adv = QGroupBox("2. 세부 설정")
        adv_layout = QVBoxLayout()
        
        self.btn_analyze = QPushButton("주제 분석하기 (타겟/질문 자동 추출)")
        self.btn_analyze.setObjectName("infoButton")
        self.btn_analyze.clicked.connect(self.run_analysis)
        adv_layout.addWidget(self.btn_analyze)
        
        adv_layout.addWidget(QLabel("타깃 독자 (1개만 선택):"))
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
        
        adv_layout.addWidget(QLabel("예상 질문 (선택):"))
        self.list_questions = QListWidget()
        self.list_questions.setMinimumHeight(120)
        adv_layout.addWidget(self.list_questions)
        
        adv_layout.addWidget(QLabel("핵심 정보 요약:"))
        self.txt_summary = QTextEdit()
        self.txt_summary.setMinimumHeight(80)
        adv_layout.addWidget(self.txt_summary)
        
        adv_layout.addWidget(QLabel("나만의 인사이트 (직접 입력):"))
        self.txt_insight = QTextEdit()
        self.txt_insight.setMinimumHeight(80)
        adv_layout.addWidget(self.txt_insight)
        
        # ========== 썸네일 이미지 (세부설정 내부) ==========
        adv_layout.addWidget(QLabel(""))  # 여백
        
        thumb_header = QHBoxLayout()
        thumb_header.addWidget(QLabel("대표 썸네일 이미지:"))
        thumb_header.addStretch()
        adv_layout.addLayout(thumb_header)
        
        thumb_desc = QLabel("원고 생성 완료 후 주제에 맞는 썸네일이 자동 생성됩니다.")
        thumb_desc.setStyleSheet("color: #9A9AB0; font-size: 12px;")
        adv_layout.addWidget(thumb_desc)
        
        # 썸네일 미리보기 + 재생성 버튼
        thumb_row = QHBoxLayout()
        
        self.thumbnail_preview = QLabel()
        self.thumbnail_preview.setFixedSize(200, 120)
        self.thumbnail_preview.setStyleSheet("border: 1px dashed #ccc; background-color: #f9f9f9;")
        self.thumbnail_preview.setAlignment(Qt.AlignCenter)
        self.thumbnail_preview.setText("썸네일 대기중...")
        thumb_row.addWidget(self.thumbnail_preview)
        
        # 오른쪽: 재생성 버튼 + 남은 횟수
        thumb_btn_layout = QVBoxLayout()
        
        self.btn_regenerate_thumbnail = QPushButton("다른 이미지로")
        self.btn_regenerate_thumbnail.setObjectName("accentButton")
        self.btn_regenerate_thumbnail.clicked.connect(self.regenerate_thumbnail)
        self.btn_regenerate_thumbnail.setEnabled(False)
        thumb_btn_layout.addWidget(self.btn_regenerate_thumbnail)
        
        self.lbl_regenerate_count = QLabel("재생성 횟수: 0회")
        self.lbl_regenerate_count.setStyleSheet("color: #9A9AB0; font-size: 11px;")
        thumb_btn_layout.addWidget(self.lbl_regenerate_count)
        
        thumb_btn_layout.addStretch()
        thumb_row.addLayout(thumb_btn_layout)
        thumb_row.addStretch()
        
        adv_layout.addLayout(thumb_row)
        
        # 썸네일 사용 체크
        self.chk_use_thumbnail = QCheckBox("이 썸네일 사용하여 발행")
        self.chk_use_thumbnail.setEnabled(False)
        adv_layout.addWidget(self.chk_use_thumbnail)
        
        group_adv.setLayout(adv_layout)
        layout.addWidget(group_adv)
        
        # 레거시 호환용 (self.group_adv 참조 유지)
        self.group_adv = group_adv

        # ========== 3. 원고 생성 버튼 ==========
        self.btn_generate = QPushButton("원고 생성")
        self.btn_generate.setObjectName("primaryButton")
        self.btn_generate.clicked.connect(self.request_generate)
        layout.addWidget(self.btn_generate)

        # ========== 4. 생성된 글 미리보기 ==========
        layout.addWidget(QLabel("생성된 글 미리보기"))
        
        self.view_text = QTextEdit()
        self.view_text.setPlaceholderText("생성된 TEXT 형식 결과가 여기에 표시됩니다.")
        self.view_text.setMinimumHeight(350)
        layout.addWidget(self.view_text)

        # ========== 5. 해시태그 ==========
        group_tags = QGroupBox("해시태그 (자동 생성)")
        tags_layout = QVBoxLayout()
        
        tags_desc = QLabel("원고 생성 후 자동으로 해시태그가 추천됩니다. 직접 수정할 수 있습니다.")
        tags_desc.setStyleSheet("color: #9A9AB0; font-size: 12px;")
        tags_layout.addWidget(tags_desc)
        
        self.txt_tags = QLineEdit()
        self.txt_tags.setPlaceholderText("해시태그가 자동 생성됩니다 (쉼표로 구분)")
        tags_layout.addWidget(self.txt_tags)
        
        tags_btn_row = QHBoxLayout()
        self.btn_regenerate_tags = QPushButton("태그 재생성")
        self.btn_regenerate_tags.setObjectName("accentButton")
        self.btn_regenerate_tags.clicked.connect(self.regenerate_tags)
        self.btn_regenerate_tags.setEnabled(False)
        tags_btn_row.addWidget(self.btn_regenerate_tags)
        tags_btn_row.addStretch()
        tags_layout.addLayout(tags_btn_row)
        
        group_tags.setLayout(tags_layout)
        layout.addWidget(group_tags)

        # ========== 6. 발행 옵션 ==========
        group_publish = QGroupBox("발행")
        publish_layout = QVBoxLayout()
        
        # 즉시 발행
        self.btn_publish = QPushButton("현재 내용으로 즉시 발행")
        self.btn_publish.setObjectName("primaryButton")
        self.btn_publish.clicked.connect(self.request_publish)
        self.btn_publish.setEnabled(False)
        publish_layout.addWidget(self.btn_publish)
        
        # 예약 발행
        schedule_row = QHBoxLayout()
        
        self.dt_schedule = QDateTimeEdit()
        self.dt_schedule.setCalendarPopup(True)
        self.dt_schedule.setDateTime(QDateTime.currentDateTime().addSecs(3600))  # 1시간 후
        self.dt_schedule.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_schedule.setMinimumDateTime(QDateTime.currentDateTime())
        schedule_row.addWidget(QLabel("예약 시간:"))
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
        
        publish_layout.addLayout(schedule_row)
        
        self.lbl_schedule_status = QLabel("")
        self.lbl_schedule_status.setStyleSheet("color: #9A9AB0; font-size: 12px;")
        publish_layout.addWidget(self.lbl_schedule_status)
        
        group_publish.setLayout(publish_layout)
        layout.addWidget(group_publish)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

    def on_detail_settings_toggled(self, checked: bool = True):
        """세부 설정 관련 처리 (레거시 호환용 - 이제 항상 표시됨)"""
        pass  # 세부 설정이 항상 표시되므로 별도 처리 불필요

    def generate_thumbnail_auto(self):
        """썸네일 자동 생성 (세부설정 펼칠 때)"""
        if not self.auth_token:
            self.thumbnail_preview.setText("로그인 필요")
            self.log_signal.emit("썸네일 생성은 로그인이 필요합니다.")
            return
        
        topic = self.get_selected_topic()
        if not topic:
            self.thumbnail_preview.setText("주제를 선택하세요")
            return
        
        self.thumbnail_preview.setText("생성 중...")
        self.btn_regenerate_thumbnail.setEnabled(False)
        self.log_signal.emit(f"'{topic}' 주제로 썸네일 이미지 생성 중...")
        
        self.thumbnail_worker = ImageGenerateWorker(topic, self.auth_token)
        self.thumbnail_worker.finished.connect(self.on_thumbnail_finished)
        self.thumbnail_worker.error.connect(self.on_thumbnail_error)
        self.thumbnail_worker.start()

    def regenerate_thumbnail(self):
        """썸네일 재생성 (버튼 클릭 시) - 서버 측 일/월 한도만 적용"""
        self.thumbnail_regenerate_count += 1
        self.update_regenerate_count_label()
        self.generate_thumbnail_auto()

    def update_regenerate_count_label(self):
        """재생성 횟수 라벨 업데이트 (참고 표시만)"""
        self.lbl_regenerate_count.setText(f"재생성 횟수: {self.thumbnail_regenerate_count}회")
        self.lbl_regenerate_count.setStyleSheet("color: #9A9AB0; font-size: 12px;")

    def toggle_topic_mode(self):
        """주제 입력 모드 토글 - 선택에 따라 카드 스타일 및 입력 필드 활성화/비활성화"""
        if self.radio_use_category.isChecked():
            # 카테고리 카드 활성화
            self.left_card.setStyleSheet("""
                QFrame { 
                    border: 2px solid #FF6B6B; 
                    border-radius: 8px; 
                    background-color: #FFF0EC; 
                    padding: 10px;
                }
            """)
            self.right_card.setStyleSheet("""
                QFrame { 
                    border: 2px solid #ddd; 
                    border-radius: 8px; 
                    background-color: #fafafa; 
                    padding: 10px;
                }
            """)
            self.combo_cat.setEnabled(True)
            self.combo_cat.setStyleSheet("")
            self.manual_topic.setEnabled(False)
            self.manual_topic.setStyleSheet("background-color: #eee;")
        else:
            # 키워드 카드 활성화
            self.left_card.setStyleSheet("""
                QFrame { 
                    border: 2px solid #ddd; 
                    border-radius: 8px; 
                    background-color: #fafafa; 
                    padding: 10px;
                }
            """)
            self.right_card.setStyleSheet("""
                QFrame { 
                    border: 2px solid #FF6B6B; 
                    border-radius: 8px; 
                    background-color: #FFF0EC; 
                    padding: 10px;
                }
            """)
            self.combo_cat.setEnabled(False)
            self.combo_cat.setStyleSheet("background-color: #eee;")
            self.manual_topic.setEnabled(True)
            self.manual_topic.setStyleSheet("")

    def get_selected_topic(self):
        """선택된 주제 반환"""
        selected_btn = self.topic_group.checkedButton()
        if selected_btn:
            return selected_btn.text()
        return None
    
    def generate_topics(self):
        """주제 생성 버튼 클릭 - 선택된 모드에 따라 주제 생성"""
        if self.radio_use_category.isChecked():
            # 카테고리 기반 추천
            self.get_recommendations()
        else:
            # 키워드 기반 추천
            self.get_keyword_recommendations()
    
    def get_keyword_recommendations(self):
        """키워드 기반 AI 추천 주제 받기"""
        keyword = self.manual_topic.text().strip()
        if not keyword:
            QMessageBox.warning(self, "경고", "키워드를 입력해주세요.")
            return
        
        self.log_signal.emit(f"'{keyword}' 키워드로 관련 주제를 분석 중입니다...")
        
        self.btn_generate_topic.setEnabled(False)
        self.btn_generate_topic.setText("주제 분석 중...")
        
        # 기존 주제 제거
        self._clear_topic_list()
        
        # 키워드를 카테고리로 활용하여 추천 요청
        self.keyword_recommend_worker = RecommendWorker(keyword)
        self.keyword_recommend_worker.finished.connect(self.on_keyword_recommend_finished)
        self.keyword_recommend_worker.error.connect(self.on_keyword_recommend_error)
        self.keyword_recommend_worker.start()
    
    def on_keyword_recommend_finished(self, topics: list):
        """키워드 기반 추천 완료"""
        self._reset_generate_button()
        self._populate_topics(topics)
        self.log_signal.emit(f"{len(topics)}개의 관련 주제가 추천되었습니다.")
    
    def on_keyword_recommend_error(self, error_msg: str):
        """키워드 기반 추천 에러"""
        self._reset_generate_button()
        self.log_signal.emit(f"{error_msg}")
 
    def get_recommendations(self):
        """카테고리 기반 AI 추천 주제 받기"""
        category = self.combo_cat.currentText()
        self.log_signal.emit(f"'{category}' 관련 최신 트렌드를 분석 중입니다...")
        
        self.btn_generate_topic.setEnabled(False)
        self.btn_generate_topic.setText("트렌드 분석 중...")
        
        # 기존 주제 제거
        self._clear_topic_list()
        
        self.recommend_worker = RecommendWorker(category)
        self.recommend_worker.finished.connect(self.on_recommend_finished)
        self.recommend_worker.error.connect(self.on_recommend_error)
        self.recommend_worker.start()

    def _clear_topic_list(self):
        """주제 목록 초기화"""
        for i in reversed(range(self.topic_layout_inner.count())): 
            widget = self.topic_layout_inner.itemAt(i).widget()
            if widget:
                widget.setParent(None)
    
    def _reset_generate_button(self):
        """주제 생성 버튼 초기화"""
        self.btn_generate_topic.setEnabled(True)
        self.btn_generate_topic.setText("주제 생성하기")
    
    def _populate_topics(self, topics: list):
        """주제 목록 채우기"""
        for t in topics:
            rb = QRadioButton(t)
            rb.setStyleSheet("font-size: 13px; padding: 5px;")
            rb.toggled.connect(self.on_topic_changed)
            self.topic_layout_inner.addWidget(rb)
            self.topic_group.addButton(rb)

    def on_recommend_finished(self, topics: list):
        """카테고리 기반 추천 완료"""
        self._reset_generate_button()
        self._populate_topics(topics)
        self.log_signal.emit(f"{len(topics)}개의 트렌드 주제가 추천되었습니다.")

    def on_topic_changed(self, checked: bool):
        """주제 변경 시 호출"""
        if checked:
            # 주제가 변경되면 썸네일 관련 상태 초기화
            new_topic = self.get_selected_topic()
            if new_topic and new_topic != self.current_topic_for_thumbnail:
                self.thumbnail_image = None
                self.thumbnail_preview.setText("원고 생성 후 자동 생성됩니다")
                self.chk_use_thumbnail.setChecked(False)
                self.chk_use_thumbnail.setEnabled(False)
                self.btn_regenerate_thumbnail.setEnabled(False)
                
                self.current_topic_for_thumbnail = new_topic
                self.thumbnail_regenerate_count = 0
                self.update_regenerate_count_label()

    def on_recommend_error(self, error_msg: str):
        """추천 에러"""
        self._reset_generate_button()
        self.log_signal.emit(f"{error_msg}")

    def run_analysis(self):
        """주제 분석 실행"""
        topic = self.get_selected_topic()
        if not topic:
            QMessageBox.warning(self, "경고", "먼저 주제를 선택하거나 입력해주세요.")
            return
            
        self.log_signal.emit(f"'{topic}' 주제를 심층 분석 중입니다...")
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.setText("분석 중...")
        
        self.analysis_worker = AnalysisWorker(topic)
        self.analysis_worker.finished.connect(self.on_analysis_finished)
        self.analysis_worker.error.connect(self.on_analysis_error)
        self.analysis_worker.start()

    def on_analysis_finished(self, data):
        """분석 완료"""
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText("주제 분석하기 (타겟/질문 추출)")
        
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
        
        self.log_signal.emit("분석 완료! 타깃과 질문을 선택해주세요.")

    def on_analysis_error(self, error_msg: str):
        """분석 에러"""
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText("주제 분석하기 (타겟/질문 추출)")
        self.log_signal.emit(f"{error_msg}")

    def request_generate(self):
        """원고 생성 요청"""
        topic = self.get_selected_topic()
        if not topic:
            QMessageBox.warning(self, "경고", "주제를 선택하거나 입력해주세요.")
            return

        # 중복 주제 경고
        if is_duplicate_topic(topic, days=30):
            reply = QMessageBox.question(
                self, "중복 주제",
                f"최근 30일 내 유사한 주제로 발행한 이력이 있습니다.\n\n"
                f"주제: {topic}\n\n계속 생성하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        # 버튼 상태 변경
        self.btn_generate.setEnabled(False)
        self.btn_generate.setText("생성 중...")
        
        # 기본 톤/분량 가져오기 (글쓰기 환경설정에서)
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

        # 네이버 에디터 서식 설정 가져오기
        naver_style_settings = {}
        if self.writing_settings_tab:
            naver_style_settings = self.writing_settings_tab.get_naver_editor_style_settings()

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
            "naver_style": naver_style_settings,  # 네이버 에디터 서식 설정 추가
        }
        self.start_signal.emit(data)

    def request_publish(self):
        """발행 요청"""
        current_content = self.view_text.toPlainText()
        
        if not current_content:
            QMessageBox.warning(self, "경고", "발행할 내용이 없습니다.")
            return
        
        lines = current_content.split('\n')
        title = self.generated_title or "무제"
        content = current_content
        
        # 제목 추출
        if len(lines) > 0 and (lines[0].startswith("제목:") or lines[0].startswith("# ")):
            title = lines[0].replace("제목:", "").replace("# ", "").strip()
            content = "\n".join(lines[1:]).strip()
        
        # 카테고리 가져오기
        category = ""
        if self.writing_settings_tab:
            category = self.writing_settings_tab.get_info_category()
        
        # 썸네일 이미지
        thumbnail = None
        if self.chk_use_thumbnail.isChecked() and self.thumbnail_image:
            thumbnail = self.thumbnail_image
        
        # 해시태그
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

    def on_thumbnail_finished(self, images: list):
        """썸네일 생성 완료"""
        self.btn_regenerate_thumbnail.setEnabled(True)
        
        if images:
            self.thumbnail_image = images[0]
            
            try:
                img_data = base64.b64decode(self.thumbnail_image)
                qimg = QImage.fromData(img_data)
                pixmap = QPixmap.fromImage(qimg)
                scaled = pixmap.scaled(200, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.thumbnail_preview.setPixmap(scaled)
                self.chk_use_thumbnail.setEnabled(True)
                self.chk_use_thumbnail.setChecked(True)
            except:
                self.thumbnail_preview.setText("로드 실패")
            
            self.log_signal.emit("썸네일 이미지 생성 완료!")

    def on_thumbnail_error(self, error_msg: str):
        """썸네일 생성 에러"""
        self.btn_regenerate_thumbnail.setEnabled(True)
        
        self.thumbnail_preview.setText("생성 실패")
        self.log_signal.emit(f"썸네일 생성 실패: {error_msg}")

    # ========== 해시태그 ==========
    
    def _auto_generate_tags(self):
        """원고 기반 해시태그 자동 생성"""
        if not self.generated_content:
            return
        
        title = self.generated_title or ""
        content = self.generated_content
        
        # 빠른 로컬 추출 (즉시 표시)
        tags = extract_tags_local(title, content)
        if tags:
            self.txt_tags.setText(", ".join(tags))
            self.btn_regenerate_tags.setEnabled(True)
            self.log_signal.emit(f"해시태그 {len(tags)}개 자동 생성 완료")
    
    def regenerate_tags(self):
        """해시태그 재생성 (AI 사용 시도)"""
        if not self.generated_content:
            return
        
        self.btn_regenerate_tags.setEnabled(False)
        self.btn_regenerate_tags.setText("생성 중...")
        
        self.hashtag_worker = HashtagWorker(
            self.generated_title or "",
            self.generated_content,
            self.auth_token
        )
        self.hashtag_worker.finished.connect(self._on_tags_generated)
        self.hashtag_worker.error.connect(self._on_tags_error)
        self.hashtag_worker.start()
    
    def _on_tags_generated(self, tags: list):
        """해시태그 생성 완료"""
        self.btn_regenerate_tags.setEnabled(True)
        self.btn_regenerate_tags.setText("태그 재생성")
        if tags:
            self.txt_tags.setText(", ".join(tags))
            self.log_signal.emit(f"해시태그 {len(tags)}개 생성 완료")
    
    def _on_tags_error(self, error_msg: str):
        """해시태그 생성 에러"""
        self.btn_regenerate_tags.setEnabled(True)
        self.btn_regenerate_tags.setText("태그 재생성")
        self.log_signal.emit(f"해시태그 생성 실패: {error_msg}")

    # ========== 예약 발행 ==========
    
    def schedule_publish(self):
        """예약 발행 설정"""
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
        
        # UI 업데이트
        self.lbl_schedule_status.setText(f"예약됨: {target_dt.toString('yyyy-MM-dd HH:mm')}")
        self.lbl_schedule_status.setStyleSheet("color: #FF6B6B; font-size: 12px; font-weight: bold;")
        self.btn_schedule.hide()
        self.btn_cancel_schedule.show()
        self.btn_publish.setEnabled(False)
        self.dt_schedule.setEnabled(False)
        
        self.log_signal.emit(f"예약 발행 설정됨: {target_dt.toString('yyyy-MM-dd HH:mm')}")
    
    def _execute_scheduled_publish(self):
        """예약 시간 도달 시 발행 실행"""
        self.schedule_timer = None
        self.lbl_schedule_status.setText("예약 시간 도달! 발행 중...")
        self.btn_cancel_schedule.hide()
        self.btn_schedule.show()
        self.dt_schedule.setEnabled(True)
        self.log_signal.emit("예약 시간 도달 - 자동 발행을 시작합니다.")
        self.request_publish()
    
    def cancel_scheduled_publish(self):
        """예약 취소"""
        if self.schedule_timer:
            self.schedule_timer.stop()
            self.schedule_timer = None
        
        self.lbl_schedule_status.setText("예약이 취소되었습니다.")
        self.lbl_schedule_status.setStyleSheet("color: #9A9AB0; font-size: 12px;")
        self.btn_cancel_schedule.hide()
        self.btn_schedule.show()
        self.btn_publish.setEnabled(True)
        self.dt_schedule.setEnabled(True)
        
        self.log_signal.emit("예약 발행이 취소되었습니다.")

    def update_result_view(self, result_data):
        """결과 뷰어 업데이트 - TEXT만 표시"""
        title = result_data.get("title", "제목 없음")
        
        # content_text 우선, 없으면 content 사용
        content = result_data.get("content_text", "") or result_data.get("content", "")
        
        # JSON 형태로 온 경우 정리
        if content and content.strip().startswith("{"):
            try:
                import json
                parsed = json.loads(content)
                content = parsed.get("content_text", "") or parsed.get("content", content)
            except:
                pass
        
        # 마크다운/HTML 형식이 섞여 있으면 순수 텍스트로 정리
        content = self._clean_to_plain_text(content)
        
        # 생성된 본문 저장
        self.generated_content = content
        self.generated_title = title
        
        # TEXT만 깔끔하게 표시
        display_text = f"제목: {title}\n\n{'━' * 50}\n\n{content}"
        self.view_text.setText(display_text)
        
        # 버튼 상태 복원
        self.btn_generate.setEnabled(True)
        self.btn_generate.setText("생성 완료!")
        
        # 발행 버튼 활성화
        self.btn_publish.setEnabled(True)
        self.btn_schedule.setEnabled(True)
        self.dt_schedule.setMinimumDateTime(QDateTime.currentDateTime())
        
        self.log_signal.emit("글 생성 완료! 확인 후 발행할 수 있습니다.")
        
        # 원고 생성 완료 후 썸네일 자동 생성
        if self.writing_settings_tab and self.writing_settings_tab.is_auto_thumbnail_enabled():
            self.generate_thumbnail_auto()
        
        # 해시태그 자동 생성
        self._auto_generate_tags()

    def _clean_to_plain_text(self, content: str) -> str:
        """
        마크다운/HTML이 섞인 콘텐츠를 순수 텍스트로 정리
        """
        if not content:
            return content
        
        import re
        
        # HTML 태그 제거
        content = re.sub(r'<[^>]+>', '', content)
        
        # 마크다운 헤딩 (#, ##, ###) -> 일반 소제목 스타일
        content = re.sub(r'^#{1,3}\s*(.+)$', r'【\1】', content, flags=re.MULTILINE)
        
        # 마크다운 볼드 (**text** 또는 __text__)
        content = re.sub(r'\*\*(.+?)\*\*', r'\1', content)
        content = re.sub(r'__(.+?)__', r'\1', content)
        
        # 마크다운 이탤릭 (*text* 또는 _text_) - 단어 내부 언더스코어는 유지
        content = re.sub(r'(?<!\w)\*([^*]+)\*(?!\w)', r'\1', content)
        content = re.sub(r'(?<!\w)_([^_]+)_(?!\w)', r'\1', content)
        
        # 마크다운 인용문 (> text)
        content = re.sub(r'^>\s*', '', content, flags=re.MULTILINE)
        
        # 마크다운 코드블록 (```...```)
        content = re.sub(r'```[\s\S]*?```', '', content)
        
        # 인라인 코드 (`code`)
        content = re.sub(r'`([^`]+)`', r'\1', content)
        
        # 마크다운 링크 [text](url) -> text
        content = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', content)
        
        # 마크다운 이미지 ![alt](url) 제거
        content = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', content)
        
        # 연속된 빈 줄 정리
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        return content.strip()

    def reset_generate_button(self):
        """생성 버튼 초기화 (에러 시 호출)"""
        self.btn_generate.setEnabled(True)
        self.btn_generate.setText("원고 생성")
    
    def cleanup_workers(self):
        """모든 워커 스레드 정리 (앱 종료 시 호출)"""
        # 추천 워커 정리
        if self.recommend_worker and self.recommend_worker.isRunning():
            self.recommend_worker.quit()
            self.recommend_worker.wait(1000)
        
        # 키워드 추천 워커 정리
        if self.keyword_recommend_worker and self.keyword_recommend_worker.isRunning():
            self.keyword_recommend_worker.quit()
            self.keyword_recommend_worker.wait(1000)
        
        # 분석 워커 정리
        if self.analysis_worker and self.analysis_worker.isRunning():
            self.analysis_worker.quit()
            self.analysis_worker.wait(1000)
        
        # 썸네일 워커 정리
        if self.thumbnail_worker and self.thumbnail_worker.isRunning():
            self.thumbnail_worker.quit()
            self.thumbnail_worker.wait(1000)
