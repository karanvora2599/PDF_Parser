"""
Layout analyzer for PDF pages.

This module provides the LayoutAnalyzer class which coordinates the
extraction of structured content from PDF pages, including column detection,
paragraph reconstruction, and table extraction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pdf_parser.core.page import Page, RawTextBlock

from pdf_parser.core.exceptions import LayoutAnalysisError
from pdf_parser.layout.columns import ColumnDetector
from pdf_parser.layout.paragraphs import ParagraphReconstructor
from pdf_parser.tables.detector import TableDetector
from pdf_parser.tables.ascii_converter import ASCIITableConverter
from pdf_parser.output.models import (
    BoundingBox,
    TextBlock,
    BlockType,
    Column,
    StructuredPage,
    Table,
)

logger = logging.getLogger(__name__)


@dataclass
class LayoutConfig:
    """
    Configuration for layout analysis.
    
    Attributes:
        column_gap_threshold: Minimum horizontal gap (in points) to detect column separation.
        paragraph_gap_threshold: Minimum vertical gap (as ratio of font size) for paragraph break.
        header_margin: Top margin (in points) to consider as header area.
        footer_margin: Bottom margin (in points) to consider as footer area.
        detect_tables: Whether to detect and extract tables.
        merge_close_blocks: Whether to merge blocks that are very close together.
    """
    
    column_gap_threshold: float = 20.0
    paragraph_gap_threshold: float = 1.5
    header_margin: float = 72.0  # 1 inch
    footer_margin: float = 72.0  # 1 inch
    detect_tables: bool = True
    merge_close_blocks: bool = True


class LayoutAnalyzer:
    """
    Analyzes PDF page layout and extracts structured content.
    
    This class coordinates multiple analysis components:
    - Column detection for multi-column layouts
    - Paragraph reconstruction for text flow
    - Table detection and extraction
    - Header/footer identification
    
    Usage:
        >>> analyzer = LayoutAnalyzer()
        >>> structured_page = analyzer.analyze_page(page)
    """
    
    def __init__(self, config: LayoutConfig | None = None) -> None:
        """
        Initialize the layout analyzer.
        
        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or LayoutConfig()
        self._column_detector = ColumnDetector(
            gap_threshold=self.config.column_gap_threshold
        )
        self._paragraph_reconstructor = ParagraphReconstructor(
            gap_threshold=self.config.paragraph_gap_threshold
        )
        self._table_detector = TableDetector()
        self._ascii_converter = ASCIITableConverter()
    
    def analyze_page(self, page: "Page") -> StructuredPage:
        """
        Analyze a page and extract structured content.
        
        Args:
            page: The Page to analyze.
        
        Returns:
            A StructuredPage with full layout information.
        
        Raises:
            LayoutAnalysisError: If analysis fails critically.
        """
        logger.debug("Analyzing page %d", page.page_number)
        
        # Step 1: Extract raw text blocks
        raw_blocks = page.extract_raw_blocks()
        
        if not raw_blocks:
            logger.debug("Page %d has no text blocks", page.page_number)
            return StructuredPage(
                page_number=page.page_number,
                width=page.width,
                height=page.height,
            )
        
        # Step 2: Identify header and footer regions
        header_text, footer_text, content_blocks = self._separate_header_footer(
            raw_blocks, page.height
        )
        
        # Step 3: Detect tables and filter out table regions from blocks
        tables: list[Table] = []
        if self.config.detect_tables:
            tables, content_blocks = self._extract_tables(
                page, content_blocks
            )
        
        # Step 4: Detect columns
        try:
            columns = self._column_detector.detect(content_blocks, page.width)
        except Exception as e:
            logger.warning(
                "Column detection failed on page %d: %s",
                page.page_number, e
            )
            columns = []
        
        # Step 5: Reconstruct paragraphs within each column
        text_blocks: list[TextBlock] = []
        structured_columns: list[Column] = []
        
        if columns:
            for col in columns:
                col_blocks = self._paragraph_reconstructor.reconstruct(
                    col.blocks, col.index
                )
                text_blocks.extend(col_blocks)
                
                structured_columns.append(Column(
                    bbox=col.bbox,
                    index=col.index,
                    blocks=tuple(col_blocks),
                ))
        else:
            # Single column - process all blocks together
            text_blocks = self._paragraph_reconstructor.reconstruct(
                content_blocks, column_index=0
            )
            
            if text_blocks:
                # Create a single column spanning the page
                col_bbox = self._compute_bounding_box([b.bbox for b in text_blocks])
                structured_columns.append(Column(
                    bbox=col_bbox,
                    index=0,
                    blocks=tuple(text_blocks),
                ))
        
        # Step 6: Sort blocks in reading order
        sorted_blocks = self._sort_reading_order(text_blocks, structured_columns)
        
        return StructuredPage(
            page_number=page.page_number,
            width=page.width,
            height=page.height,
            blocks=tuple(sorted_blocks),
            tables=tuple(tables),
            columns=tuple(structured_columns),
            header=header_text,
            footer=footer_text,
        )
    
    def _separate_header_footer(
        self,
        blocks: list["RawTextBlock"],
        page_height: float,
    ) -> tuple[str, str, list["RawTextBlock"]]:
        """
        Separate header and footer content from main content.
        
        Returns:
            Tuple of (header_text, footer_text, remaining_blocks).
        """
        header_blocks: list["RawTextBlock"] = []
        footer_blocks: list["RawTextBlock"] = []
        content_blocks: list["RawTextBlock"] = []
        
        header_threshold = page_height - self.config.header_margin
        footer_threshold = self.config.footer_margin
        
        for block in blocks:
            # Check if block is in header region (top of page)
            if block.bbox.y1 > header_threshold:
                header_blocks.append(block)
            # Check if block is in footer region (bottom of page)
            elif block.bbox.y0 < footer_threshold:
                footer_blocks.append(block)
            else:
                content_blocks.append(block)
        
        header_text = " ".join(b.text for b in header_blocks)
        footer_text = " ".join(b.text for b in footer_blocks)
        
        return header_text.strip(), footer_text.strip(), content_blocks
    
    def _extract_tables(
        self,
        page: "Page",
        blocks: list["RawTextBlock"],
    ) -> tuple[list[Table], list["RawTextBlock"]]:
        """
        Extract tables from the page and filter blocks that are part of tables.
        
        Returns:
            Tuple of (tables, blocks_without_table_content).
        """
        try:
            tables = self._table_detector.detect_tables(page)
        except Exception as e:
            logger.warning(
                "Table detection failed on page %d: %s",
                page.page_number, e
            )
            return [], blocks
        
        if not tables:
            return [], blocks
        
        # Convert tables to ASCII and filter out overlapping blocks
        final_tables: list[Table] = []
        table_bboxes: list[BoundingBox] = []
        
        for table in tables:
            ascii_repr = self._ascii_converter.convert(table)
            # Create new table with ASCII representation
            final_tables.append(Table(
                cells=table.cells,
                bbox=table.bbox,
                num_rows=table.num_rows,
                num_cols=table.num_cols,
                has_header=table.has_header,
                ascii_representation=ascii_repr,
            ))
            table_bboxes.append(table.bbox)
        
        # Filter out blocks that overlap with table regions
        filtered_blocks: list["RawTextBlock"] = []
        for block in blocks:
            overlaps_table = any(
                block.bbox.intersects(table_bbox)
                for table_bbox in table_bboxes
            )
            if not overlaps_table:
                filtered_blocks.append(block)
        
        return final_tables, filtered_blocks
    
    def _compute_bounding_box(self, bboxes: list[BoundingBox]) -> BoundingBox:
        """Compute a bounding box that encompasses all given boxes."""
        if not bboxes:
            return BoundingBox(0, 0, 0, 0)
        
        x0 = min(b.x0 for b in bboxes)
        y0 = min(b.y0 for b in bboxes)
        x1 = max(b.x1 for b in bboxes)
        y1 = max(b.y1 for b in bboxes)
        
        return BoundingBox(x0, y0, x1, y1)
    
    def _sort_reading_order(
        self,
        blocks: list[TextBlock],
        columns: list[Column],
    ) -> list[TextBlock]:
        """
        Sort blocks in natural reading order.
        
        Reading order is: left-to-right by column, top-to-bottom within column.
        """
        if not blocks:
            return []
        
        if len(columns) <= 1:
            # Single column: sort top to bottom (higher y first)
            return sorted(blocks, key=lambda b: -b.bbox.y1)
        
        # Multi-column: sort by column index, then by vertical position
        return sorted(blocks, key=lambda b: (b.column_index, -b.bbox.y1))
