"""
Gemini 기반 이미지 생성 모듈
주제에 맞는 블로그용 이미지 자동 생성

지원 모델 (2025년 기준):
- gemini-2.5-flash-image: 최신 안정판 (권장)
- imagen-3.0-generate-001: Imagen 3 고품질 모델
- gemini-2.0-flash-preview-image-generation: 레거시 모델
"""
import os
import base64
import logging
from typing import Optional, Tuple, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Gemini API 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# 사용 가능한 이미지 생성 모델
AVAILABLE_IMAGE_MODELS = {
    "gemini-2.5-flash-image": {
        "name": "Gemini 2.5 Flash Image",
        "description": "최신 안정판, 빠르고 고품질",
        "type": "gemini",  # google-genai SDK 사용
        "recommended": True
    },
    "imagen-3.0-generate-001": {
        "name": "Imagen 3",
        "description": "Google 최고 품질 이미지 생성 모델",
        "type": "imagen",  # google-generativeai SDK 사용
        "recommended": False
    },
    "gemini-2.0-flash-preview-image-generation": {
        "name": "Gemini 2.0 Flash Image (Legacy)",
        "description": "이전 버전 (호환성 유지)",
        "type": "gemini",
        "recommended": False
    }
}

# 기본 모델
DEFAULT_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")


class GeminiImageGenerator:
    """이미지 생성기 - Gemini 및 Imagen 모델 지원"""
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        초기화
        
        Args:
            api_key: Gemini API 키 (없으면 환경변수에서 로드)
            model: 사용할 이미지 모델 (기본: gemini-2.5-flash-image)
        """
        self.api_key = api_key or GEMINI_API_KEY
        self.model = model or DEFAULT_IMAGE_MODEL
        self._client = None
        self._genai_configured = False
        
        # 모델 유효성 검사
        if self.model not in AVAILABLE_IMAGE_MODELS:
            logger.warning(f"모델 '{self.model}'이 목록에 없습니다. 기본 모델을 사용합니다.")
            self.model = DEFAULT_IMAGE_MODEL
        
        self.model_info = AVAILABLE_IMAGE_MODELS.get(self.model, {})
        logger.info(f"이미지 생성기 초기화: {self.model_info.get('name', self.model)}")
        
    def is_available(self) -> bool:
        """이미지 생성 가능 여부 확인"""
        return bool(self.api_key)
    
    def get_model_info(self) -> Dict[str, Any]:
        """현재 모델 정보 반환"""
        return {
            "model": self.model,
            "info": self.model_info,
            "available_models": list(AVAILABLE_IMAGE_MODELS.keys())
        }
    
    def set_model(self, model: str) -> bool:
        """모델 변경"""
        if model in AVAILABLE_IMAGE_MODELS:
            self.model = model
            self.model_info = AVAILABLE_IMAGE_MODELS[model]
            self._client = None  # 클라이언트 재설정 필요
            logger.info(f"이미지 모델 변경: {model}")
            return True
        logger.warning(f"지원되지 않는 모델: {model}")
        return False
    
    def _get_genai_client(self):
        """google-genai SDK 클라이언트 (Gemini 모델용)"""
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
    
    def _configure_generativeai(self):
        """google-generativeai SDK 설정 (Imagen 모델용)"""
        if not self._genai_configured:
            if not self.api_key:
                raise ValueError("Gemini API 키가 설정되지 않았습니다.")
            
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._genai_configured = True
            except ImportError:
                logger.error("google-generativeai 패키지가 설치되지 않았습니다.")
                raise ImportError("pip install google-generativeai 명령으로 설치해주세요.")
    
    def generate_blog_image(
        self, 
        topic: str, 
        style: str = "블로그 썸네일",
        output_path: Optional[str] = None,
        aspect_ratio: str = "16:9"
    ) -> Tuple[bool, str, Optional[bytes]]:
        """
        주제에 맞는 블로그 이미지 생성
        
        Args:
            topic: 블로그 주제
            style: 이미지 스타일 (블로그 썸네일, 인포그래픽, 일러스트 등)
            output_path: 이미지 저장 경로 (선택)
            aspect_ratio: 이미지 비율 ("1:1", "3:4", "4:3", "9:16", "16:9")
            
        Returns:
            Tuple of (성공여부, 메시지, 이미지 바이트)
        """
        if not self.is_available():
            return False, "Gemini API 키가 설정되지 않았습니다.", None
        
        model_type = self.model_info.get("type", "gemini")
        
        if model_type == "imagen":
            return self._generate_with_imagen(topic, style, output_path, aspect_ratio)
        else:
            return self._generate_with_gemini(topic, style, output_path)
    
    def _generate_with_gemini(self, topic: str, style: str, output_path: Optional[str]) -> Tuple[bool, str, Optional[bytes]]:
        """Gemini 모델로 이미지 생성 (google-genai SDK)"""
        try:
            from google.genai import types
            
            client = self._get_genai_client()
            prompt = self._create_image_prompt(topic, style)
            
            logger.info(f"[Gemini] 이미지 생성 요청: {topic} (모델: {self.model})")
            
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=['Text', 'Image']
                )
            )
            
            # 응답에서 이미지 추출
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    image_data = part.inline_data.data
                    
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
            logger.error(f"[Gemini] 이미지 생성 실패: {e}")
            return False, f"이미지 생성 실패: {str(e)}", None
    
    def _generate_with_imagen(self, topic: str, style: str, output_path: Optional[str], aspect_ratio: str) -> Tuple[bool, str, Optional[bytes]]:
        """Imagen 3 모델로 이미지 생성 (google-generativeai SDK)"""
        try:
            import google.generativeai as genai
            
            self._configure_generativeai()
            
            prompt = self._create_image_prompt(topic, style)
            
            logger.info(f"[Imagen] 이미지 생성 요청: {topic} (모델: {self.model})")
            
            imagen = genai.ImageGenerationModel(self.model)
            
            result = imagen.generate_images(
                prompt=prompt,
                number_of_images=1,
                safety_filter_level="block_only_high",
                person_generation="allow_adult",
                aspect_ratio=aspect_ratio
            )
            
            if result.images:
                # Imagen 응답에서 이미지 바이트 추출
                image = result.images[0]
                
                # PIL 이미지를 바이트로 변환
                import io
                img_byte_arr = io.BytesIO()
                image._pil_image.save(img_byte_arr, format='PNG')
                image_data = img_byte_arr.getvalue()
                
                if output_path:
                    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, 'wb') as f:
                        f.write(image_data)
                    logger.info(f"이미지 저장 완료: {output_path}")
                
                return True, "이미지 생성 성공 (Imagen 3)", image_data
            
            return False, "이미지 생성 결과가 없습니다.", None
            
        except ImportError as e:
            return False, f"필요한 패키지가 없습니다: {str(e)}", None
        except Exception as e:
            logger.error(f"[Imagen] 이미지 생성 실패: {e}")
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
            ),
            "본문 삽화": (
                f"Create a simple, clean illustration for: '{topic}'. "
                "Style: Minimalist, flat design illustration. "
                "Soft, muted colors. Simple shapes. "
                "Suitable as a blog post illustration. "
                "No text, just visual elements."
            )
        }
        
        return style_prompts.get(style, style_prompts["블로그 썸네일"])
    
    def generate_from_text(
        self,
        prompt: str,
        output_path: Optional[str] = None,
        aspect_ratio: str = "16:9"
    ) -> Tuple[bool, str, Optional[bytes]]:
        """
        사용자 정의 프롬프트로 이미지 생성
        
        Args:
            prompt: 이미지 생성 프롬프트
            output_path: 이미지 저장 경로 (선택)
            aspect_ratio: 이미지 비율
            
        Returns:
            Tuple of (성공여부, 메시지, 이미지 바이트)
        """
        if not self.is_available():
            return False, "Gemini API 키가 설정되지 않았습니다.", None
        
        model_type = self.model_info.get("type", "gemini")
        
        if model_type == "imagen":
            return self._generate_with_imagen_direct(prompt, output_path, aspect_ratio)
        else:
            return self._generate_with_gemini_direct(prompt, output_path)
    
    def _generate_with_gemini_direct(self, prompt: str, output_path: Optional[str]) -> Tuple[bool, str, Optional[bytes]]:
        """Gemini 모델로 직접 프롬프트 이미지 생성"""
        try:
            from google.genai import types
            
            client = self._get_genai_client()
            
            response = client.models.generate_content(
                model=self.model,
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
    
    def _generate_with_imagen_direct(self, prompt: str, output_path: Optional[str], aspect_ratio: str) -> Tuple[bool, str, Optional[bytes]]:
        """Imagen 모델로 직접 프롬프트 이미지 생성"""
        try:
            import google.generativeai as genai
            
            self._configure_generativeai()
            imagen = genai.ImageGenerationModel(self.model)
            
            result = imagen.generate_images(
                prompt=prompt,
                number_of_images=1,
                safety_filter_level="block_only_high",
                person_generation="allow_adult",
                aspect_ratio=aspect_ratio
            )
            
            if result.images:
                import io
                img_byte_arr = io.BytesIO()
                result.images[0]._pil_image.save(img_byte_arr, format='PNG')
                image_data = img_byte_arr.getvalue()
                
                if output_path:
                    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, 'wb') as f:
                        f.write(image_data)
                
                return True, "이미지 생성 성공 (Imagen 3)", image_data
            
            return False, "이미지 생성 결과가 없습니다.", None
            
        except Exception as e:
            logger.error(f"이미지 생성 실패: {e}")
            return False, f"이미지 생성 실패: {str(e)}", None


def get_image_generator(model: Optional[str] = None) -> GeminiImageGenerator:
    """이미지 생성기 인스턴스 반환"""
    return GeminiImageGenerator(model=model)


# 편의 함수들
def generate_thumbnail(
    topic: str, 
    output_path: Optional[str] = None,
    model: Optional[str] = None
) -> Tuple[bool, str, Optional[bytes]]:
    """블로그 썸네일 이미지 생성"""
    generator = get_image_generator(model)
    return generator.generate_blog_image(topic, "블로그 썸네일", output_path)


def generate_car_image(
    topic: str, 
    output_path: Optional[str] = None,
    model: Optional[str] = None
) -> Tuple[bool, str, Optional[bytes]]:
    """자동차 관련 이미지 생성"""
    generator = get_image_generator(model)
    return generator.generate_blog_image(topic, "자동차", output_path)


def is_image_generation_available() -> bool:
    """이미지 생성 가능 여부 확인"""
    return bool(GEMINI_API_KEY)


def get_available_models() -> Dict[str, Dict[str, Any]]:
    """사용 가능한 이미지 모델 목록 반환"""
    return AVAILABLE_IMAGE_MODELS.copy()
