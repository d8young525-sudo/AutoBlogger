# CHANGELOG

## v3.18.0 — qt-material 테마 적용 + UI 디자인 개선

### 테마 시스템 교체

**Fusion + QPalette → qt-material 라이브러리**:
- `qt-material` 패키지 도입 (`light_lightgreen.xml` 테마)
- 기존 `get_app_palette()`, `QStyleFactory("Fusion")` 제거
- Material Design 기반 일관된 UI 제공

### accent 색상 중립화 (가시성 개선)

qt-material의 연두색 accent가 불필요하게 적용되는 위젯들을 중립 색상으로 변경:
- **QTextEdit/QPlainTextEdit**: 일반 상태 텍스트 + 테두리, focus 테두리 → 회색
- **QLineEdit**: focus 테두리 → 회색 (`#aaaaaa`)
- **QComboBox**: 드롭다운 선택, 열린/포커스 상태 테두리+텍스트 → 회색
- **QScrollBar**: 핸들 색상 → 회색 (`#c0c0c0`)
- **일반 버튼**: `NEUTRAL_BUTTON_STYLE` 추가 (회색 배경/테두리)
  - 출고후기탭: 사진 추가, 전체 삭제
  - 설정탭: 이미지 선택, 삭제
- 체크박스/라디오버튼은 accent 색상 유지

### GUI 이모지 전면 제거

- `ui/unified_settings_tab.py`: QGroupBox 타이틀 5개 (🔒📝✏️⚙️📁)
- `ui/delivery_tab.py`: QGroupBox 타이틀 4개 + 결과뷰 1개 (📷📅🚗💬📷)
- `main.py`: 로그 메시지 5개 (📞✅🚪❌×2)
- `core/worker.py`: 시스템 로그 12개 (🖼️✅⚠️📷🎨📋❌🚀🔑📝📁💡)
- `ui/info_tab.py`: 결과뷰 1개 (📷)
- 스티커팩/감정매칭 모듈은 블로그 콘텐츠용이므로 미수정

### 카드 테두리 버그 수정

- `QFrame` → `.QFrame` (dot prefix): 자식 QLabel로 테두리 전파 차단
- Qt QSS `.ClassName`은 정확히 해당 클래스만 매칭 (서브클래스 제외)

### UI 레이아웃 개선

- 정보성글쓰기탭: QGroupBox 섹션 적용 ("주제 생성", "주제 선택")
- 정보성글쓰기탭: 카드 컴팩트화 (부연설명 제거, 타이틀 12pt 중앙정렬, 여백 축소)
- `_label_above()` / `_two_col()` 헬퍼 추가 (label-above + 2-column 그리드)
- 로그 영역 높이 축소 (150px → 80px)

### 수정 파일

| 파일 | 변경 |
|------|------|
| `requirements.txt` | `qt-material>=2.14` 추가 |
| `main.py` | qt-material 적용, 전역 QSS 오버라이드, 이모지 제거 |
| `ui/styles.py` | QPalette 제거, `NEUTRAL_BUTTON_STYLE` 추가, 카드 `.QFrame` 수정 |
| `ui/info_tab.py` | 카드 설명/라벨 추가, 이모지 제거 |
| `ui/delivery_tab.py` | 2-column 레이아웃, 중립 버튼, 이모지 제거 |
| `ui/unified_settings_tab.py` | 2-column 그리드, 중립 버튼, 이모지 제거 |
| `core/worker.py` | 시스템 로그 이모지 전면 제거 |

---

## v3.17.0 — UI 간소화 및 발행 흐름 개선

### UI 간소화 (`ui/unified_settings_tab.py`)

**제거된 기능**:
- CSV 내보내기 버튼 및 기능 제거 (`_create_data_section`, `export_csv`)
- 썸네일 자동생성 체크박스 제거 (항상 생성으로 변경)

**스티커팩 이미지 전용**:
- 드롭다운에서 텍스트 제거, 아이콘만 표시
- `setMinimumWidth(70)` 설정

**기본 스타일 적용** (`ui/styles.py`):
- QComboBox, QCheckBox, QRadioButton, QSpinBox 커스텀 indicator 제거
- OS 기본 스타일 사용 (화살표 깨짐 문제 해결)

### 정보성 글쓰기 탭 (`ui/info_tab.py`)

**헤더 완전 제거**:
- 섹션 프레임 제거, 카드를 content_layout에 직접 배치

**라디오버튼 숨김**:
- QRadioButton → QLabel (cardTitle) + 숨겨진 QRadioButton
- 카드 클릭으로 모드 전환 유지

**입력필드 항상 표시**:
- setVisible 제거, setEnabled만 사용
- 비선택 모드 입력필드는 비활성화만

**발행 흐름 변경** (핵심):
```
기존: 주제 선택 → (자동 분석) → 발행 클릭
변경: 주제 선택 → 발행 클릭 → (분석+썸네일) → 발행
```

- 주제 선택 시 분석 자동 실행 제거
- 발행 버튼 클릭 시 분석 + 썸네일 병렬 실행
- 둘 다 완료 후 자동으로 발행 진행
- 버튼 상태: "분석 중..." → "발행 중..."

**새 메서드**:
- `_check_ready_to_publish()`: 분석/썸네일 완료 체크
- `_do_actual_publish()`: 실제 발행 로직

### 포스팅 구조 유연화 (`functions/main.py`)

**프롬프트 변경**:
```
기존: "정확히 {N}개" (엄격한 강제)
변경: "약 {N}개 내외 (±1 자연스러운 변동 허용)"
```

- heading, quotation, image_placeholder 모두 유연하게 적용
- 글 흐름에 따라 자연스러운 변동 허용

---

## v3.16.1 — UI 초간소화 + 프롬프트 강화

### UI 초간소화 (`ui/info_tab.py`)

**플로우 변경: 4단계 → 2단계**
```
기존: 주제생성 → 주제선택(자동분석) → 세부설정 → [발행]
변경: 주제생성 → 주제선택 → [발행]
```

- **세부설정 섹션 완전 제거**: 타깃 독자, 예상 질문, 썸네일 미리보기 UI 삭제
- **발행 버튼 이동**: 섹션 1(주제 선택)로 이동
- **내부 데이터 유지**: 분석/썸네일 백그라운드 실행, UI 표시 없음
- **사용되지 않는 import 정리**: `QListWidget`, `QListWidgetItem`, `QTextEdit` 제거

### 스티커팩 미리보기 이미지 (`ui/unified_settings_tab.py`)

- 콤보박스에 `sticker_0.png` 아이콘 표시 (40x40)
- `QIcon` 사용하여 드롭다운에 스티커 미리보기

### 강조/구조 프롬프트 강화 (`functions/main.py`)

**이모지 금지 강화**:
- `"이모지 절대 사용 금지 (💡, ✅, ⚠️ 등 모든 이모지 포함)"`
- 소제목(heading)에 이모지 사용 금지 명시

**emphasis 배열 명확화**:
```
예시: {"type": "paragraph", "text": "엔진오일은 5,000km마다 교체해야 합니다.", "emphasis": ["5,000km마다"]}
```

**구조 제약 엄격화**:
- `"최소 N개"` → `"정확히 N개"` 변경
- heading, quotation, image_placeholder 개수 정확히 준수 요구

---

## v3.16.0 — 썸네일 대표이미지 + 강조 기능 + UI 간소화

### 썸네일(대표이미지) 자동 삽입 (`core/worker.py`)

- **문제**: 썸네일 이미지가 생성되지만 블로그 대표이미지로 삽입 안됨
- **원인**: `data["images"]["thumbnail"]`이 전달되지만 `upload_cover_image()` 호출 없음
- **해결**: `_run_publish_only()`에 썸네일 업로드 단계 추가
  - `_save_thumbnail_temp()`: base64 → 임시 파일 저장
  - `self.bot.upload_cover_image(temp_path)` 호출
  - `_cleanup_thumbnail()`: 발행 후 임시 파일 정리

### 스티커팩 UI 개선

- **`assets/stickers/sticker_map.json`**: 각 팩에 `display_name` 필드 추가
  - 예: `cafe_001` → "카페 1 (따뜻한 감성)"
- **`ui/unified_settings_tab.py`**: `_load_sticker_packs()` 수정
  - 콤보박스에 display_name 표시, 내부적으로 pack_id 유지
  - `currentData()`로 pack_id 가져오기

### 강조/배경색 기능 구현

**백엔드 프롬프트 (`functions/main.py`)**:
- `key_points` 파라미터 지원 (summary/insight 대체)
- blocks에 `emphasis` 배열 지시 추가:
  ```json
  {"type": "paragraph", "text": "...", "emphasis": ["강조할부분"]}
  ```

**프론트엔드 적용 (`automation.py`)**:
- `_write_paragraph_block()`: emphasis 배열 감지 시 부분 강조 적용
- `_write_paragraph_with_emphasis()`: 타이핑 방식 강조 구현
  - 텍스트를 세그먼트로 분리 (`_split_text_by_emphasis()`)
  - 강조 세그먼트 전에 색상/형광펜 적용
  - 강조 세그먼트 후에 서식 리셋
- `_reset_highlight_color()`: 형광펜 서식 제거

### UI 간소화 (`ui/info_tab.py`)

- **제거**: "핵심 정보 요약" (`txt_summary`) 위젯
- **제거**: "나만의 인사이트" (`txt_insight`) 위젯
- **변경**: `request_full_publish()`에서 `summary`, `insight` 제거, `key_points` 전달

### 수정 파일 목록

| 파일 | 변경 내용 |
|------|-----------|
| `core/worker.py` | 썸네일 업로드 로직 추가 |
| `assets/stickers/sticker_map.json` | display_name 추가 |
| `ui/unified_settings_tab.py` | 스티커팩 ID→이름 매핑, 미리보기 이미지 |
| `ui/info_tab.py` | 세부설정 섹션 제거, 발행 버튼 이동 |
| `functions/main.py` | key_points 지원, 이모지 금지, 구조 엄격화 |
| `automation.py` | 타이핑 방식 부분 강조 구현 |

---

## v3.15.0 — UI 대폭 간소화 + JSON 디버깅 강화

### UI 플로우 간소화 (6단계 → 4단계)

**기존 플로우:**
```
주제생성 → 주제선택 → [분석버튼] → 세부설정 → [원고생성] → [즉시발행]
```

**변경 플로우:**
```
주제생성 → 주제선택(자동분석) → 세부설정(자동선택) → [발행]
```

### 정보성 글쓰기 탭 (`ui/info_tab.py`)

- **분석 버튼 제거** → 주제 선택 시 `run_analysis()` 자동 실행
- **타겟 독자/예상 질문 자동 선택** → 분석 완료 시 첫 번째 항목 자동 체크
- **버튼 통합**: "원고 생성" + "즉시 발행" → **"발행" 버튼 하나** (`request_full_publish()`)
- **action 변경**: `"generate"` / `"publish_only"` → `"full"` (원고 생성 + 발행 한번에)
- **섹션 3 완전 제거**: 미리보기, 해시태그 입력, 예약 발행 UI 삭제
  - 예약 발행은 추후 Selenium으로 네이버 에디터 내 예약 기능 직접 조작 방식으로 별도 구현 예정

### 출고후기 탭 (`ui/delivery_tab.py`)

- **버튼 통합**: "후기 글 생성하기" + "현재 내용으로 발행하기" → **"발행" 버튼 하나** (`request_full_publish()`)
- **자동 발행**: `DeliveryPostWorker` 생성 완료 후 자동으로 `start_signal` emit

### JSON 디버그 로깅 강화 (`core/worker.py`)

- `logs/debug/` 폴더에 발행 시 전체 설정값 포함 JSON 저장
- 저장 항목:
  ```json
  {
    "timestamp": "...",
    "title": "...",
    "tags": "...",
    "blocks": [...],
    "block_count": 18,
    "block_types": ["paragraph", "heading", ...],
    "naver_style": { "font": {...}, "heading": {...}, ... },
    "settings": {
      "topic": "...",
      "mode": "info",
      "tone": "친근한 이웃 (해요체)",
      "length": "보통 (1,500자)",
      "category": "...",
      "targets": [...],
      "questions": [...],
      "intro": "...",
      "outro": "...",
      "post_structure": "default",
      "structure_params": { "heading_count": 3, ... }
    }
  }
  ```
- 실제 발행된 포스팅과 JSON 비교로 서식 적용 디버깅 용이

### 기타 변경

- **main.py**: `reset_generate_button()` → `reset_publish_button()` 함수명 변경
- **CLAUDE.md**: v3.15.0 플로우 문서 업데이트

### 소제목(Heading) 서식 적용 — 부분 해결 (🔴 작업 중)

- **문제**: 소제목 색상/크기 서식이 적용되지 않음
- **해결된 부분**:
  - 드롭다운 클릭: `dispatchEvent` 방식으로 `__se-sentry` 자동화 감지 우회
  - 폰트 크기 매핑: fs18 → fs19 (네이버 에디터에 fs18 없음)
  - 색상 fallback: #03C75A → #54b800 (팔레트에 없는 색상 대체)
- **미해결 부분**:
  - 텍스트 선택 실패로 서식이 커서에만 적용되고 실제 텍스트에는 미적용
  - 서식 리셋 단계에서 커서 서식이 기본값으로 돌아감
- **다음 시도**: 순서 변경 (서식 적용 → 텍스트 입력 → 서식 리셋)
  - 상세 내용: `CLAUDE.md` "현재 작업 중" 섹션 참고

---

## v3.14.0 — 본문 이미지/스티커 자동 삽입 + 해시태그 개선

### 본문 이미지 생성 및 삽입

- **이미지 생성 파이프라인** (`core/worker.py`)
  - 블록 중 `image_placeholder`에서 최대 3개 균등 선택
  - Gemini로 본문 삽화 이미지 생성 → 임시 파일 저장
  - `write_content_with_blocks()`에 `image_paths` 전달
- **이미지 삽입** (`automation.py`)
  - `image_placeholder` 블록에서 `_insert_image_at_cursor()` 호출
- **UI** (`ui/unified_settings_tab.py`)
  - `spin_image_count` 범위: 0~3 (0=이미지 없음)

### 스티커 문맥 매칭 자동 삽입

- **스티커 수집 도구** (`tools/collect_stickers.py`, `tools/crop_stickers.py`)
  - 네이버 에디터 스티커 스프라이트 시트에서 개별 이미지 crop
  - 7팩 177개 스티커 이미지 추출
- **감정 분류** (`tools/classify_stickers.py`)
  - Gemini 3 Flash 비전으로 각 스티커 감정 분류 (11개 카테고리)
  - 결과: `assets/stickers/sticker_map.json`
- **문맥 매칭 엔진** (`core/sticker_matcher.py`)
  - 한국어 감정 키워드 사전 기반 텍스트→감정→스티커 매칭
  - 중복 삽입 방지, 팩 선택 지원
- **발행 시 자동 삽입** (`automation.py`)
  - heading 블록 뒤 빈도 설정에 따라 스티커 삽입
  - 빈도: 사용안함/적게(3개마다)/보통(2개마다)/많이(매 heading)
- **UI** (`ui/unified_settings_tab.py`)
  - 스티커팩 옵션: `sticker_map.json`에서 실제 팩 이름 로드
  - 스티커 빈도 설정: 사용안함/적게/보통/많이

### 네이버 에디터 서식 DOM 적용 (`automation.py`)

- `write_content_with_blocks()`: flat 모드 → 블록별 순차 입력으로 리팩토링
- heading: 볼드/크기/색상 서식 적용 (naver_style 연동)
- quotation: 인용구 스타일 선택 (line/bubble/corner/underline/postit)
- divider: 구분선 스타일 선택 (line1~7)
- `_apply_font_color()`: 색상 팔레트 선택 헬퍼
- 실패 시 `_write_flat_mode()` 폴백

### 해시태그 품질 개선 (`core/hashtag_generator.py`)

- Gemini + Google Search grounding으로 트렌드 반영 해시태그 생성
- 우선순위: Gemini grounding → 백엔드 AI → 로컬 키워드 추출

### UI/UX 개선

- 마크다운 `**볼드**` 표시 제거 (`ui/info_tab.py` — `_clean_to_plain_text()`)
- 세부설정 질문 기본 체크 해제 (선택적 질문 포함)
- 체크박스/라디오버튼 SVG 아이콘 적용 (`ui/styles.py`)
- 중복 주제 경고 팝업 제거 (동일 주제 반복 발행 허용)

---

## v3.13.0 — UI 정리 (인라인 스타일 제거 + 중첩 스크롤 해결)

### 중첩 스크롤 제거 (`ui/info_tab.py`)

- `topic_area` QScrollArea → 일반 QWidget으로 변경 (메인 스크롤이 전체 관리)
- `target_scroll` QScrollArea → 일반 QWidget으로 변경
- 이중 스크롤바 문제 해결

### 인라인 스타일 → QSS objectName 전환

- **`ui/styles.py`**: objectName 기반 QSS 셀렉터 추가
  - `sectionCard`, `sectionHeader`, `sectionDivider` (섹션 카드)
  - `cardSelected`, `cardUnselected` (토글 카드)
  - `topicRadio` (카드형 라디오버튼)
  - `mutedLabel`, `warningLabel`, `infoLabel` (안내 텍스트)
  - `dialogTitle`, `thumbnailPreview` (UI 요소)
  - `userEmailLabel`, `subscriptionGold`, `subscriptionNormal` (사용자 정보)
  - `scheduleActive`, `scheduleInactive` (예약 상태)

- **인라인 `setStyleSheet()` 완전 제거**
  - `ui/info_tab.py`: 13개 → 0개
  - `ui/delivery_tab.py`: 3개 → 0개 (해시태그 추가분 포함)
  - `ui/unified_settings_tab.py`: 5개 → 0개
  - `ui/login_dialog.py`: 5개 → 0개
  - `main.py`: 3개 → 0개

- **동적 스타일 변경**: `setProperty()` + `style().unpolish()/polish()` 패턴 적용

---

## v3.12.0 — 컨텐츠 품질 개선

### 백엔드 프롬프트 개선 (`functions/main.py`)

- **기본 글 구조를 Q&A/선문답 → 정보 나열형으로 변경**
  - ending_prompt 기본값: "질문 유도" → "요약"
  - 프롬프트에 "Q&A 형식 금지" 명시적 지시 추가
  - 질문은 `[참고 질문]`으로 본문에 자연스럽게 통합
  - structure_params(소제목 수, 인용구 수, 이미지 수) 프롬프트 반영

### naver_style 서식 체인 연결

- **Worker → Automation 스타일 전달 (`core/worker.py`)**
  - API 응답의 blocks를 직접 전달 (불필요한 텍스트→블록 재변환 제거)
  - naver_style 설정을 write_content_with_blocks에 전달

- **Automation 서식 적용 (`automation.py`)**
  - write_content_with_blocks()에 naver_style 파라미터 추가
  - heading: naver_style에서 제목 크기 적용
  - paragraph: 본문 폰트 크기 적용
  - quotation: 인용구 스타일 변형 선택

### 출고후기 탭 해시태그 자동생성 (`ui/delivery_tab.py`)

- 글 생성 완료 시 로컬 키워드 추출 기반 해시태그 자동 생성
- 태그 입력 필드 + "태그 재생성" 버튼 추가
- 발행 시 태그 데이터 포함

---

## v3.11.0 — 구조개선 및 UI 리팩토링

### UI 변경

- **정보성 글쓰기 탭: 3단 위저드 → 세로 스크롤 레이아웃으로 변경**
  - QStackedWidget 기반 위저드 제거, QScrollArea 기반 단일 페이지로 통합
  - 3개 섹션(주제 선택 / 세부 설정 / 미리보기·발행)이 카드 형태로 세로 배치
  - 세부 설정 섹션: 주제 분석 완료 시 자동 활성화 + 스크롤 이동
  - 미리보기 섹션: 원고 생성 완료 시 자동 활성화 + 스크롤 이동
  - 위저드 네비게이션(다음/이전) 버튼 제거
  - 공개 인터페이스(시그널, getter 메서드) 변경 없음

### 구조개선

- **레거시 설정 탭 파일 삭제**
  - `ui/settings_tab.py` 삭제 (UnifiedSettingsTab으로 대체 완료)
  - `ui/writing_settings_tab.py` 삭제 (UnifiedSettingsTab으로 대체 완료)
  - `ui/content_manager_tab.py` 삭제 (미사용 orphan 코드)

- **모듈 export 정리**
  - `ui/__init__.py`: `SettingsTab` → `UnifiedSettingsTab`으로 변경
  - `core/__init__.py`: `HashtagWorker`, `is_duplicate_topic`, `get_stats` export 추가

- **불필요 파일 정리**
  - `captured_payload.txt`, `nul` 삭제
  - `.gitignore`에 `*.db`, `captured_payload.txt`, `nul`, `naver_editor_structure.html` 추가
