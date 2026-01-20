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
        Extract raw text blocks from the page using hybrid approach.
        
        Uses PyMuPDF for text extraction (proper word spacing) and
        automatically detects and handles two-column layouts.
        
        Returns:
            List of RawTextBlock objects with text and spatial information.
        """
        # Step 1: Extract blocks with PyMuPDF (good word spacing)
        blocks = self._extract_blocks_pymupdf()
        
        if not blocks:
            return blocks
        
        # Step 2: Use column assignment to handle both 1-column and 2-column layouts
        # This ensures that blocks are correctly categorized and merged within their respective columns,
        # preventing interleaving of adjacent columns and fragmented table rows.
        page_center = self.width / 2
        blocks = self._assign_blocks_to_columns(blocks, page_center)
        
        return blocks
    
    def _detect_column_boundary_pdfplumber(self) -> float | None:
        """
        Use pdfplumber to detect if page has two-column layout.
        
        Returns:
            x-coordinate of column boundary, or None if single column.
        """
        import pdfplumber
        
        doc_path = self._page.parent.name
        
        with pdfplumber.open(doc_path) as pdf:
            plumber_page = pdf.pages[self.page_number - 1]
            words = plumber_page.extract_words()
        
        if len(words) < 20:
            return None  # Too few words to detect columns
        
        page_center = self.width / 2
        margin = 50  # Minimum margin from edge
        
        # Count words in left vs right halves
        left_words = [w for w in words if margin < float(w['x0']) < page_center - 20]
        right_words = [w for w in words if page_center + 20 < float(w['x0']) < self.width - margin]
        
        # Check if there's a clear gap in the middle
        if len(left_words) > 10 and len(right_words) > 10:
            # Get rightmost point of left column and leftmost point of right column
            left_max_x = max(float(w['x1']) for w in left_words)
            right_min_x = min(float(w['x0']) for w in right_words)
            
            gap = right_min_x - left_max_x
            
            if gap > 15:  # Clear gap between columns
                # Return the midpoint of the gap
                return (left_max_x + right_min_x) / 2
        
        return None
    
    def _assign_blocks_to_columns(
        self,
        blocks: list[RawTextBlock],
        column_boundary: float,
    ) -> list[RawTextBlock]:
        """
        Split and reorder blocks based on column boundary.
        
        Args:
            blocks: Raw text blocks from PyMuPDF.
            column_boundary: x-coordinate separating left and right columns.
        
        Returns:
            Blocks ordered: wide/centered blocks first, then left column, then right column.
        """
        center_blocks: list[RawTextBlock] = []
        left_blocks: list[RawTextBlock] = []
        right_blocks: list[RawTextBlock] = []
        
        for block in blocks:
            block_center_x = (block.bbox.x0 + block.bbox.x1) / 2
            block_width = block.bbox.x1 - block.bbox.x0
            
            # Check if block spans both columns (like title)
            if block.bbox.x0 < column_boundary - 30 and block.bbox.x1 > column_boundary + 30:
                # Wide block spanning columns - check if it should be split
                if self._should_split_block(block, column_boundary):
                    left_part, right_part = self._split_block_at_boundary(block, column_boundary)
                    if left_part:
                        left_blocks.append(left_part)
                    if right_part:
                        right_blocks.append(right_part)
                else:
                    # Keep as centered block (title, header)
                    center_blocks.append(block)
            elif block_center_x < column_boundary:
                left_blocks.append(block)
            else:
                right_blocks.append(block)
        
        # Sort each group by y position (top to bottom)
        # Note: PyMuPDF y increases downwards, so y0 ascending is top-to-bottom
        center_blocks.sort(key=lambda b: b.bbox.y0)
        left_blocks.sort(key=lambda b: b.bbox.y0)
        right_blocks.sort(key=lambda b: b.bbox.y0)
        
        # Merge horizontally aligned blocks within columns (fixes table rows)
        center_blocks = self._merge_column_blocks(center_blocks)
        left_blocks = self._merge_column_blocks(left_blocks)
        right_blocks = self._merge_column_blocks(right_blocks)
        
        # Return in reading order: center/title first, then left column, then right column
        return center_blocks + left_blocks + right_blocks

    def _vertically_overlaps(self, bbox1: BoundingBox, bbox2: BoundingBox) -> bool:
        """Check if two bounding boxes vertically overlap significantly."""
        y0_1, y1_1 = bbox1.y0, bbox1.y1
        y0_2, y1_2 = bbox2.y0, bbox2.y1
        
        # Check actual overlap
        overlap = max(0.0, min(y1_1, y1_2) - max(y0_1, y0_2))
        min_h = min(y1_1 - y0_1, y1_2 - y0_2)
        
        if min_h <= 0:
            return False
            
        # Consistent overlap (relaxed to 20%)
        if overlap > min_h * 0.2:
            return True
            
        # Check center alignment (fallback for slight misalignments)
        c1 = (y0_1 + y1_1) / 2
        c2 = (y0_2 + y1_2) / 2
        if abs(c1 - c2) < 5:
            return True
            
        return False

    def _merge_column_blocks(self, blocks: list[RawTextBlock]) -> list[RawTextBlock]:
        """Merge blocks in a column that are horizontally aligned (split table rows)."""
        if not blocks:
            return []
            
        # First, ensure that each block's internal lines are merged if they are vertically aligned
        processed_blocks = []
        for block in blocks:
            if len(block.lines) > 1:
                merged_lines = self._merge_lines(block.lines)
                if len(merged_lines) < len(block.lines):
                    block = RawTextBlock(bbox=block.bbox, lines=merged_lines, spans=block.spans)
            processed_blocks.append(block)
        
        blocks = processed_blocks
        
        merged: list[RawTextBlock] = []
        current_group: list[RawTextBlock] = [blocks[0]]
        
        for block in blocks[1:]:
            last = current_group[-1]
            
            # Check overlap logic which is more robust than mid-point
            if self._vertically_overlaps(last.bbox, block.bbox):
                current_group.append(block)
            else:
                # Process current group
                if len(current_group) == 1:
                    merged.append(current_group[0])
                else:
                    merged.append(self._merge_raw_blocks(current_group))
                current_group = [block]
        
        # Process last group
        if len(current_group) == 1:
            merged.append(current_group[0])
        else:
            merged.append(self._merge_raw_blocks(current_group))
            
        return merged
    
    def _merge_raw_blocks(self, blocks: list[RawTextBlock]) -> RawTextBlock:
        """Merge a group of blocks into one."""
        # Sort left-to-right
        blocks.sort(key=lambda b: b.bbox.x0)
        
        # Calculate new bbox
        x0 = min(b.bbox.x0 for b in blocks)
        y0 = min(b.bbox.y0 for b in blocks)
        x1 = max(b.bbox.x1 for b in blocks)
        y1 = max(b.bbox.y1 for b in blocks)
        bbox = BoundingBox(x0, y0, x1, y1)
        
        # Collect and merge lines
        all_lines: list[RawLine] = []
        for b in blocks:
            all_lines.extend(b.lines)
            
        merged_lines = self._merge_lines(all_lines)
        
        # Collect all spans for the block
        all_spans = []
        for line in merged_lines:
            all_spans.extend(line.spans)
            
        return RawTextBlock(bbox=bbox, lines=merged_lines, spans=all_spans)
    
    def _merge_lines(self, lines: list[RawLine]) -> list[RawLine]:
        """Merge lines that are vertically aligned."""
        if not lines:
            return []
            
        # Sort by y0
        lines.sort(key=lambda l: l.bbox.y0)
        
        result: list[RawLine] = []
        current_line_group: list[RawLine] = [lines[0]]
        
        for line in lines[1:]:
            last = current_line_group[-1]
            if self._vertically_overlaps(last.bbox, line.bbox):
                current_line_group.append(line)
            else:
                result.append(self._create_merged_line(current_line_group))
                current_line_group = [line]
                
        result.append(self._create_merged_line(current_line_group))
        return result
        
    def _create_merged_line(self, lines: list[RawLine]) -> RawLine:
        """Create a single line from multiple aligned lines."""
        if len(lines) == 1:
            return lines[0]
            
        # Sort left-to-right
        lines.sort(key=lambda l: l.bbox.x0)
        
        x0 = min(l.bbox.x0 for l in lines)
        y0 = min(l.bbox.y0 for l in lines)
        x1 = max(l.bbox.x1 for l in lines)
        y1 = max(l.bbox.y1 for l in lines)
        
        all_spans = []
        text_parts = []
        last_x = None
        
        for line in lines:
            all_spans.extend(line.spans)
            
            # Add spacing between line segments
            if last_x is not None:
                gap = line.bbox.x0 - last_x
                if gap > 5: # space width guess
                    text_parts.append(" ")
            
            text_parts.append(line.text)
            last_x = line.bbox.x1
            
        return RawLine(
            bbox=BoundingBox(x0, y0, x1, y1),
            text="".join(text_parts),
            spans=all_spans
        )
    
    def _should_split_block(self, block: RawTextBlock, column_boundary: float) -> bool:
        """
        Determine if a wide block should be split at column boundary.
        
        Split if the block contains spans from both columns.
        Only preserve truly centered content (like titles) which have
        few lines and are centered on the page.
        """
        # Very short blocks near page center are likely titles - don't split
        if len(block.lines) <= 1:
            block_center = (block.bbox.x0 + block.bbox.x1) / 2
            # If roughly centered, don't split
            if abs(block_center - column_boundary) < 50:
                return False
        
        # Check if spans exist in both columns
        has_left_span = False
        has_right_span = False
        
        for span in block.spans:
            span_center = (span.bbox.x0 + span.bbox.x1) / 2
            if span_center < column_boundary:
                has_left_span = True
            else:
                has_right_span = True
            
            # Early exit if we found spans in both columns
            if has_left_span and has_right_span:
                return True
        
        return False
    
    def _split_block_at_boundary(
        self,
        block: RawTextBlock,
        column_boundary: float,
    ) -> tuple[RawTextBlock | None, RawTextBlock | None]:
        """
        Split a block into left and right column parts.
        
        Splits at the span level to handle lines that span both columns.
        """
        left_lines: list[RawLine] = []
        right_lines: list[RawLine] = []
        
        for line in block.lines:
            # Check if line spans both columns (by checking span positions)
            left_spans_in_line: list[TextSpan] = []
            right_spans_in_line: list[TextSpan] = []
            
            for span in line.spans:
                span_center = (span.bbox.x0 + span.bbox.x1) / 2
                if span_center < column_boundary:
                    left_spans_in_line.append(span)
                else:
                    right_spans_in_line.append(span)
            
            # Create separate lines for left and right spans
            if left_spans_in_line:
                left_text = " ".join(s.text for s in left_spans_in_line)
                left_line_bbox = BoundingBox(
                    x0=min(s.bbox.x0 for s in left_spans_in_line),
                    y0=line.bbox.y0,
                    x1=max(s.bbox.x1 for s in left_spans_in_line),
                    y1=line.bbox.y1,
                )
                left_lines.append(RawLine(
                    bbox=left_line_bbox,
                    text=left_text,
                    spans=left_spans_in_line,
                ))
            
            if right_spans_in_line:
                right_text = " ".join(s.text for s in right_spans_in_line)
                right_line_bbox = BoundingBox(
                    x0=min(s.bbox.x0 for s in right_spans_in_line),
                    y0=line.bbox.y0,
                    x1=max(s.bbox.x1 for s in right_spans_in_line),
                    y1=line.bbox.y1,
                )
                right_lines.append(RawLine(
                    bbox=right_line_bbox,
                    text=right_text,
                    spans=right_spans_in_line,
                ))
        
        left_block = None
        right_block = None
        
        if left_lines:
            left_bbox = BoundingBox(
                x0=min(l.bbox.x0 for l in left_lines),
                y0=min(l.bbox.y0 for l in left_lines),
                x1=max(l.bbox.x1 for l in left_lines),
                y1=max(l.bbox.y1 for l in left_lines),
            )
            left_spans = [s for l in left_lines for s in l.spans]
            left_block = RawTextBlock(bbox=left_bbox, lines=left_lines, spans=left_spans)
        
        if right_lines:
            right_bbox = BoundingBox(
                x0=min(l.bbox.x0 for l in right_lines),
                y0=min(l.bbox.y0 for l in right_lines),
                x1=max(l.bbox.x1 for l in right_lines),
                y1=max(l.bbox.y1 for l in right_lines),
            )
            right_spans = [s for l in right_lines for s in l.spans]
            right_block = RawTextBlock(bbox=right_bbox, lines=right_lines, spans=right_spans)
        
        return left_block, right_block
    
    def _extract_blocks_pymupdf(self) -> list[RawTextBlock]:
        """
        Extract text blocks using PyMuPDF (good word spacing).
        """
        blocks: list[RawTextBlock] = []
        
        try:
            # Don't use flags=11 as it removes word spacing
            page_dict = self._page.get_text("dict")  # type: ignore[union-attr]
        except Exception as e:
            logger.warning(
                "Failed to extract text dict from page %d: %s",
                self.page_number, e
            )
            return blocks
        
        for block in page_dict.get("blocks", []):
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
    
    def _split_blocks_at_column(
        self,
        blocks: list[RawTextBlock],
        page_width: float,
    ) -> list[RawTextBlock]:
        """
        Split wide blocks at the column boundary for two-column layouts.
        
        This processes each line within a block and separates content that
        spans both columns into separate blocks for each column.
        
        Args:
            blocks: List of raw text blocks.
            page_width: Width of the page in points.
        
        Returns:
            List of blocks, with wide blocks split into column-specific blocks.
        """
        # Column boundary is slightly left of center to account for gutter
        column_center = page_width / 2
        # Minimum gap between columns (gutter)
        min_gap = 20.0
        
        result: list[RawTextBlock] = []
        
        for block in blocks:
            # Check if this block might span both columns
            block_width = block.bbox.x1 - block.bbox.x0
            
            # If block is narrower than 60% of page width, it's in one column
            if block_width < page_width * 0.6:
                result.append(block)
                continue
            
            # This block might span columns - split its lines
            left_lines: list[RawLine] = []
            right_lines: list[RawLine] = []
            
            for line in block.lines:
                # Check if this line spans the column boundary
                if line.bbox.x0 < column_center - min_gap and line.bbox.x1 > column_center + min_gap:
                    # Line spans both columns - split by spans
                    left_spans: list[TextSpan] = []
                    right_spans: list[TextSpan] = []
                    
                    for span in line.spans:
                        span_center = (span.bbox.x0 + span.bbox.x1) / 2
                        if span_center < column_center:
                            left_spans.append(span)
                        else:
                            right_spans.append(span)
                    
                    # Create separate lines for each column
                    if left_spans:
                        left_text = " ".join(s.text for s in left_spans)
                        left_bbox = BoundingBox(
                            x0=min(s.bbox.x0 for s in left_spans),
                            y0=line.bbox.y0,
                            x1=max(s.bbox.x1 for s in left_spans),
                            y1=line.bbox.y1,
                        )
                        left_lines.append(RawLine(bbox=left_bbox, text=left_text, spans=left_spans))
                    
                    if right_spans:
                        right_text = " ".join(s.text for s in right_spans)
                        right_bbox = BoundingBox(
                            x0=min(s.bbox.x0 for s in right_spans),
                            y0=line.bbox.y0,
                            x1=max(s.bbox.x1 for s in right_spans),
                            y1=line.bbox.y1,
                        )
                        right_lines.append(RawLine(bbox=right_bbox, text=right_text, spans=right_spans))
                else:
                    # Line is in one column only
                    line_center = (line.bbox.x0 + line.bbox.x1) / 2
                    if line_center < column_center:
                        left_lines.append(line)
                    else:
                        right_lines.append(line)
            
            # Create separate blocks for each column
            if left_lines:
                left_bbox = BoundingBox(
                    x0=min(l.bbox.x0 for l in left_lines),
                    y0=min(l.bbox.y0 for l in left_lines),
                    x1=max(l.bbox.x1 for l in left_lines),
                    y1=max(l.bbox.y1 for l in left_lines),
                )
                left_spans = [s for l in left_lines for s in l.spans]
                result.append(RawTextBlock(bbox=left_bbox, lines=left_lines, spans=left_spans))
            
            if right_lines:
                right_bbox = BoundingBox(
                    x0=min(l.bbox.x0 for l in right_lines),
                    y0=min(l.bbox.y0 for l in right_lines),
                    x1=max(l.bbox.x1 for l in right_lines),
                    y1=max(l.bbox.y1 for l in right_lines),
                )
                right_spans = [s for l in right_lines for s in l.spans]
                result.append(RawTextBlock(bbox=right_bbox, lines=right_lines, spans=right_spans))
        
        return result
    
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
