# CHANGELOG

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
