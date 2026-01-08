"""
Gemini 기반 이미지 생성 모듈
주제에 맞는 블로그용 이미지 자동 생성
"""
import os
import base64
import logging
from typing import Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Gemini API 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_IMAGE_MODEL = "gemini-2.0-flash-exp-image-generation"


class GeminiImageGenerator:
    """Gemini 기반 이미지 생성기"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        초기화
        
        Args:
            api_key: Gemini API 키 (없으면 환경변수에서 로드)
        """
        self.api_key = api_key or GEMINI_API_KEY
        self._client = None
        
    def is_available(self) -> bool:
        """이미지 생성 가능 여부 확인"""
        return bool(self.api_key)
    
    def _get_client(self):
        """Gemini 클라이언트 가져오기 (lazy loading)"""
        if self._client is None:
            if not self.api_key:
                raise ValueError("Gemini API 키가 설정되지 않았습니다.")
            
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except ImportError:
                logger.error("google-genai 패키지가 설치되지 않았습니다.")
                raise ImportError("pip install google-genai 명령으로 설치해주세요.")
                
        return self._client
    
    def generate_blog_image(
        self, 
        topic: str, 
        style: str = "블로그 썸네일",
        output_path: Optional[str] = None
    ) -> Tuple[bool, str, Optional[bytes]]:
        """
        주제에 맞는 블로그 이미지 생성
        
        Args:
            topic: 블로그 주제
            style: 이미지 스타일 (블로그 썸네일, 인포그래픽, 일러스트 등)
            output_path: 이미지 저장 경로 (선택)
            
        Returns:
            Tuple of (성공여부, 메시지, 이미지 바이트)
        """
        if not self.is_available():
            return False, "Gemini API 키가 설정되지 않았습니다.", None
        
        try:
            from google.genai import types
            
            client = self._get_client()
            
            # 이미지 생성 프롬프트 구성
            prompt = self._create_image_prompt(topic, style)
            
            logger.info(f"이미지 생성 요청: {topic}")
            
            response = client.models.generate_content(
                model=GEMINI_IMAGE_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=['Text', 'Image']
                )
            )
            
            # 응답에서 이미지 추출
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    image_data = part.inline_data.data
                    
                    # 파일로 저장 (선택)
                    if output_path:
                        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                        with open(output_path, 'wb') as f:
                            f.write(image_data)
                        logger.info(f"이미지 저장 완료: {output_path}")
                    
                    return True, "이미지 생성 성공", image_data
            
            return False, "이미지 생성 결과가 없습니다.", None
            
        except ImportError as e:
            return False, f"필요한 패키지가 없습니다: {str(e)}", None
        except Exception as e:
            logger.error(f"이미지 생성 실패: {e}")
            return False, f"이미지 생성 실패: {str(e)}", None
    
    def _create_image_prompt(self, topic: str, style: str) -> str:
        """이미지 생성 프롬프트 구성"""
        style_prompts = {
            "블로그 썸네일": (
                f"Create a professional blog thumbnail image for the topic: '{topic}'. "
                "Style: Clean, modern, minimal design with soft colors. "
                "Include relevant icons or simple illustrations. "
                "Make it suitable for a Korean blog post. "
                "No text in the image. High quality, 16:9 aspect ratio."
            ),
            "인포그래픽": (
                f"Create an infographic-style image about: '{topic}'. "
                "Style: Informative, organized, with icons and visual elements. "
                "Use a clean color palette. "
                "Suitable for educational content. "
                "No text, just visual elements."
            ),
            "일러스트": (
                f"Create a friendly illustration about: '{topic}'. "
                "Style: Warm, approachable, cartoon-like illustration. "
                "Bright and cheerful colors. "
                "Suitable for a lifestyle blog."
            ),
            "자동차": (
                f"Create a professional car-related image for: '{topic}'. "
                "Style: Sleek, modern automotive photography style. "
                "Show car details or driving scenes. "
                "Professional lighting and composition."
            ),
            "음식/맛집": (
                f"Create a delicious food image for: '{topic}'. "
                "Style: Appetizing food photography. "
                "Warm lighting, close-up shots. "
                "Make it look delicious and inviting."
            )
        }
        
        return style_prompts.get(style, style_prompts["블로그 썸네일"])
    
    def generate_from_text(
        self,
        prompt: str,
        output_path: Optional[str] = None
    ) -> Tuple[bool, str, Optional[bytes]]:
        """
        사용자 정의 프롬프트로 이미지 생성
        
        Args:
            prompt: 이미지 생성 프롬프트
            output_path: 이미지 저장 경로 (선택)
            
        Returns:
            Tuple of (성공여부, 메시지, 이미지 바이트)
        """
        if not self.is_available():
            return False, "Gemini API 키가 설정되지 않았습니다.", None
        
        try:
            from google.genai import types
            
            client = self._get_client()
            
            response = client.models.generate_content(
                model=GEMINI_IMAGE_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=['Text', 'Image']
                )
            )
            
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    image_data = part.inline_data.data
                    
                    if output_path:
                        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                        with open(output_path, 'wb') as f:
                            f.write(image_data)
                    
                    return True, "이미지 생성 성공", image_data
            
            return False, "이미지 생성 결과가 없습니다.", None
            
        except Exception as e:
            logger.error(f"이미지 생성 실패: {e}")
            return False, f"이미지 생성 실패: {str(e)}", None


def get_image_generator() -> GeminiImageGenerator:
    """이미지 생성기 인스턴스 반환"""
    return GeminiImageGenerator()


# 편의 함수들
def generate_thumbnail(topic: str, output_path: Optional[str] = None) -> Tuple[bool, str, Optional[bytes]]:
    """블로그 썸네일 이미지 생성"""
    generator = get_image_generator()
    return generator.generate_blog_image(topic, "블로그 썸네일", output_path)


def generate_car_image(topic: str, output_path: Optional[str] = None) -> Tuple[bool, str, Optional[bytes]]:
    """자동차 관련 이미지 생성"""
    generator = get_image_generator()
    return generator.generate_blog_image(topic, "자동차", output_path)


def is_image_generation_available() -> bool:
    """이미지 생성 가능 여부 확인"""
    return bool(GEMINI_API_KEY)
