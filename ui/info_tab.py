"""
정보성 글쓰기 탭 - 블로그 포스팅 자동 생성 기능
UX 개선: 드롭다운/직접입력 상호배타, AI 추천 상태표시, 이미지 생성 옵션
"""
import requests
import markdown
import re
import base64
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, 
                               QComboBox, QLineEdit, QPushButton, QRadioButton, 
                               QButtonGroup, QLabel, QMessageBox, QScrollArea, 
                               QListWidget, QListWidgetItem, QTextEdit, QTabWidget, QCheckBox,
                               QAbstractItemView, QFrame, QSpinBox)
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
    
    def __init__(self, topic: str, count: int, auth_token: str):
        super().__init__()
        self.topic = topic
        self.count = count
        self.auth_token = auth_token
    
    def run(self):
        try:
            results = []
            
            for i in range(self.count):
                self.progress.emit(i + 1, self.count)
                
                headers = {"Authorization": f"Bearer {self.auth_token}"}
                payload = {
                    "mode": "generate_image",
                    "prompt": self.topic,
                    "style": "블로그 썸네일"
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
        self.image_worker = None
        self.generated_images = []  # base64 이미지 리스트
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

        # 4. 이미지 생성 (새로 추가)
        group_image = QGroupBox("4. 썸네일 이미지 생성 (선택)")
        group_image.setCheckable(True)
        group_image.setChecked(False)
        image_layout = QVBoxLayout()
        
        # 이미지 생성 옵션
        img_option_layout = QHBoxLayout()
        img_option_layout.addWidget(QLabel("생성할 이미지 수:"))
        self.spin_image_count = QSpinBox()
        self.spin_image_count.setRange(1, 3)
        self.spin_image_count.setValue(1)
        img_option_layout.addWidget(self.spin_image_count)
        img_option_layout.addStretch()
        
        self.btn_gen_images = QPushButton("🖼️ 이미지 생성")
        self.btn_gen_images.clicked.connect(self.generate_images)
        self.btn_gen_images.setStyleSheet("background-color: #9B59B6; color: white; padding: 8px;")
        img_option_layout.addWidget(self.btn_gen_images)
        image_layout.addLayout(img_option_layout)
        
        # 이미지 안내
        img_notice = QLabel("💡 주제에 맞는 블로그 썸네일 이미지를 AI가 생성합니다. (글씨 없는 이미지)")
        img_notice.setStyleSheet("color: #666; font-size: 11px;")
        image_layout.addWidget(img_notice)
        
        # 생성된 이미지 표시 영역
        self.image_preview_layout = QHBoxLayout()
        image_layout.addLayout(self.image_preview_layout)
        
        # 이미지 삽입 여부 체크박스들
        self.image_checkboxes = []
        self.image_checkbox_layout = QHBoxLayout()
        image_layout.addLayout(self.image_checkbox_layout)
        
        group_image.setLayout(image_layout)
        layout.addWidget(group_image)
        self.group_image = group_image

        # 5. 실행 버튼
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

        # 6. 결과 뷰어 (단순화 - 텍스트만)
        layout.addWidget(QLabel("📝 생성된 글 미리보기 (수정 후 발행 가능)"))
        self.view_result = QTextEdit()
        self.view_result.setMinimumHeight(350)
        self.view_result.setPlaceholderText("생성된 글이 여기에 표시됩니다. 직접 수정도 가능합니다.")
        layout.addWidget(self.view_result)

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
        """AI 이미지 생성"""
        topic = self.get_selected_topic()
        if not topic:
            QMessageBox.warning(self, "경고", "먼저 주제를 선택하거나 입력해주세요.")
            return
        
        if not self.auth_token:
            QMessageBox.warning(self, "인증 필요", "이미지 생성은 로그인이 필요합니다.")
            return
        
        count = self.spin_image_count.value()
        
        self.btn_gen_images.setEnabled(False)
        self.btn_gen_images.setText(f"⏳ 생성 중... (0/{count})")
        
        # 기존 이미지 클리어
        self.clear_image_previews()
        
        self.image_worker = ImageGenerateWorker(topic, count, self.auth_token)
        self.image_worker.progress.connect(self.on_image_progress)
        self.image_worker.finished.connect(self.on_images_finished)
        self.image_worker.error.connect(self.on_image_error)
        self.image_worker.start()
        
        self.log_signal.emit(f"🖼️ '{topic}' 관련 이미지 {count}장 생성 중...")

    def on_image_progress(self, current: int, total: int):
        """이미지 생성 진행률"""
        self.btn_gen_images.setText(f"⏳ 생성 중... ({current}/{total})")

    def on_images_finished(self, images: list):
        """이미지 생성 완료"""
        self.btn_gen_images.setEnabled(True)
        self.btn_gen_images.setText("🖼️ 이미지 생성")
        
        self.generated_images = images
        
        # 이미지 미리보기 및 체크박스 표시
        for i, img_base64 in enumerate(images):
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
            
            self.image_preview_layout.addWidget(preview)
            
            # 체크박스
            chk = QCheckBox(f"이미지 {i+1} 삽입")
            chk.setChecked(True)
            self.image_checkboxes.append(chk)
            self.image_checkbox_layout.addWidget(chk)
        
        self.log_signal.emit(f"✅ {len(images)}개의 이미지가 생성되었습니다. 삽입할 이미지를 선택하세요.")

    def on_image_error(self, error_msg: str):
        """이미지 생성 에러"""
        self.btn_gen_images.setEnabled(True)
        self.btn_gen_images.setText("🖼️ 이미지 생성")
        self.log_signal.emit(f"❌ {error_msg}")

    def clear_image_previews(self):
        """이미지 미리보기 클리어"""
        while self.image_preview_layout.count():
            item = self.image_preview_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        while self.image_checkbox_layout.count():
            item = self.image_checkbox_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.image_checkboxes = []
        self.generated_images = []

    def get_selected_images(self) -> list:
        """선택된 이미지 base64 리스트 반환"""
        selected = []
        for i, chk in enumerate(self.image_checkboxes):
            if chk.isChecked() and i < len(self.generated_images):
                selected.append(self.generated_images[i])
        return selected

    def request_start(self, action="full"):
        """작업 시작 요청"""
        if action == "publish_only":
            current_content = self.view_result.toPlainText()
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
        selected_images = self.get_selected_images() if self.group_image.isChecked() else []

        data = {
            "action": action, "mode": "info", "topic": topic,
            "tone": self.combo_tone.currentText(), "length": self.combo_len.currentText(),
            "emoji_level": self.combo_emoji.currentText(), "targets": targets,
            "questions": questions, "summary": self.txt_summary.toPlainText(),
            "insight": self.txt_insight.toPlainText(),
            "images": selected_images  # base64 이미지 리스트
        }
        self.start_signal.emit(data)

    def update_result_view(self, result_data):
        """결과 뷰어 업데이트"""
        title = result_data.get("title", "제목 없음")
        content = result_data.get("content", "") or result_data.get("content_text", "")
        
        # 단순 텍스트로 표시
        result_text = f"제목: {title}\n\n{'=' * 50}\n\n{content}"
        self.view_result.setText(result_text)
        
        self.btn_publish_now.setEnabled(True)
        self.log_signal.emit("✨ 글 생성 완료! 내용을 확인하고 필요시 수정 후 발행하세요.")
