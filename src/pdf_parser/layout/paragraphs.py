"""
Paragraph reconstruction from text blocks.

This module provides the ParagraphReconstructor class which merges
fragmented text blocks into coherent paragraphs based on spatial
and typographic analysis.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pdf_parser.core.page import RawTextBlock

from pdf_parser.output.models import (
    BoundingBox,
    TextBlock,
    BlockType,
    TextAlignment,
    FontInfo,
    TextSpan,
)

logger = logging.getLogger(__name__)


class ParagraphReconstructor:
    """
    Reconstructs paragraphs from raw text blocks.
    
    This class analyzes the spatial relationships between text blocks
    to determine which ones should be merged into a single paragraph
    and which represent separate paragraphs.
    
    Features:
    - Merges lines that belong to the same paragraph
    - Detects paragraph breaks based on vertical spacing
    - Identifies headings based on font properties
    - Preserves indentation information
    - Reconstructs hyphenated words at line breaks
    """
    
    def __init__(self, gap_threshold: float = 1.5) -> None:
        """
        Initialize the paragraph reconstructor.
        
        Args:
            gap_threshold: Vertical spacing (as ratio of font size) above
                          which a paragraph break is detected.
        """
        self.gap_threshold = gap_threshold
    
    def reconstruct(
        self,
        blocks: list["RawTextBlock"],
        column_index: int = 0,
    ) -> list[TextBlock]:
        """
        Reconstruct paragraphs from raw text blocks.
        
        Args:
            blocks: Raw text blocks to process.
            column_index: The column these blocks belong to.
        
        Returns:
            List of TextBlock objects representing paragraphs.
        """
        if not blocks:
            return []
        
        # Sort blocks by vertical position (top to bottom)
        sorted_blocks = sorted(blocks, key=lambda b: -b.bbox.y1)
        
        # Group blocks into paragraphs
        paragraphs: list[list["RawTextBlock"]] = []
        current_paragraph: list["RawTextBlock"] = []
        
        for i, block in enumerate(sorted_blocks):
            if not current_paragraph:
                current_paragraph.append(block)
                continue
            
            # Check if this block continues the current paragraph
            prev_block = current_paragraph[-1]
            
            if self._should_merge(prev_block, block):
                current_paragraph.append(block)
            else:
                # Start new paragraph
                paragraphs.append(current_paragraph)
                current_paragraph = [block]
        
        # Don't forget the last paragraph
        if current_paragraph:
            paragraphs.append(current_paragraph)
        
        # Convert grouped blocks to TextBlock objects
        text_blocks: list[TextBlock] = []
        
        for para_blocks in paragraphs:
            text_block = self._create_text_block(para_blocks, column_index)
            if text_block:
                text_blocks.append(text_block)
        
        return text_blocks
    
    def _should_merge(
        self,
        prev_block: "RawTextBlock",
        curr_block: "RawTextBlock",
    ) -> bool:
        """
        Determine if two blocks should be merged into one paragraph.
        
        Use very conservative merging - only merge if blocks are:
        1. Horizontally aligned (high overlap)
        2. Very close vertically (within 1 line height)
        3. Have similar horizontal extents
        
        Args:
            prev_block: The previous block in reading order.
            curr_block: The current block being considered.
        
        Returns:
            True if blocks should be merged, False if they're separate paragraphs.
        """
        # Require high horizontal overlap (at least 80%)
        overlap = prev_block.bbox.horizontal_overlap(curr_block.bbox)
        if overlap < 0.8:
            return False
        
        # Check that blocks have similar widths (within 20%)
        prev_width = prev_block.bbox.width
        curr_width = curr_block.bbox.width
        if prev_width > 0 and curr_width > 0:
            width_ratio = min(prev_width, curr_width) / max(prev_width, curr_width)
            if width_ratio < 0.7:
                return False
        
        # Check vertical distance - must be very close
        vertical_gap = prev_block.bbox.y0 - curr_block.bbox.y1
        
        # Estimate font size
        avg_font_size = self._estimate_font_size(prev_block)
        
        # Only merge if gap is less than 1.2x line height
        max_gap = avg_font_size * 1.2
        
        if vertical_gap > max_gap or vertical_gap < 0:
            return False
        
        # Check for significant indentation difference
        indent_diff = abs(prev_block.bbox.x0 - curr_block.bbox.x0)
        if indent_diff > avg_font_size * 1.5:
            return False
        
        return True
    
    def _estimate_font_size(self, block: "RawTextBlock") -> float:
        """Estimate the average font size of a block."""
        if not block.spans:
            return 12.0  # Default font size
        
        sizes = [span.font.size for span in block.spans if span.font.size > 0]
        
        if not sizes:
            return 12.0
        
        return sum(sizes) / len(sizes)
    
    def _create_text_block(
        self,
        blocks: list["RawTextBlock"],
        column_index: int,
    ) -> TextBlock | None:
        """
        Create a TextBlock from a group of raw blocks.
        
        Args:
            blocks: Raw blocks that form a single paragraph.
            column_index: The column index for this block.
        
        Returns:
            A TextBlock, or None if no valid content.
        """
        if not blocks:
            return None
        
        # Collect all spans
        all_spans: list[TextSpan] = []
        for block in blocks:
            all_spans.extend(block.spans)
        
        if not all_spans:
            return None
        
        # Compute combined bounding box
        bbox = self._compute_combined_bbox(blocks)
        
        # Reconstruct text with proper spacing
        text = self._reconstruct_text(blocks)
        
        if not text.strip():
            return None
        
        # Determine block type
        block_type = self._classify_block(blocks, all_spans)
        
        # Determine text alignment
        alignment = self._detect_alignment(blocks, bbox)
        
        # Calculate indentation
        indentation = blocks[0].bbox.x0 - bbox.x0 if len(blocks) > 1 else 0
        
        # Calculate average line spacing
        line_spacing = self._calculate_line_spacing(blocks)
        
        return TextBlock(
            text=text,
            bbox=bbox,
            block_type=block_type,
            spans=tuple(all_spans),
            alignment=alignment,
            indentation=max(0, indentation),
            line_spacing=line_spacing,
            column_index=column_index,
        )
    
    def _compute_combined_bbox(
        self,
        blocks: list["RawTextBlock"],
    ) -> BoundingBox:
        """Compute a bounding box encompassing all blocks."""
        x0 = min(b.bbox.x0 for b in blocks)
        y0 = min(b.bbox.y0 for b in blocks)
        x1 = max(b.bbox.x1 for b in blocks)
        y1 = max(b.bbox.y1 for b in blocks)
        
        return BoundingBox(x0, y0, x1, y1)
    
    def _reconstruct_text(self, blocks: list["RawTextBlock"]) -> str:
        """
        Reconstruct text from blocks with proper handling of line breaks.
        
        Handles:
        - Joining lines within a paragraph
        - Reconstructing hyphenated words
        - Preserving intentional line breaks
        """
        lines: list[str] = []
        
        for block in blocks:
            line_text = block.text.strip()
            if line_text:
                lines.append(line_text)
        
        if not lines:
            return ""
        
        # Join lines, handling hyphenation
        result_parts: list[str] = []
        
        for i, line in enumerate(lines):
            if i == 0:
                result_parts.append(line)
                continue
            
            prev_line = result_parts[-1] if result_parts else ""
            
            # Check for hyphenation
            if prev_line.endswith("-"):
                # Remove hyphen and join without space
                result_parts[-1] = prev_line[:-1]
                result_parts.append(line)
            else:
                # Join with space
                result_parts.append(" " + line)
        
        return "".join(result_parts)
    
    def _classify_block(
        self,
        blocks: list["RawTextBlock"],
        spans: list[TextSpan],
    ) -> BlockType:
        """
        Classify the type of a text block.
        
        Uses heuristics based on:
        - Font size relative to document average
        - Bold/italic styling
        - Text length
        - All caps
        """
        if not spans:
            return BlockType.UNKNOWN
        
        # Check font properties
        avg_size = sum(s.font.size for s in spans) / len(spans)
        is_bold = any(s.font.is_bold for s in spans)
        
        # Get full text
        full_text = " ".join(b.text for b in blocks).strip()
        
        # Heading detection heuristics
        is_short = len(full_text) < 100
        is_all_caps = full_text.isupper() and len(full_text) > 3
        has_large_font = avg_size >= 14  # Larger than typical body text
        
        # Check if it looks like a heading
        if is_short and (is_bold or has_large_font or is_all_caps):
            return BlockType.HEADING
        
        # Check for list item
        list_pattern = re.compile(r"^[\•\-\*\d]+[\.\)]\s")
        if list_pattern.match(full_text):
            return BlockType.LIST_ITEM
        
        return BlockType.PARAGRAPH
    
    def _detect_alignment(
        self,
        blocks: list["RawTextBlock"],
        container_bbox: BoundingBox,
    ) -> TextAlignment:
        """
        Detect the text alignment of a block.
        
        Analyzes the distribution of line start/end positions.
        """
        if len(blocks) < 2:
            return TextAlignment.LEFT  # Default for single line
        
        # Sample multiple blocks for alignment detection
        left_margins: list[float] = []
        right_margins: list[float] = []
        
        for block in blocks:
            left_margins.append(block.bbox.x0 - container_bbox.x0)
            right_margins.append(container_bbox.x1 - block.bbox.x1)
        
        # Calculate variance in margins
        left_variance = self._calculate_variance(left_margins)
        right_variance = self._calculate_variance(right_margins)
        
        threshold = 5.0  # Points
        
        left_aligned = left_variance < threshold
        right_aligned = right_variance < threshold
        
        if left_aligned and right_aligned:
            return TextAlignment.JUSTIFY
        elif right_aligned:
            return TextAlignment.RIGHT
        elif left_aligned:
            return TextAlignment.LEFT
        else:
            return TextAlignment.LEFT  # Default to left
    
    def _calculate_variance(self, values: list[float]) -> float:
        """Calculate variance of a list of values."""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        
        return variance ** 0.5  # Return standard deviation
    
    def _calculate_line_spacing(
        self,
        blocks: list["RawTextBlock"],
    ) -> float:
        """Calculate average vertical spacing between lines."""
        if len(blocks) < 2:
            return 0.0
        
        spacings: list[float] = []
        
        # Sort by vertical position
        sorted_blocks = sorted(blocks, key=lambda b: -b.bbox.y1)
        
        for i in range(len(sorted_blocks) - 1):
            current = sorted_blocks[i]
            next_block = sorted_blocks[i + 1]
            
            spacing = current.bbox.y0 - next_block.bbox.y1
            if spacing > 0:
                spacings.append(spacing)
        
        if not spacings:
            return 0.0
        
        return sum(spacings) / len(spacings)
