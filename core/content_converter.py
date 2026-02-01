"""
Content Converter Module
TEXT 기반 콘텐츠를 Markdown/HTML/NaverDocument JSON으로 변환
네이버 블로그 에디터 스타일 지원
"""
import re
from typing import Optional, Dict, Any
from dataclasses import dataclass

from naver_editor import NaverDocument


@dataclass
class TextStyle:
    """TEXT 스타일 설정"""
    heading: str = "【 】 대괄호"
    emphasis: str = "** 별표 **"
    divider: str = "━━━━━━ (실선)"
    spacing: str = "기본 (1줄)"


@dataclass
class MarkdownStyle:
    """Markdown 스타일 설정"""
    heading: str = "## H2 사용"
    list_marker: str = "- 하이픈"
    qa: str = "> 인용문 스타일"
    narrative: str = "짧은 문장 (모바일 최적화)"


@dataclass
class HTMLStyle:
    """HTML 스타일 설정"""
    title: str = "<h2> 태그"
    qa: str = "<blockquote> 인용"
    color: str = "네이버 그린 (#03C75A)"
    font: str = "기본 (시스템)"
    box: str = "배경색 박스"


class ContentConverter:
    """콘텐츠 변환기 - TEXT를 기준으로 Markdown/HTML 생성"""
    
    # 네이버 블로그 에디터 스타일 매핑
    NAVER_STYLES = {
        "heading": {
            "h2": '<div class="se-module se-module-text se-title-text"><p class="se-text-paragraph se-text-paragraph-align-center" style=""><span class="se-fs32 se-ff1" style="">{text}</span></p></div>',
            "h3": '<div class="se-module se-module-text"><p class="se-text-paragraph se-text-paragraph-align-" style=""><span class="se-fs24 se-ff1 se-style-boldWeight" style="">{text}</span></p></div>',
        },
        "quote": '<div class="se-module se-module-oglink se-oglink-type1"><a href="#" class="se-oglink-anchor"><div class="se-oglink-info"><div class="se-oglink-info-container"><strong class="se-oglink-title">{text}</strong></div></div></a></div>',
        "blockquote": '<div class="se-module se-module-text se-quote"><blockquote class="se-text-blockquote"><p class="se-text-paragraph">{text}</p></blockquote></div>',
    }
    
    # 테마 컬러 매핑
    THEME_COLORS = {
        "네이버 그린 (#03C75A)": "#03C75A",
        "블루 (#4A90E2)": "#4A90E2",
        "오렌지 (#F39C12)": "#F39C12",
        "그레이 (#666)": "#666666",
    }
    
    # 폰트 매핑
    FONTS = {
        "기본 (시스템)": "inherit",
        "나눔고딕": "'Nanum Gothic', sans-serif",
        "맑은 고딕": "'Malgun Gothic', sans-serif",
    }
    
    def __init__(self, style_settings: Optional[Dict[str, Any]] = None):
        """
        Args:
            style_settings: 스타일 설정 딕셔너리
                {
                    "text": {...},
                    "markdown": {...},
                    "html": {...}
                }
        """
        self.style_settings = style_settings or {}
        self._init_styles()
    
    def _init_styles(self):
        """스타일 설정 초기화"""
        text_config = self.style_settings.get("text", {})
        md_config = self.style_settings.get("markdown", {})
        html_config = self.style_settings.get("html", {})
        
        self.text_style = TextStyle(
            heading=text_config.get("heading", "【 】 대괄호"),
            emphasis=text_config.get("emphasis", "** 별표 **"),
            divider=text_config.get("divider", "━━━━━━ (실선)"),
            spacing=text_config.get("spacing", "기본 (1줄)"),
        )
        
        self.md_style = MarkdownStyle(
            heading=md_config.get("heading", "## H2 사용"),
            list_marker=md_config.get("list", "- 하이픈"),
            qa=md_config.get("qa", "> 인용문 스타일"),
            narrative=md_config.get("narrative", "짧은 문장 (모바일 최적화)"),
        )
        
        self.html_style = HTMLStyle(
            title=html_config.get("title", "<h2> 태그"),
            qa=html_config.get("qa", "<blockquote> 인용"),
            color=html_config.get("color", "네이버 그린 (#03C75A)"),
            font=html_config.get("font", "기본 (시스템)"),
            box=html_config.get("box", "배경색 박스"),
        )
    
    # ========== TEXT 파싱 ==========
    
    def parse_text_content(self, text: str) -> Dict[str, Any]:
        """TEXT 콘텐츠를 구조화된 형태로 파싱"""
        result = {
            "title": "",
            "sections": [],
            "raw": text
        }
        
        lines = text.strip().split('\n')
        current_section = {"heading": "", "content": [], "type": "paragraph"}
        
        # 제목 추출
        if lines and (lines[0].startswith("제목:") or lines[0].startswith("# ")):
            result["title"] = lines[0].replace("제목:", "").replace("# ", "").strip()
            lines = lines[1:]
        
        # 소제목 패턴 (스타일에 따라 다름)
        heading_patterns = [
            r'^【(.+?)】',           # 대괄호
            r'^▶\s*(.+)',           # 화살표
            r'^●\s*(.+)',           # 원형
            r'^■\s*(.+)',           # 사각형
            r'^※\s*(.+)',           # 꽃표
            r'^#{2,3}\s*(.+)',      # Markdown 스타일
        ]
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 소제목 체크
            is_heading = False
            for pattern in heading_patterns:
                match = re.match(pattern, line)
                if match:
                    # 이전 섹션 저장
                    if current_section["heading"] or current_section["content"]:
                        result["sections"].append(current_section)
                    
                    current_section = {
                        "heading": match.group(1).strip(),
                        "content": [],
                        "type": "section"
                    }
                    is_heading = True
                    break
            
            if not is_heading:
                # Q&A 패턴 체크
                if line.startswith("Q:") or line.startswith("Q.") or line.startswith("질문:"):
                    current_section["content"].append({
                        "type": "question",
                        "text": re.sub(r'^(Q[:.:]|질문:)\s*', '', line)
                    })
                elif line.startswith("A:") or line.startswith("A.") or line.startswith("답변:"):
                    current_section["content"].append({
                        "type": "answer",
                        "text": re.sub(r'^(A[:.:]|답변:)\s*', '', line)
                    })
                # 리스트 패턴 체크
                elif re.match(r'^[-•*]\s+', line) or re.match(r'^\d+[.)]\s+', line):
                    current_section["content"].append({
                        "type": "list_item",
                        "text": re.sub(r'^[-•*\d.)+]\s*', '', line)
                    })
                # 구분선 체크
                elif re.match(r'^[━\-═]{3,}', line):
                    current_section["content"].append({
                        "type": "divider",
                        "text": ""
                    })
                else:
                    current_section["content"].append({
                        "type": "paragraph",
                        "text": line
                    })
        
        # 마지막 섹션 추가
        if current_section["heading"] or current_section["content"]:
            result["sections"].append(current_section)
        
        return result
    
    # ========== TEXT 포맷팅 ==========
    
    def format_text(self, content: str, title: str = "") -> str:
        """TEXT 형식으로 포맷팅 (스타일 적용)"""
        # 소제목 스타일 결정
        heading_style = self._get_text_heading_style()
        
        # 구분선 스타일
        divider = self._get_text_divider()
        
        # 문단 간격
        spacing = self._get_text_spacing()
        
        result = []
        if title:
            result.append(f"제목: {title}")
            result.append("")
            result.append(divider)
            result.append("")
        
        # 내용 처리 (기존 소제목을 새 스타일로 변환)
        lines = content.split('\n')
        for line in lines:
            # 소제목 패턴 매칭 및 변환
            heading_match = None
            for pattern in [r'^【(.+?)】', r'^▶\s*(.+)', r'^●\s*(.+)', r'^■\s*(.+)', r'^※\s*(.+)']:
                match = re.match(pattern, line)
                if match:
                    heading_match = match.group(1)
                    break
            
            if heading_match:
                result.append("")
                result.append(heading_style.format(text=heading_match))
                result.append("")
            else:
                result.append(line)
        
        return (spacing + '\n').join(result)
    
    def _get_text_heading_style(self) -> str:
        """TEXT 소제목 스타일 반환"""
        style_map = {
            "【 】 대괄호": "【{text}】",
            "▶ 화살표": "▶ {text}",
            "● 원형": "● {text}",
            "■ 사각형": "■ {text}",
            "※ 꽃표": "※ {text}",
        }
        return style_map.get(self.text_style.heading, "【{text}】")
    
    def _get_text_divider(self) -> str:
        """TEXT 구분선 스타일 반환"""
        style_map = {
            "━━━━━━ (실선)": "━" * 50,
            "- - - - - (점선)": "- " * 25,
            "═══════ (이중선)": "═" * 50,
            "빈 줄만": "",
        }
        return style_map.get(self.text_style.divider, "━" * 50)
    
    def _get_text_spacing(self) -> str:
        """TEXT 문단 간격 반환"""
        style_map = {
            "기본 (1줄)": "\n",
            "넓게 (2줄)": "\n\n",
            "좁게 (줄바꿈만)": "",
        }
        return style_map.get(self.text_style.spacing, "\n")
    
    # ========== MARKDOWN 변환 ==========
    
    def text_to_markdown(self, text: str, title: str = "") -> str:
        """TEXT를 Markdown으로 변환"""
        parsed = self.parse_text_content(text)
        
        result = []
        
        # 제목
        doc_title = title or parsed.get("title", "")
        if doc_title:
            result.append(f"# {doc_title}")
            result.append("")
        
        # 헤딩 스타일 결정
        heading_prefix = self._get_md_heading_prefix()
        list_marker = self._get_md_list_marker()
        
        for section in parsed.get("sections", []):
            # 섹션 헤딩
            if section.get("heading"):
                result.append("")
                result.append(f"{heading_prefix} {section['heading']}")
                result.append("")
            
            # 섹션 내용
            for item in section.get("content", []):
                item_type = item.get("type", "paragraph")
                item_text = item.get("text", "")
                
                if item_type == "question":
                    qa_style = self._get_md_qa_style()
                    if "인용문" in self.md_style.qa:
                        result.append(f"> **Q:** {item_text}")
                    elif "헤딩" in self.md_style.qa:
                        result.append(f"### Q: {item_text}")
                    else:
                        result.append(f"**Q:** {item_text}")
                elif item_type == "answer":
                    if "인용문" in self.md_style.qa:
                        result.append(f"> **A:** {item_text}")
                    else:
                        result.append(f"**A:** {item_text}")
                    result.append("")
                elif item_type == "list_item":
                    result.append(f"{list_marker} {item_text}")
                elif item_type == "divider":
                    result.append("")
                    result.append("---")
                    result.append("")
                else:
                    result.append(item_text)
                    result.append("")
        
        return '\n'.join(result)
    
    def _get_md_heading_prefix(self) -> str:
        """Markdown 헤딩 접두사"""
        if "H2" in self.md_style.heading:
            return "##"
        elif "H3" in self.md_style.heading:
            return "###"
        else:
            return "**"
    
    def _get_md_list_marker(self) -> str:
        """Markdown 리스트 마커"""
        if "하이픈" in self.md_style.list_marker:
            return "-"
        elif "별표" in self.md_style.list_marker:
            return "*"
        else:
            return "1."
    
    def _get_md_qa_style(self) -> str:
        """Markdown Q&A 스타일"""
        return self.md_style.qa
    
    # ========== HTML 변환 ==========
    
    def text_to_html(self, text: str, title: str = "", for_naver: bool = True) -> str:
        """TEXT를 HTML로 변환
        
        Args:
            text: 원본 TEXT
            title: 제목
            for_naver: 네이버 블로그 에디터 스타일 사용 여부
        """
        parsed = self.parse_text_content(text)
        
        # 스타일 설정
        theme_color = self.THEME_COLORS.get(self.html_style.color, "#03C75A")
        font_family = self.FONTS.get(self.html_style.font, "inherit")
        
        result = []
        
        # 기본 스타일 정의
        base_style = f"""
<style>
.blog-content {{
    font-family: {font_family};
    line-height: 1.8;
    color: #333;
}}
.blog-title {{
    color: {theme_color};
    font-size: 24px;
    font-weight: bold;
    margin-bottom: 20px;
    padding-bottom: 10px;
    border-bottom: 2px solid {theme_color};
}}
.blog-heading {{
    color: {theme_color};
    font-size: 18px;
    font-weight: bold;
    margin: 25px 0 15px 0;
    padding-left: 10px;
    border-left: 4px solid {theme_color};
}}
.blog-paragraph {{
    margin: 10px 0;
    text-align: justify;
}}
.blog-qa {{
    background-color: #f8f9fa;
    border-left: 4px solid {theme_color};
    padding: 15px 20px;
    margin: 15px 0;
}}
.blog-qa .question {{
    font-weight: bold;
    color: {theme_color};
    margin-bottom: 10px;
}}
.blog-qa .answer {{
    color: #555;
}}
.blog-list {{
    margin: 10px 0 10px 20px;
}}
.blog-list li {{
    margin: 5px 0;
}}
.blog-divider {{
    border: none;
    border-top: 1px solid #ddd;
    margin: 20px 0;
}}
.blog-box {{
    background-color: #f0f7f0;
    border: 1px solid {theme_color};
    border-radius: 8px;
    padding: 15px;
    margin: 15px 0;
}}
</style>
"""
        
        if not for_naver:
            result.append(base_style)
        
        result.append('<div class="blog-content">')
        
        # 제목
        doc_title = title or parsed.get("title", "")
        if doc_title:
            if for_naver:
                result.append(self._naver_heading(doc_title, level=1))
            else:
                result.append(f'<h1 class="blog-title">{self._escape_html(doc_title)}</h1>')
        
        # 섹션 처리
        for section in parsed.get("sections", []):
            # 섹션 헤딩
            if section.get("heading"):
                heading_text = section["heading"]
                if for_naver:
                    result.append(self._naver_heading(heading_text, level=2))
                else:
                    tag = "h2" if "<h2>" in self.html_style.title else "h3"
                    result.append(f'<{tag} class="blog-heading">{self._escape_html(heading_text)}</{tag}>')
            
            # 섹션 내용
            list_buffer = []
            for item in section.get("content", []):
                item_type = item.get("type", "paragraph")
                item_text = item.get("text", "")
                
                # 리스트 버퍼 처리
                if item_type != "list_item" and list_buffer:
                    result.append(self._render_list(list_buffer, for_naver))
                    list_buffer = []
                
                if item_type == "question":
                    if for_naver:
                        result.append(self._naver_qa(item_text, is_question=True))
                    else:
                        result.append(f'<div class="blog-qa"><div class="question">Q. {self._escape_html(item_text)}</div>')
                elif item_type == "answer":
                    if for_naver:
                        result.append(self._naver_qa(item_text, is_question=False))
                    else:
                        result.append(f'<div class="answer">A. {self._escape_html(item_text)}</div></div>')
                elif item_type == "list_item":
                    list_buffer.append(item_text)
                elif item_type == "divider":
                    result.append('<hr class="blog-divider">')
                else:
                    if for_naver:
                        result.append(self._naver_paragraph(item_text))
                    else:
                        result.append(f'<p class="blog-paragraph">{self._escape_html(item_text)}</p>')
            
            # 남은 리스트 버퍼 처리
            if list_buffer:
                result.append(self._render_list(list_buffer, for_naver))
        
        result.append('</div>')
        
        return '\n'.join(result)
    
    def _escape_html(self, text: str) -> str:
        """HTML 이스케이프"""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))
    
    def _naver_heading(self, text: str, level: int = 2) -> str:
        """네이버 블로그 스타일 헤딩"""
        if level == 1:
            return f'''<div class="se-module se-module-text se-title-text">
<p class="se-text-paragraph se-text-paragraph-align-center">
<span class="se-fs32 se-ff1" style="color:#03C75A;"><b>{self._escape_html(text)}</b></span>
</p>
</div>'''
        else:
            return f'''<div class="se-module se-module-text">
<p class="se-text-paragraph se-text-paragraph-align-">
<span class="se-fs24 se-ff1" style="color:#333;"><b>📌 {self._escape_html(text)}</b></span>
</p>
</div>'''
    
    def _naver_paragraph(self, text: str) -> str:
        """네이버 블로그 스타일 문단"""
        return f'''<div class="se-module se-module-text">
<p class="se-text-paragraph se-text-paragraph-align-">
<span class="se-fs15 se-ff1">{self._escape_html(text)}</span>
</p>
</div>'''
    
    def _naver_qa(self, text: str, is_question: bool = True) -> str:
        """네이버 블로그 스타일 Q&A"""
        if is_question:
            return f'''<div class="se-module se-module-text se-quote">
<blockquote class="se-text-blockquote">
<p class="se-text-paragraph">
<span class="se-fs15 se-ff1"><b>❓ Q. {self._escape_html(text)}</b></span>
</p>
</blockquote>
</div>'''
        else:
            return f'''<div class="se-module se-module-text">
<p class="se-text-paragraph se-text-paragraph-align-">
<span class="se-fs15 se-ff1">💡 A. {self._escape_html(text)}</span>
</p>
</div>'''
    
    def _render_list(self, items: list, for_naver: bool = True) -> str:
        """리스트 렌더링"""
        if for_naver:
            list_items = '\n'.join([
                f'<li class="se-text-paragraph"><span class="se-fs15 se-ff1">{self._escape_html(item)}</span></li>'
                for item in items
            ])
            return f'''<div class="se-module se-module-text">
<ul class="se-list-ul">
{list_items}
</ul>
</div>'''
        else:
            list_items = '\n'.join([f'<li>{self._escape_html(item)}</li>' for item in items])
            return f'<ul class="blog-list">\n{list_items}\n</ul>'
    
    # ========== 통합 변환 ==========
    
    def convert_all(self, content: str, title: str = "") -> Dict[str, str]:
        """TEXT를 모든 형식으로 변환
        
        Returns:
            {
                "text": "...",
                "markdown": "...",
                "html": "...",
                "html_naver": "..."
            }
        """
        return {
            "text": self.format_text(content, title),
            "markdown": self.text_to_markdown(content, title),
            "html": self.text_to_html(content, title, for_naver=False),
            "html_naver": self.text_to_html(content, title, for_naver=True),
        }


# 편의 함수
def convert_text_to_formats(
    text: str, 
    title: str = "", 
    style_settings: Optional[Dict] = None
) -> Dict[str, str]:
    """TEXT를 여러 형식으로 변환하는 편의 함수"""
    converter = ContentConverter(style_settings)
    return converter.convert_all(text, title)


def text_to_naver_html(text: str, title: str = "") -> str:
    """TEXT를 네이버 블로그 HTML로 변환하는 편의 함수"""
    converter = ContentConverter()
    return converter.text_to_html(text, title, for_naver=True)


def text_to_naver_document(
    text: str,
    title: str = "",
    style_settings: Optional[Dict] = None
) -> NaverDocument:
    """
    TEXT를 NaverDocument (JSON API payload)로 변환하는 편의 함수.
    
    AI가 생성한 plain text를 파싱하여 네이버 에디터 JSON 컴포넌트로 변환합니다.
    
    Args:
        text: AI 생성 본문 텍스트
        title: 블로그 포스트 제목
        style_settings: 스타일 설정 딕셔너리 (선택)
        
    Returns:
        NaverDocument instance ready for to_payload() / to_json()
    """
    converter = ContentConverter(style_settings)
    parsed = converter.parse_text_content(text)
    
    doc = NaverDocument()
    
    # Title
    doc_title = title or parsed.get("title", "")
    if doc_title:
        doc.add_title(doc_title)
    
    # Sections
    for section in parsed.get("sections", []):
        # Section heading -> sectionTitle
        heading = section.get("heading", "")
        if heading:
            doc.add_section_title(heading, bold=True, font_size_code="fs24")
        
        # Section content -> text / quotation / horizontalLine
        text_buffer: list = []  # accumulate consecutive paragraphs
        
        def _flush_text_buffer():
            if text_buffer:
                doc.add_text(text_buffer.copy())
                text_buffer.clear()
        
        for item in section.get("content", []):
            item_type = item.get("type", "paragraph")
            item_text = item.get("text", "")
            
            if item_type == "paragraph":
                text_buffer.append(item_text)
            elif item_type == "question":
                _flush_text_buffer()
                # Q as bold text
                doc.add_text([
                    [("Q. " + item_text, {"bold": True})]
                ])
            elif item_type == "answer":
                # A as normal text
                doc.add_text("A. " + item_text)
            elif item_type == "list_item":
                # Accumulate as regular paragraph (Naver JSON doesn't have list ctype)
                text_buffer.append("- " + item_text)
            elif item_type == "divider":
                _flush_text_buffer()
                doc.add_horizontal_line()
            else:
                text_buffer.append(item_text)
        
        _flush_text_buffer()
    
    return doc


def blocks_to_naver_document(
    blocks: list,
    title: str = "",
    style_settings: Optional[Dict] = None,
    images: Optional[list] = None
) -> NaverDocument:
    """
    AI가 생성한 블록 배열을 NaverDocument로 변환하는 함수.

    인기 블로그 스타일 프롬프트에서 반환된 blocks JSON을 직접 처리합니다.
    image_placeholder 블록은 images 리스트에서 순서대로 이미지를 삽입합니다.

    Args:
        blocks: AI 응답의 blocks 배열 (list of dict)
        title: 블로그 포스트 제목
        style_settings: 네이버 에디터 스타일 설정
        images: 업로드된 이미지 메타데이터 리스트 (각 항목은 dict with src, path, width, height 등)

    Returns:
        NaverDocument instance
    """
    doc = NaverDocument()
    image_list = list(images) if images else []
    image_idx = 0

    # 스타일 설정 파싱
    settings = style_settings or {}
    font_family = settings.get("font_family", "nanumgothic")
    font_size = settings.get("font_size", "fs15")
    heading_bold = settings.get("heading_bold", True)
    heading_font_size = settings.get("heading_font_size", "fs24")
    heading_color = settings.get("heading_color")
    quote_layout = settings.get("quote_layout", "quotation_line")
    divider_layout = settings.get("divider_layout", "line1")

    if title:
        doc.add_title(title)

    for block in blocks:
        block_type = block.get("type", "paragraph")

        if block_type == "paragraph":
            text = block.get("text", "")
            if text:
                doc.add_text(
                    text,
                    font_family=font_family,
                    font_size_code=font_size
                )

        elif block_type == "heading":
            heading_text = block.get("text", "")
            level = block.get("level", 2)
            if heading_text:
                fs = heading_font_size if level == 2 else "fs18"
                kwargs = {
                    "bold": heading_bold,
                    "font_size_code": fs,
                }
                if heading_color:
                    kwargs["font_color"] = heading_color
                doc.add_section_title(heading_text, **kwargs)

        elif block_type == "quotation":
            text = block.get("text", "")
            if text:
                doc.add_quotation(text, layout=quote_layout)

        elif block_type == "list":
            items = block.get("items", [])
            style = block.get("style", "bullet")
            if items:
                prefix = "- " if style == "bullet" else ""
                lines = []
                for i, item in enumerate(items):
                    if style == "number":
                        lines.append(f"{i+1}. {item}")
                    else:
                        lines.append(f"{prefix}{item}")
                doc.add_text(
                    "\n".join(lines),
                    font_family=font_family,
                    font_size_code=font_size
                )

        elif block_type == "divider":
            doc.add_horizontal_line(layout=divider_layout)

        elif block_type == "image_placeholder":
            if image_idx < len(image_list):
                img = image_list[image_idx]
                doc.add_image(
                    src=img.get("src", ""),
                    path=img.get("path", ""),
                    domain=img.get("domain", "https://blogfiles.pstatic.net"),
                    width=img.get("width", 500),
                    height=img.get("height", 500),
                    original_width=img.get("original_width", 960),
                    original_height=img.get("original_height", 960),
                    file_name=img.get("file_name", "image.jpeg"),
                    file_size=img.get("file_size", 0),
                    represent=(image_idx == 0),
                )
                image_idx += 1

    return doc
