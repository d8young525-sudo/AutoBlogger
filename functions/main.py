import os
import json
import logging
from firebase_functions import https_fn
from firebase_admin import initialize_app
from google import genai
from google.genai import types

initialize_app()

@https_fn.on_request(region="asia-northeast3", timeout_sec=300, secrets=["GEMINI_API_KEY"])
def generate_blog_post(req: https_fn.Request) -> https_fn.Response:
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        return https_fn.Response("Server Error: Gemini API Key not configured.", status=500)

    client = genai.Client(api_key=gemini_key)

    req_json = req.get_json(silent=True)
    if not req_json:
        return https_fn.Response("Bad Request", status=400)

    mode = req_json.get("mode", "write")
    MODEL_NAME = "gemini-3-flash-preview"

    try:
        # [모드 1, 2] 주제 추천/분석 (기존과 동일)
        if mode in ["recommend", "analyze"]:
            # ... (기존 로직 유지, 편의상 생략하지 않고 전체 작성)
            if mode == "recommend":
                prompt = f"""
                자동차 전문 블로거로서 '{req_json.get("category")}' 관련 조회수 높은 주제 5개 추천.
                형식: JSON (배열) -> {{"topics": ["주제1", "주제2", ...]}}
                """
            else:
                prompt = f"""
                주제 '{req_json.get("topic")}' 마케팅 분석.
                형식: JSON -> {{"targets": [...], "questions": [...], "key_points": [...]}}
                """
            
            resp = client.models.generate_content(
                model=MODEL_NAME, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return https_fn.Response(resp.text.replace("```json", "").replace("```", "").strip(), status=200, mimetype="application/json")

        # [모드 3] 글 작성 (여기가 핵심!)
        else:
            topic = req_json.get("topic", "")
            full_prompt = f"""
            [ROLE] 네이버 자동차 파워 블로거
            [TOPIC] {topic}
            
            [REQUIREMENTS]
            {req_json.get("prompt", "")}
            
            [STYLE]
            {req_json.get("style_options", "")}
            
            [OUTPUT FORMAT (Strict JSON)]
            반드시 아래 4가지 키를 포함해야 함.
            {{
                "title": "제목",
                "content_text": "텍스트 버전 본문 (최소 2000자, 줄바꿈 필수)",
                "content_md": "마크다운 버전 본문",
                "content_html": "HTML 버전 본문"
            }}
            """

            resp = client.models.generate_content(
                model=MODEL_NAME, contents=full_prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            
            # [안전장치] AI가 준 JSON을 파싱해서 키값 검사
            raw_text = resp.text.replace("```json", "").replace("```", "").strip()
            try:
                data = json.loads(raw_text)
                
                # 만약 content_text가 없으면 content나 body에서 찾아 채워넣기
                if "content_text" not in data:
                    data["content_text"] = data.get("content", data.get("body", "내용 생성 실패"))
                
                # HTML이나 MD가 없으면 텍스트로 대충 채워넣기 (에러 방지)
                if "content_md" not in data: data["content_md"] = data["content_text"]
                if "content_html" not in data: data["content_html"] = f"<p>{data['content_text']}</p>"
                
                return https_fn.Response(json.dumps(data), status=200, mimetype="application/json")
                
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 원본 텍스트라도 보냄
                return https_fn.Response(json.dumps({
                    "title": f"{topic} (형식 오류)",
                    "content_text": raw_text,
                    "content_md": raw_text,
                    "content_html": f"<pre>{raw_text}</pre>"
                }), status=200, mimetype="application/json")

    except Exception as e:
        return https_fn.Response(f"Gemini Error: {str(e)}", status=500)
