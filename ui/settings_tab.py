from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QFormLayout, 
                               QLineEdit, QTextEdit, QPushButton, QMessageBox)
from PySide6.QtCore import QSettings

class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("MySoft", "NaverBlogBot")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        group = QGroupBox("계정 및 기본 설정")
        form = QFormLayout()
        
        self.input_id = QLineEdit()
        self.input_pw = QLineEdit()
        self.input_pw.setEchoMode(QLineEdit.Password)
        self.input_intro = QTextEdit(); self.input_intro.setMaximumHeight(60)
        self.input_outro = QTextEdit(); self.input_outro.setMaximumHeight(60)
        
        # Load
        self.input_id.setText(self.settings.value("id", ""))
        self.input_pw.setText(self.settings.value("pw", ""))
        self.input_intro.setText(self.settings.value("intro", ""))
        self.input_outro.setText(self.settings.value("outro", ""))
        
        form.addRow("네이버 ID:", self.input_id)
        form.addRow("네이버 PW:", self.input_pw)
        form.addRow("고정 인사말:", self.input_intro)
        form.addRow("고정 맺음말:", self.input_outro)
        
        group.setLayout(form)
        layout.addWidget(group)
        
        btn_save = QPushButton("설정 저장")
        btn_save.clicked.connect(self.save_settings)
        btn_save.setStyleSheet("padding: 10px; font-weight: bold;")
        layout.addWidget(btn_save)
        layout.addStretch()
        self.setLayout(layout)

    def save_settings(self):
        self.settings.setValue("id", self.input_id.text())
        self.settings.setValue("pw", self.input_pw.text())
        self.settings.setValue("intro", self.input_intro.toPlainText())
        self.settings.setValue("outro", self.input_outro.toPlainText())
        QMessageBox.information(self, "완료", "설정이 저장되었습니다.")
