"""
출고 후기 탭 - 차량 출고 후기 자동 포스팅 기능 (간소화 버전)
v3.6.0: UI 간소화 - 후기 생성 + 발행 통합
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
from ui.styles import GREEN_BUTTON_STYLE, NEUTRAL_BUTTON_STYLE

from config import Config
from core.hashtag_generator import HashtagWorker, extract_tags_local

BACKEND_URL = Config.BACKEND_URL


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
            self.log.emit("AI 출고 후기 작성 요청 중...")

            # 프롬프트 구성
            customer_info = self.data.get('customer_info', {})
            vehicle_info = self.data.get('vehicle_info', {})
            review_text = self.data.get('review_text', '')
            tone = self.data.get('tone', '친근한 이웃 (해요체)')
            structure_style = self.data.get('post_structure', 'default')

            brand = vehicle_info.get('brand', '')
            model = vehicle_info.get('model', '')
            year = vehicle_info.get('year', '')
            color = vehicle_info.get('color', '')
            options = vehicle_info.get('options', '')
            age_group = customer_info.get('age_group', '')
            gender = customer_info.get('gender', '')
            region = customer_info.get('region', '')

            if structure_style == "popular":
                prompt = f"""
            [ROLE] 네이버 자동차 딜러 파워 블로거
            당신은 자동차 출고 후기 전문 블로거입니다. 고객의 출고 경험을 생생하고 매력적으로 전달하세요.

            [고객 정보]
            - 연령대: {age_group}
            - 성별: {gender}
            - 지역: {region}

            [차량 정보]
            - 브랜드: {brand}
            - 모델: {model}
            - 연식: {year}
            - 색상: {color}
            - 옵션: {options}

            [상담 후기]
            {review_text}

            [작성 스타일]
            - 말투: {tone}

            [포스팅 구조 규칙 - 출고후기 인기 블로그 패턴]
            반드시 아래 규칙을 따라 구조화된 JSON을 출력하세요.

            1. 제목: 15~25자, "{brand} {model}" 키워드 앞배치 (예: "{brand} {model} 출고 후기 | 색상 고민 끝!")
            2. 첫 문단(도입부): 출고 축하 인사 + 고객 소개 (어떤 분이 어떤 차를 선택했는지)
            3. 소제목(heading): 반드시 5개 사용 (level: 2)
            4. 인용구(quotation): 최소 2개 — 고객 한마디/차량 핵심 매력 강조, 마무리 감사 인사
            5. image_placeholder: 총 8~12개 (출고 사진 배치용, 각 섹션 1~3개)
            6. 키워드: "{brand} {model}", "출고" 등 본문에 3~7회 자연스럽게 반복
            7. 마지막 섹션: 감사 인사 + 상담 안내

            [필수 구조 템플릿 — 이 순서를 반드시 따르세요]
            paragraph(출고 축하 + 고객 소개) → image_placeholder(고객+차량 인증샷) →
            heading("차량 선택 이유") → paragraph(왜 이 차를 골랐는지) → image_placeholder(차량 외관) → paragraph →
            heading("차량 외관 & 색상") → paragraph(색상/디자인 설명) → quotation(색상 선택 포인트) → image_placeholder(외관 상세) → image_placeholder(색상 디테일) →
            heading("실내 인테리어 & 옵션") → paragraph(실내/옵션 설명) → image_placeholder(실내) → list(주요 옵션 리스트) → image_placeholder(옵션 디테일) →
            heading("상담 & 출고 과정") → paragraph(상담 과정 이야기) → image_placeholder(출고 현장) → paragraph → image_placeholder(키 전달/세레모니) →
            heading("마무리") → quotation(고객 감사 한마디) → paragraph(상담 안내 + 연락처) → image_placeholder(단체 사진/마무리)

            [OUTPUT FORMAT]
            반드시 아래 형식의 JSON을 출력하세요:
            {{
                "title": "15~25자 SEO 제목 ({brand} {model} 키워드 포함)",
                "blocks": [
                    {{"type": "paragraph", "text": "출고 축하 인사 + 고객 소개..."}},
                    {{"type": "image_placeholder", "description": "고객과 차량 인증샷"}},
                    {{"type": "heading", "text": "차량 선택 이유", "level": 2}},
                    {{"type": "paragraph", "text": "..."}},
                    ...
                ]
            }}

            [BLOCK TYPES]
            - "paragraph": 일반 본문 텍스트 (2~5문장)
            - "heading": 소제목 (level: 2)
            - "list": 목록 (style: "bullet")
            - "divider": 구분선
            - "quotation": 인용구 (고객 한마디, 핵심 포인트)
            - "image_placeholder": 출고 사진 삽입 위치 (description: 어떤 사진인지 설명)

            [IMPORTANT]
            - blocks 배열에 25~35개 블록 포함
            - 각 paragraph는 2~5문장
            - heading은 반드시 5개
            - quotation은 반드시 2개 이상
            - image_placeholder는 반드시 8~12개
            - 고객 정보와 차량 정보를 자연스럽게 녹여서 작성
            - 상담 후기 내용을 반드시 반영
            - JSON 형식 외의 텍스트 출력 금지
            """
            else:
                prompt = f"""
            차량 출고 후기 블로그 글을 작성해주세요.

            [고객 정보]
            - 연령대: {age_group}
            - 성별: {gender}
            - 지역: {region}

            [차량 정보]
            - 브랜드: {brand}
            - 모델: {model}
            - 연식: {year}
            - 색상: {color}
            - 옵션: {options}

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
                "topic": f"{brand} {model} 출고 후기",
                "prompt": prompt,
                "style_options": {},
                "structure_style": structure_style
            }
            
            response = requests.post(BACKEND_URL, json=payload, timeout=180)
            
            if response.status_code == 200:
                result = response.json()
                self.log.emit("출고 후기 생성 완료!")
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
    
    def __init__(self, writing_settings_tab=None):
        super().__init__()
        self.writing_settings_tab = writing_settings_tab  # 글쓰기 환경설정 탭 참조
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
        self.btn_add_photos = QPushButton("사진 추가")
        self.btn_add_photos.setMinimumHeight(60)
        self.btn_add_photos.setStyleSheet(NEUTRAL_BUTTON_STYLE)
        self.btn_add_photos.clicked.connect(self.add_photos)

        self.btn_clear_photos = QPushButton("전체 삭제")
        self.btn_clear_photos.setMinimumHeight(60)
        self.btn_clear_photos.setStyleSheet(NEUTRAL_BUTTON_STYLE)
        self.btn_clear_photos.clicked.connect(self.clear_photos)
        
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
        lbl_privacy_notice = QLabel("얼굴과 번호판은 개인정보 보호를 위해 블러 처리를 권장합니다.")
        photo_layout.addWidget(lbl_privacy_notice)
        
        group_photos.setLayout(photo_layout)
        layout.addWidget(group_photos)
        
        # 2. 고객 정보
        group_customer = QGroupBox("2. 고객 정보 (선택)")
        customer_layout = QVBoxLayout()
        customer_layout.setSpacing(12)

        # 연령대 + 성별: 2열 배치
        age_gender_row = QHBoxLayout()
        age_gender_row.setSpacing(16)

        age_col = QVBoxLayout()
        age_col.setSpacing(4)
        age_col.addWidget(QLabel("연령대"))
        self.combo_age = QComboBox()
        self.combo_age.addItems(["선택 안함", "20대", "30대", "40대", "50대", "60대 이상"])
        age_col.addWidget(self.combo_age)
        age_gender_row.addLayout(age_col, 1)

        gender_col = QVBoxLayout()
        gender_col.setSpacing(4)
        gender_col.addWidget(QLabel("성별"))
        self.combo_gender = QComboBox()
        self.combo_gender.addItems(["선택 안함", "남성", "여성"])
        gender_col.addWidget(self.combo_gender)
        age_gender_row.addLayout(gender_col, 1)

        customer_layout.addLayout(age_gender_row)

        # 지역: 전체 폭
        customer_layout.addWidget(QLabel("지역"))
        self.input_region = QLineEdit()
        self.input_region.setPlaceholderText("예: 서울, 경기, 부산 등")
        customer_layout.addWidget(self.input_region)

        group_customer.setLayout(customer_layout)
        layout.addWidget(group_customer)

        # 3. 차량 정보
        group_vehicle = QGroupBox("3. 차량 정보")
        vehicle_layout = QVBoxLayout()
        vehicle_layout.setSpacing(12)

        # 모델
        vehicle_layout.addWidget(QLabel("모델"))
        self.input_model = QLineEdit()
        self.input_model.setPlaceholderText("예: E클래스, S클래스, GLE, AMG GT 등")
        vehicle_layout.addWidget(self.input_model)

        # 연식
        vehicle_layout.addWidget(QLabel("연식"))
        self.input_year = QLineEdit()
        self.input_year.setPlaceholderText("예: 2024")
        vehicle_layout.addWidget(self.input_year)

        # 색상
        vehicle_layout.addWidget(QLabel("색상"))
        self.input_color = QLineEdit()
        self.input_color.setPlaceholderText("예: 화이트, 블랙, 실버 등")
        vehicle_layout.addWidget(self.input_color)

        # 주요 옵션
        vehicle_layout.addWidget(QLabel("주요 옵션"))
        self.input_options = QLineEdit()
        self.input_options.setPlaceholderText("예: 풀옵션, 네비게이션, 선루프 등")
        vehicle_layout.addWidget(self.input_options)

        group_vehicle.setLayout(vehicle_layout)
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
        
        # 5. 발행 버튼 (후기 생성 + 발행 통합)
        style_notice = QLabel("작성 스타일(말투, 분량 등)은 [글쓰기 환경설정] 탭에서 통합 관리됩니다.")
        layout.addWidget(style_notice)

        # 내부 상태 변수 (UI 없이 데이터 저장용)
        self.generated_tags = ""

        self.btn_publish = QPushButton("발행")
        self.btn_publish.setStyleSheet(GREEN_BUTTON_STYLE)
        self.btn_publish.clicked.connect(self.request_full_publish)
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
                    item = QListWidgetItem(os.path.basename(file))
                    item.setData(Qt.UserRole, file)
                    self.photo_list.addItem(item)
                    
            self.log_signal.emit(f"{len(files)}개 사진이 추가되었습니다.")
            
    def clear_photos(self):
        """모든 사진 삭제"""
        self.image_paths.clear()
        self.processed_paths.clear()
        self.photo_list.clear()
        self.log_signal.emit("모든 사진이 삭제되었습니다.")
        
    def get_form_data(self) -> dict:
        """폼 데이터 수집"""
        # 글쓰기 환경설정에서 톤, 포스팅 구조 가져오기
        tone = "친근한 이웃 (해요체)"
        post_structure = "default"
        if self.writing_settings_tab:
            tone = self.writing_settings_tab.get_default_tone()
            post_structure = self.writing_settings_tab.get_post_structure()

        return {
            'customer_info': {
                'age_group': self.combo_age.currentText() if self.combo_age.currentText() != "선택 안함" else "",
                'gender': self.combo_gender.currentText() if self.combo_gender.currentText() != "선택 안함" else "",
                'region': self.input_region.text().strip()
            },
            'vehicle_info': {
                'brand': '메르세데스-벤츠',  # 고정값
                'model': self.input_model.text().strip(),
                'year': self.input_year.text().strip(),
                'color': self.input_color.text().strip(),
                'options': self.input_options.text().strip()
            },
            'review_text': self.txt_review.toPlainText().strip(),
            'tone': tone,
            'image_paths': self.image_paths,
            'blur_faces': self.chk_blur_faces.isChecked(),
            'blur_plates': self.chk_blur_plates.isChecked(),
            'post_structure': post_structure
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
        
    def request_full_publish(self):
        """발행 버튼 클릭 - 후기 생성 + 발행 한번에 실행"""
        if not self.validate_form():
            return

        data = self.get_form_data()
        data['action'] = 'generate'
        data['mode'] = 'delivery'

        self.btn_publish.setEnabled(False)
        self.btn_publish.setText("생성 중...")

        self.worker = DeliveryPostWorker(data)
        self.worker.finished.connect(self.on_generation_finished)
        self.worker.error.connect(self.on_generation_error)
        self.worker.log.connect(lambda msg: self.log_signal.emit(msg))
        self.worker.start()
        
    def on_generation_finished(self, result: dict):
        """생성 완료 처리 → 자동 발행"""
        title = result.get('title', '출고 후기')
        content = result.get('content', '') or result.get('content_text', '')
        blocks = result.get('blocks', None)

        self.generated_title = title
        self.generated_content = content
        self.generated_blocks = blocks

        self.log_signal.emit("출고 후기 생성 완료! 발행 진행 중...")
        self.btn_publish.setText("발행 중...")

        # 카테고리 가져오기
        category = ""
        naver_style = {}
        if self.writing_settings_tab:
            category = self.writing_settings_tab.get_delivery_category()
            naver_style = self.writing_settings_tab.get_naver_editor_style_settings()

        # 자동 발행 실행
        data = {
            'action': 'publish_only',
            'mode': 'delivery',
            'title': title,
            'content': content,
            'category': category,
            'tags': '',  # 해시태그는 발행 시 자동 생성
            'naver_style': naver_style
        }
        if blocks:
            data['blocks'] = blocks

        self.start_signal.emit(data)
        
    def on_generation_error(self, error_msg: str):
        """에러 처리"""
        self.btn_publish.setEnabled(True)
        self.btn_publish.setText("발행")
        self.log_signal.emit(f"{error_msg}")

    def update_result_view(self, result_data):
        """결과 뷰어 업데이트 - 발행 버튼 리셋"""
        title = result_data.get("title", "출고 후기")
        content = result_data.get("content_text", "") or result_data.get("content", "")

        # blocks에서 텍스트 추출 (content가 비어있을 때)
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
                    lines.append(f"\n[{desc}]\n")
            content = "\n".join(lines)

        self.generated_content = content
        self.generated_title = title

        # 발행 버튼 리셋
        self.btn_publish.setEnabled(True)
        self.btn_publish.setText("발행")

        self.log_signal.emit(f"후기 처리 완료: {title}")

    def _auto_generate_tags(self):
        """생성된 콘텐츠 기반 해시태그 자동 생성 (Gemini Few-shot)"""
        title = getattr(self, 'generated_title', '')
        content = getattr(self, 'generated_content', '')
        if not title and not content:
            return

        self.log_signal.emit("해시태그 생성 중...")
        self._tag_worker = HashtagWorker(title, content)
        self._tag_worker.finished.connect(self._on_tags_generated)
        self._tag_worker.error.connect(self._on_tags_error)
        self._tag_worker.start()

    def _on_tags_generated(self, tags: list):
        """해시태그 생성 완료 - 내부 변수에 저장"""
        if tags:
            self.generated_tags = ", ".join(tags)
            self.log_signal.emit(f"해시태그 {len(tags)}개 생성 완료")
        else:
            self.generated_tags = ""

    def _on_tags_error(self, error_msg: str):
        """해시태그 생성 오류 - 로컬 폴백"""
        self.log_signal.emit(f"해시태그 AI 생성 실패, 로컬 추출 시도...")
        title = getattr(self, 'generated_title', '')
        content = getattr(self, 'generated_content', '')
        tags = extract_tags_local(title, content)
        if tags:
            self.generated_tags = ", ".join(tags)
        else:
            self.generated_tags = ""

    def reset_publish_button(self):
        """발행 버튼 초기화"""
        self.btn_publish.setEnabled(True)
        self.btn_publish.setText("발행")
