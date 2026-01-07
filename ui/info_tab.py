import requests
import markdown
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, 
                               QComboBox, QLineEdit, QPushButton, QRadioButton, 
                               QButtonGroup, QLabel, QMessageBox, QScrollArea, 
                               QListWidget, QListWidgetItem, QTextEdit, QTabWidget, QCheckBox,
                               QAbstractItemView)
from PySide6.QtCore import Qt, Signal, QThread

BACKEND_URL = "https://generate-blog-post-yahp6ia25q-du.a.run.app"

class AnalysisWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, topic):
        super().__init__()
        self.topic = topic

    def run(self):
        try:
            # 타임아웃 60초로 연장
            response = requests.post(BACKEND_URL, json={"mode": "analyze", "topic": self.topic}, timeout=60)
            if response.status_code == 200:
                self.finished.emit(response.json())
            else:
                # 에러 메시지 상세 출력
                self.error.emit(f"분석 실패 ({response.status_code}): {response.text}")
        except Exception as e:
            self.error.emit(f"통신 오류: {str(e)}")

class InfoTab(QWidget):
    start_signal = Signal(dict) 
    log_signal = Signal(str)

    def __init__(self):
        super().__init__()
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
        form_cat = QFormLayout()
        self.combo_cat = QComboBox()
        self.combo_cat.setEditable(True)
        self.combo_cat.addItems([
            "차량 관리 상식", "자동차 보험/사고처리", "리스/렌트/할부 금융", 
            "교통법규/범칙금", "자동차 여행 코스", "지역 맛집 탐방", 
            "전기차 라이프", "중고차 거래 팁", "신차 출고 대기/결함"
        ])
        form_cat.addRow("카테고리:", self.combo_cat)
        
        self.btn_recommend = QPushButton("✨ AI 추천 주제 받기")
        self.btn_recommend.clicked.connect(self.get_recommendations)
        self.btn_recommend.setStyleSheet("background-color: #5D5D5D; color: white; padding: 8px;")
        
        topic_layout.addLayout(form_cat)
        topic_layout.addWidget(self.btn_recommend)
        
        self.topic_area = QScrollArea()
        self.topic_area.setWidgetResizable(True)
        self.topic_area.setMinimumHeight(250) 
        self.topic_widget = QWidget()
        self.topic_group = QButtonGroup()
        self.topic_layout = QVBoxLayout(self.topic_widget)
        self.topic_layout.setAlignment(Qt.AlignTop)
        self.topic_area.setWidget(self.topic_widget)
        
        topic_layout.addWidget(QLabel("추천 주제 선택:"))
        topic_layout.addWidget(self.topic_area)
        
        self.manual_topic = QLineEdit()
        self.manual_topic.setPlaceholderText("또는 주제를 직접 입력하세요")
        topic_layout.addWidget(self.manual_topic)
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
        
        adv_layout.addWidget(QLabel("🎯 타겟 독자 (1개만 선택):"))
        self.list_target = QListWidget()
        self.list_target.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_target.setMinimumHeight(150)
        adv_layout.addWidget(self.list_target)
        
        adv_layout.addWidget(QLabel("❓ 예상 질문 (선택):"))
        self.list_questions = QListWidget()
        self.list_questions.setMinimumHeight(200)
        adv_layout.addWidget(self.list_questions)
        
        adv_layout.addWidget(QLabel("📌 핵심 정보 요약 (AI 자동 생성):"))
        self.txt_summary = QTextEdit()
        self.txt_summary.setMinimumHeight(150)
        adv_layout.addWidget(self.txt_summary)
        
        adv_layout.addWidget(QLabel("💡 나만의 인사이트 (직접 입력):"))
        self.txt_insight = QTextEdit()
        self.txt_insight.setMinimumHeight(150)
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
        self.txt_emphasis = QComboBox(); self.txt_emphasis.addItems(["*강조*", "**강조**", "「강조」", "“강조”"])
        self.txt_divider = QComboBox(); self.txt_divider.addItems(["===", "---", "(빈 줄만)"])
        self.txt_body_style = QComboBox(); self.txt_body_style.addItems(["기본 간격", "넓은 간격 (가독성 UP)"]) 
        form_text.addRow("소제목 기호:", self.txt_subhead); form_text.addRow("강조 표현:", self.txt_emphasis); form_text.addRow("구분선:", self.txt_divider); form_text.addRow("문단 간격:", self.txt_body_style)
        tab_text.setLayout(form_text)
        self.style_tabs.addTab(tab_text, "Text 설정")

        tab_md = QWidget(); form_md = QFormLayout()
        self.md_heading = QComboBox(); self.md_heading.addItems(["H2 (##)", "H3 (###)", "H4 (####)"])
        self.md_list = QComboBox(); self.md_list.addItems(["- 리스트", "* 리스트", "1. 리스트"])
        self.md_qa = QComboBox(); self.md_qa.addItems(["인용구 (>)", "굵게 (**Q**)", "일반 텍스트"])
        self.md_body_style = QComboBox(); self.md_body_style.addItems(["줄글(서술형) 위주", "개조식(리스트) 위주"])
        form_md.addRow("시작 헤딩:", self.md_heading); form_md.addRow("목록 기호:", self.md_list); form_md.addRow("Q&A 표현:", self.md_qa); form_md.addRow("서술 방식:", self.md_body_style)
        tab_md.setLayout(form_md)
        self.style_tabs.addTab(tab_md, "Markdown 설정")

        tab_html = QWidget(); form_html = QFormLayout()
        self.html_title_style = QComboBox(); self.html_title_style.addItems(["기본 (심플)", "밑줄 (Border Bottom)", "배경색 (Box)"])
        self.html_qa_style = QComboBox(); self.html_qa_style.addItems(["기본", "박스형 (Border)", "아코디언 (Details)"])
        self.html_color = QComboBox(); self.html_color.addItems(["네이버 그린", "모던 블랙", "트러스트 블루", "웜 오렌지"])
        self.html_font_size = QComboBox(); self.html_font_size.addItems(["기본 (16px)", "조금 크게 (18px)", "시원하게 (20px)"])
        self.html_highlight = QComboBox(); self.html_highlight.addItems(["없음", "중요 문단 회색 박스", "중요 문단 컬러 박스"])
        form_html.addRow("제목 스타일:", self.html_title_style); form_html.addRow("Q&A 스타일:", self.html_qa_style); form_html.addRow("테마 컬러:", self.html_color); form_html.addRow("본문 폰트:", self.html_font_size); form_html.addRow("강조 박스:", self.html_highlight)
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

    def get_selected_topic(self):
        if self.manual_topic.text().strip(): return self.manual_topic.text().strip()
        selected_btn = self.topic_group.checkedButton()
        if selected_btn: return selected_btn.text()
        return None

    def get_recommendations(self):
        category = self.combo_cat.currentText()
        self.log_signal.emit(f"🤖 '{category}' 관련 주제를 생각 중입니다...")
        for i in reversed(range(self.topic_layout.count())): self.topic_layout.itemAt(i).widget().setParent(None)
        
        try:
            # 타임아웃 60초로 연장
            response = requests.post(BACKEND_URL, json={"mode": "recommend", "category": category}, timeout=60)
            if response.status_code == 200:
                result = response.json()
                topics = result.get("topics", [])
                for t in topics:
                    rb = QRadioButton(t)
                    rb.setStyleSheet("font-size: 14px; padding: 5px;")
                    self.topic_layout.addWidget(rb)
                    self.topic_group.addButton(rb)
                self.log_signal.emit(f"✅ {len(topics)}개의 주제가 추천되었습니다.")
            else:
                # 상세 에러 메시지 출력
                self.log_signal.emit(f"❌ 추천 실패 ({response.status_code}): {response.text}")
        except Exception as e:
            self.log_signal.emit(f"❌ 통신 오류: {str(e)}")

    def run_analysis(self):
        topic = self.get_selected_topic()
        if not topic:
            QMessageBox.warning(self, "경고", "먼저 주제를 선택하거나 입력해주세요.")
            return
        self.log_signal.emit(f"🔍 '{topic}' 주제를 심층 분석 중입니다...")
        self.btn_analyze.setEnabled(False)
        self.worker = AnalysisWorker(topic)
        self.worker.finished.connect(self.on_analysis_finished)
        self.worker.error.connect(lambda e: self.log_signal.emit(f"❌ {e}"))
        self.worker.start()

    # ... (나머지 코드는 동일) ...
    def on_analysis_finished(self, data):
        self.btn_analyze.setEnabled(True)
        self.list_target.clear()
        self.list_questions.clear()
        targets = data.get("targets", [])
        questions = data.get("questions", [])
        key_points = data.get("key_points", [])
        for t in targets:
            self.list_target.addItem(t) 
        for q in questions:
            item = QListWidgetItem(q)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.list_questions.addItem(item)
        summary_text = "\n".join([f"• {p}" for p in key_points])
        self.txt_summary.setText(summary_text)
        self.log_signal.emit("✅ 분석 완료! 타겟과 질문을 선택해주세요.")

    def request_start(self, action="full"):
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

        targets = [item.text() for item in self.list_target.selectedItems()]
        questions = [self.list_questions.item(i).text() for i in range(self.list_questions.count()) if self.list_questions.item(i).checkState() == Qt.Checked]

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
        title = result_data.get("title", "제목 없음")
        text_content = result_data.get("content_text", "")
        md_content = result_data.get("content_md", "")
        html_content = result_data.get("content_html", "")
        self.view_text.setText(f"제목: {title}\n\n{text_content}")
        self.view_md.setText(f"# {title}\n\n{md_content}")
        self.view_html.setText(html_content)
        self.btn_publish_now.setEnabled(True)
        self.log_signal.emit("✨ 3가지 스타일로 생성 완료! 탭을 눌러 비교해보세요.")
