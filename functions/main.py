import os
import json
from firebase_functions import https_fn
from firebase_admin import initialize_app
from google import genai
from google.genai import types

initialize_app()

# 지원하는 카테고리 목록 (앱 브라우저와 동기화 필요)
SUPPORTED_CATEGORIES = {
    "자동차": "자동차, 차량 관리, 운전 팁, 신차 정보, 중고차",
    "여행": "여행, 국내여행, 해외여행, 맛집, 숙소",
    "IT/테크": "IT, 기술, 가젯, 스마트폰, 컴퓨터",
    "건강": "건강, 운동, 다이어트, 영양, 웰빙",
    "재테크": "재테크, 투자, 주식, 부동산, 저축",
    "일상": "일상, 라이프스타일, 취미, 문화생활",
    "육아": "육아, 자녀교육, 임신, 출산",
    "요리": "요리, 레시피, 식재료, 홈쿠킹",
}

DEFAULT_CATEGORY = "자동차"


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
        # [Mode 1] Topic Recommendation - 카테고리 기반 동적 주제 추천
        if mode == "recommend":
            prompt = f"""
            당신은 네이버 블로그 콘텐츠 전략가입니다.
            
            [카테고리]
            {category}
            
            [관련 키워드]
            {category_keywords}
            
            [요청사항]
            위 카테고리에 맞는 블로그 주제를 5개 추천해주세요.
            
            [조건]
            1. 네이버 검색량이 높을 것으로 예상되는 주제
            2. 클릭을 유도하는 구체적이고 매력적인 주제
            3. 현재 시즌/트렌드를 반영한 시의성 있는 주제
            4. 각 주제는 명확하고 구체적이어야 함
            
            [출력 형식]
            JSON 형식 (key: topics, value: 문자열 배열)
            """
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
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
            
            # 카테고리별 역할 설정
            role_mapping = {
                "자동차": "네이버 자동차 '이달의 블로그'에 선정된 10년차 자동차 전문 에디터",
                "여행": "월 100만 방문자를 보유한 여행 전문 블로거",
                "IT/테크": "IT 업계 10년차 테크 리뷰어 겸 블로거",
                "건강": "헬스/웰빙 전문 콘텐츠 크리에이터",
                "재테크": "금융권 경력 10년의 재테크 전문 블로거",
                "일상": "일상 공유로 많은 공감을 얻는 라이프스타일 블로거",
                "육아": "세 아이 엄마이자 육아 전문 블로거",
                "요리": "요리 유튜버 겸 레시피 전문 블로거",
            }
            
            role = role_mapping.get(category, f"{category} 분야 전문 블로거")
            
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
