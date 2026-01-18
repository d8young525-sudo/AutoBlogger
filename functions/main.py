import os
import json
from firebase_functions import https_fn
from firebase_admin import initialize_app
from google import genai
from google.genai import types

initialize_app()

# 자동차 전문 블로그 카테고리 (앱 브라우저와 동기화 필요)
SUPPORTED_CATEGORIES = {
    "차량관리 상식": "차량 관리, 엔진오일, 타이어, 소모품 교체, 세차, 정비, 점검",
    "자동차보험/사고처리": "자동차보험, 보험료, 사고 처리, 과실비율, 보상, 렌트비",
    "리스/렌트/할부/금융": "자동차 리스, 장기렌트, 할부, 오토론, 금융, 잔존가치",
    "교통법규/범칙금": "교통법규, 범칙금, 과태료, 음주운전, 신호위반, 주정차",
    "자동차여행코스": "자동차 여행, 드라이브 코스, 차박, 캠핑, 휴게소, 국내여행",
    "전기차 라이프": "전기차, 충전소, 보조금, 테슬라, 아이오닉, EV6, 배터리",
    "중고차 거래팁": "중고차, 시세, 매매, 허위매물, 성능점검, 이전등록, 감가",
}

DEFAULT_CATEGORY = "차량관리 상식"

# Google Search Grounding 도구 설정
def get_grounding_tool():
    """Google Search Grounding 도구 반환"""
    return types.Tool(google_search=types.GoogleSearch())


@https_fn.on_request(region="asia-northeast3", timeout_sec=300, secrets=["GEMINI_API_KEY"])
def generate_blog_post(req: https_fn.Request) -> https_fn.Response:
    # 1. API Key Validation
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        return https_fn.Response("Server Error: Gemini API Key not configured.", status=500)

    # 2. Client Initialization (New SDK)
    client = genai.Client(api_key=gemini_key)

    req_json = req.get_json(silent=True)
    if not req_json:
        return https_fn.Response("Bad Request", status=400)

    mode = req_json.get("mode", "write")
    
    # 카테고리 검증 및 기본값 설정
    category = req_json.get("category", "").strip()
    if not category or category not in SUPPORTED_CATEGORIES:
        category = DEFAULT_CATEGORY
    
    category_keywords = SUPPORTED_CATEGORIES.get(category, category)
    
    # Using Gemini 3.0 Flash as requested
    MODEL_NAME = "gemini-3-flash-preview"

    try:
        # [Mode 1] Topic Recommendation - Google Search Grounding으로 실시간 트렌드 기반 주제 추천
        if mode == "recommend":
            # Step 1: Google Search Grounding으로 최신 트렌드 검색
            trend_prompt = f"""
            "{category}" 관련 최신 뉴스, 트렌드, 이슈를 검색해서 알려주세요.
            
            검색 키워드: {category_keywords}
            
            최근 1개월 내 화제가 된 내용, 법규 변경, 신제품 출시, 시즌 이슈 등을 중심으로 알려주세요.
            """
            
            # Grounding으로 실시간 트렌드 검색
            grounding_response = client.models.generate_content(
                model=MODEL_NAME,
                contents=trend_prompt,
                config=types.GenerateContentConfig(
                    tools=[get_grounding_tool()]
                )
            )
            
            # 검색된 트렌드 정보 추출
            trend_info = grounding_response.text
            
            # Step 2: 트렌드 기반으로 블로그 주제 생성
            topic_prompt = f"""
            당신은 네이버 자동차 블로그 콘텐츠 전략가입니다.
            
            [카테고리]
            {category}
            
            [최신 트렌드 정보 (Google 검색 결과)]
            {trend_info}
            
            [요청사항]
            위 최신 트렌드를 바탕으로 네이버 블로그에 올릴 주제를 5개 추천해주세요.
            
            [조건]
            1. 위 트렌드 정보를 반영한 시의성 있는 주제
            2. 네이버 검색량이 높을 것으로 예상되는 주제  
            3. 클릭을 유도하는 구체적이고 매력적인 제목 형태
            4. 일반인이 검색할 법한 실용적인 주제
            5. 각 주제는 30자 내외로 명확하게
            
            [출력 형식]
            반드시 JSON 형식으로만 출력 (key: topics, value: 문자열 배열)
            예시: {{"topics": ["주제1", "주제2", "주제3", "주제4", "주제5"]}}
            """
            
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=topic_prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return https_fn.Response(response.text.replace("```json", "").replace("```", "").strip(), status=200, mimetype="application/json")

        # [Mode 2] Topic Analysis - 주제 분석 및 키워드 추출
        elif mode == "analyze":
            topic = req_json.get("topic", "")
            prompt = f"""
            당신은 블로그 마케팅 전문가입니다.
            
            [카테고리]
            {category}
            
            [주제]
            {topic}
            
            [분석 요청]
            위 주제에 대해 블로그 마케팅 관점에서 분석해주세요.
            
            [출력 형식]
            JSON 형식으로 다음 키를 포함:
            - targets: 타겟 독자층 (배열)
            - questions: 독자들이 궁금해할 질문 (배열)
            - key_points: 반드시 포함해야 할 핵심 포인트 (배열)
            - keywords: SEO 키워드 (배열)
            - related_topics: 연관 주제 (배열)
            """
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return https_fn.Response(response.text.replace("```json", "").replace("```", "").strip(), status=200, mimetype="application/json")

        # [Mode 3] Content Generation - 카테고리 기반 콘텐츠 생성
        else:
            topic = req_json.get("topic", "")
            
            # 카테고리별 역할 설정 (자동차 전문)
            role_mapping = {
                "차량관리 상식": "네이버 자동차 '이달의 블로그'에 선정된 10년차 자동차 정비 전문가",
                "자동차보험/사고처리": "손해사정사 출신 자동차보험 전문 블로거",
                "리스/렌트/할부/금융": "자동차 금융 컨설턴트 출신 10년차 블로거",
                "교통법규/범칙금": "전직 경찰관 출신 교통법규 전문 블로거",
                "자동차여행코스": "전국 드라이브 코스를 섭렵한 자동차 여행 전문 블로거",
                "전기차 라이프": "전기차 3년차 오너이자 EV 전문 리뷰어",
                "중고차 거래팁": "중고차 딜러 출신 10년차 자동차 전문 블로거",
            }
            
            role = role_mapping.get(category, "네이버 자동차 '이달의 블로그'에 선정된 10년차 자동차 전문 에디터")
            
            full_prompt = f"""
            [ROLE]
            당신은 {role}입니다.
            
            [CATEGORY]
            {category}
            
            [TOPIC]
            {topic}
            
            [REQUIREMENTS]
            {req_json.get("prompt", "독자에게 유용한 정보를 제공하세요.")}
            
            [STYLE OPTION]
            {req_json.get("style_options", "친근하고 전문적인 어조")}
            
            [CRITICAL INSTRUCTION]
            1. **카테고리({category})에 맞는 전문성을 보여주세요.**
            2. **본문 내용(Content)을 최우선으로 작성하세요.**
            3. 2,000자 이상의 풍부한 정보, 전문적인 식견, 독자의 공감을 이끄는 문장을 포함하세요.
            4. {category} 분야 독자들이 관심 가질 만한 실용적인 정보를 포함하세요.
            5. 내용은 동일하지만, 아래 3가지 포맷(Format)에 맞춰 각각 출력하세요.
            
            [OUTPUT JSON FORMAT]
            {{
                "title": "블로그 제목 (이모지 제외)",
                "category": "{category}",
                "content_text": "순수 텍스트 버전 (가독성 있는 줄바꿈 필수)",
                "content_md": "마크다운 버전 (## 헤딩, **볼드**, - 리스트 활용)",
                "content_html": "HTML 버전 (<p style='...'>, <h3>, <b> 등 인라인 스타일 적극 활용)"
            }}
            """

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            # Safety cleanup to remove potential markdown code fences from the JSON string
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            return https_fn.Response(clean_text, status=200, mimetype="application/json")

    except Exception as e:
        return https_fn.Response(f"Gemini Error: {str(e)}", status=500)
