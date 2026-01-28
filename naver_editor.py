"""
Naver Blog Editor JSON Document Builder
RabbitWrite.naver API payload generator

Captured payload structure reference:
- POST https://blog.naver.com/RabbitWrite.naver
- document version: 2.9.0
- Components: documentTitle, sectionTitle, text, quotation, horizontalLine, image, sticker
"""
import uuid
import random
import string
import json
from typing import Optional, List, Dict, Any, Union, Tuple


def _se_id() -> str:
    """Generate SE-{uuid4} format ID for components/paragraphs/nodes"""
    return f"SE-{uuid.uuid4()}"


def _ulid_id() -> str:
    """Generate ULID-like 26-char uppercase alphanumeric ID for document"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=26))


def _node_style(**kwargs) -> Optional[Dict[str, Any]]:
    """
    Build nodeStyle dict. Only includes non-None values.
    
    Supported keys:
        bold, italic, underline, strikeThrough (bool)
        fontFamily (str) - e.g. "nanumgothic", "nanummyeongjo"
        fontSizeCode (str) - e.g. "fs9","fs10","fs11","fs13","fs15","fs18","fs24","fs32"
        fontColor (str) - hex e.g. "#0078cb"
        backgroundColor (str) - hex e.g. "#fff593"
    """
    style = {}
    for key in ("bold", "italic", "underline", "strikeThrough",
                "fontFamily", "fontSizeCode", "fontColor", "backgroundColor"):
        val = kwargs.get(key)
        if val is not None:
            style[key] = val
    
    if not style:
        return None
    
    style["@ctype"] = "nodeStyle"
    return style


def _text_node(value: str, style: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a textNode"""
    node: Dict[str, Any] = {
        "id": _se_id(),
        "value": value,
        "@ctype": "textNode"
    }
    if style:
        node["style"] = style
    return node


def _paragraph(nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create a paragraph containing textNodes"""
    return {
        "id": _se_id(),
        "nodes": nodes,
        "@ctype": "paragraph"
    }


def _simple_paragraph(text: str, style_kwargs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a paragraph with a single textNode, optionally styled"""
    style = _node_style(**style_kwargs) if style_kwargs else None
    return _paragraph([_text_node(text, style)])


# Type alias for text input: either a plain string or list of (text, style_dict) tuples
ParagraphInput = Union[str, List[Tuple[str, Dict[str, Any]]]]


class NaverDocument:
    """
    Builder for Naver Blog Editor JSON documents.
    
    Generates payloads compatible with RabbitWrite.naver API.
    
    Usage:
        doc = NaverDocument()
        doc.add_title("My Title")
        doc.add_section_title("Section", bold=True, font_size_code="fs24")
        doc.add_text("Body paragraph text")
        doc.add_quotation("Quote text", source="Source")
        doc.add_horizontal_line()
        payload = doc.to_payload()
    """

    def __init__(self):
        self._doc_id: str = _ulid_id()
        self._components: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # documentTitle
    # ------------------------------------------------------------------
    def add_title(self, title: str, align: str = "left") -> "NaverDocument":
        """
        Add document title component.
        
        Args:
            title: Title text
            align: Text alignment ("left", "center", "right")
        """
        comp = {
            "id": _se_id(),
            "layout": "default",
            "title": [_simple_paragraph(title)],
            "subTitle": None,
            "align": align,
            "@ctype": "documentTitle"
        }
        self._components.append(comp)
        return self

    # ------------------------------------------------------------------
    # sectionTitle
    # ------------------------------------------------------------------
    def add_section_title(
        self,
        title: str,
        bold: bool = True,
        font_size_code: str = "fs24",
        **style_kwargs
    ) -> "NaverDocument":
        """
        Add section title (subtitle) component.
        
        Args:
            title: Section title text
            bold: Apply bold style
            font_size_code: Font size code (fs9~fs32)
            **style_kwargs: Additional nodeStyle properties
        """
        all_style = {"bold": bold, "fontSizeCode": font_size_code, **style_kwargs}
        style = _node_style(**all_style)
        
        comp = {
            "id": _se_id(),
            "layout": "default",
            "title": [_paragraph([_text_node(title, style)])],
            "@ctype": "sectionTitle"
        }
        self._components.append(comp)
        return self

    # ------------------------------------------------------------------
    # text
    # ------------------------------------------------------------------
    def add_text(
        self,
        content: Union[str, List[ParagraphInput]],
        **style_kwargs
    ) -> "NaverDocument":
        """
        Add text component (body text).
        
        Args:
            content: Either:
                - A single string (creates one paragraph)
                - A list of paragraph inputs, where each is either:
                    - A string (plain text paragraph)
                    - A list of (text, style_dict) tuples (mixed-style paragraph)
            **style_kwargs: Default nodeStyle applied to plain string inputs.
                           Ignored for tuple inputs which carry their own styles.
        """
        paragraphs = []
        
        if isinstance(content, str):
            # Single string -> one paragraph
            paragraphs.append(_simple_paragraph(content, style_kwargs if style_kwargs else None))
        else:
            # List of paragraph inputs
            for para_input in content:
                if isinstance(para_input, str):
                    paragraphs.append(
                        _simple_paragraph(para_input, style_kwargs if style_kwargs else None)
                    )
                elif isinstance(para_input, list):
                    # List of (text, style_dict) tuples
                    nodes = []
                    for item in para_input:
                        if isinstance(item, str):
                            nodes.append(_text_node(item))
                        elif isinstance(item, (tuple, list)) and len(item) == 2:
                            text, sdict = item
                            nodes.append(_text_node(text, _node_style(**sdict)))
                        else:
                            nodes.append(_text_node(str(item)))
                    paragraphs.append(_paragraph(nodes))
        
        comp = {
            "id": _se_id(),
            "layout": "default",
            "value": paragraphs,
            "@ctype": "text"
        }
        self._components.append(comp)
        return self

    # ------------------------------------------------------------------
    # quotation
    # ------------------------------------------------------------------
    def add_quotation(
        self,
        text: str,
        source: Optional[str] = None,
        layout: str = "default"
    ) -> "NaverDocument":
        """
        Add quotation component.
        
        Args:
            text: Quote text
            source: Optional source/attribution text
            layout: One of: default, quotation_line, quotation_bubble,
                    quotation_underline, quotation_postit, quotation_corner
        """
        comp: Dict[str, Any] = {
            "id": _se_id(),
            "layout": layout,
            "value": [_simple_paragraph(text)],
            "source": [_simple_paragraph(source)] if source else [_simple_paragraph("")],
            "@ctype": "quotation"
        }
        self._components.append(comp)
        return self

    # ------------------------------------------------------------------
    # horizontalLine
    # ------------------------------------------------------------------
    def add_horizontal_line(self, layout: str = "default") -> "NaverDocument":
        """
        Add horizontal line (divider) component.
        
        Args:
            layout: One of: default, line1, line2, line3, line4, line5, line6, line7
        """
        comp = {
            "id": _se_id(),
            "layout": layout,
            "@ctype": "horizontalLine"
        }
        self._components.append(comp)
        return self

    # ------------------------------------------------------------------
    # image
    # ------------------------------------------------------------------
    def add_image(
        self,
        src: str,
        path: str,
        domain: str = "https://blogfiles.pstatic.net",
        width: int = 500,
        height: int = 500,
        original_width: int = 960,
        original_height: int = 960,
        file_name: str = "image.jpeg",
        file_size: int = 0,
        caption: Optional[str] = None,
        represent: bool = True,
        content_mode: str = "fit",
        format_: str = "normal",
        display_format: str = "normal",
        src_from: str = "local"
    ) -> "NaverDocument":
        """
        Add image component (references already-uploaded image).
        
        Args:
            src: Full image URL with type parameter
            path: Image path on server
            domain: Image domain
            width/height: Display dimensions
            original_width/original_height: Original image dimensions
            file_name: Image filename
            file_size: File size in bytes
            caption: Optional image caption
            represent: Whether this is the representative image
            content_mode: Display mode ("fit", "fill")
            format_: Image format ("normal")
            display_format: Display format ("normal")
            src_from: Image source ("local", "url")
        """
        comp = {
            "id": _se_id(),
            "layout": "default",
            "src": src,
            "internalResource": True,
            "represent": represent,
            "path": path,
            "domain": domain,
            "fileSize": file_size,
            "width": width,
            "height": height,
            "originalWidth": original_width,
            "originalHeight": original_height,
            "fileName": file_name,
            "caption": caption,
            "format": format_,
            "displayFormat": display_format,
            "imageLoaded": True,
            "contentMode": content_mode,
            "origin": {
                "srcFrom": src_from,
                "@ctype": "imageOrigin"
            },
            "ai": False,
            "@ctype": "image"
        }
        self._components.append(comp)
        return self

    # ------------------------------------------------------------------
    # sticker
    # ------------------------------------------------------------------
    def add_sticker(
        self,
        pack_code: str,
        seq: int,
        thumbnail_src: str,
        thumbnail_width: int = 185,
        thumbnail_height: int = 160,
        format_: str = "normal"
    ) -> "NaverDocument":
        """
        Add sticker component.
        
        Args:
            pack_code: Sticker pack code (e.g., "motion2d_01")
            seq: Sticker sequence number
            thumbnail_src: Thumbnail image URL
            thumbnail_width/thumbnail_height: Thumbnail dimensions
            format_: Display format
        """
        comp = {
            "id": _se_id(),
            "layout": "default",
            "packCode": pack_code,
            "seq": seq,
            "thumbnail": {
                "src": thumbnail_src,
                "width": thumbnail_width,
                "height": thumbnail_height,
                "@ctype": "thumbnail"
            },
            "format": format_,
            "@ctype": "sticker"
        }
        self._components.append(comp)
        return self

    # ------------------------------------------------------------------
    # Payload generation
    # ------------------------------------------------------------------
    def to_payload(self) -> Dict[str, Any]:
        """
        Generate the complete RabbitWrite.naver payload.
        
        Returns:
            Dict ready for JSON serialization matching Naver's expected format.
        """
        return {
            "documentId": "",
            "document": {
                "version": "2.9.0",
                "theme": "default",
                "language": "ko-KR",
                "id": self._doc_id,
                "components": self._components,
                "di": {
                    "dif": False,
                    "dio": []
                }
            }
        }

    def to_json(self) -> str:
        """Serialize payload to JSON string."""
        return json.dumps(self.to_payload(), ensure_ascii=False)

    @property
    def components(self) -> List[Dict[str, Any]]:
        """Access the component list directly."""
        return self._components

    def clear(self) -> "NaverDocument":
        """Reset document, clearing all components and generating new IDs."""
        self._doc_id = _ulid_id()
        self._components = []
        return self
