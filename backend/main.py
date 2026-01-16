import os
from firebase_functions import https_fn
from firebase_admin import initialize_app
import google.generativeai as genai

# Firebase 앱 초기화
initialize_app()

# Gemini API 설정 (환경변수에서 키를 가져옵니다)
# 배포할 때 환경변수로 설정할 것입니다.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

@https_fn.on_request(region="asia-northeast3") # 서울 리전
def generate_blog_post(req: https_fn.Request) -> https_fn.Response:
    """
    앱에서 요청을 받아 Gemini에게 글 작성을 시키는 함수
    요청 형식(JSON): {"topic": "주제", "tone": "말투"}
    """
    
    # 1. API 키 확인
    if not GEMINI_API_KEY:
        return https_fn.Response("Server Error: Gemini API Key not configured.", status=500)

    # 2. 요청 데이터 파싱
    req_json = req.get_json(silent=True)
    if not req_json or 'topic' not in req_json:
        return https_fn.Response("Bad Request: 'topic' is required.", status=400)

    topic = req_json['topic']
    
    # 3. 프롬프트 엔지니어링 (블로그 글쓰기 비법 소스!)
    prompt = f"""
    당신은 10년차 베테랑 자동차 영업사원이자 파워 블로거입니다.
    아래 주제로 네이버 블로그 포스팅을 작성해주세요.

    주제: {topic}

    [필수 조건]
    1. 말투: 친근하고 신뢰감 있는 "해요체"를 사용하세요. (이모지 적절히 사용)
    2. 구조:
       - 제목: 클릭을 유도하는 매력적인 제목 (한 줄)
       - 본문: 서론(인사) - 본론(정보 전달) - 결론(영업 사원으로서의 팁 및 마무리 인사)
    3. 형식: 제목과 본문을 명확히 구분해서 출력해주세요. 
       출력 예시:
       TITLE: 제목내용
       CONTENT: 본문내용
    """

    try:
        # 4. Gemini 모델 호출 (gemini-pro 사용)
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        
        return https_fn.Response(response.text, status=200)

    except Exception as e:
        return https_fn.Response(f"Gemini Error: {str(e)}", status=500)
