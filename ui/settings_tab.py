"""
환경 설정 탭 - 네이버 계정, 고정 인사말/맺음말, 명함 이미지
v3.5.0: 글쓰기 관련 설정을 별도 탭으로 분리 (간소화)
"""
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout, 
    QLineEdit, QTextEdit, QPushButton, QMessageBox,
    QHBoxLayout, QLabel, QFileDialog, QScrollArea
)
from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QPixmap


class SettingsTab(QWidget):
    """환경 설정 탭 - 기본 계정 및 인사말 설정"""
    
    settings_changed = Signal()
    
    def __init__(self):
        super().__init__()
        self.settings = QSettings("MySoft", "NaverBlogBot")
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        
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
        
        # ========== 2. 고정 인사말 ==========
        group_intro = QGroupBox("👋 고정 인사말 (글 시작 부분)")
        intro_layout = QVBoxLayout()
        
        intro_desc = QLabel("모든 글의 첫 부분에 자동으로 삽입됩니다.")
        intro_desc.setStyleSheet("color: #666; font-size: 11px;")
        intro_layout.addWidget(intro_desc)
        
        self.input_intro = QTextEdit()
        self.input_intro.setMaximumHeight(100)
        self.input_intro.setPlaceholderText("예: 안녕하세요, 자동차 전문 상담사 OOO입니다!")
        intro_layout.addWidget(self.input_intro)
        
        group_intro.setLayout(intro_layout)
        layout.addWidget(group_intro)
        
        # ========== 3. 고정 맺음말 + 명함 이미지 ==========
        group_outro = QGroupBox("🤝 고정 맺음말 (글 마무리 부분)")
        outro_layout = QVBoxLayout()
        
        outro_desc = QLabel("모든 글의 마지막 부분에 자동으로 삽입됩니다.")
        outro_desc.setStyleSheet("color: #666; font-size: 11px;")
        outro_layout.addWidget(outro_desc)
        
        self.input_outro = QTextEdit()
        self.input_outro.setMaximumHeight(100)
        self.input_outro.setPlaceholderText("예: 차량 구매 상담은 언제든 연락주세요! 감사합니다")
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
        
        # ========== 저장 버튼 ==========
        self.btn_save = QPushButton("💾 설정 저장")
        self.btn_save.clicked.connect(self.save_settings)
        self.btn_save.setStyleSheet("""
            background-color: #03C75A; 
            color: white; 
            padding: 12px; 
            font-weight: bold;
            font-size: 14px;
        """)
        layout.addWidget(self.btn_save)
        
        # 안내 문구
        notice = QLabel("💡 글쓰기 관련 설정(카테고리, 스타일, 썸네일 등)은 [글쓰기 환경설정] 탭에서 관리됩니다.")
        notice.setStyleSheet("color: #888; font-size: 11px; padding: 10px; background-color: #f8f8f8; border-radius: 4px;")
        notice.setWordWrap(True)
        layout.addWidget(notice)
        
        layout.addStretch()
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)
        
        # 저장된 설정 로드
        self.load_settings()
    
    def load_settings(self):
        """저장된 설정 로드"""
        self.input_id.setText(self.settings.value("id", ""))
        self.input_pw.setText(self.settings.value("pw", ""))
        self.input_intro.setText(self.settings.value("intro", ""))
        self.input_outro.setText(self.settings.value("outro", ""))
        
        # 명함 이미지 로드
        outro_image = self.settings.value("outro_image", "")
        if outro_image and os.path.exists(outro_image):
            self.load_image_preview(outro_image)
            self.lbl_image_path.setText(f"📎 {os.path.basename(outro_image)}")
        else:
            self.lbl_image_preview.setText("이미지 없음")
    
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
        """설정 저장"""
        self.settings.setValue("id", self.input_id.text())
        self.settings.setValue("pw", self.input_pw.text())
        self.settings.setValue("intro", self.input_intro.toPlainText())
        self.settings.setValue("outro", self.input_outro.toPlainText())
        
        self.settings_changed.emit()
        QMessageBox.information(self, "완료", "설정이 저장되었습니다.")
    
    # ========== 외부 호출용 Getter ==========
    def get_intro(self) -> str:
        """인사말 반환"""
        return self.input_intro.toPlainText()
    
    def get_outro(self) -> str:
        """맺음말 반환"""
        return self.input_outro.toPlainText()
    
    def get_outro_image_path(self) -> str:
        """명함 이미지 경로 반환"""
        return self.settings.value("outro_image", "")
    
    def get_naver_id(self) -> str:
        """네이버 ID 반환"""
        return self.input_id.text()
    
    def get_naver_pw(self) -> str:
        """네이버 PW 반환"""
        return self.input_pw.text()
