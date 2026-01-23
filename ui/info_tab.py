"""
정보성 글쓰기 탭 - 블로그 포스팅 자동 생성 기능
v3.7.1: 주제기획 UI 개편 (좌우 2단), 직접입력 제거, QThread 크래시 수정
"""
import requests
import re
import os
import base64
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, 
                               QComboBox, QLineEdit, QPushButton, QRadioButton, 
                               QButtonGroup, QLabel, QMessageBox, QScrollArea, 
                               QListWidget, QListWidgetItem, QTextEdit, QCheckBox,
                               QFrame)
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
    """주제 추천 워커 스레드 (카테고리 기반)"""
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


class KeywordRecommendWorker(QThread):
    """키워드 기반 주제 추천 워커 스레드"""
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, keywords: list):
        super().__init__()
        self.keywords = keywords

    def run(self):
        try:
            response = requests.post(
                BACKEND_URL, 
                json={"mode": "recommend_by_keywords", "keywords": self.keywords}, 
                timeout=60
            )
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
                "style": "블로그 대표 썸네일, 텍스트 없이, 주제를 잘 나타내는 시각적 이미지, 16:9 가로 비율"
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
        self.keyword_recommend_worker = None  # 키워드 추천 워커
        self.analysis_worker = None
        self.thumbnail_worker = None
        self.thumbnail_image = None
        self.auth_token = ""
        self.generated_content = ""
        self.generated_title = ""
        self.generated_blocks = []  # 구조화된 블록 데이터 (Selenium 에디터 조작용)
        
        # 썸네일 재생성 횟수 추적 (주제별)
        self.current_topic_for_thumbnail = ""
        self.thumbnail_regenerate_count = 0
        self.max_regenerate_count = 2  # 최대 재생성 횟수
        
        self.init_ui()
    
    def cleanup_workers(self):
        """실행 중인 워커 스레드 정리 (앱 종료 시 호출)"""
        workers = [self.recommend_worker, self.keyword_recommend_worker, self.analysis_worker, self.thumbnail_worker]
        for worker in workers:
            if worker and worker.isRunning():
                worker.quit()
                worker.wait(1000)  # 최대 1초 대기
                if worker.isRunning():
                    worker.terminate()
                    worker.wait()

    def set_auth_token(self, token: str):
        """인증 토큰 설정"""
        self.auth_token = token

    def init_ui(self):
        main_layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)

        # ========== 1. 주제 기획 (좌우 2단) ==========
        group_topic = QGroupBox("1. 주제 기획")
        topic_layout = QVBoxLayout()
        
        # 주제 생성 방식 선택 (좌우 2단 구성)
        mode_row = QHBoxLayout()
        
        # 라디오 버튼 그룹
        self.topic_mode_group = QButtonGroup()
        
        # ===== 좌측: 카테고리에서 주제 생성 =====
        self.category_frame = QFrame()
        self.category_frame.setFrameShape(QFrame.StyledPanel)
        self.category_frame.setStyleSheet("QFrame { border: 2px solid #4A90E2; border-radius: 5px; background-color: #f0f8ff; }")
        left_layout = QVBoxLayout(self.category_frame)
        
        self.radio_use_category = QRadioButton("📂 카테고리에서 주제 생성하기")
        self.radio_use_category.setChecked(True)
        self.radio_use_category.toggled.connect(self.toggle_topic_mode)
        self.topic_mode_group.addButton(self.radio_use_category, 0)
        left_layout.addWidget(self.radio_use_category)
        
        self.combo_cat = QComboBox()
        self.combo_cat.addItems([
            "차량 관리 상식", "자동차 보험/사고처리", "리스/렌트/할부 금융", 
            "교통법규/범칙금", "자동차 여행 코스", "전기차 라이프", "중고차 거래 팁"
        ])
        left_layout.addWidget(self.combo_cat)
        
        mode_row.addWidget(self.category_frame)
        
        # ===== 우측: 키워드 기반 주제 생성 =====
        self.keyword_frame = QFrame()
        self.keyword_frame.setFrameShape(QFrame.StyledPanel)
        self.keyword_frame.setStyleSheet("QFrame { border: 1px solid #ddd; border-radius: 5px; background-color: #f9f9f9; }")
        right_layout = QVBoxLayout(self.keyword_frame)
        
        self.radio_use_keyword = QRadioButton("🔑 키워드 기반 주제 생성하기")
        self.radio_use_keyword.toggled.connect(self.toggle_topic_mode)
        self.topic_mode_group.addButton(self.radio_use_keyword, 1)
        right_layout.addWidget(self.radio_use_keyword)
        
        self.input_keywords = QLineEdit()
        self.input_keywords.setPlaceholderText("예: 타이어관리, 엔진오일, 연비")
        self.input_keywords.setEnabled(False)
        right_layout.addWidget(self.input_keywords)
        
        mode_row.addWidget(self.keyword_frame)
        
        topic_layout.addLayout(mode_row)
        
        # 주제 생성 버튼 (통합)
        self.btn_generate_topic = QPushButton("🚀 주제 생성하기")
        self.btn_generate_topic.clicked.connect(self.generate_topics)
        self.btn_generate_topic.setStyleSheet("""
            background-color: #5D5D5D; 
            color: white; 
            padding: 10px; 
            font-weight: bold;
        """)
        topic_layout.addWidget(self.btn_generate_topic)
        
        # 구분선
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("color: #ddd;")
        topic_layout.addWidget(divider)
        
        # 생성된 주제 표시 영역
        topic_layout.addWidget(QLabel("📋 생성된 주제 선택:"))
        
        self.topic_area = QScrollArea()
        self.topic_area.setWidgetResizable(True)
        self.topic_area.setMinimumHeight(150)
        self.topic_widget = QWidget()
        self.topic_group = QButtonGroup()
        self.topic_layout_inner = QVBoxLayout(self.topic_widget)
        self.topic_layout_inner.setAlignment(Qt.AlignTop)
        self.topic_area.setWidget(self.topic_widget)
        topic_layout.addWidget(self.topic_area)
        
        group_topic.setLayout(topic_layout)
        layout.addWidget(group_topic)

        # ========== 2. 세부 설정 (항상 활성화) ==========
        self.group_adv = QGroupBox("2. 세부 설정")
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
        
        # ========== 썸네일 이미지 (세부설정 내부) ==========
        adv_layout.addWidget(QLabel(""))  # 여백
        
        thumb_header = QHBoxLayout()
        thumb_header.addWidget(QLabel("🖼️ 대표 썸네일 이미지:"))
        thumb_header.addStretch()
        adv_layout.addLayout(thumb_header)
        
        thumb_desc = QLabel("세부 설정을 펼치면 주제에 맞는 썸네일이 자동 생성됩니다.")
        thumb_desc.setStyleSheet("color: #666; font-size: 11px;")
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
        
        self.btn_regenerate_thumbnail = QPushButton("🔄 다른 이미지로")
        self.btn_regenerate_thumbnail.clicked.connect(self.regenerate_thumbnail)
        self.btn_regenerate_thumbnail.setStyleSheet("background-color: #9B59B6; color: white; padding: 8px;")
        self.btn_regenerate_thumbnail.setEnabled(False)
        thumb_btn_layout.addWidget(self.btn_regenerate_thumbnail)
        
        self.lbl_regenerate_count = QLabel("재생성 가능: 2회")
        self.lbl_regenerate_count.setStyleSheet("color: #888; font-size: 11px;")
        thumb_btn_layout.addWidget(self.lbl_regenerate_count)
        
        thumb_btn_layout.addStretch()
        thumb_row.addLayout(thumb_btn_layout)
        thumb_row.addStretch()
        
        adv_layout.addLayout(thumb_row)
        
        self.group_adv.setLayout(adv_layout)
        layout.addWidget(self.group_adv)

        # ========== 3. 원고 생성 버튼 ==========
        self.btn_generate = QPushButton("📝 원고 생성")
        self.btn_generate.setStyleSheet("""
            background-color: #03C75A; 
            color: white; 
            font-weight: bold; 
            padding: 15px;
            font-size: 16px;
        """)
        self.btn_generate.clicked.connect(self.request_generate)
        layout.addWidget(self.btn_generate)

        # ========== 4. 생성된 글 미리보기 ==========
        layout.addWidget(QLabel("📝 생성된 글 미리보기"))
        
        self.view_text = QTextEdit()
        self.view_text.setPlaceholderText("생성된 TEXT 형식 결과가 여기에 표시됩니다.")
        self.view_text.setMinimumHeight(350)
        layout.addWidget(self.view_text)

        # ========== 5. 최종 발행 버튼 ==========
        self.btn_publish = QPushButton("📤 현재 내용으로 발행하기")
        self.btn_publish.setStyleSheet("""
            background-color: #4A90E2; 
            color: white; 
            font-weight: bold; 
            padding: 15px; 
            font-size: 16px;
        """)
        self.btn_publish.clicked.connect(self.request_publish)
        self.btn_publish.setEnabled(False)
        layout.addWidget(self.btn_publish)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

    def generate_thumbnail_auto(self):
        """썸네일 자동 생성 (세부설정 펼칠 때)"""
        if not self.auth_token:
            self.thumbnail_preview.setText("로그인 필요")
            self.log_signal.emit("⚠️ 썸네일 생성은 로그인이 필요합니다.")
            return
        
        topic = self.get_selected_topic()
        if not topic:
            self.thumbnail_preview.setText("주제를 선택하세요")
            return
        
        self.thumbnail_preview.setText("⏳ 생성 중...")
        self.btn_regenerate_thumbnail.setEnabled(False)
        self.log_signal.emit(f"🖼️ '{topic}' 주제로 썸네일 이미지 생성 중...")
        
        self.thumbnail_worker = ImageGenerateWorker(topic, self.auth_token)
        self.thumbnail_worker.finished.connect(self.on_thumbnail_finished)
        self.thumbnail_worker.error.connect(self.on_thumbnail_error)
        self.thumbnail_worker.start()

    def regenerate_thumbnail(self):
        """썸네일 재생성 (버튼 클릭 시)"""
        if self.thumbnail_regenerate_count >= self.max_regenerate_count:
            QMessageBox.warning(self, "제한 초과", 
                f"이 주제에 대한 썸네일 재생성은 {self.max_regenerate_count}회까지만 가능합니다.\n"
                "새로운 주제를 선택하면 다시 생성할 수 있습니다.")
            return
        
        self.thumbnail_regenerate_count += 1
        self.update_regenerate_count_label()
        self.generate_thumbnail_auto()

    def update_regenerate_count_label(self):
        """재생성 가능 횟수 라벨 업데이트"""
        remaining = self.max_regenerate_count - self.thumbnail_regenerate_count
        self.lbl_regenerate_count.setText(f"재생성 가능: {remaining}회")
        
        if remaining <= 0:
            self.lbl_regenerate_count.setStyleSheet("color: #E74C3C; font-size: 11px;")
            self.btn_regenerate_thumbnail.setEnabled(False)
        else:
            self.lbl_regenerate_count.setStyleSheet("color: #888; font-size: 11px;")

    def toggle_topic_mode(self):
        """주제 입력 모드 토글 (카테고리 vs 키워드)"""
        use_category = self.radio_use_category.isChecked()
        use_keyword = self.radio_use_keyword.isChecked()
        
        # 카테고리 모드
        self.combo_cat.setEnabled(use_category)
        
        # 키워드 모드
        self.input_keywords.setEnabled(use_keyword)
        
        # 프레임 스타일 변경 (선택된 모드 강조)
        if use_category:
            self.category_frame.setStyleSheet("QFrame { border: 2px solid #4A90E2; border-radius: 5px; background-color: #f0f8ff; }")
            self.keyword_frame.setStyleSheet("QFrame { border: 1px solid #ddd; border-radius: 5px; background-color: #f9f9f9; }")
        else:
            self.category_frame.setStyleSheet("QFrame { border: 1px solid #ddd; border-radius: 5px; background-color: #f9f9f9; }")
            self.keyword_frame.setStyleSheet("QFrame { border: 2px solid #4A90E2; border-radius: 5px; background-color: #f0f8ff; }")

    def get_selected_topic(self):
        """선택된 주제 반환"""
        selected_btn = self.topic_group.checkedButton()
        if selected_btn:
            return selected_btn.text()
        return None
    
    def generate_topics(self):
        """통합 주제 생성 함수 (선택된 모드에 따라 분기)"""
        if self.radio_use_category.isChecked():
            self._generate_by_category()
        else:
            self._generate_by_keywords()
    
    def _generate_by_category(self):
        """카테고리 기반 주제 생성"""
        category = self.combo_cat.currentText()
        self.log_signal.emit(f"🤖 '{category}' 관련 최신 트렌드를 분석 중입니다...")
        
        self.btn_generate_topic.setEnabled(False)
        self.btn_generate_topic.setText("⏳ 트렌드 분석 중...")
        self.btn_generate_topic.setStyleSheet("background-color: #888; color: white; padding: 10px; font-weight: bold;")
        
        self._clear_topic_list()
        
        # 이전 워커가 있으면 정리
        if self.recommend_worker and self.recommend_worker.isRunning():
            self.recommend_worker.quit()
            self.recommend_worker.wait(500)
        
        self.recommend_worker = RecommendWorker(category)
        self.recommend_worker.finished.connect(self._on_topic_generated)
        self.recommend_worker.error.connect(self._on_topic_error)
        self.recommend_worker.start()
    
    def _generate_by_keywords(self):
        """키워드 기반 주제 생성"""
        keywords_text = self.input_keywords.text().strip()
        if not keywords_text:
            self.log_signal.emit("⚠️ 키워드를 입력해주세요.")
            return
        
        # 쉼표로 분리하여 키워드 리스트 생성
        keywords = [k.strip() for k in keywords_text.split(',') if k.strip()]
        if not keywords:
            self.log_signal.emit("⚠️ 유효한 키워드를 입력해주세요.")
            return
        
        self.log_signal.emit(f"🔑 키워드 '{', '.join(keywords)}' 기반 주제 생성 중...")
        
        self.btn_generate_topic.setEnabled(False)
        self.btn_generate_topic.setText("⏳ 분석 중...")
        self.btn_generate_topic.setStyleSheet("background-color: #888; color: white; padding: 10px; font-weight: bold;")
        
        self._clear_topic_list()
        
        # 이전 워커가 있으면 정리
        if self.keyword_recommend_worker and self.keyword_recommend_worker.isRunning():
            self.keyword_recommend_worker.quit()
            self.keyword_recommend_worker.wait(500)
        
        self.keyword_recommend_worker = KeywordRecommendWorker(keywords)
        self.keyword_recommend_worker.finished.connect(self._on_topic_generated)
        self.keyword_recommend_worker.error.connect(self._on_topic_error)
        self.keyword_recommend_worker.start()
    
    def _on_topic_generated(self, topics: list):
        """주제 생성 완료 (공통 핸들러)"""
        self.btn_generate_topic.setEnabled(True)
        self.btn_generate_topic.setText("✅ 생성 완료! (다시 생성)")
        self.btn_generate_topic.setStyleSheet("background-color: #27AE60; color: white; padding: 10px; font-weight: bold;")
        
        self._display_recommended_topics(topics)
        self.log_signal.emit(f"✅ {len(topics)}개의 주제가 생성되었습니다.")
    
    def _on_topic_error(self, error_msg: str):
        """주제 생성 에러 (공통 핸들러)"""
        self.btn_generate_topic.setEnabled(True)
        self.btn_generate_topic.setText("🚀 주제 생성하기")
        self.btn_generate_topic.setStyleSheet("background-color: #5D5D5D; color: white; padding: 10px; font-weight: bold;")
        self.log_signal.emit(f"❌ {error_msg}")

    def _clear_topic_list(self):
        """주제 목록 초기화"""
        for i in reversed(range(self.topic_layout_inner.count())): 
            widget = self.topic_layout_inner.itemAt(i).widget()
            if widget:
                widget.setParent(None)

    def _display_recommended_topics(self, topics: list):
        """추천된 주제 목록 표시"""
        self._clear_topic_list()
        
        for t in topics:
            rb = QRadioButton(t)
            rb.setStyleSheet("font-size: 13px; padding: 5px;")
            rb.toggled.connect(self.on_topic_changed)
            self.topic_layout_inner.addWidget(rb)
            self.topic_group.addButton(rb)

    def on_topic_changed(self, checked: bool):
        """주제 변경 시 호출"""
        if checked:
            # 주제가 변경되면 썸네일 관련 상태 초기화 및 자동 생성
            new_topic = self.get_selected_topic()
            if new_topic and new_topic != self.current_topic_for_thumbnail:
                self.thumbnail_image = None
                self.thumbnail_preview.setText("썸네일 대기중...")
                
                # 썸네일 자동 생성
                self.current_topic_for_thumbnail = new_topic
                self.thumbnail_regenerate_count = 0
                self.update_regenerate_count_label()
                self.generate_thumbnail_auto()

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

    def request_generate(self):
        """원고 생성 요청"""
        topic = self.get_selected_topic()
        if not topic:
            QMessageBox.warning(self, "경고", "주제를 선택하거나 입력해주세요.")
            return

        # 버튼 상태 변경
        self.btn_generate.setEnabled(False)
        self.btn_generate.setText("⏳ 생성 중...")
        
        # 기본 톤/분량/스타일 가져오기 (글쓰기 환경설정에서)
        tone = "친근한 이웃 (해요체)"
        length = "보통 (1,500자)"
        style_options = {}
        if self.writing_settings_tab:
            tone = self.writing_settings_tab.get_default_tone()
            length = self.writing_settings_tab.get_default_length()
            style_options = self.writing_settings_tab.get_output_style_settings()

        targets = []
        selected_target = self.target_group.checkedButton()
        if selected_target:
            targets = [selected_target.text().strip()]
            
        questions = [self.list_questions.item(i).text() 
                     for i in range(self.list_questions.count()) 
                     if self.list_questions.item(i).checkState() == Qt.Checked]

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
            "style_options": style_options,  # 출력 스타일 설정 추가
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
        
        # 썸네일 이미지 (글쓰기 환경설정의 자동 업로드 설정 확인)
        thumbnail = None
        thumbnail_path = None
        if self.writing_settings_tab and self.writing_settings_tab.is_auto_upload_thumbnail_enabled():
            if self.thumbnail_image:
                thumbnail = self.thumbnail_image
                # 썸네일 파일 저장 경로
                thumbnail_path = self._save_thumbnail_to_file()
        
        data = {
            "action": "publish_only",
            "title": title,
            "content": content,
            "blocks": self.generated_blocks,  # 구조화된 블록 데이터 추가
            "category": category,
            "thumbnail_path": thumbnail_path,
            "images": {"thumbnail": thumbnail, "illustrations": []}
        }
        self.start_signal.emit(data)

    def on_thumbnail_finished(self, images: list):
        """썸네일 생성 완료"""
        remaining = self.max_regenerate_count - self.thumbnail_regenerate_count
        if remaining > 0:
            self.btn_regenerate_thumbnail.setEnabled(True)
        
        if images:
            self.thumbnail_image = images[0]
            
            try:
                img_data = base64.b64decode(self.thumbnail_image)
                qimg = QImage.fromData(img_data)
                pixmap = QPixmap.fromImage(qimg)
                scaled = pixmap.scaled(200, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.thumbnail_preview.setPixmap(scaled)
            except:
                self.thumbnail_preview.setText("로드 실패")
            
            self.log_signal.emit("✅ 썸네일 이미지 생성 완료!")

    def _save_thumbnail_to_file(self) -> str:
        """썸네일 이미지를 파일로 저장하고 경로 반환"""
        if not self.thumbnail_image:
            return ""
        
        try:
            # 저장 경로 가져오기
            if self.writing_settings_tab:
                save_dir = self.writing_settings_tab.get_thumbnail_path()
            else:
                save_dir = os.path.join(os.path.expanduser("~"), "Desktop", "blog_thumbnails")
            
            # 폴더 생성
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            
            # 파일명 생성 (타임스탬프)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"thumbnail_{timestamp}.png"
            filepath = os.path.join(save_dir, filename)
            
            # base64 디코딩 후 저장
            img_data = base64.b64decode(self.thumbnail_image)
            with open(filepath, 'wb') as f:
                f.write(img_data)
            
            self.log_signal.emit(f"📁 썸네일 저장: {filepath}")
            return filepath
            
        except Exception as e:
            self.log_signal.emit(f"⚠️ 썸네일 저장 실패: {str(e)}")
            return ""

    def on_thumbnail_error(self, error_msg: str):
        """썸네일 생성 에러"""
        remaining = self.max_regenerate_count - self.thumbnail_regenerate_count
        if remaining > 0:
            self.btn_regenerate_thumbnail.setEnabled(True)
        
        self.thumbnail_preview.setText("생성 실패")
        self.log_signal.emit(f"❌ {error_msg}")

    def update_result_view(self, result_data):
        """결과 뷰어 업데이트 - TEXT 표시 + blocks 저장"""
        title = result_data.get("title", "제목 없음")
        
        # blocks 저장 (Selenium 에디터 조작용)
        self.generated_blocks = result_data.get("blocks", [])
        
        # content_text 우선, 없으면 content 사용
        content = result_data.get("content_text", "") or result_data.get("content", "")
        
        # JSON 형태로 온 경우 정리
        if content and content.strip().startswith("{"):
            try:
                import json
                parsed = json.loads(content)
                content = parsed.get("content_text", "") or parsed.get("content", content)
                # blocks도 추출
                if "blocks" in parsed and not self.generated_blocks:
                    self.generated_blocks = parsed.get("blocks", [])
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
        self.btn_generate.setText("✅ 생성 완료!")
        
        # 발행 버튼 활성화
        self.btn_publish.setEnabled(True)
        
        # 로그에 blocks 정보 표시
        block_count = len(self.generated_blocks) if self.generated_blocks else 0
        self.log_signal.emit(f"✨ 글 생성 완료! ({block_count}개 블록) 확인 후 발행할 수 있습니다.")

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
        self.btn_generate.setText("📝 원고 생성")
