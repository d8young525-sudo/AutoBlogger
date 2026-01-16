import os
import json
from firebase_functions import https_fn
from firebase_admin import initialize_app
from google import genai
from google.genai import types

initialize_app()

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
    # Using Gemini 3.0 Flash as requested
    MODEL_NAME = "gemini-3-flash-preview"

    try:
        # [Mode 1] Topic Recommendation
        if mode == "recommend":
            prompt = f"""
            자동차 전문 블로그 주제 추천.
            카테고리: {req_json.get("category")}
            조건: 검색량 많고 클릭 유도하는 구체적 주제 5개.
            형식: JSON (key: topics, value: list of strings)
            """
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return https_fn.Response(response.text.replace("```json", "").replace("```", "").strip(), status=200, mimetype="application/json")

        # [Mode 2] Topic Analysis
        elif mode == "analyze":
            prompt = f"""
            주제 '{req_json.get("topic")}'에 대한 블로그 마케팅 분석.
            형식: JSON (keys: targets, questions, key_points)
            """
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return https_fn.Response(response.text.replace("```json", "").replace("```", "").strip(), status=200, mimetype="application/json")

        # [Mode 3] Content Generation (The complex part)
        else:
            topic = req_json.get("topic", "")
            full_prompt = f"""
            [ROLE]
            당신은 네이버 자동차 '이달의 블로그'에 선정된 10년차 전문 에디터입니다.
            
            [TOPIC]
            {topic}
            
            [REQUIREMENTS]
            {req_json.get("prompt", "")}
            
            [STYLE OPTION]
            {req_json.get("style_options", "")}
            
            [CRITICAL INSTRUCTION]
            1. **본문 내용(Content)을 최우선으로 작성하세요.**
            2. 2,000자 이상의 풍부한 정보, 전문적인 식견, 독자의 공감을 이끄는 문장을 포함하세요.
            3. 내용은 동일하지만, 아래 3가지 포맷(Format)에 맞춰 각각 출력하세요.
            
            [OUTPUT JSON FORMAT]
            {{
                "title": "블로그 제목 (이모지 제외)",
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
