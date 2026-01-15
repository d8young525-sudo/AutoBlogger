"""
Gemini API Client Module
Google Gemini AI를 사용한 콘텐츠 생성

지원 모델 (2025년 기준):
- gemini-2.5-flash: 빠르고 가성비 좋은 모델 (권장)
- gemini-2.5-pro: 고품질 추론 모델
- gemini-2.5-flash-lite: 초고속 경량 모델
"""
import logging
from typing import Optional, Dict, Any, List

from config import Config

logger = logging.getLogger(__name__)

# 사용 가능한 모델 목록
AVAILABLE_MODELS = [
    "gemini-2.5-flash",       # 권장 - 빠르고 가성비 좋음
    "gemini-2.5-flash-lite",  # 초고속 경량
    "gemini-2.5-pro",         # 고품질 추론
    "gemini-2.0-flash",       # 이전 버전 (호환성)
]

DEFAULT_MODEL = "gemini-2.5-flash"


class GeminiClientError(Exception):
    """Gemini API related errors"""
    pass


class GeminiClient:
    """Google Gemini AI Client for content generation"""
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        use_grounding: bool = True
    ):
        """
        Initialize Gemini client
        
        Args:
            api_key: Gemini API key (optional, uses Config if not provided)
            model: Model name to use (default: gemini-2.5-flash)
            use_grounding: Enable Google Search grounding for real-time info
        """
        self.api_key = api_key or Config.GEMINI_API_KEY
        self.model_name = model or getattr(Config, 'GEMINI_MODEL', DEFAULT_MODEL)
        self.use_grounding = use_grounding
        self._client = None
        self._initialized = False
        
        if not self.api_key:
            logger.warning("Gemini API key not provided")
        
        # 모델 유효성 검사
        if self.model_name not in AVAILABLE_MODELS:
            logger.warning(f"Model '{self.model_name}' not in recommended list. Using anyway.")
    
    def _initialize(self) -> bool:
        """Initialize Gemini API connection with new SDK"""
        if self._initialized:
            return True
        
        if not self.api_key:
            raise GeminiClientError("Gemini API key is required")
        
        try:
            from google import genai
            
            self._client = genai.Client(api_key=self.api_key)
            self._initialized = True
            logger.info(f"Gemini client initialized with model: {self.model_name}")
            return True
            
        except ImportError:
            raise GeminiClientError(
                "google-genai package not installed. "
                "Install with: pip install google-genai"
            )
        except Exception as e:
            raise GeminiClientError(f"Failed to initialize Gemini client: {e}")
    
    def _get_grounding_config(self):
        """Get configuration with Google Search grounding enabled"""
        from google.genai import types
        
        if self.use_grounding:
            grounding_tool = types.Tool(
                google_search=types.GoogleSearch()
            )
            return types.GenerateContentConfig(
                tools=[grounding_tool]
            )
        return None
    
    def generate_blog_content(
        self, 
        topic: str, 
        style: str = "informative",
        length: str = "medium",
        language: str = "korean",
        use_grounding: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Generate blog content using Gemini AI with Google Search grounding
        
        Args:
            topic: Blog topic/subject
            style: Writing style (informative, casual, professional, creative)
            length: Content length (short, medium, long)
            language: Output language (korean, english)
            use_grounding: Override default grounding setting for this request
            
        Returns:
            Dict with 'title', 'content', 'sources' keys
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
- 최신 정보와 트렌드 반영
- 결론 포함

출력 형식:
제목: [SEO 최적화된 매력적인 제목]

---

[본문 내용]
"""
        
        try:
            from google.genai import types
            
            # Determine if grounding should be used
            should_ground = use_grounding if use_grounding is not None else self.use_grounding
            
            # Build config
            config = None
            if should_ground:
                grounding_tool = types.Tool(
                    google_search=types.GoogleSearch()
                )
                config = types.GenerateContentConfig(
                    tools=[grounding_tool]
                )
            
            # Generate content
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            
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
            
            # Extract grounding sources if available
            sources = self._extract_sources(response)
            
            logger.info(f"Blog content generated successfully for topic: {topic}")
            if sources:
                logger.info(f"Grounded with {len(sources)} sources")
            
            return {
                "title": title,
                "content": content,
                "topic": topic,
                "style": style,
                "length": length,
                "sources": sources,
                "grounded": bool(sources)
            }
            
        except Exception as e:
            logger.error(f"Failed to generate content: {e}")
            raise GeminiClientError(f"Content generation failed: {e}")
    
    def _extract_sources(self, response) -> List[Dict[str, str]]:
        """
        Extract grounding sources from response metadata
        
        Args:
            response: Gemini API response
            
        Returns:
            List of source dictionaries with 'title' and 'uri'
        """
        sources = []
        try:
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                    metadata = candidate.grounding_metadata
                    if hasattr(metadata, 'grounding_chunks') and metadata.grounding_chunks:
                        for chunk in metadata.grounding_chunks:
                            if hasattr(chunk, 'web') and chunk.web:
                                sources.append({
                                    "title": getattr(chunk.web, 'title', 'Unknown'),
                                    "uri": getattr(chunk.web, 'uri', '')
                                })
        except Exception as e:
            logger.warning(f"Failed to extract sources: {e}")
        
        return sources
    
    def improve_content(
        self, 
        content: str, 
        instruction: str,
        use_grounding: Optional[bool] = None
    ) -> str:
        """
        Improve existing content based on instruction
        
        Args:
            content: Original content
            instruction: Improvement instruction
            use_grounding: Enable Google Search for latest info
            
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
            from google.genai import types
            
            should_ground = use_grounding if use_grounding is not None else self.use_grounding
            
            config = None
            if should_ground:
                grounding_tool = types.Tool(
                    google_search=types.GoogleSearch()
                )
                config = types.GenerateContentConfig(
                    tools=[grounding_tool]
                )
            
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            return response.text.strip() if response.text else content
            
        except Exception as e:
            logger.error(f"Failed to improve content: {e}")
            return content
    
    def generate_tags(self, content: str, max_tags: int = 10) -> List[str]:
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
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            if response.text:
                tags = [tag.strip().replace("#", "") for tag in response.text.split(",")]
                return tags[:max_tags]
            return []
            
        except Exception as e:
            logger.error(f"Failed to generate tags: {e}")
            return []
    
    def search_trending_topics(
        self, 
        category: str = "technology",
        count: int = 5
    ) -> List[Dict[str, str]]:
        """
        Search for trending topics using Google Search grounding
        
        Args:
            category: Topic category (technology, lifestyle, business, etc.)
            count: Number of topics to return
            
        Returns:
            List of trending topics with descriptions
        """
        self._initialize()
        
        prompt = f"""
{category} 분야에서 현재 가장 인기 있고 트렌딩한 블로그 주제 {count}개를 추천해주세요.
각 주제에 대해 간단한 설명도 포함해주세요.

형식:
1. [주제]: [간단한 설명]
2. [주제]: [간단한 설명]
...
"""
        
        try:
            from google.genai import types
            
            # Always use grounding for trending topics
            grounding_tool = types.Tool(
                google_search=types.GoogleSearch()
            )
            config = types.GenerateContentConfig(
                tools=[grounding_tool]
            )
            
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            
            topics = []
            if response.text:
                lines = response.text.strip().split("\n")
                for line in lines:
                    line = line.strip()
                    if line and (line[0].isdigit() or line.startswith("-")):
                        # Parse "1. Topic: Description" format
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            topic = parts[0].lstrip("0123456789.-) ").strip()
                            description = parts[1].strip()
                            topics.append({
                                "topic": topic,
                                "description": description
                            })
                        elif len(parts) == 1:
                            topic = parts[0].lstrip("0123456789.-) ").strip()
                            topics.append({
                                "topic": topic,
                                "description": ""
                            })
            
            logger.info(f"Found {len(topics)} trending topics in {category}")
            return topics[:count]
            
        except Exception as e:
            logger.error(f"Failed to search trending topics: {e}")
            return []
    
    def is_available(self) -> bool:
        """Check if Gemini client is available"""
        try:
            self._initialize()
            return True
        except GeminiClientError:
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get current model information"""
        return {
            "model": self.model_name,
            "grounding_enabled": self.use_grounding,
            "available_models": AVAILABLE_MODELS,
            "initialized": self._initialized
        }
