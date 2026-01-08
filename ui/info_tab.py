"""
정보성 글쓰기 탭 - 블로그 포스팅 자동 생성 기능
UX 개선: 드롭다운/직접입력 상호배타, AI 추천 상태표시
"""
import requests
import markdown
import re
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, 
                               QComboBox, QLineEdit, QPushButton, QRadioButton, 
                               QButtonGroup, QLabel, QMessageBox, QScrollArea, 
                               QListWidget, QListWidgetItem, QTextEdit, QTabWidget, QCheckBox,
                               QAbstractItemView, QFrame)
from PySide6.QtCore import Qt, Signal, QThread

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


class InfoTab(QWidget):
    """정보성 글쓰기 탭"""
    start_signal = Signal(dict) 
    log_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.recommend_worker = None
        self.analysis_worker = None
        self.init_ui()

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
        self.topic_area.setMinimumHeight(200) 
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

        # 3. 세부 설정
        self.group_adv = QGroupBox("3. 세부 설정 (고도화)")
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
        
        # 타깃 독자 스크롤 영역
        target_scroll = QScrollArea()
        target_scroll.setWidgetResizable(True)
        target_scroll.setMinimumHeight(120)
        target_scroll.setMaximumHeight(150)
        target_scroll.setWidget(self.target_widget)
        adv_layout.addWidget(target_scroll)
        
        adv_layout.addWidget(QLabel("❓ 예상 질문 (선택):"))
        self.list_questions = QListWidget()
        self.list_questions.setMinimumHeight(150)
        adv_layout.addWidget(self.list_questions)
        
        adv_layout.addWidget(QLabel("📌 핵심 정보 요약 (AI 자동 생성):"))
        self.txt_summary = QTextEdit()
        self.txt_summary.setMinimumHeight(100)
        adv_layout.addWidget(self.txt_summary)
        
        adv_layout.addWidget(QLabel("💡 나만의 인사이트 (직접 입력):"))
        self.txt_insight = QTextEdit()
        self.txt_insight.setMinimumHeight(100)
        adv_layout.addWidget(self.txt_insight)
        
        self.group_adv.setLayout(adv_layout)
        layout.addWidget(self.group_adv)

        # 4. 출력 스타일 설정
        group_style = QGroupBox("4. 출력 스타일 설정 (Format Options)")
        group_style.setCheckable(True)
        group_style.setChecked(True)
        style_layout = QVBoxLayout()
        self.style_tabs = QTabWidget()

        tab_text = QWidget(); form_text = QFormLayout()
        self.txt_subhead = QComboBox(); self.txt_subhead.addItems(["▶ 소제목", "# 소제목", "[소제목]", "1. 소제목"])
        self.txt_emphasis = QComboBox(); self.txt_emphasis.addItems(["*강조*", "**강조**", "「강조」", '"강조"'])
        self.txt_divider = QComboBox(); self.txt_divider.addItems(["===", "---", "(빈 줄만)"])
        self.txt_body_style = QComboBox(); self.txt_body_style.addItems(["기본 간격", "넓은 간격 (가독성 UP)"]) 
        form_text.addRow("소제목 기호:", self.txt_subhead)
        form_text.addRow("강조 표현:", self.txt_emphasis)
        form_text.addRow("구분선:", self.txt_divider)
        form_text.addRow("문단 간격:", self.txt_body_style)
        tab_text.setLayout(form_text)
        self.style_tabs.addTab(tab_text, "Text 설정")

        tab_md = QWidget(); form_md = QFormLayout()
        self.md_heading = QComboBox(); self.md_heading.addItems(["H2 (##)", "H3 (###)", "H4 (####)"])
        self.md_list = QComboBox(); self.md_list.addItems(["- 리스트", "* 리스트", "1. 리스트"])
        self.md_qa = QComboBox(); self.md_qa.addItems(["인용구 (>)", "굵게 (**Q**)", "일반 텍스트"])
        self.md_body_style = QComboBox(); self.md_body_style.addItems(["줄글(서술형) 위주", "개조식(리스트) 위주"])
        form_md.addRow("시작 헤딩:", self.md_heading)
        form_md.addRow("목록 기호:", self.md_list)
        form_md.addRow("Q&A 표현:", self.md_qa)
        form_md.addRow("서술 방식:", self.md_body_style)
        tab_md.setLayout(form_md)
        self.style_tabs.addTab(tab_md, "Markdown 설정")

        tab_html = QWidget(); form_html = QFormLayout()
        self.html_title_style = QComboBox(); self.html_title_style.addItems(["기본 (심플)", "밑줄 (Border Bottom)", "배경색 (Box)"])
        self.html_qa_style = QComboBox(); self.html_qa_style.addItems(["기본", "박스형 (Border)", "아코디언 (Details)"])
        self.html_color = QComboBox(); self.html_color.addItems(["네이버 그린", "모던 블랙", "트러스트 블루", "웜 오렌지"])
        self.html_font_size = QComboBox(); self.html_font_size.addItems(["기본 (16px)", "조금 크게 (18px)", "시원하게 (20px)"])
        self.html_highlight = QComboBox(); self.html_highlight.addItems(["없음", "중요 문단 회색 박스", "중요 문단 컬러 박스"])
        form_html.addRow("제목 스타일:", self.html_title_style)
        form_html.addRow("Q&A 스타일:", self.html_qa_style)
        form_html.addRow("테마 컬러:", self.html_color)
        form_html.addRow("본문 폰트:", self.html_font_size)
        form_html.addRow("강조 박스:", self.html_highlight)
        tab_html.setLayout(form_html)
        self.style_tabs.addTab(tab_html, "HTML 설정")

        style_layout.addWidget(self.style_tabs)
        group_style.setLayout(style_layout)
        layout.addWidget(group_style)

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

        # 6. 결과 뷰어
        layout.addWidget(QLabel("📝 생성된 글 미리보기 (여기서 수정 후 발행 가능)"))
        self.result_tabs = QTabWidget()
        self.result_tabs.setMinimumHeight(400) 
        self.view_text = QTextEdit(); self.view_text.setPlaceholderText("Text 버전 결과")
        self.view_md = QTextEdit(); self.view_md.setReadOnly(True); self.view_md.setPlaceholderText("Markdown 버전 결과")
        self.view_html = QTextEdit(); self.view_html.setReadOnly(True); self.view_html.setPlaceholderText("HTML 버전 결과")
        self.result_tabs.addTab(self.view_text, "Text (수정 가능)")
        self.result_tabs.addTab(self.view_md, "Markdown")
        self.result_tabs.addTab(self.view_html, "HTML")
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
        
        # 카테고리 관련 컨트롤 활성화/비활성화
        self.combo_cat.setEnabled(use_category)
        self.btn_recommend.setEnabled(use_category)
        self.topic_area.setEnabled(use_category)
        
        # 직접 입력 활성화/비활성화
        self.manual_topic.setEnabled(not use_category)
        
        # 시각적 피드백
        if use_category:
            self.category_frame.setStyleSheet("")
            self.manual_frame.setStyleSheet("color: #999;")
        else:
            self.category_frame.setStyleSheet("color: #999;")
            self.manual_frame.setStyleSheet("")

    def get_selected_topic(self):
        """선택된 주제 반환"""
        # 직접 입력 모드인 경우
        if self.radio_use_manual.isChecked():
            return self.manual_topic.text().strip()
        
        # 카테고리 추천 모드인 경우
        selected_btn = self.topic_group.checkedButton()
        if selected_btn:
            return selected_btn.text()
        return None

    def get_recommendations(self):
        """AI 추천 주제 받기"""
        category = self.combo_cat.currentText()
        self.log_signal.emit(f"🤖 '{category}' 관련 주제를 생각 중입니다...")
        
        # 버튼 상태 변경 - 생성 중 표시
        self.btn_recommend.setEnabled(False)
        self.btn_recommend.setText("⏳ 주제 생성 중...")
        self.btn_recommend.setStyleSheet("background-color: #888; color: white; padding: 8px;")
        
        # 기존 추천 주제 삭제
        for i in reversed(range(self.topic_layout_inner.count())): 
            widget = self.topic_layout_inner.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        # 워커 스레드로 API 호출
        self.recommend_worker = RecommendWorker(category)
        self.recommend_worker.finished.connect(self.on_recommend_finished)
        self.recommend_worker.error.connect(self.on_recommend_error)
        self.recommend_worker.start()

    def on_recommend_finished(self, topics: list):
        """추천 완료 처리"""
        # 버튼 상태 복원 - 생성 완료 표시
        self.btn_recommend.setEnabled(True)
        self.btn_recommend.setText("✅ 주제 생성 완료! (다시 받기)")
        self.btn_recommend.setStyleSheet("background-color: #27AE60; color: white; padding: 8px;")
        
        # 추천 주제 라디오 버튼으로 표시
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
        
        # 기존 타깃 라디오버튼 삭제
        for i in reversed(range(self.target_layout.count())):
            widget = self.target_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        self.list_questions.clear()
        
        targets = data.get("targets", [])
        questions = data.get("questions", [])
        key_points = data.get("key_points", [])
        
        # 타깃 독자 라디오버튼 추가 (왼쪽 배치)
        for t in targets:
            rb = QRadioButton(f"  {t}")  # 왼쪽 여백
            rb.setStyleSheet("font-size: 13px; padding: 3px 5px;")
            self.target_layout.addWidget(rb)
            self.target_group.addButton(rb)
            
        # 첫 번째 타깃 기본 선택
        if self.target_group.buttons():
            self.target_group.buttons()[0].setChecked(True)
            
        # 예상 질문 체크박스 리스트
        for q in questions:
            item = QListWidgetItem(q)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.list_questions.addItem(item)
            
        # 핵심 정보 요약
        summary_text = "\n".join([f"• {p}" for p in key_points])
        self.txt_summary.setText(summary_text)
        
        self.log_signal.emit("✅ 분석 완료! 타깃과 질문을 선택해주세요.")

    def on_analysis_error(self, error_msg: str):
        """분석 에러 처리"""
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText("🔍 주제 분석하기 (타겟/질문 추출)")
        self.log_signal.emit(f"❌ {error_msg}")

    def request_start(self, action="full"):
        """작업 시작 요청"""
        if action == "publish_only":
            current_idx = self.result_tabs.currentIndex()
            current_widget = self.result_tabs.widget(current_idx)
            current_content = current_widget.toPlainText()
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

        # 타깃 독자 선택 (라디오버튼에서)
        targets = []
        selected_target = self.target_group.checkedButton()
        if selected_target:
            targets = [selected_target.text().strip()]
            
        questions = [self.list_questions.item(i).text() 
                     for i in range(self.list_questions.count()) 
                     if self.list_questions.item(i).checkState() == Qt.Checked]

        style_options = {
            "text_subhead": self.txt_subhead.currentText(),
            "text_emphasis": self.txt_emphasis.currentText(),
            "text_divider": self.txt_divider.currentText(),
            "text_body": self.txt_body_style.currentText(),
            "md_heading": self.md_heading.currentText(),
            "md_qa": self.md_qa.currentText(),
            "md_body": self.md_body_style.currentText(),
            "html_title": self.html_title_style.currentText(),
            "html_qa": self.html_qa_style.currentText(),
            "html_color": self.html_color.currentText(),
            "html_font": self.html_font_size.currentText(),
            "html_box": self.html_highlight.currentText()
        }

        data = {
            "action": action, "mode": "info", "topic": topic,
            "tone": self.combo_tone.currentText(), "length": self.combo_len.currentText(),
            "emoji_level": self.combo_emoji.currentText(), "targets": targets,
            "questions": questions, "summary": self.txt_summary.toPlainText(),
            "insight": self.txt_insight.toPlainText(), "style_options": style_options
        }
        self.start_signal.emit(data)

    def update_result_view(self, result_data):
        """결과 뷰어 업데이트 - 개선된 포맷팅"""
        title = result_data.get("title", "제목 없음")
        
        # API 응답 구조에 맞게 처리 (content 또는 content_text 둘 다 지원)
        content = result_data.get("content", "") or result_data.get("content_text", "")
        
        # Text 버전 - 가독성 개선
        text_content = self._format_text_content(title, content)
        self.view_text.setText(text_content)
        
        # Markdown 버전 - 구조화된 포맷
        md_content = self._format_markdown_content(title, content)
        self.view_md.setText(md_content)
        
        # HTML 버전 - 스타일링 적용
        html_content = self._format_html_content(title, content)
        self.view_html.setText(html_content)
        
        self.btn_publish_now.setEnabled(True)
        self.log_signal.emit("✨ 글 생성 완료! 탭을 눌러 확인하세요.")

    def _format_text_content(self, title: str, content: str) -> str:
        """텍스트 포맷팅 - 가독성 개선"""
        lines = []
        lines.append(f"제목: {title}")
        lines.append("")
        lines.append("=" * 50)
        lines.append("")
        
        # 본문 처리 - 문단 구분 강화
        paragraphs = content.split('\n\n')
        for para in paragraphs:
            if para.strip():
                # 소제목 스타일 적용
                if para.startswith('##') or para.startswith('▶'):
                    lines.append("")
                    lines.append(para.strip())
                    lines.append("-" * 30)
                else:
                    lines.append(para.strip())
                lines.append("")
        
        return '\n'.join(lines)

    def _format_markdown_content(self, title: str, content: str) -> str:
        """마크다운 포맷팅 - 구조화"""
        lines = []
        lines.append(f"# {title}")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # 본문에서 섹션 구분 강화
        paragraphs = content.split('\n')
        for para in paragraphs:
            para = para.strip()
            if not para:
                lines.append("")
                continue
                
            # 이미 마크다운 헤딩이면 그대로
            if para.startswith('#'):
                lines.append(para)
            # 소제목 패턴 감지 (▶, [, 숫자.)
            elif para.startswith('▶') or para.startswith('[') or (len(para) > 2 and para[0].isdigit() and para[1] == '.'):
                lines.append(f"\n## {para}")
            # 중요 키워드 강조
            elif '**' in para or '핵심' in para or '중요' in para or '포인트' in para:
                lines.append(f"**{para}**")
            else:
                lines.append(para)
            
        return '\n'.join(lines)

    def _format_html_content(self, title: str, content: str) -> str:
        """HTML 포맷팅 - 스타일링 적용"""
        # 색상 테마 선택
        color_map = {
            "네이버 그린": "#03C75A",
            "모던 블랙": "#333333",
            "트러스트 블루": "#4A90E2",
            "웜 오렌지": "#E67E22"
        }
        theme_color = color_map.get(self.html_color.currentText(), "#03C75A")
        
        # 폰트 크기
        font_map = {
            "기본 (16px)": "16px",
            "조금 크게 (18px)": "18px",
            "시원하게 (20px)": "20px"
        }
        font_size = font_map.get(self.html_font_size.currentText(), "16px")
        
        # 제목 스타일
        title_style_map = {
            "기본 (심플)": f"font-size: 24px; font-weight: bold; color: {theme_color};",
            "밑줄 (Border Bottom)": f"font-size: 24px; font-weight: bold; color: {theme_color}; border-bottom: 3px solid {theme_color}; padding-bottom: 10px;",
            "배경색 (Box)": f"font-size: 24px; font-weight: bold; color: white; background-color: {theme_color}; padding: 15px; border-radius: 8px;"
        }
        title_style = title_style_map.get(self.html_title_style.currentText(), title_style_map["기본 (심플)"])
        
        # HTML 생성
        html_parts = []
        html_parts.append(f'''<div style="font-family: 'Noto Sans KR', sans-serif; line-height: 1.8; font-size: {font_size};">''')
        html_parts.append(f'<h1 style="{title_style}">{title}</h1>')
        html_parts.append('<hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">')
        
        # 본문 처리
        paragraphs = content.split('\n')
        for para in paragraphs:
            para = para.strip()
            if not para:
                html_parts.append('<br>')
                continue
            
            # 소제목 감지 및 스타일링
            if para.startswith('##'):
                para = para.replace('##', '').strip()
                html_parts.append(f'<h2 style="font-size: 20px; color: {theme_color}; margin-top: 25px; border-left: 4px solid {theme_color}; padding-left: 12px;">{para}</h2>')
            elif para.startswith('▶') or para.startswith('['):
                html_parts.append(f'<h3 style="font-size: 18px; color: {theme_color}; margin-top: 20px;">{para}</h3>')
            # 중요 포인트 강조
            elif '**' in para:
                para = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color: ' + theme_color + r';">\1</strong>', para)
                html_parts.append(f'<p style="margin: 10px 0;">{para}</p>')
            # 리스트 아이템
            elif para.startswith('-') or para.startswith('•'):
                html_parts.append(f'<li style="margin: 5px 0 5px 20px;">{para[1:].strip()}</li>')
            # 해시태그
            elif para.startswith('#') and not para.startswith('##'):
                html_parts.append(f'<p style="color: #1DA1F2; margin-top: 20px;">{para}</p>')
            else:
                html_parts.append(f'<p style="margin: 12px 0; text-align: justify;">{para}</p>')
        
        html_parts.append('</div>')
        
        return '\n'.join(html_parts)
