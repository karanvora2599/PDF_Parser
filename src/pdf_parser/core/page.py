"""
PDF Page representation and processing.

This module provides the Page class that wraps a PDF page and provides
access to its content with spatial information.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import fitz

from pdf_parser.output.models import BoundingBox, FontInfo, TextSpan

logger = logging.getLogger(__name__)


@dataclass
class RawLine:
    """
    A line of text extracted from the PDF.
    
    Lines are the fundamental unit of text - they preserve natural
    reading order and word spacing.
    """
    
    bbox: BoundingBox
    text: str
    spans: list[TextSpan] = field(default_factory=list)
    
    @property
    def is_empty(self) -> bool:
        """Check if the line contains no text."""
        return not self.text.strip()


@dataclass
class RawTextBlock:
    """
    A raw text block extracted from the PDF before layout analysis.
    
    This is an intermediate representation used during parsing.
    A block contains multiple lines.
    """
    
    bbox: BoundingBox
    lines: list[RawLine] = field(default_factory=list)
    spans: list[TextSpan] = field(default_factory=list)
    
    @property
    def text(self) -> str:
        """Concatenated text of all lines with proper line breaks."""
        return "\n".join(line.text for line in self.lines if line.text.strip())
    
    @property
    def is_empty(self) -> bool:
        """Check if the block contains no text."""
        return not self.lines or all(line.is_empty for line in self.lines)


class Page:
    """
    Represents a single PDF page with content extraction capabilities.
    
    This class wraps a PyMuPDF page and provides methods for extracting
    text content with spatial and font information.
    
    Attributes:
        page_number: 1-indexed page number.
        width: Page width in points.
        height: Page height in points.
    """
    
    # Threshold for detecting space between characters (as ratio of font size)
    SPACE_THRESHOLD = 0.3
    
    def __init__(self, fitz_page: "fitz.Page", page_number: int) -> None:
        """
        Initialize a Page wrapper.
        
        Args:
            fitz_page: The underlying PyMuPDF page object.
            page_number: 1-indexed page number.
        """
        self._page = fitz_page
        self.page_number = page_number
        
        rect = fitz_page.rect
        self.width = float(rect.width)
        self.height = float(rect.height)
    
    def extract_raw_blocks(self) -> list[RawTextBlock]:
        """
        Extract raw text blocks from the page.
        
        Returns:
            List of RawTextBlock objects with text and spatial information.
        """
        blocks: list[RawTextBlock] = []
        
        try:
            # Use dict extraction for detailed text information
            # Note: Don't use flags=11 as it removes word spacing
            page_dict = self._page.get_text("dict")  # type: ignore[union-attr]
        except Exception as e:
            logger.warning(
                "Failed to extract text dict from page %d: %s",
                self.page_number, e
            )
            return blocks
        
        for block in page_dict.get("blocks", []):
            # Skip image blocks
            if block.get("type") != 0:
                continue
            
            raw_block = self._process_text_block(block)
            if raw_block and not raw_block.is_empty:
                blocks.append(raw_block)
        
        return blocks
    
    def _process_text_block(self, block: dict) -> RawTextBlock | None:
        """
        Process a raw text block from PyMuPDF.
        
        Args:
            block: A block dictionary from page.get_text("dict").
        
        Returns:
            A RawTextBlock, or None if the block is invalid.
        """
        try:
            bbox = BoundingBox(
                x0=float(block["bbox"][0]),
                y0=float(block["bbox"][1]),
                x1=float(block["bbox"][2]),
                y1=float(block["bbox"][3]),
            )
        except (KeyError, IndexError, ValueError) as e:
            logger.debug("Invalid block bbox: %s", e)
            return None
        
        raw_lines: list[RawLine] = []
        all_spans: list[TextSpan] = []
        
        for line_data in block.get("lines", []):
            raw_line = self._process_line(line_data)
            if raw_line and not raw_line.is_empty:
                raw_lines.append(raw_line)
                all_spans.extend(raw_line.spans)
        
        if not raw_lines:
            return None
        
        return RawTextBlock(bbox=bbox, lines=raw_lines, spans=all_spans)
    
    def _process_line(self, line_data: dict) -> RawLine | None:
        """
        Process a line of text from PyMuPDF.
        
        This method properly handles spacing between spans within a line
        by analyzing character positions.
        
        Args:
            line_data: A line dictionary from a block.
        
        Returns:
            A RawLine, or None if the line is invalid.
        """
        try:
            bbox = BoundingBox(
                x0=float(line_data["bbox"][0]),
                y0=float(line_data["bbox"][1]),
                x1=float(line_data["bbox"][2]),
                y1=float(line_data["bbox"][3]),
            )
        except (KeyError, IndexError, ValueError) as e:
            logger.debug("Invalid line bbox: %s", e)
            return None
        
        spans_data = line_data.get("spans", [])
        if not spans_data:
            return None
        
        # Process spans and build line text with proper spacing
        text_parts: list[str] = []
        text_spans: list[TextSpan] = []
        last_span_end_x: float | None = None
        last_font_size: float = 12.0
        
        for span_data in spans_data:
            span = self._process_span(span_data)
            if not span:
                continue
            
            text_spans.append(span)
            span_text = span.text
            
            # Check if we need to insert a space before this span
            if last_span_end_x is not None:
                gap = span.bbox.x0 - last_span_end_x
                space_width = last_font_size * self.SPACE_THRESHOLD
                
                if gap > space_width:
                    # There's a gap - insert space
                    text_parts.append(" ")
            
            text_parts.append(span_text)
            last_span_end_x = span.bbox.x1
            last_font_size = span.font.size
        
        line_text = "".join(text_parts).strip()
        
        if not line_text:
            return None
        
        return RawLine(bbox=bbox, text=line_text, spans=text_spans)
    
    def _process_span(self, span: dict) -> TextSpan | None:
        """
        Process a text span from PyMuPDF.
        
        Args:
            span: A span dictionary from a line.
        
        Returns:
            A TextSpan, or None if the span is invalid.
        """
        text = span.get("text", "")
        if not text:  # Allow spans with just whitespace for spacing calculation
            return None
        
        try:
            bbox = BoundingBox(
                x0=float(span["bbox"][0]),
                y0=float(span["bbox"][1]),
                x1=float(span["bbox"][2]),
                y1=float(span["bbox"][3]),
            )
        except (KeyError, IndexError, ValueError) as e:
            logger.debug("Invalid span bbox: %s", e)
            return None
        
        # Extract font information
        font_name = span.get("font", "unknown")
        font_size = float(span.get("size", 12.0))
        
        # Detect bold/italic from font name or flags
        flags = span.get("flags", 0)
        is_bold = bool(flags & 16) or "bold" in font_name.lower()
        is_italic = bool(flags & 2) or "italic" in font_name.lower()
        
        # Extract color (stored as integer)
        color_int = span.get("color", 0)
        color = self._int_to_rgb(color_int)
        
        font = FontInfo(
            name=font_name,
            size=font_size,
            is_bold=is_bold,
            is_italic=is_italic,
            color=color,
        )
        
        return TextSpan(text=text, bbox=bbox, font=font)
    
    @staticmethod
    def _int_to_rgb(color_int: int) -> tuple[int, int, int]:
        """Convert an integer color value to RGB tuple."""
        if color_int == 0:
            return (0, 0, 0)
        
        r = (color_int >> 16) & 0xFF
        g = (color_int >> 8) & 0xFF
        b = color_int & 0xFF
        return (r, g, b)
    
    def get_text_simple(self) -> str:
        """
        Get simple text extraction without layout analysis.
        
        This is a fallback method that returns all text from the page
        without preserving layout structure.
        
        Returns:
            Plain text content of the page.
        """
        try:
            return self._page.get_text("text")  # type: ignore[union-attr]
        except Exception as e:
            logger.error(
                "Failed to extract text from page %d: %s",
                self.page_number, e
            )
            return ""
