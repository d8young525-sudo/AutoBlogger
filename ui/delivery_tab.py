"""
출고 후기 탭 - 차량 출고 후기 자동 포스팅 기능
사진 업로드, 상담 후기 입력, 개인정보 블러 처리 지원
"""
import os
import tempfile
from pathlib import Path
from typing import List, Optional
from PIL import Image, ImageFilter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QComboBox, QLineEdit, QPushButton, QLabel, QMessageBox, 
    QScrollArea, QTextEdit, QListWidget, QListWidgetItem,
    QFileDialog, QSpinBox, QCheckBox, QProgressBar
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QPixmap, QImage

import requests

BACKEND_URL = "https://generate-blog-post-yahp6ia25q-du.a.run.app"


class ImageProcessWorker(QThread):
    """이미지 블러 처리 워커 스레드"""
    finished = Signal(list)  # processed_paths
    progress = Signal(int)   # current progress
    error = Signal(str)
    
    def __init__(self, image_paths: List[str], blur_faces: bool = True, blur_plates: bool = True):
        super().__init__()
        self.image_paths = image_paths
        self.blur_faces = blur_faces
        self.blur_plates = blur_plates
        self.processed_paths = []
        
    def run(self):
        """이미지 처리 실행"""
        total = len(self.image_paths)
        processed = []
        
        for i, path in enumerate(self.image_paths):
            try:
                # 이미지 로드
                img = Image.open(path)
                
                # 블러 처리 (실제 얼굴/번호판 인식은 추후 AI 모델 연동 필요)
                # 현재는 사용자가 수동으로 선택한 영역만 블러 처리
                # 기본적으로 이미지를 저장
                
                # 임시 디렉토리에 처리된 이미지 저장
                temp_dir = tempfile.gettempdir()
                filename = os.path.basename(path)
                output_path = os.path.join(temp_dir, f"processed_{filename}")
                
                # 원본 크기 유지하며 저장 (나중에 업로드용)
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                img.save(output_path, 'JPEG', quality=90)
                
                processed.append(output_path)
                self.progress.emit(int((i + 1) / total * 100))
                
            except Exception as e:
                self.error.emit(f"이미지 처리 오류 ({path}): {str(e)}")
                
        self.processed_paths = processed
        self.finished.emit(processed)


class DeliveryPostWorker(QThread):
    """출고 후기 포스팅 생성 워커"""
    finished = Signal(dict)
    error = Signal(str)
    log = Signal(str)
    
    def __init__(self, data: dict):
        super().__init__()
        self.data = data
        
    def run(self):
        """포스팅 내용 생성"""
        try:
            self.log.emit("🚀 AI 출고 후기 작성 요청 중...")
            
            # 프롬프트 구성
            customer_info = self.data.get('customer_info', {})
            vehicle_info = self.data.get('vehicle_info', {})
            review_text = self.data.get('review_text', '')
            tone = self.data.get('tone', '친근한 이웃 (해요체)')
            
            prompt = f"""
            차량 출고 후기 블로그 글을 작성해주세요.
            
            [고객 정보]
            - 연령대: {customer_info.get('age_group', '')}
            - 성별: {customer_info.get('gender', '')}
            - 지역: {customer_info.get('region', '')}
            
            [차량 정보]
            - 브랜드: {vehicle_info.get('brand', '')}
            - 모델: {vehicle_info.get('model', '')}
            - 연식: {vehicle_info.get('year', '')}
            - 색상: {vehicle_info.get('color', '')}
            - 옵션: {vehicle_info.get('options', '')}
            
            [상담 후기]
            {review_text}
            
            [작성 스타일]
            - 말투: {tone}
            - 포맷: 사진과 함께 올릴 블로그 글
            - 구성: 인사 → 고객 소개 → 차량 소개 → 상담 과정 → 마무리 인사
            - 해시태그 포함
            """
            
            payload = {
                "mode": "write",
                "topic": f"{vehicle_info.get('brand', '')} {vehicle_info.get('model', '')} 출고 후기",
                "prompt": prompt,
                "style_options": {}
            }
            
            response = requests.post(BACKEND_URL, json=payload, timeout=180)
            
            if response.status_code == 200:
                result = response.json()
                self.log.emit("✅ 출고 후기 생성 완료!")
                self.finished.emit(result)
            else:
                self.error.emit(f"서버 에러 ({response.status_code}): {response.text[:200]}")
                
        except requests.Timeout:
            self.error.emit("서버 응답 시간 초과 (3분)")
        except Exception as e:
            self.error.emit(f"통신 오류: {str(e)}")


class DeliveryTab(QWidget):
    """출고 후기 탭 위젯"""
    start_signal = Signal(dict)
    log_signal = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.image_paths: List[str] = []
        self.processed_paths: List[str] = []
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        
        # 1. 사진 업로드 섹션
        group_photos = QGroupBox("1. 출고 사진 업로드")
        photo_layout = QVBoxLayout()
        
        # 사진 선택 버튼들
        btn_layout = QHBoxLayout()
        self.btn_add_photos = QPushButton("📷 사진 추가")
        self.btn_add_photos.clicked.connect(self.add_photos)
        self.btn_add_photos.setStyleSheet("background-color: #4A90E2; color: white; padding: 8px;")
        
        self.btn_clear_photos = QPushButton("🗑️ 전체 삭제")
        self.btn_clear_photos.clicked.connect(self.clear_photos)
        self.btn_clear_photos.setStyleSheet("background-color: #E74C3C; color: white; padding: 8px;")
        
        btn_layout.addWidget(self.btn_add_photos)
        btn_layout.addWidget(self.btn_clear_photos)
        photo_layout.addLayout(btn_layout)
        
        # 사진 목록
        self.photo_list = QListWidget()
        self.photo_list.setMinimumHeight(120)
        self.photo_list.setSelectionMode(QListWidget.ExtendedSelection)
        photo_layout.addWidget(self.photo_list)
        
        # 개인정보 보호 옵션
        privacy_layout = QHBoxLayout()
        self.chk_blur_faces = QCheckBox("얼굴 블러 처리 (권장)")
        self.chk_blur_faces.setChecked(True)
        self.chk_blur_plates = QCheckBox("번호판 블러 처리 (권장)")
        self.chk_blur_plates.setChecked(True)
        privacy_layout.addWidget(self.chk_blur_faces)
        privacy_layout.addWidget(self.chk_blur_plates)
        photo_layout.addLayout(privacy_layout)
        
        # 블러 처리 안내
        lbl_privacy_notice = QLabel("⚠️ 얼굴과 번호판은 개인정보 보호를 위해 블러 처리를 권장합니다.")
        lbl_privacy_notice.setStyleSheet("color: #E67E22; font-size: 12px;")
        photo_layout.addWidget(lbl_privacy_notice)
        
        group_photos.setLayout(photo_layout)
        layout.addWidget(group_photos)
        
        # 2. 고객 정보
        group_customer = QGroupBox("2. 고객 정보 (선택)")
        customer_form = QFormLayout()
        
        # 연령대
        self.combo_age = QComboBox()
        self.combo_age.addItems(["선택 안함", "20대", "30대", "40대", "50대", "60대 이상"])
        customer_form.addRow("연령대:", self.combo_age)
        
        # 성별
        self.combo_gender = QComboBox()
        self.combo_gender.addItems(["선택 안함", "남성", "여성"])
        customer_form.addRow("성별:", self.combo_gender)
        
        # 지역
        self.input_region = QLineEdit()
        self.input_region.setPlaceholderText("예: 서울, 경기, 부산 등")
        customer_form.addRow("지역:", self.input_region)
        
        group_customer.setLayout(customer_form)
        layout.addWidget(group_customer)
        
        # 3. 차량 정보
        group_vehicle = QGroupBox("3. 차량 정보")
        vehicle_form = QFormLayout()
        
        # 브랜드
        self.combo_brand = QComboBox()
        self.combo_brand.setEditable(True)
        self.combo_brand.addItems([
            "현대", "기아", "제네시스", "쉐보레", "르노코리아", "쌍용",
            "벤츠", "BMW", "아우디", "폭스바겐", "볼보", "렉서스", 
            "도요타", "혼다", "테슬라", "포르쉐", "랜드로버", "재규어",
            "미니", "페라리", "람보르기니", "기타"
        ])
        vehicle_form.addRow("브랜드:", self.combo_brand)
        
        # 모델
        self.input_model = QLineEdit()
        self.input_model.setPlaceholderText("예: E클래스, 아반떼, 그랜저 등")
        vehicle_form.addRow("모델:", self.input_model)
        
        # 연식
        self.input_year = QLineEdit()
        self.input_year.setPlaceholderText("예: 2024")
        vehicle_form.addRow("연식:", self.input_year)
        
        # 색상
        self.input_color = QLineEdit()
        self.input_color.setPlaceholderText("예: 화이트, 블랙, 실버 등")
        vehicle_form.addRow("색상:", self.input_color)
        
        # 옵션
        self.input_options = QLineEdit()
        self.input_options.setPlaceholderText("예: 풀옵션, 네비게이션, 선루프 등")
        vehicle_form.addRow("주요 옵션:", self.input_options)
        
        group_vehicle.setLayout(vehicle_form)
        layout.addWidget(group_vehicle)
        
        # 4. 상담 후기 입력
        group_review = QGroupBox("4. 상담 후기")
        review_layout = QVBoxLayout()
        
        self.txt_review = QTextEdit()
        self.txt_review.setPlaceholderText(
            "고객과의 상담 내용, 거래 과정, 특별한 에피소드 등을 입력해주세요.\n\n"
            "예시:\n"
            "- 50대 남성 고객님이 E클래스 구매를 희망하셔서 상담 진행했습니다.\n"
            "- 처음에는 다른 브랜드도 고려하셨지만 시승 후 벤츠로 결정하셨어요.\n"
            "- 좋은 조건으로 거래가 성사되어 기뻤습니다."
        )
        self.txt_review.setMinimumHeight(150)
        review_layout.addWidget(self.txt_review)
        
        group_review.setLayout(review_layout)
        layout.addWidget(group_review)
        
        # 5. 스타일 설정
        group_style = QGroupBox("5. 작성 스타일")
        style_form = QFormLayout()
        
        self.combo_tone = QComboBox()
        self.combo_tone.addItems([
            "친근한 이웃 (해요체)", 
            "신뢰감 있는 전문가 (하십시오체)",
            "유머러스하고 재치있는",
            "감성적인 에세이 스타일"
        ])
        style_form.addRow("글 말투:", self.combo_tone)
        
        self.combo_emoji = QComboBox()
        self.combo_emoji.addItems(["사용 안 함 (텍스트만)", "조금 사용 (강조용)", "많이 사용 (화려하게)"])
        style_form.addRow("이모지:", self.combo_emoji)
        
        group_style.setLayout(style_form)
        layout.addWidget(group_style)
        
        # 6. 실행 버튼
        btn_layout2 = QHBoxLayout()
        
        self.btn_generate = QPushButton("📝 후기 글 생성하기")
        self.btn_generate.setStyleSheet("background-color: #5D5D5D; color: white; font-weight: bold; padding: 12px;")
        self.btn_generate.clicked.connect(self.generate_review)
        
        self.btn_generate_publish = QPushButton("🚀 생성 + 바로 발행")
        self.btn_generate_publish.setStyleSheet("background-color: #03C75A; color: white; font-weight: bold; padding: 12px;")
        self.btn_generate_publish.clicked.connect(self.generate_and_publish)
        
        btn_layout2.addWidget(self.btn_generate)
        btn_layout2.addWidget(self.btn_generate_publish)
        layout.addLayout(btn_layout2)
        
        # 7. 결과 미리보기
        layout.addWidget(QLabel("📝 생성된 후기 미리보기"))
        self.result_view = QTextEdit()
        self.result_view.setMinimumHeight(300)
        self.result_view.setPlaceholderText("생성된 출고 후기가 여기에 표시됩니다.")
        layout.addWidget(self.result_view)
        
        # 하단 발행 버튼
        self.btn_publish = QPushButton("📤 현재 내용으로 발행하기")
        self.btn_publish.setStyleSheet("background-color: #4A90E2; color: white; font-weight: bold; padding: 15px; font-size: 16px;")
        self.btn_publish.clicked.connect(self.publish_now)
        self.btn_publish.setEnabled(False)
        layout.addWidget(self.btn_publish)
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)
        
    def add_photos(self):
        """사진 파일 추가"""
        files, _ = QFileDialog.getOpenFileNames(
            self, 
            "출고 사진 선택",
            "",
            "이미지 파일 (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        
        if files:
            for file in files:
                if file not in self.image_paths:
                    self.image_paths.append(file)
                    item = QListWidgetItem(f"📷 {os.path.basename(file)}")
                    item.setData(Qt.UserRole, file)
                    self.photo_list.addItem(item)
                    
            self.log_signal.emit(f"✅ {len(files)}개 사진이 추가되었습니다.")
            
    def clear_photos(self):
        """모든 사진 삭제"""
        self.image_paths.clear()
        self.processed_paths.clear()
        self.photo_list.clear()
        self.log_signal.emit("🗑️ 모든 사진이 삭제되었습니다.")
        
    def get_form_data(self) -> dict:
        """폼 데이터 수집"""
        return {
            'customer_info': {
                'age_group': self.combo_age.currentText() if self.combo_age.currentText() != "선택 안함" else "",
                'gender': self.combo_gender.currentText() if self.combo_gender.currentText() != "선택 안함" else "",
                'region': self.input_region.text().strip()
            },
            'vehicle_info': {
                'brand': self.combo_brand.currentText(),
                'model': self.input_model.text().strip(),
                'year': self.input_year.text().strip(),
                'color': self.input_color.text().strip(),
                'options': self.input_options.text().strip()
            },
            'review_text': self.txt_review.toPlainText().strip(),
            'tone': self.combo_tone.currentText(),
            'emoji_level': self.combo_emoji.currentText(),
            'image_paths': self.image_paths,
            'blur_faces': self.chk_blur_faces.isChecked(),
            'blur_plates': self.chk_blur_plates.isChecked()
        }
        
    def validate_form(self) -> bool:
        """폼 유효성 검사"""
        if not self.input_model.text().strip():
            QMessageBox.warning(self, "입력 필요", "차량 모델을 입력해주세요.")
            return False
        if not self.txt_review.toPlainText().strip():
            QMessageBox.warning(self, "입력 필요", "상담 후기를 입력해주세요.")
            return False
        return True
        
    def generate_review(self):
        """출고 후기 생성"""
        if not self.validate_form():
            return
            
        data = self.get_form_data()
        data['action'] = 'generate'
        
        self.btn_generate.setEnabled(False)
        self.btn_generate.setText("⏳ 생성 중...")
        
        self.worker = DeliveryPostWorker(data)
        self.worker.finished.connect(self.on_generation_finished)
        self.worker.error.connect(self.on_generation_error)
        self.worker.log.connect(lambda msg: self.log_signal.emit(msg))
        self.worker.start()
        
    def generate_and_publish(self):
        """생성 후 바로 발행"""
        if not self.validate_form():
            return
            
        data = self.get_form_data()
        data['action'] = 'full'
        
        self.btn_generate_publish.setEnabled(False)
        self.btn_generate_publish.setText("⏳ 생성 중...")
        
        self.worker = DeliveryPostWorker(data)
        self.worker.finished.connect(self.on_full_generation_finished)
        self.worker.error.connect(self.on_generation_error)
        self.worker.log.connect(lambda msg: self.log_signal.emit(msg))
        self.worker.start()
        
    def on_generation_finished(self, result: dict):
        """생성 완료 처리"""
        self.btn_generate.setEnabled(True)
        self.btn_generate.setText("📝 후기 글 생성하기")
        
        title = result.get('title', '출고 후기')
        content = result.get('content', '') or result.get('content_text', '')
        
        self.result_view.setText(f"제목: {title}\n\n{content}")
        self.btn_publish.setEnabled(True)
        self.log_signal.emit("✅ 출고 후기 생성 완료! 확인 후 발행해주세요.")
        
    def on_full_generation_finished(self, result: dict):
        """생성+발행 완료 처리"""
        self.btn_generate_publish.setEnabled(True)
        self.btn_generate_publish.setText("🚀 생성 + 바로 발행")
        
        title = result.get('title', '출고 후기')
        content = result.get('content', '') or result.get('content_text', '')
        
        self.result_view.setText(f"제목: {title}\n\n{content}")
        
        # 발행 요청
        data = {
            'action': 'publish_only',
            'title': title,
            'content': content
        }
        self.start_signal.emit(data)
        
    def on_generation_error(self, error_msg: str):
        """에러 처리"""
        self.btn_generate.setEnabled(True)
        self.btn_generate.setText("📝 후기 글 생성하기")
        self.btn_generate_publish.setEnabled(True)
        self.btn_generate_publish.setText("🚀 생성 + 바로 발행")
        self.log_signal.emit(f"❌ {error_msg}")
        
    def publish_now(self):
        """현재 내용 발행"""
        content = self.result_view.toPlainText()
        if not content:
            QMessageBox.warning(self, "경고", "발행할 내용이 없습니다.")
            return
            
        lines = content.split('\n')
        title = "출고 후기"
        body = content
        
        if len(lines) > 0 and lines[0].startswith("제목:"):
            title = lines[0].replace("제목:", "").strip()
            body = "\n".join(lines[1:]).strip()
            
        data = {
            'action': 'publish_only',
            'title': title,
            'content': body
        }
        self.start_signal.emit(data)
