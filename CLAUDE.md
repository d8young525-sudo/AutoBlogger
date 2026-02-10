# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Naver Blog Auto Blogger Pro (v3.18.0) — a Python desktop application that automates Naver blog posting using AI-generated content. Combines PySide6 GUI, Selenium browser automation, Google Gemini AI for content/image generation, and Firebase for auth and backend.

**v3.18.0 주요 변경**:
- qt-material 라이브러리 적용 (`light_lightgreen.xml` 테마)
- 기존 Fusion + QPalette 제거, Material Design 기반 UI
- 불필요한 accent 색상(연두색) 중립화 (버튼, 입력필드, 스크롤바, 콤보박스)
- GUI 전체 이모지 제거
- 카드 테두리 버그 수정 (`.QFrame` dot prefix)
- Figma 참고 UI 레이아웃 개선 (label-above, 2-column 그리드)

## Running the Application

```bash
pip install -r requirements.txt
python main.py              # GUI mode (default)
python main.py --cli        # CLI mode
python main.py --debug      # Debug mode
```

Environment variables needed in `.env`: `GEMINI_API_KEY`, `FIREBASE_API_KEY`, `BACKEND_URL`.

## Deploying Firebase Functions

```bash
cd functions
pip install -r requirements.txt
firebase deploy --only functions
```

---

## 핵심 흐름도 (Critical Flow Map)

> **수정 원칙**: 아래 흐름을 변경할 때는 반드시 연결된 전체 체인을 확인할 것.
> 새 기능 추가 시 기존 시그널 체인은 건드리지 않는 것을 원칙으로 한다.

### 시그널 정의

| 위치 | 시그널 | 용도 |
|------|--------|------|
| `ui/info_tab.py` | `start_signal(dict)` | MainWindow에 작업 요청 |
| `ui/info_tab.py` | `log_signal(str)` | 시스템 로그 출력 |
| `ui/delivery_tab.py` | `start_signal(dict)` | MainWindow에 작업 요청 |
| `ui/delivery_tab.py` | `log_signal(str)` | 시스템 로그 출력 |
| `core/worker.py` | `log_signal(str)` | 작업 로그 |
| `core/worker.py` | `result_signal(dict)` | 생성 결과 데이터 전달 |
| `core/worker.py` | `finished_signal()` | 작업 완료 (버튼 리셋) |
| `core/worker.py` | `error_signal(str)` | 에러 메시지 |
| `core/worker.py` | `progress_signal(int)` | 진행률 (미연결 상태) |

### 시그널 연결 (main.py)

```
tab_info.start_signal    ──> MainWindow.start_automation(data)
tab_info.log_signal      ──> MainWindow.update_log(msg)
tab_delivery.start_signal ──> MainWindow.start_automation(data)
tab_delivery.log_signal   ──> MainWindow.update_log(msg)

# start_automation() 내부에서 매번 생성:
worker.log_signal        ──> MainWindow.update_log
worker.result_signal     ──> MainWindow.on_worker_result
worker.error_signal      ──> MainWindow.on_worker_error
worker.finished_signal   ──> MainWindow.on_worker_finished
```

---

## 정보성 글쓰기 (Info Tab) 전체 흐름 — v3.15.0 간소화 버전

> **플로우 변경**: 6단계 → 4단계
> - 기존: 주제생성 → 주제선택 → [분석버튼] → 세부설정 → [원고생성] → [즉시발행]
> - 변경: 주제생성 → 주제선택(자동분석) → 세부설정(자동선택) → [발행](원고+발행 통합)

### Phase 1: 주제 생성
```
btn_generate_topic 클릭
  └─> generate_topics() / get_recommendations() / get_keyword_recommendations()
       └─> RecommendWorker.start()
            ├─ .finished ──> _populate_topics() + _reset_generate_button()
            └─ .error    ──> _reset_generate_button()
```

### Phase 2: 주제 선택 (v3.17.0)
```
주제 라디오버튼 선택
  └─> on_topic_changed()
       └─ btn_publish.setEnabled(True)  ⬅️ 분석 없이 버튼만 활성화
```

### Phase 3: 발행 (분석 → 썸네일 → 원고 생성 + 발행) ⚠️ 핵심 체인
```
btn_publish 클릭 ("발행" 버튼 하나로 통합)
  └─> request_full_publish()
       ├─ btn_publish.setText("분석 중...")
       ├─ _pending_publish = True
       ├─ run_analysis()  ⬅️ 분석 시작 (여기서 실행)
       │    └─ AnalysisWorker(topic).start()
       │         └─ .finished ──> on_analysis_finished()
       │              └─ _check_ready_to_publish()
       └─ generate_thumbnail_auto()  ⬅️ 썸네일 병렬 생성
            └─ ImageGenerateWorker.start()
                 └─ .finished ──> on_thumbnail_finished()
                      └─ _check_ready_to_publish()

_check_ready_to_publish()
  └─ 분석 완료 확인 → _do_actual_publish()
       ├─ btn_publish.setText("발행 중...")
       ├─ data dict 구성 {action:"full", mode:"info", ...}
       └─> start_signal.emit(data)
            └─> MainWindow.start_automation(data)
                 └─> AutomationWorker(data, settings).start()
                      └─> worker.run()
                           ├─ _run_generation() ──> POST BACKEND_URL
                           ├─ result_signal.emit(res_data)
                           ├─ _run_publish_only()
                           │    └─> NaverBlogBot 순차 실행
                           └─ finished_signal.emit()
```

---

## 출고후기 (Delivery Tab) 흐름 — v3.15.0 간소화 버전

> **변경**: "후기 글 생성하기" + "발행하기" → "발행" 버튼 하나로 통합
> DeliveryPostWorker로 생성 후 자동으로 AutomationWorker로 발행

```
btn_publish 클릭 ("발행" 버튼 하나로 통합)
  └─> request_full_publish()
       └─> DeliveryPostWorker.start()  (자체 워커로 원고 생성)
            ├─ .finished ──> on_generation_finished()
            │    └─> start_signal.emit({action:"publish_only", ...})  ⬅️ 자동 발행
            │         └─> AutomationWorker._run_publish_only()
            └─ .error ──> on_generation_error()
```

---

## 자동화 흐름 (NaverBlogBot - automation.py)

```
_run_publish_only() 실행 순서:

1. NaverBlogBot() 생성
2. start_browser()         — Chrome + anti-detection 설정
3. login(id, pw)           — 네이버 로그인 (clipboard 입력)
4. go_to_editor()          — 블로그 에디터 진입 + 임시저장 팝업 처리
5. [이미지 생성]            — _generate_content_images() (Gemini)
6. write_content_with_blocks(title, blocks, image_paths, naver_style)
   ├─ _write_title()
   ├─ _click_content_area()
   ├─ 블록별 순차 입력:
   │    ├─ heading → _write_heading_block() + 스티커 삽입 (빈도 설정에 따라)
   │    ├─ paragraph → _write_paragraph_block()
   │    ├─ list → _write_list_block()
   │    ├─ quotation → _write_quotation_block()
   │    ├─ divider → _write_divider_block()
   │    └─ image_placeholder → _insert_image_at_cursor()
   └─ 실패 시 _write_flat_mode() 폴백
7. input_tags(tags)        — 해시태그 입력
8. publish_post(category)  — 발행 버튼 + 카테고리 선택 + 최종 발행
9. _record_publish()       — SQLite 이력 저장
10. close()                — 브라우저 종료
```

---

## 설정 데이터 흐름

```
UnifiedSettingsTab (ui/unified_settings_tab.py)
  │
  ├── InfoTab/DeliveryTab에 constructor arg로 전달 (writing_settings_tab)
  │
  ├── 원고 생성 시 getter 호출:
  │     get_default_tone()                 → data["tone"]
  │     get_default_length()               → data["length"]
  │     get_naver_editor_style_settings()  → data["naver_style"]
  │     get_post_structure()               → data["post_structure"]
  │     get_structure_params()             → data["structure_params"]
  │     get_info_category()                → data["category"]
  │
  └── naver_style 구조:
        {
          font: {name, size},
          heading: {bold, size, color},
          quotation: {style},
          divider: {style},
          emphasis: {bold, italic, underline},
          align: "left"|"center",
          sticker: {enabled, pack_name, frequency, frequencyName}
        }
```

---

## 수정 시 체크리스트

### 새 기능 추가 시
- [ ] 기존 시그널 체인(result_signal → update_result_view → 버튼리셋) 영향 없는지 확인
- [ ] worker.run()의 action 분기 흐름 변경 안 했는지 확인
- [ ] try/except에서 시그널 emit 누락 없는지 확인 (특히 finished_signal)

### worker.py 수정 시
- [ ] result_signal.emit()이 항상 호출되는지 확인
- [ ] finished_signal.emit()이 finally 블록에서 호출되는지 확인
- [ ] 새 단계 추가 시 기존 단계 순서/데이터 변경하지 않았는지 확인

### automation.py 수정 시
- [ ] write_content_with_blocks()의 fallback(_write_flat_mode) 유지되는지 확인
- [ ] 새 블록 타입 추가 시 기존 블록 처리 로직 변경 안 했는지 확인
- [ ] Selenium selector 변경 시 해당 selector만 수정 (다른 메서드 영향 X)

### UI 수정 시
- [ ] 위젯 이름(objectName) 변경 시 styles.py QSS 셀렉터도 함께 수정
- [ ] 시그널 연결 순서 변경하지 않았는지 확인

---

## Anti-Detection

Selenium automation uses clipboard-based input (`pyperclip`), custom user agents, and `navigator.webdriver` removal. Changes to these mechanisms should be made carefully.

## Key Modules

| 파일 | 역할 |
|------|------|
| `main.py` | Entry point, MainWindow, 시그널 연결 허브 |
| `automation.py` | NaverBlogBot — Selenium 자동화 |
| `core/worker.py` | AutomationWorker — QThread 백그라운드 작업 |
| `core/content_converter.py` | 마크다운/텍스트 → 네이버 에디터 블록 변환 |
| `core/image_generator.py` | Gemini 이미지 생성 |
| `core/hashtag_generator.py` | 해시태그 생성 (Gemini grounding → 백엔드 AI → 로컬) |
| `core/sticker_matcher.py` | 텍스트 감정 분석 → 스티커 매칭 |
| `core/post_history.py` | SQLite 발행 이력 관리 |
| `ui/info_tab.py` | 정보성 글쓰기 탭 |
| `ui/delivery_tab.py` | 출고후기 탭 |
| `ui/unified_settings_tab.py` | 통합 환경설정 탭 |
| `ui/styles.py` | 인라인 위젯 스타일 (GREEN/RED/NEUTRAL_BUTTON, CARD) |
| `ui/login_dialog.py` | Firebase 로그인 다이얼로그 |
| `config.py` | 앱 설정 상수 |

## Important Notes

- UI and all content are in Korean
- No test suite or linting config exists currently
- Naver blog editor selectors in `automation.py` are fragile — they break when Naver updates their frontend
- Chrome/Chromium must be installed; `webdriver-manager` handles ChromeDriver
- 스크린샷 확인 경로: `C:\Users\tnlqo\Desktop\dev\screenshot`

---

## 알려진 이슈 / TODO

- [x] **소제목(Heading) 서식 적용** — 서식 먼저 적용 → 텍스트 입력 방식으로 해결
- [x] **강조/배경색 기능** — 타이핑 방식 부분 강조 구현 (v3.16.0)
- [x] **썸네일 대표이미지 삽입** — `upload_cover_image()` 연동 (v3.16.0)
- [ ] progress_signal이 정의되어 있지만 main.py에서 미연결 상태
- [ ] 출고후기탭 사진 업로드 → 발행 연동
- [ ] 얼굴/번호판 블러 AI
- [ ] CSV 내보내기
- [ ] 네이버 에디터 예약발행 (Selenium 직접 조작 방식으로 별도 구현 예정)
- [ ] PyInstaller 배포
- [ ] 구독관리 / 관리자 대시보드

---

## 해결된 이슈: 소제목/강조 서식 적용 (2026-02-05)

### 해결 방식: "서식 먼저 적용 → 텍스트 입력"

네이버 에디터의 contentEditable 특성 활용:
```
Before: 텍스트 입력 → 텍스트 선택 → 서식 적용 (선택 실패)
After:  서식 적용 → 텍스트 입력 → 서식 리셋 (서식 상속됨)
```

### 네이버 에디터 참고 정보

| 항목 | 셀렉터/값 | 비고 |
|------|-----------|------|
| 폰트 크기 | `button[data-value='fs19']` | fs18 없음 → fs19 매핑 |
| 색상 | `button.se-color-palette[data-color='#54b800']` | #03C75A 없음 → fallback |
| 유효 크기 | fs11, fs13, fs15, fs16, fs19, fs24, fs28, fs30, fs34, fs38 | |
| 자동화 감지 | `__se-sentry` 클래스 | dispatchEvent로 우회 |

---

## 완료된 작업

- [x] v3.18.0 qt-material 테마 적용 (light_lightgreen.xml)
- [x] v3.18.0 accent 색상 중립화 (버튼/입력필드/스크롤바/콤보박스)
- [x] v3.18.0 GUI 전체 이모지 제거
- [x] v3.18.0 카드 테두리 버그 수정 (.QFrame dot prefix)
- [x] v3.18.0 Figma 참고 UI 레이아웃 개선
- [x] v3.17.0 발행 흐름 변경: 주제 선택 시 분석 → 발행 클릭 시 분석으로 변경
- [x] v3.17.0 스티커팩 이미지 전용 (텍스트 제거)
- [x] v3.17.0 헤더 완전 제거, 라디오버튼 숨김 (라벨로 대체)
- [x] v3.17.0 입력필드 항상 표시 (비선택 모드 비활성화만)
- [x] v3.17.0 QComboBox/QCheckBox/QRadioButton 기본 OS 스타일 적용
- [x] v3.17.0 구조 유연화: "정확히 N개" → "약 N개 내외"
- [x] v3.17.0 썸네일 필수화 (체크박스 제거)
- [x] v3.17.0 CSV 내보내기 기능 제거
- [x] v3.16.1 UI 초간소화: 세부설정 섹션 제거, 발행 버튼 섹션1로 이동
- [x] v3.16.1 스티커팩 미리보기 이미지 (드롭다운 아이콘)
- [x] v3.16.1 프롬프트 강화: 이모지 금지, 구조 개수 엄격화
- [x] v3.16.0 썸네일 대표이미지 자동 삽입
- [x] v3.16.0 강조/배경색 타이핑 방식 구현
- [x] v3.16.0 스티커팩 display_name UI 개선
- [x] v3.16.0 UI 간소화 (summary/insight 제거)
- [x] v3.15.0 소제목 서식 적용 — 서식 먼저 적용 → 텍스트 입력 방식
- [x] v3.15.0 UI 간소화: 6단계 → 4단계 플로우
- [x] JSON 디버그 로깅 강화 (logs/debug/ 폴더에 전체 설정값 포함)
- [x] 해시태그 생성 Gemini Few-shot 적용
- [x] 드롭다운 클릭 개선 — dispatchEvent 방식 + 폰트 크기 매핑
