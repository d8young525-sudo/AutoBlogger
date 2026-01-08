import os
import json
import base64
import logging
from datetime import datetime
from firebase_functions import https_fn
from firebase_admin import initialize_app, firestore, auth
from google import genai
from google.genai import types

# Firebase 앱 초기화
initialize_app()

# 사용량 제한 설정
DAILY_IMAGE_LIMIT = 20
MONTHLY_IMAGE_LIMIT = 300

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
                "daily_image_count": 0,
                "monthly_image_count": 0,
                "last_reset_date": datetime.now().strftime("%Y-%m-%d"),
                "last_reset_month": datetime.now().strftime("%Y-%m")
            }
            user_ref.set(user_data)
            return {
                "allowed": False,
                "reason": "관리자 승인이 필요합니다. 관리자에게 문의하세요.",
                "usage": user_data
            }
        
        user_data = user_doc.to_dict()
        
        # 활성화 체크
        if not user_data.get("is_active", False):
            return {
                "allowed": False,
                "reason": "관리자 승인 대기 중입니다. 관리자에게 문의하세요.",
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
        
        # 승인된 사용자는 무제한
        plan_limits = {"daily": 9999, "monthly": 99999}
        
        # 승인된 사용자는 무제한 허용
        return {
            "allowed": True,
            "reason": "OK",
            "usage": user_data,
            "limits": plan_limits
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


@https_fn.on_request(
    region="asia-northeast3", 
    timeout_sec=300, 
    secrets=["GEMINI_API_KEY"],
    cors=True
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
        # [모드 1] 주제 추천
        # ============================================
        if mode == "recommend":
            prompt = f"""
            자동차 전문 블로거로서 '{req_json.get("category")}' 관련 조회수 높은 주제 5개 추천.
            형식: JSON (배열) -> {{"topics": ["주제1", "주제2", ...]}}
            """
            
            resp = client.models.generate_content(
                model=MODEL_NAME, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return https_fn.Response(
                resp.text.replace("```json", "").replace("```", "").strip(), 
                status=200, 
                mimetype="application/json"
            )

        # ============================================
        # [모드 2] 주제 분석
        # ============================================
        elif mode == "analyze":
            prompt = f"""
            주제 '{req_json.get("topic")}' 마케팅 분석.
            형식: JSON -> {{"targets": [...], "questions": [...], "key_points": [...]}}
            """
            
            resp = client.models.generate_content(
                model=MODEL_NAME, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return https_fn.Response(
                resp.text.replace("```json", "").replace("```", "").strip(), 
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
            
            # 스타일별 프롬프트 구성
            style_prompts = {
                "블로그 썸네일": f"Create a professional blog thumbnail image for: '{image_prompt}'. Style: Clean, modern, minimal design with soft colors. No text. High quality, 16:9 aspect ratio.",
                "자동차": f"Create a professional automotive image for: '{image_prompt}'. Style: Sleek, modern car photography. Professional lighting.",
                "출고 후기": f"Create a warm, celebratory car delivery image for: '{image_prompt}'. Style: Happy customer receiving new car. Bright and positive mood.",
                "인포그래픽": f"Create an infographic-style image about: '{image_prompt}'. Style: Informative, organized with icons and visual elements."
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
        # [모드 5] 글 작성 (기존)
        # ============================================
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
            반드시 아래 키를 포함해야 함.
            {{
                "title": "제목",
                "content": "본문 내용 (최소 2000자, 줄바꿈 필수)",
                "content_text": "텍스트 버전 본문",
                "content_md": "마크다운 버전 본문",
                "content_html": "HTML 버전 본문"
            }}
            """

            resp = client.models.generate_content(
                model=MODEL_NAME, contents=full_prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            
            raw_text = resp.text.replace("```json", "").replace("```", "").strip()
            
            try:
                data = json.loads(raw_text)
                
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
                
            except json.JSONDecodeError:
                return https_fn.Response(json.dumps({
                    "title": f"{topic} (형식 오류)",
                    "content": raw_text,
                    "content_text": raw_text,
                    "content_md": raw_text,
                    "content_html": f"<pre>{raw_text}</pre>"
                }), status=200, mimetype="application/json")

    except Exception as e:
        logging.error(f"API Error: {e}")
        return https_fn.Response(f"Server Error: {str(e)}", status=500)
