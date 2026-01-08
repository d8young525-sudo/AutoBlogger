"""
Blog Generator Module
블로그 콘텐츠 생성 및 포스팅 통합 모듈
"""
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class BlogPost:
    """Blog post data class"""
    title: str
    content: str
    topic: str
    tags: List[str]
    created_at: datetime
    posted: bool = False
    post_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "title": self.title,
            "content": self.content,
            "topic": self.topic,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "posted": self.posted,
            "post_url": self.post_url
        }


class BlogGeneratorError(Exception):
    """Blog generation related errors"""
    pass


class BlogGenerator:
    """
    Blog content generator and poster
    Combines Gemini AI content generation with Naver blog posting
    """
    
    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        naver_id: Optional[str] = None,
        naver_pw: Optional[str] = None
    ):
        """
        Initialize blog generator
        
        Args:
            gemini_api_key: Gemini API key
            naver_id: Naver account ID
            naver_pw: Naver account password
        """
        self._gemini_client = None
        self._naver_poster = None
        
        self._gemini_api_key = gemini_api_key
        self._naver_id = naver_id
        self._naver_pw = naver_pw
        
        self._posts: List[BlogPost] = []
        
        logger.info("BlogGenerator initialized")
    
    @property
    def gemini_client(self):
        """Lazy load Gemini client"""
        if self._gemini_client is None:
            from core.gemini_client import GeminiClient
            self._gemini_client = GeminiClient(api_key=self._gemini_api_key)
        return self._gemini_client
    
    @property
    def naver_poster(self):
        """Lazy load Naver poster"""
        if self._naver_poster is None:
            from core.naver_poster import NaverPoster
            self._naver_poster = NaverPoster(
                naver_id=self._naver_id,
                naver_pw=self._naver_pw
            )
        return self._naver_poster
    
    def generate(
        self,
        topic: str,
        style: str = "informative",
        length: str = "medium",
        language: str = "korean",
        auto_tags: bool = True
    ) -> str:
        """
        Generate blog content for a topic
        
        Args:
            topic: Blog topic/subject
            style: Writing style
            length: Content length
            language: Output language
            auto_tags: Automatically generate tags
            
        Returns:
            Generated content as string
        """
        logger.info(f"Generating blog content for topic: {topic}")
        
        try:
            # Generate content using Gemini
            result = self.gemini_client.generate_blog_content(
                topic=topic,
                style=style,
                length=length,
                language=language
            )
            
            title = result.get("title", topic)
            content = result.get("content", "")
            
            # Generate tags
            tags = []
            if auto_tags and content:
                tags = self.gemini_client.generate_tags(content)
            
            # Create blog post object
            post = BlogPost(
                title=title,
                content=content,
                topic=topic,
                tags=tags,
                created_at=datetime.now()
            )
            
            self._posts.append(post)
            
            # Format output
            output = f"제목: {title}\n"
            output += "=" * 50 + "\n\n"
            output += content
            
            if tags:
                output += "\n\n" + "=" * 50 + "\n"
                output += "태그: " + ", ".join(f"#{tag}" for tag in tags)
            
            logger.info(f"Content generated successfully: {title}")
            return output
            
        except Exception as e:
            logger.error(f"Content generation failed: {e}")
            raise BlogGeneratorError(f"Failed to generate content: {e}")
    
    def generate_and_post(
        self,
        topic: str,
        style: str = "informative",
        length: str = "medium",
        language: str = "korean"
    ) -> Dict[str, Any]:
        """
        Generate content and post to Naver blog
        
        Args:
            topic: Blog topic
            style: Writing style
            length: Content length
            language: Output language
            
        Returns:
            Dict with generation and posting results
        """
        result = {
            "success": False,
            "topic": topic,
            "title": None,
            "content": None,
            "tags": [],
            "post_url": None,
            "message": ""
        }
        
        try:
            # Step 1: Generate content
            logger.info("Step 1: Generating content...")
            
            gen_result = self.gemini_client.generate_blog_content(
                topic=topic,
                style=style,
                length=length,
                language=language
            )
            
            title = gen_result.get("title", topic)
            content = gen_result.get("content", "")
            
            result["title"] = title
            result["content"] = content
            
            # Step 2: Generate tags
            logger.info("Step 2: Generating tags...")
            tags = self.gemini_client.generate_tags(content)
            result["tags"] = tags
            
            # Step 3: Post to Naver
            if not self.naver_poster.is_available():
                result["message"] = "Content generated but Naver credentials not configured"
                result["success"] = True  # Partial success
                return result
            
            logger.info("Step 3: Posting to Naver blog...")
            
            post_result = self.naver_poster.post_blog(
                title=title,
                content=content,
                tags=tags
            )
            
            if post_result["success"]:
                result["success"] = True
                result["post_url"] = post_result.get("url")
                result["message"] = "Blog generated and posted successfully"
                
                # Update stored post
                if self._posts:
                    self._posts[-1].posted = True
                    self._posts[-1].post_url = result["post_url"]
            else:
                result["message"] = f"Content generated but posting failed: {post_result.get('message')}"
            
            return result
            
        except Exception as e:
            logger.error(f"Generate and post failed: {e}")
            result["message"] = f"Failed: {e}"
            return result
        
        finally:
            # Cleanup
            if self._naver_poster:
                self._naver_poster.close()
    
    def get_posts(self) -> List[Dict[str, Any]]:
        """Get all generated posts"""
        return [post.to_dict() for post in self._posts]
    
    def get_last_post(self) -> Optional[Dict[str, Any]]:
        """Get the last generated post"""
        if self._posts:
            return self._posts[-1].to_dict()
        return None
    
    def clear_posts(self):
        """Clear stored posts"""
        self._posts.clear()
        logger.info("Stored posts cleared")
    
    def check_status(self) -> Dict[str, Any]:
        """
        Check generator status and available services
        
        Returns:
            Dict with status information
        """
        status = {
            "gemini_available": False,
            "naver_available": False,
            "posts_count": len(self._posts),
            "last_post_title": None
        }
        
        # Check Gemini
        try:
            status["gemini_available"] = self.gemini_client.is_available()
        except Exception:
            pass
        
        # Check Naver
        try:
            status["naver_available"] = self.naver_poster.is_available()
        except Exception:
            pass
        
        # Last post info
        if self._posts:
            status["last_post_title"] = self._posts[-1].title
        
        return status
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup resources"""
        if self._naver_poster:
            self._naver_poster.close()
