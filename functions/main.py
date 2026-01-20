import os
import json
import base64
import logging
import random
from datetime import datetime
from firebase_functions import https_fn
from firebase_functions.options import CorsOptions
from firebase_admin import initialize_app, firestore, auth
from google import genai
from google.genai import types

# Firebase 앱 초기화
initialize_app()

# 사용량 제한 설정
DAILY_IMAGE_LIMIT = 20  # 일반회원 일일 제한
MONTHLY_IMAGE_LIMIT = 500  # 일반회원 월간 제한

# Firestore 클라이언트 (lazy initialization)
_db = None

def get_db():
    """Firestore 클라이언트를 필요할 때만 초기화"""
    global _db
    if _db is None:
        _db = firestore.client()
    return _db


def verify_user_token(req: https_fn.Request) -> dict:
    """Firebase Auth 토큰 검증"""
    auth_header = req.headers.get("Authorization", "")
    
    if not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.split("Bearer ")[1]
    
    try:
        decoded_token = auth.verify_id_token(token)
        return {
            "uid": decoded_token["uid"],
            "email": decoded_token.get("email", "")
        }
    except Exception as e:
        logging.error(f"Token verification failed: {e}")
        return None


def check_user_permission(uid: str) -> dict:
    """사용자 권한 및 사용량 체크"""
    try:
        db = get_db()
        user_ref = db.collection("users").document(uid)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            # 새 사용자 생성
            user_data = {
                "created_at": datetime.now(),
                "is_active": False,
                "is_admin": False,
                "daily_image_count": 0,
                "monthly_image_count": 0,
                "last_reset_date": datetime.now().strftime("%Y-%m-%d"),
                "last_reset_month": datetime.now().strftime("%Y-%m")
            }
            user_ref.set(user_data)
            return {
                "allowed": False,
                "reason": "관리자 승인이 필요합니다. 오픈카톡으로 문의해주세요: https://open.kakao.com/o/sgbYdyai",
                "usage": user_data
            }
        
        user_data = user_doc.to_dict()
        
        # 활성화 체크
        if not user_data.get("is_active", False):
            return {
                "allowed": False,
                "reason": "관리자 승인 대기 중입니다. 오픈카톡으로 문의해주세요: https://open.kakao.com/o/sgbYdyai",
                "usage": user_data
            }
        
        # 일일 리셋 체크
        today = datetime.now().strftime("%Y-%m-%d")
        if user_data.get("last_reset_date") != today:
            user_ref.update({
                "daily_image_count": 0,
                "last_reset_date": today
            })
            user_data["daily_image_count"] = 0
        
        # 월간 리셋 체크
        this_month = datetime.now().strftime("%Y-%m")
        if user_data.get("last_reset_month") != this_month:
            user_ref.update({
                "monthly_image_count": 0,
                "last_reset_month": this_month
            })
            user_data["monthly_image_count"] = 0
        
        # 관리자인지 확인
        is_admin = user_data.get("is_admin", False)
        
        if is_admin:
            # 관리자는 무제한
            plan_limits = {"daily": 999999, "monthly": 9999999}
        else:
            # 일반 회원 제한: 하루 20개, 한달 500개
            plan_limits = {"daily": DAILY_IMAGE_LIMIT, "monthly": MONTHLY_IMAGE_LIMIT}
            
            # 일일 제한 체크
            if user_data.get("daily_image_count", 0) >= DAILY_IMAGE_LIMIT:
                return {
                    "allowed": False,
                    "reason": f"일일 이미지 생성 한도({DAILY_IMAGE_LIMIT}장)를 초과했습니다. 내일 다시 시도해주세요.",
                    "usage": user_data,
                    "limits": plan_limits
                }
            
            # 월간 제한 체크
            if user_data.get("monthly_image_count", 0) >= MONTHLY_IMAGE_LIMIT:
                return {
                    "allowed": False,
                    "reason": f"월간 이미지 생성 한도({MONTHLY_IMAGE_LIMIT}장)를 초과했습니다. 다음 달에 다시 시도해주세요.",
                    "usage": user_data,
                    "limits": plan_limits
                }
        
        return {
            "allowed": True,
            "reason": "OK",
            "usage": user_data,
            "limits": plan_limits,
            "is_admin": is_admin
        }
        
    except Exception as e:
        logging.error(f"Permission check failed: {e}")
        return {
            "allowed": False,
            "reason": f"권한 확인 중 오류: {str(e)}",
            "usage": {}
        }


def increment_usage(uid: str, count: int = 1):
    """이미지 사용량 증가"""
    try:
        db = get_db()
        user_ref = db.collection("users").document(uid)
        user_ref.update({
            "daily_image_count": firestore.Increment(count),
            "monthly_image_count": firestore.Increment(count)
        })
    except Exception as e:
        logging.error(f"Failed to increment usage: {e}")


# ============================================
# 동적 프롬프트 생성 시스템
# ============================================

def get_dynamic_context():
    """실시간 컨텍스트 생성 - 매 요청마다 다른 변수"""
    now = datetime.now()
    
    # 요일별 테마
    weekday_themes = {
        0: "주말 드라이브 준비",  # 월요일
        1: "자동차 관리 팁",
        2: "중고차 시장 동향", 
        3: "신차 소식",
        4: "주말 여행 준비",  # 금요일
        5: "가족 나들이",  # 토요일
        6: "다음 주 준비"  # 일요일
    }
    
    # 계절별 키워드
    month = now.month
    if month in [3, 4, 5]:
        season = "봄"
        season_keywords = ["봄맞이 세차", "황사 대비", "에어컨 점검", "봄나들이", "꽃구경 드라이브"]
    elif month in [6, 7, 8]:
        season = "여름"
        season_keywords = ["에어컨 관리", "장마철 대비", "여름휴가 차량점검", "타이어 공기압", "냉각수 점검"]
    elif month in [9, 10, 11]:
        season = "가을"
        season_keywords = ["단풍 드라이브", "가을철 차량관리", "겨울 대비", "히터 점검", "부동액 교체"]
    else:
        season = "겨울"
        season_keywords = ["동절기 관리", "스노우타이어", "배터리 점검", "결빙 주의", "워셔액 보충"]
    
    # 관점/앵글 다양화
    perspectives = [
        "비용 절감 관점",
        "초보 운전자 관점",
        "가족 중심 관점",
        "성능/퍼포먼스 관점",
        "친환경/전기차 관점",
        "안전 중심 관점",
        "중고차 구매자 관점",
        "장거리 운전자 관점",
        "출퇴근 운전자 관점",
        "주말 드라이버 관점"
    ]
    
    # 콘텐츠 유형 다양화
    content_types = [
        "비교 분석 (A vs B)",
        "체크리스트/가이드",
        "흔한 실수와 해결법",
        "숨겨진 팁 공개",
        "실제 경험담 기반",
        "전문가 인터뷰 형식",
        "Q&A 형식",
        "타임라인/순서 가이드",
        "비용 분석표",
        "before/after 비교"
    ]
    
    # 세부 카테고리 (자동차)
    sub_categories = [
        "신차 정보", "중고차 팁", "자동차 관리", "보험/금융",
        "튜닝/액세서리", "전기차/하이브리드", "수입차", "국산차",
        "SUV/RV", "세단", "경차", "상용차",
        "자동차 여행", "드라이브 코스", "주차 팁", "운전 습관",
        "자동차 세금", "명의이전", "폐차", "리스/렌트"
    ]
    
    return {
        "date": now.strftime("%Y년 %m월 %d일"),
        "weekday": ["월", "화", "수", "목", "금", "토", "일"][now.weekday()],
        "weekday_theme": weekday_themes[now.weekday()],
        "season": season,
        "season_keyword": random.choice(season_keywords),
        "perspective": random.choice(perspectives),
        "content_type": random.choice(content_types),
        "sub_category": random.choice(sub_categories),
        "hour": now.hour,
        "random_seed": random.randint(1, 1000)  # 추가 랜덤성
    }


# 카테고리별 키워드 및 예시 정의
CATEGORY_CONFIG = {
    "차량 관리 상식": {
        "keywords": ["엔진오일 교체", "타이어 관리", "와이퍼 교체", "배터리 점검", "냉각수", "브레이크 패드", "에어컨 필터", "세차", "광택", "부식 방지"],
        "examples": ["엔진오일 5,000km vs 10,000km 교체, 정답은?", "타이어 마모 한계선, 직접 확인하는 3가지 방법", "겨울철 배터리 방전 예방, 이것만 알면 OK"]
    },
    "자동차 보험/사고처리": {
        "keywords": ["자동차보험", "사고 접수", "과실비율", "블랙박스", "렌터카 특약", "자기부담금", "보험료 할인", "무보험 사고", "대물배상", "대인배상"],
        "examples": ["내 과실 0%인데 보험료 오른다? 진실 공개", "블랙박스 없이 사고 났을 때 과실비율 정하는 법", "자동차보험 갱신 전 꼭 확인해야 할 3가지"]
    },
    "리스/렌트/할부 금융": {
        "keywords": ["자동차 리스", "장기렌트", "할부 금융", "잔존가치", "선납금", "보증금", "리스료", "렌트료", "신용등급", "중도해지"],
        "examples": ["리스 vs 렌트 vs 할부, 내 상황에 맞는 선택은?", "장기렌트 3년 후 인수 vs 반납, 뭐가 이득?", "자동차 할부 금리 비교, 캐피탈별 실제 이자율"]
    },
    "교통법규/범칙금": {
        "keywords": ["속도위반", "신호위반", "주정차 위반", "음주운전", "무면허", "범칙금", "과태료", "벌점", "면허정지", "면허취소"],
        "examples": ["범칙금 vs 과태료, 뭐가 다르고 뭐가 더 불리할까?", "2026년 바뀐 교통법규 총정리", "어린이보호구역 속도위반, 벌점과 벌금은?"]
    },
    "자동차 여행 코스": {
        "keywords": ["드라이브 코스", "자동차 여행", "차박", "오토캠핑", "휴게소 맛집", "해안도로", "단풍 드라이브", "벚꽃 드라이브", "야경 드라이브", "국도 여행"],
        "examples": ["서울 근교 2시간 드라이브 코스 TOP 5", "차박 초보를 위한 장비 리스트와 추천 장소", "겨울 야경 드라이브, 수도권 베스트 코스"]
    },
    "전기차 라이프": {
        "keywords": ["전기차 충전", "충전소", "보조금", "주행거리", "배터리 관리", "테슬라", "아이오닉", "EV6", "충전요금", "완속충전", "급속충전"],
        "examples": ["2026년 전기차 보조금 변경사항 총정리", "전기차 겨울철 주행거리 줄어드는 이유와 대처법", "아파트 전기차 충전, 설치부터 요금까지"]
    },
    "중고차 거래 팁": {
        "keywords": ["중고차 시세", "허위매물", "침수차 확인", "사고차 확인", "중고차 딜러", "직거래", "중고차 감가", "중고차 계약", "명의이전", "이전비용"],
        "examples": ["중고차 허위매물 구별하는 5가지 방법", "침수차 확인법, 이 부분만 보면 바로 알 수 있다", "2026년 중고차 시세 전망, 지금 사야 할까?"]
    }
}

def build_dynamic_recommend_prompt(category: str, context: dict) -> str:
    """2단계 동적 프롬프트 생성 - 카테고리 강제 적용"""
    
    # 카테고리 설정 가져오기 (없으면 기본값)
    cat_config = CATEGORY_CONFIG.get(category, {
        "keywords": ["자동차"],
        "examples": ["자동차 관련 주제"]
    })
    
    keywords_str = ", ".join(cat_config["keywords"][:5])
    examples_str = "\n    ".join([f'- "{ex}"' for ex in cat_config["examples"]])
    
    prompt = f"""
    [🎯 중요: 카테고리 제한]
    **반드시 "{category}" 카테고리에 해당하는 주제만 생성하세요!**
    관련 키워드: {keywords_str}
    
    다른 카테고리 주제는 절대 포함하지 마세요.
    예를 들어 "{category}"를 선택했으면:
    - ❌ 일반적인 자동차 관리 → 포함 금지
    - ❌ 다른 카테고리 주제 → 포함 금지  
    - ✅ "{category}" 관련 구체적 주제만 → 필수
    
    [CONTEXT - 오늘의 조건]
    - 오늘 날짜: {context['date']} ({context['weekday']}요일)
    - 계절: {context['season']}
    - 오늘의 테마: {context['weekday_theme']}
    - 계절 키워드: {context['season_keyword']}
    
    [TASK 1] Google 검색으로 "{category}" 관련 최신 정보를 조사하세요:
    1. "{category}" 관련 최신 뉴스나 이슈
    2. 네이버/구글에서 "{category}" 인기 검색어
    3. "{category}" 관련 커뮤니티 화제 주제
    4. {context['season']}철 "{category}" 관련 관심사
    
    [TASK 2] 조사 결과를 바탕으로 "{category}" 블로그 주제 5개를 추천하세요.
    
    ["{category}" 카테고리 좋은 예시]
    {examples_str}
    
    [필수 조건]
    - 5개 주제 모두 반드시 "{category}" 카테고리 범위 내에서만
    - 콘텐츠 유형: {context['content_type']} 스타일 1개 이상
    - 타깃 관점: {context['perspective']}에서 1개 이상
    - 계절감: {context['season']}철 관련 1개 포함
    - 구체적인 숫자, 상황이 포함된 제목
    - 클릭을 유도하는 호기심 자극 제목
    
    [금지 사항]
    - "{category}"와 관련 없는 일반 자동차 주제
    - "~하는 방법", "~팁" 같은 뻔한 제목
    - 너무 광범위한 주제
    
    반드시 아래 JSON 형식으로만 응답하세요:
    {{"topics": ["주제1", "주제2", "주제3", "주제4", "주제5"], "trend_keywords": ["검색에서 발견한 트렌드 키워드 3개"]}}
    """
    
    return prompt


def convert_topic_to_visual_description(client, model_name: str, topic: str) -> str:
    """
    한국어 주제를 영어 시각적 설명으로 변환
    이미지 생성 시 한국어 텍스트가 이미지에 들어가는 것을 방지
    """
    try:
        conversion_prompt = f"""
You are a visual description translator. Convert the following Korean blog topic into a detailed English visual description for image generation.

Korean topic: {topic}

IMPORTANT RULES:
1. DO NOT include any text, words, or letters in the description
2. Describe only VISUAL ELEMENTS: objects, scenes, colors, composition, mood
3. Focus on what can be PHOTOGRAPHED or ILLUSTRATED
4. Be specific about visual details (lighting, angle, atmosphere)
5. Output ONLY the English visual description, nothing else

Example:
- Input: "겨울철 와이퍼 관리법"
- Output: "A car windshield with clean wiper blades on a snowy winter day, frost crystals on glass, cold blue morning light, close-up angle showing the rubber blade detail"

- Input: "엔진오일 교체주기"
- Output: "A mechanic's gloved hand pouring golden engine oil from a bottle into a car engine, workshop setting with warm lighting, oil droplets catching light, clean professional environment"

Now convert this topic into a visual description:
"""
        
        resp = client.models.generate_content(
            model=model_name,
            contents=conversion_prompt,
            config=types.GenerateContentConfig(
                temperature=0.3  # 낮은 온도로 일관된 결과
            )
        )
        
        visual_desc = resp.text.strip()
        logging.info(f"Topic '{topic}' converted to visual: {visual_desc[:100]}...")
        return visual_desc
        
    except Exception as e:
        logging.error(f"Failed to convert topic to visual description: {e}")
        # 실패 시 기본 설명 반환
        return f"Professional photograph related to automotive topic, clean composition, natural lighting"


@https_fn.on_request(
    region="asia-northeast3", 
    timeout_sec=300, 
    secrets=["GEMINI_API_KEY"],
    cors=CorsOptions(cors_origins="*", cors_methods=["GET", "POST", "OPTIONS"])
)
def generate_blog_post(req: https_fn.Request) -> https_fn.Response:
    """메인 API 엔드포인트"""
    
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        return https_fn.Response("Server Error: Gemini API Key not configured.", status=500)

    client = genai.Client(api_key=gemini_key)

    req_json = req.get_json(silent=True)
    if not req_json:
        return https_fn.Response("Bad Request", status=400)

    mode = req_json.get("mode", "write")
    MODEL_NAME = "gemini-2.0-flash"
    IMAGE_MODEL_NAME = "gemini-2.0-flash-exp-image-generation"

    try:
        # ============================================
        # [모드 0] 회원가입 시 Firestore 문서 생성 (인증 토큰으로)
        # ============================================
        if mode == "register_user":
            # 토큰 검증
            user = verify_user_token(req)
            if not user:
                return https_fn.Response(
                    json.dumps({"error": "유효하지 않은 토큰입니다."}),
                    status=401,
                    mimetype="application/json"
                )
            
            uid = user["uid"]
            email = user.get("email", "")
            
            try:
                db = get_db()
                user_ref = db.collection("users").document(uid)
                user_doc = user_ref.get()
                
                if user_doc.exists:
                    # 이미 문서가 있으면 그냥 반환
                    return https_fn.Response(
                        json.dumps({"success": True, "message": "이미 등록된 사용자입니다.", "uid": uid}),
                        status=200,
                        mimetype="application/json"
                    )
                
                # 새 사용자 문서 생성
                user_data = {
                    "email": email,
                    "created_at": datetime.now(),
                    "is_active": False,  # 관리자 승인 필요
                    "is_admin": False,
                    "daily_image_count": 0,
                    "monthly_image_count": 0,
                    "last_reset_date": datetime.now().strftime("%Y-%m-%d"),
                    "last_reset_month": datetime.now().strftime("%Y-%m")
                }
                user_ref.set(user_data)
                
                return https_fn.Response(
                    json.dumps({
                        "success": True, 
                        "message": "회원가입 완료! 관리자 승인 후 이용 가능합니다.",
                        "uid": uid,
                        "contact": "https://open.kakao.com/o/sgbYdyai"
                    }),
                    status=200,
                    mimetype="application/json"
                )
                
            except Exception as e:
                logging.error(f"Register user failed: {e}")
                return https_fn.Response(
                    json.dumps({"error": f"사용자 등록 실패: {str(e)}"}),
                    status=500,
                    mimetype="application/json"
                )

        # ============================================
        # [모드 1] 주제 추천 (동적 프롬프트 + Grounding)
        # ============================================
        elif mode == "recommend":
            category = req_json.get("category", "자동차")
            
            # 동적 컨텍스트 생성
            context = get_dynamic_context()
            
            # 동적 프롬프트 생성
            prompt = build_dynamic_recommend_prompt(category, context)
            
            logging.info(f"Recommend request - context: {context['sub_category']}, {context['perspective']}, seed: {context['random_seed']}")
            
            # Grounding with Google Search
            resp = client.models.generate_content(
                model=MODEL_NAME, 
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.9  # 더 창의적인 응답
                )
            )
            
            # 응답에서 JSON 추출
            raw_text = resp.text.replace("```json", "").replace("```", "").strip()
            
            # JSON 객체만 추출 (첫 번째 { 부터 마지막 } 까지)
            try:
                start_idx = raw_text.find('{')
                end_idx = raw_text.rfind('}') + 1
                if start_idx != -1 and end_idx > start_idx:
                    json_str = raw_text[start_idx:end_idx]
                    parsed = json.loads(json_str)
                    
                    # 응답에 컨텍스트 정보 추가 (디버깅/참고용)
                    parsed["context"] = {
                        "date": context["date"],
                        "theme": context["weekday_theme"],
                        "season": context["season"],
                        "perspective": context["perspective"]
                    }
                    
                    return https_fn.Response(
                        json.dumps(parsed), 
                        status=200, 
                        mimetype="application/json"
                    )
                else:
                    # JSON 형식이 아니면 기본값 반환
                    return https_fn.Response(
                        json.dumps({"topics": ["주제를 다시 생성해주세요"]}), 
                        status=200, 
                        mimetype="application/json"
                    )
            except json.JSONDecodeError as e:
                logging.error(f"JSON parse error in recommend: {e}, raw: {raw_text[:500]}")
                return https_fn.Response(
                    json.dumps({"topics": ["주제 생성 중 오류가 발생했습니다. 다시 시도해주세요."]}), 
                    status=200, 
                    mimetype="application/json"
                )

        # ============================================
        # [모드 2] 주제 분석 (Grounding 적용)
        # ============================================
        elif mode == "analyze":
            topic = req_json.get("topic", "")
            
            # 동적 컨텍스트
            context = get_dynamic_context()
            
            prompt = f"""
            주제 '{topic}'에 대한 심층 마케팅 분석을 해주세요.
            
            [오늘의 컨텍스트]
            - 날짜: {context['date']} ({context['weekday']}요일)
            - 계절: {context['season']}
            
            Google 검색으로 최신 정보를 조사하여 다음을 분석해주세요:
            
            1. 타깃 독자층 (4~5개)
               - 구체적인 상황/니즈 포함 (예: "첫 차 구매 고민 중인 사회초년생")
            
            2. 독자들이 실제로 궁금해하는 질문 (6~8개)
               - 네이버 지식인, 자동차 커뮤니티에서 실제로 묻는 질문
               - 구체적인 상황이 담긴 질문
            
            3. 반드시 포함해야 할 핵심 정보 (6~8개)
               - 최신 데이터, 가격, 비교 정보 포함
               - {context['season']}철 관련 정보 1개 이상
            
            반드시 아래 JSON 형식으로만 응답하세요:
            {{"targets": ["타깃1 (상황 설명)", "타깃2", ...], "questions": ["구체적 질문1", "질문2", ...], "key_points": ["핵심정보1 (수치 포함)", "포인트2", ...]}}
            """
            
            resp = client.models.generate_content(
                model=MODEL_NAME, 
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                )
            )
            
            # 응답에서 JSON 추출
            raw_text = resp.text.replace("```json", "").replace("```", "").strip()
            
            try:
                start_idx = raw_text.find('{')
                end_idx = raw_text.rfind('}') + 1
                if start_idx != -1 and end_idx > start_idx:
                    json_str = raw_text[start_idx:end_idx]
                    parsed = json.loads(json_str)
                    return https_fn.Response(
                        json.dumps(parsed), 
                        status=200, 
                        mimetype="application/json"
                    )
                else:
                    return https_fn.Response(
                        json.dumps({"targets": [], "questions": [], "key_points": []}), 
                        status=200, 
                        mimetype="application/json"
                    )
            except json.JSONDecodeError as e:
                logging.error(f"JSON parse error in analyze: {e}, raw: {raw_text[:500]}")
                return https_fn.Response(
                    json.dumps({"targets": [], "questions": [], "key_points": []}), 
                    status=200, 
                    mimetype="application/json"
                )

        # ============================================
        # [모드 3] 이미지 생성 (인증 필요)
        # ============================================
        elif mode == "generate_image":
            # 사용자 인증 체크
            user = verify_user_token(req)
            if not user:
                return https_fn.Response(
                    json.dumps({"error": "인증이 필요합니다. 로그인 후 이용해주세요."}),
                    status=401,
                    mimetype="application/json"
                )
            
            # 권한 및 사용량 체크
            permission = check_user_permission(user["uid"])
            if not permission["allowed"]:
                return https_fn.Response(
                    json.dumps({
                        "error": permission["reason"],
                        "usage": permission["usage"]
                    }),
                    status=403,
                    mimetype="application/json"
                )
            
            # 이미지 생성 프롬프트
            image_prompt = req_json.get("prompt", "")
            style = req_json.get("style", "블로그 썸네일")
            
            if not image_prompt:
                return https_fn.Response(
                    json.dumps({"error": "이미지 설명(prompt)이 필요합니다."}),
                    status=400,
                    mimetype="application/json"
                )
            
            # 2단계 프롬프트 생성: 먼저 주제를 시각적 설명으로 변환
            # 한국어 주제가 이미지에 텍스트로 들어가는 것을 방지
            visual_description = convert_topic_to_visual_description(client, MODEL_NAME, image_prompt)
            
            # 스타일별 프롬프트 구성 - 텍스트 제거 강화
            base_no_text_instruction = """
CRITICAL REQUIREMENTS:
- ABSOLUTELY NO TEXT, LETTERS, WORDS, NUMBERS, SYMBOLS, or CHARACTERS of any kind in the image
- Do NOT render any Korean, English, Chinese, or any language text
- Do NOT include any typography, labels, watermarks, or signs
- Pure visual imagery only - photograph style without any overlays
- If you feel tempted to add text, DO NOT - leave that space empty or fill with visual elements
"""
            
            style_prompts = {
                "블로그 썸네일": f"""
{base_no_text_instruction}

Create a professional blog thumbnail photograph.
Visual concept: {visual_description}
Style: Clean, modern, minimal design with soft natural colors. Professional photography with shallow depth of field. 16:9 landscape aspect ratio.
Mood: Professional, inviting, trustworthy.

REMINDER: NO TEXT WHATSOEVER in the image.
""",
                "블로그 대표 썸네일, 텍스트 없이, 주제를 잘 나타내는 시각적 이미지, 16:9 가로 비율": f"""
{base_no_text_instruction}

Create a beautiful, eye-catching blog thumbnail photograph.
Visual concept: {visual_description}
Style: Professional photography, vibrant but balanced colors, clean composition.
Aspect ratio: 16:9 landscape (wide format).
Lighting: Natural, soft lighting with gentle shadows.

REMINDER: ZERO TEXT - this means no letters, no words, no numbers, no symbols. Pure photography only.
""",
                "블로그 본문 삽화, 텍스트 없이, 심플하고 깔끔한 일러스트레이션": f"""
{base_no_text_instruction}

Create a simple, clean illustration.
Visual concept: {visual_description}
Style: Flat design, minimal modern illustration. Soft pastel colors.
Format: Square composition.

REMINDER: NO TEXT - pure illustration only, no labels or captions.
""",
                "자동차": f"""
{base_no_text_instruction}

Create a professional automotive photograph.
Visual concept: {visual_description}
Style: Sleek, modern car photography. Studio or outdoor setting with professional lighting.
Mood: Premium, sophisticated.

REMINDER: NO TEXT on the image - no brand names, no labels, no overlays.
""",
                "출고 후기": f"""
{base_no_text_instruction}

Create a warm car delivery celebration photograph.
Visual concept: {visual_description}
Style: Candid photography style. Happy moment of receiving a new car.
Mood: Bright, positive, celebratory.

REMINDER: NO TEXT - no dealership names, no signs, no congratulation text.
""",
                "인포그래픽": f"""
{base_no_text_instruction}

Create a visual infographic-style image using only icons and visual elements.
Visual concept: {visual_description}
Style: Clean icons, visual diagrams, flowchart shapes WITHOUT any text labels.
Use arrows, shapes, and pictograms to convey information visually.

REMINDER: NO TEXT - use only visual symbols, icons, and shapes. No labels or captions.
"""
            }
            
            full_prompt = style_prompts.get(style, style_prompts["블로그 썸네일"])
            
            try:
                response = client.models.generate_content(
                    model=IMAGE_MODEL_NAME,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=['Text', 'Image']
                    )
                )
                
                # 응답에서 이미지 추출
                for part in response.candidates[0].content.parts:
                    if part.inline_data is not None:
                        image_base64 = base64.b64encode(part.inline_data.data).decode('utf-8')
                        
                        # 사용량 증가
                        increment_usage(user["uid"], 1)
                        
                        return https_fn.Response(
                            json.dumps({
                                "success": True,
                                "image_base64": image_base64,
                                "mime_type": "image/png",
                                "usage": {
                                    "daily_used": permission["usage"].get("daily_image_count", 0) + 1,
                                    "daily_limit": permission["limits"]["daily"],
                                    "monthly_used": permission["usage"].get("monthly_image_count", 0) + 1,
                                    "monthly_limit": permission["limits"]["monthly"]
                                }
                            }),
                            status=200,
                            mimetype="application/json"
                        )
                
                return https_fn.Response(
                    json.dumps({"error": "이미지 생성 결과가 없습니다."}),
                    status=500,
                    mimetype="application/json"
                )
                
            except Exception as img_error:
                logging.error(f"Image generation failed: {img_error}")
                return https_fn.Response(
                    json.dumps({"error": f"이미지 생성 실패: {str(img_error)}"}),
                    status=500,
                    mimetype="application/json"
                )

        # ============================================
        # [모드 4] 사용자 정보 조회
        # ============================================
        elif mode == "user_info":
            user = verify_user_token(req)
            if not user:
                return https_fn.Response(
                    json.dumps({"error": "인증이 필요합니다."}),
                    status=401,
                    mimetype="application/json"
                )
            
            permission = check_user_permission(user["uid"])
            
            return https_fn.Response(
                json.dumps({
                    "uid": user["uid"],
                    "email": user["email"],
                    "is_active": permission["usage"].get("is_active", False),
                    "plan": permission["usage"].get("plan", "free"),
                    "usage": {
                        "daily_image_count": permission["usage"].get("daily_image_count", 0),
                        "monthly_image_count": permission["usage"].get("monthly_image_count", 0)
                    }
                }),
                status=200,
                mimetype="application/json"
            )

        # ============================================
        # [모드 5] 본문 기반 삽화 프롬프트 생성
        # ============================================
        elif mode == "generate_illustration_prompts":
            content = req_json.get("content", "")
            count = req_json.get("count", 2)
            
            if not content:
                return https_fn.Response(
                    json.dumps({"error": "본문 내용이 필요합니다."}),
                    status=400,
                    mimetype="application/json"
                )
            
            # 다양한 이미지 스타일 목록
            styles = [
                "realistic photo style",
                "minimalist flat illustration",
                "isometric 3D style",
                "watercolor painting style",
                "infographic diagram style"
            ]
            style_list = ", ".join(styles[:count])
            
            prompt = f"""
            다음 블로그 글의 본문을 분석하여 삽화 이미지 {count}개를 위한 프롬프트를 생성해주세요.
            
            [본문]
            {content[:3000]}
            
            요구사항:
            - 각 삽화는 본문의 서로 다른 섹션/주제를 시각화
            - 이미지에 텍스트나 글자가 절대 들어가지 않도록 명시
            - 각 이미지는 서로 다른 스타일로 생성 (예: {style_list})
            - 블로그 글의 이해를 돕는 구체적인 시각 자료
            - 프롬프트는 영어로 작성, 구체적이고 상세하게 (50단어 이상)
            - 각 프롬프트 끝에 "NO TEXT, NO LETTERS, NO WORDS" 필수 포함
            
            반드시 아래 JSON 형식으로만 응답하세요:
            {{"prompts": ["삽화1 영어 상세 설명 (스타일 포함)", "삽화2 영어 상세 설명 (다른 스타일)"], "positions": ["서론 후", "중반", "결론 전"]}}
            """
            
            resp = client.models.generate_content(
                model=MODEL_NAME, 
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            
            raw_text = resp.text.replace("```json", "").replace("```", "").strip()
            
            try:
                start_idx = raw_text.find('{')
                end_idx = raw_text.rfind('}') + 1
                if start_idx != -1 and end_idx > start_idx:
                    json_str = raw_text[start_idx:end_idx]
                    parsed = json.loads(json_str)
                    return https_fn.Response(
                        json.dumps(parsed), 
                        status=200, 
                        mimetype="application/json"
                    )
                else:
                    return https_fn.Response(
                        json.dumps({"prompts": [], "positions": []}), 
                        status=200, 
                        mimetype="application/json"
                    )
            except json.JSONDecodeError as e:
                logging.error(f"JSON parse error in illustration prompts: {e}")
                return https_fn.Response(
                    json.dumps({"prompts": [], "positions": []}), 
                    status=200, 
                    mimetype="application/json"
                )

        # ============================================
        # [모드 6] 글 작성 (Grounding 적용 - 최신 정보 반영)
        # ============================================
        else:
            topic = req_json.get("topic", "")
            tone = req_json.get("tone", "친근한 이웃 (해요체)")
            length = req_json.get("length", "보통 (1,500자)")
            emoji_level = req_json.get("emoji_level", "사용 안 함")
            targets = req_json.get("targets", [])
            questions = req_json.get("questions", [])
            summary = req_json.get("summary", "")
            insight = req_json.get("insight", "")
            
            # 인사말/마무리말 (prompt에서 추출)
            prompt_text = req_json.get("prompt", "")
            intro = ""
            outro = ""
            if "인사말:" in prompt_text:
                try:
                    intro_part = prompt_text.split("인사말:")[1]
                    intro = intro_part.split("맺음말:")[0].strip() if "맺음말:" in intro_part else intro_part.strip()
                except:
                    pass
            if "맺음말:" in prompt_text:
                try:
                    outro = prompt_text.split("맺음말:")[1].strip()
                except:
                    pass
            
            # 출력 스타일 설정
            output_style = req_json.get("output_style", {})
            if isinstance(output_style, list):
                output_style = {}
            
            text_style = output_style.get("text", {}) if isinstance(output_style, dict) else {}
            md_style = output_style.get("markdown", {}) if isinstance(output_style, dict) else {}
            html_style = output_style.get("html", {}) if isinstance(output_style, dict) else {}
            
            # 이미지 정보 처리 (호환성)
            images = req_json.get("images", {})
            if isinstance(images, list):
                images = {"thumbnail": None, "illustrations": images}
            
            # 타깃 문자열 처리
            target_str = ""
            if targets:
                if isinstance(targets, list):
                    target_str = ", ".join(targets)
                else:
                    target_str = str(targets)
            
            # 분량 파싱
            char_count = "1500"
            if "2,000" in length or "2000" in length:
                char_count = "2000"
            elif "2,500" in length or "2500" in length:
                char_count = "2500"
            
            # 이모지 사용 여부
            use_emoji = "조금" in emoji_level or "많이" in emoji_level
            emoji_instruction = "이모지 적절히 사용" if use_emoji else "이모지 사용하지 마세요. 텍스트만 사용하세요."
            
            # 인사말/마무리말 프롬프트 구성
            intro_instruction = f"[인사말] 다음 인사말로 글을 시작하세요: \"{intro}\"" if intro else ""
            outro_instruction = f"[마무리말] 다음 맺음말로 글을 마무리하세요: \"{outro}\"" if outro else ""
            
            full_prompt = f"""
            [ROLE] 네이버 자동차 파워 블로거
            당신은 자동차에 대해 깊은 지식을 가진 전문 블로거입니다.
            최신 정보를 검색하여 정확하고 신뢰할 수 있는 정보를 제공하세요.
            
            [TOPIC] {topic}
            
            [STYLE]
            - 말투: {tone}
            - 분량: {char_count}자 이상
            - {emoji_instruction}
            - 타깃 독자: {target_str}
            
            {intro_instruction}
            
            [QUESTIONS TO ANSWER]
            {chr(10).join([f"- {q}" for q in questions]) if questions else "없음"}
            
            [KEY POINTS]
            {summary if summary else "없음"}
            
            [PERSONAL INSIGHT]
            {insight if insight else "없음"}
            
            {outro_instruction}
            
            [OUTPUT STYLE PREFERENCES]
            TEXT 형식: 소제목={text_style.get('heading', '【 】 대괄호')}, 강조={text_style.get('emphasis', '** 별표 **')}
            Markdown 형식: 헤딩={md_style.get('heading', '## H2 사용')}, Q&A={md_style.get('qa', '> 인용문 스타일')}
            HTML 형식: 제목={html_style.get('title', '<h2> 태그')}, 색상={html_style.get('color', '네이버 그린 (#03C75A)')}
            - HTML에서는 이모지를 절대 사용하지 마세요!
            
            [OUTPUT FORMAT - STRICT JSON]
            반드시 아래 형식의 JSON을 출력하세요:
            {{
                "title": "SEO 최적화된 매력적인 제목",
                "content": "본문 전체 (줄바꿈 포함)",
                "content_text": "TEXT 형식 본문 (위 스타일 적용)",
                "content_md": "Markdown 형식 본문",
                "content_html": "HTML 형식 본문"
            }}
            
            [IMPORTANT]
            - 최신 정보와 실제 데이터를 검색하여 포함
            - 실용적이고 구체적인 정보 제공
            - 독자가 바로 활용할 수 있는 팁 포함
            - 최소 {char_count}자 이상 작성
            """

            # Grounding with Google Search로 최신 정보 반영
            resp = client.models.generate_content(
                model=MODEL_NAME, 
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                )
            )
            
            raw_text = resp.text.replace("```json", "").replace("```", "").strip()
            
            # JSON 객체 추출
            try:
                start_idx = raw_text.find('{')
                end_idx = raw_text.rfind('}') + 1
                if start_idx != -1 and end_idx > start_idx:
                    json_str = raw_text[start_idx:end_idx]
                    data = json.loads(json_str)
                else:
                    raise json.JSONDecodeError("No JSON found", raw_text, 0)
                
                # content 키 호환성 처리
                if "content" not in data:
                    data["content"] = data.get("content_text", data.get("body", "내용 생성 실패"))
                if "content_text" not in data:
                    data["content_text"] = data.get("content", "")
                if "content_md" not in data: 
                    data["content_md"] = data["content_text"]
                if "content_html" not in data: 
                    data["content_html"] = f"<p>{data['content_text']}</p>"
                
                return https_fn.Response(
                    json.dumps(data), 
                    status=200, 
                    mimetype="application/json"
                )
                
            except json.JSONDecodeError as e:
                logging.error(f"JSON parse error in write: {e}, raw: {raw_text[:500]}")
                return https_fn.Response(json.dumps({
                    "title": f"{topic}",
                    "content": raw_text,
                    "content_text": raw_text,
                    "content_md": raw_text,
                    "content_html": f"<pre>{raw_text}</pre>"
                }), status=200, mimetype="application/json")

    except Exception as e:
        logging.error(f"API Error: {e}")
        return https_fn.Response(f"Server Error: {str(e)}", status=500)
