"""
Column detector for multi-column layouts.

This module provides the ColumnDetector class which identifies column
regions in a PDF page based on block positioning analysis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pdf_parser.core.page import RawTextBlock

from pdf_parser.output.models import BoundingBox

logger = logging.getLogger(__name__)


@dataclass
class DetectedColumn:
    """
    A detected column region with its blocks.
    
    Attributes:
        bbox: Bounding box of the column region.
        index: Column index from left to right (0-indexed).
        blocks: Raw text blocks within this column.
    """
    
    bbox: BoundingBox
    index: int
    blocks: list["RawTextBlock"] = field(default_factory=list)


class ColumnDetector:
    """
    Detects column regions in a PDF page.
    
    This detector uses a simple but effective algorithm:
    1. Analyze block center positions to find clustering
    2. Detect if blocks cluster in left vs right halves
    3. For two-column layouts, use page center as divider
    
    This works well for academic papers and similar documents.
    """
    
    def __init__(self, gap_threshold: float = 20.0) -> None:
        """
        Initialize the column detector.
        
        Args:
            gap_threshold: Minimum horizontal gap (in points) to consider as
                          a column separator. Default is 20 points.
        """
        self.gap_threshold = gap_threshold
    
    def detect(
        self,
        blocks: list["RawTextBlock"],
        page_width: float,
    ) -> list[DetectedColumn]:
        """
        Detect columns in a set of text blocks.
        
        Args:
            blocks: Raw text blocks from the page.
            page_width: Width of the page in points.
        
        Returns:
            List of DetectedColumn objects, sorted left to right.
            Returns empty list if only one column is detected.
        """
        if not blocks:
            return []
        
        # Try simple two-column detection first (most common case)
        two_col_result = self._detect_two_columns(blocks, page_width)
        if two_col_result:
            logger.debug("Detected 2 columns using center-split method")
            return two_col_result
        
        # Fall back to gap-based detection for more complex layouts
        gaps = self._find_horizontal_gaps(blocks, page_width)
        
        if not gaps:
            logger.debug("No column gaps detected - single column layout")
            return []
        
        # Create column regions based on gaps
        columns = self._create_columns_from_gaps(gaps, blocks, page_width)
        
        if len(columns) <= 1:
            return []
        
        logger.debug("Detected %d columns using gap method", len(columns))
        return columns
    
    def _detect_two_columns(
        self,
        blocks: list["RawTextBlock"],
        page_width: float,
    ) -> list[DetectedColumn] | None:
        """
        Detect two-column layout using page center as divider.
        
        This is optimized for academic papers and similar documents.
        
        Returns:
            List of two columns if detected, None otherwise.
        """
        if len(blocks) < 4:
            # Need at least a few blocks to detect columns
            return None
        
        page_center = page_width / 2
        margin = 50  # Assume at least 50pt margins
        
        left_blocks: list["RawTextBlock"] = []
        right_blocks: list["RawTextBlock"] = []
        center_blocks: list["RawTextBlock"] = []  # Blocks spanning center
        
        for block in blocks:
            block_center = (block.bbox.x0 + block.bbox.x1) / 2
            block_width = block.bbox.x1 - block.bbox.x0
            
            # Check if block spans across the center (likely a header/title)
            if block.bbox.x0 < page_center - 30 and block.bbox.x1 > page_center + 30:
                # This block spans both columns (e.g., title)
                center_blocks.append(block)
            elif block_center < page_center:
                left_blocks.append(block)
            else:
                right_blocks.append(block)
        
        # Check if we have a valid two-column layout
        # Both sides should have content
        if len(left_blocks) < 2 or len(right_blocks) < 2:
            return None
        
        # Check for a clear gap between columns
        # Get the rightmost point of left column and leftmost point of right column
        if left_blocks and right_blocks:
            left_max_x = max(b.bbox.x1 for b in left_blocks)
            right_min_x = min(b.bbox.x0 for b in right_blocks)
            gap = right_min_x - left_max_x
            
            if gap < 10:  # Less than 10 points gap - probably not two columns
                return None
        
        # Build column objects
        columns: list[DetectedColumn] = []
        
        # Left column
        if left_blocks:
            y_values = [b.bbox.y0 for b in left_blocks] + [b.bbox.y1 for b in left_blocks]
            left_col = DetectedColumn(
                bbox=BoundingBox(
                    margin,
                    min(y_values),
                    page_center - self.gap_threshold / 2,
                    max(y_values)
                ),
                index=0,
                blocks=left_blocks,
            )
            columns.append(left_col)
        
        # Right column  
        if right_blocks:
            y_values = [b.bbox.y0 for b in right_blocks] + [b.bbox.y1 for b in right_blocks]
            right_col = DetectedColumn(
                bbox=BoundingBox(
                    page_center + self.gap_threshold / 2,
                    min(y_values),
                    page_width - margin,
                    max(y_values)
                ),
                index=1,
                blocks=right_blocks,
            )
            columns.append(right_col)
        
        # Handle center-spanning blocks (like titles)
        # Add them to the first column for proper ordering
        if center_blocks and columns:
            columns[0].blocks = center_blocks + columns[0].blocks
        
        return columns if len(columns) == 2 else None
    
    def _find_horizontal_gaps(
        self,
        blocks: list["RawTextBlock"],
        page_width: float,
    ) -> list[tuple[float, float]]:
        """
        Find significant horizontal gaps between blocks.
        
        Returns:
            List of (gap_start, gap_end) tuples representing gap regions.
        """
        if not blocks:
            return []
        
        # Create a projection of blocks onto the horizontal axis
        coverage: list[tuple[float, float]] = []
        
        for block in blocks:
            coverage.append((block.bbox.x0, block.bbox.x1))
        
        # Sort by start position
        coverage.sort(key=lambda c: c[0])
        
        # Merge overlapping regions
        merged: list[tuple[float, float]] = []
        for start, end in coverage:
            if merged and start <= merged[-1][1] + self.gap_threshold:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        
        # Find gaps between merged regions
        gaps: list[tuple[float, float]] = []
        for i in range(len(merged) - 1):
            gap_start = merged[i][1]
            gap_end = merged[i + 1][0]
            gap_width = gap_end - gap_start
            
            if gap_width >= self.gap_threshold:
                gaps.append((gap_start, gap_end))
        
        return gaps
    
    def _create_columns_from_gaps(
        self,
        gaps: list[tuple[float, float]],
        blocks: list["RawTextBlock"],
        page_width: float,
    ) -> list[DetectedColumn]:
        """
        Create column regions based on detected gaps.
        """
        if not gaps:
            return []
        
        # Define column boundaries
        boundaries: list[tuple[float, float]] = []
        
        # First column: from left edge to first gap
        boundaries.append((0, gaps[0][0]))
        
        # Middle columns: between gaps
        for i in range(len(gaps) - 1):
            boundaries.append((gaps[i][1], gaps[i + 1][0]))
        
        # Last column: from last gap to right edge
        boundaries.append((gaps[-1][1], page_width))
        
        # Create columns and assign blocks
        columns: list[DetectedColumn] = []
        
        for idx, (left, right) in enumerate(boundaries):
            col_blocks: list["RawTextBlock"] = []
            y_values: list[float] = []
            
            for block in blocks:
                block_center_x = (block.bbox.x0 + block.bbox.x1) / 2
                
                if left <= block_center_x <= right:
                    col_blocks.append(block)
                    y_values.extend([block.bbox.y0, block.bbox.y1])
            
            if col_blocks:
                min_y = min(y_values) if y_values else 0
                max_y = max(y_values) if y_values else 0
                
                column = DetectedColumn(
                    bbox=BoundingBox(left, min_y, right, max_y),
                    index=idx,
                    blocks=col_blocks,
                )
                columns.append(column)
        
        return columns
    
    def estimate_column_count(
        self,
        blocks: list["RawTextBlock"],
        page_width: float,
    ) -> int:
        """
        Estimate the number of columns on a page.
        """
        if not blocks:
            return 1
        
        # Quick check using page center
        page_center = page_width / 2
        left_count = sum(1 for b in blocks if (b.bbox.x0 + b.bbox.x1) / 2 < page_center)
        right_count = len(blocks) - left_count
        
        if left_count >= 2 and right_count >= 2:
            return 2
        
        return 1
