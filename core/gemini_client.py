"""
Gemini API Client Module
Google Gemini AI를 사용한 콘텐츠 생성
"""
import logging
from typing import Optional, Dict, Any

from config import Config

logger = logging.getLogger(__name__)


class GeminiClientError(Exception):
    """Gemini API related errors"""
    pass


class GeminiClient:
    """Google Gemini AI Client for content generation"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini client
        
        Args:
            api_key: Gemini API key (optional, uses Config if not provided)
        """
        self.api_key = api_key or Config.GEMINI_API_KEY
        self._model = None
        self._initialized = False
        
        if not self.api_key:
            logger.warning("Gemini API key not provided")
    
    def _initialize(self) -> bool:
        """Initialize Gemini API connection"""
        if self._initialized:
            return True
        
        if not self.api_key:
            raise GeminiClientError("Gemini API key is required")
        
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.api_key)
            self._model = genai.GenerativeModel('gemini-1.5-flash')
            self._initialized = True
            logger.info("Gemini client initialized successfully")
            return True
            
        except ImportError:
            raise GeminiClientError(
                "google-generativeai package not installed. "
                "Install with: pip install google-generativeai"
            )
        except Exception as e:
            raise GeminiClientError(f"Failed to initialize Gemini client: {e}")
    
    def generate_blog_content(
        self, 
        topic: str, 
        style: str = "informative",
        length: str = "medium",
        language: str = "korean"
    ) -> Dict[str, str]:
        """
        Generate blog content using Gemini AI
        
        Args:
            topic: Blog topic/subject
            style: Writing style (informative, casual, professional, creative)
            length: Content length (short, medium, long)
            language: Output language (korean, english)
            
        Returns:
            Dict with 'title' and 'content' keys
        """
        self._initialize()
        
        length_guide = {
            "short": "500-800자",
            "medium": "1000-1500자", 
            "long": "2000-3000자"
        }
        
        style_guide = {
            "informative": "정보 전달 위주의 객관적인",
            "casual": "친근하고 가벼운",
            "professional": "전문적이고 격식있는",
            "creative": "창의적이고 독특한"
        }
        
        lang_instruction = "한국어로" if language == "korean" else "in English"
        
        prompt = f"""
당신은 전문 블로그 작가입니다. 다음 주제에 대해 블로그 글을 작성해주세요.

주제: {topic}

요구사항:
- 글 스타일: {style_guide.get(style, style_guide['informative'])}
- 글 길이: {length_guide.get(length, length_guide['medium'])}
- 언어: {lang_instruction}
- SEO에 최적화된 제목 포함
- 읽기 쉽게 문단 구분
- 적절한 소제목 사용
- 결론 포함

출력 형식:
제목: [SEO 최적화된 매력적인 제목]

---

[본문 내용]
"""
        
        try:
            response = self._model.generate_content(prompt)
            
            if not response.text:
                raise GeminiClientError("Empty response from Gemini API")
            
            # Parse response
            content = response.text.strip()
            title = topic  # Default title
            
            # Try to extract title from response
            if content.startswith("제목:"):
                lines = content.split("\n", 2)
                if len(lines) >= 1:
                    title = lines[0].replace("제목:", "").strip()
                    if len(lines) > 2:
                        content = lines[2].replace("---", "").strip()
            
            logger.info(f"Blog content generated successfully for topic: {topic}")
            
            return {
                "title": title,
                "content": content,
                "topic": topic,
                "style": style,
                "length": length
            }
            
        except Exception as e:
            logger.error(f"Failed to generate content: {e}")
            raise GeminiClientError(f"Content generation failed: {e}")
    
    def improve_content(self, content: str, instruction: str) -> str:
        """
        Improve existing content based on instruction
        
        Args:
            content: Original content
            instruction: Improvement instruction
            
        Returns:
            Improved content
        """
        self._initialize()
        
        prompt = f"""
다음 블로그 글을 개선해주세요.

원본 글:
{content}

개선 요청:
{instruction}

개선된 글:
"""
        
        try:
            response = self._model.generate_content(prompt)
            return response.text.strip() if response.text else content
            
        except Exception as e:
            logger.error(f"Failed to improve content: {e}")
            return content
    
    def generate_tags(self, content: str, max_tags: int = 10) -> list:
        """
        Generate relevant tags for blog content
        
        Args:
            content: Blog content
            max_tags: Maximum number of tags
            
        Returns:
            List of relevant tags
        """
        self._initialize()
        
        prompt = f"""
다음 블로그 글에 적합한 해시태그를 {max_tags}개 이내로 추천해주세요.
한국어 태그로, 쉼표로 구분해서 출력해주세요.

글 내용:
{content[:1000]}

태그:
"""
        
        try:
            response = self._model.generate_content(prompt)
            if response.text:
                tags = [tag.strip().replace("#", "") for tag in response.text.split(",")]
                return tags[:max_tags]
            return []
            
        except Exception as e:
            logger.error(f"Failed to generate tags: {e}")
            return []
    
    def is_available(self) -> bool:
        """Check if Gemini client is available"""
        try:
            self._initialize()
            return True
        except GeminiClientError:
            return False
