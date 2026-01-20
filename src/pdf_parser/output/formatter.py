"""
Output formatters for structured PDF content.

This module provides the OutputFormatter class which converts
StructuredDocument objects into various output formats.
"""

from __future__ import annotations

import json
import logging
from enum import Enum, auto
from typing import Any

from pdf_parser.output.models import (
    StructuredDocument,
    StructuredPage,
    TextBlock,
    Table,
    BlockType,
)
from pdf_parser.tables.ascii_converter import ASCIITableConverter

logger = logging.getLogger(__name__)


class OutputFormat(Enum):
    """Available output formats."""
    
    PLAIN_TEXT = auto()
    MARKDOWN = auto()
    JSON = auto()


class OutputFormatter:
    """
    Formats StructuredDocument objects for output.
    
    Supports multiple output formats:
    - Plain text: Human-readable text with ASCII tables
    - Markdown: Formatted with headers and markdown tables
    - JSON: Structured data for programmatic access
    
    Usage:
        >>> formatter = OutputFormatter()
        >>> text = formatter.format(document, OutputFormat.PLAIN_TEXT)
    """
    
    def __init__(self, include_coordinates: bool = False) -> None:
        """
        Initialize the formatter.
        
        Args:
            include_coordinates: If True, include bounding box coordinates
                               in JSON output.
        """
        self.include_coordinates = include_coordinates
        self._ascii_converter = ASCIITableConverter()
    
    def format(
        self,
        document: StructuredDocument,
        output_format: OutputFormat = OutputFormat.PLAIN_TEXT,
    ) -> str:
        """
        Format a document in the specified format.
        
        Args:
            document: The StructuredDocument to format.
            output_format: The desired output format.
        
        Returns:
            Formatted string representation.
        """
        if output_format == OutputFormat.PLAIN_TEXT:
            return self._format_plain_text(document)
        elif output_format == OutputFormat.MARKDOWN:
            return self._format_markdown(document)
        elif output_format == OutputFormat.JSON:
            return self._format_json(document)
        else:
            raise ValueError(f"Unsupported output format: {output_format}")
    
    def _format_plain_text(self, document: StructuredDocument) -> str:
        """
        Format document as plain text.
        
        Features:
        - Page separators with page numbers
        - Paragraphs separated by blank lines
        - Tables in ASCII format
        - Headers/footers at page boundaries
        """
        lines: list[str] = []
        
        for page in document.pages:
            # Page header
            lines.append("")
            lines.append("=" * 80)
            lines.append(f"{'PAGE ' + str(page.page_number):^80}")
            lines.append("=" * 80)
            lines.append("")
            
            # Page header text
            if page.header:
                lines.append(f"[Header: {page.header}]")
                lines.append("")
            
            # Collect all content items with positions for ordering
            content_items = self._collect_page_content(page)
            
            # Sort by vertical position (top to bottom)
            content_items.sort(key=lambda x: -x[0])
            
            # Output content
            for _, content in content_items:
                lines.append(content)
                lines.append("")
            
            # Page footer text
            if page.footer:
                lines.append("")
                lines.append(f"[Footer: {page.footer}]")
        
        return "\n".join(lines)
    
    def _collect_page_content(
        self,
        page: StructuredPage,
    ) -> list[tuple[float, str]]:
        """
        Collect all content from a page with vertical positions.
        
        Returns list of (y_position, content_string) tuples.
        """
        items: list[tuple[float, str]] = []
        
        # Add text blocks
        for block in page.blocks:
            content = self._format_text_block_plain(block)
            if content.strip():
                items.append((block.bbox.y1, content))
        
        # Add tables
        for table in page.tables:
            if table.ascii_representation:
                items.append((table.bbox.y1, table.ascii_representation))
            else:
                # Generate ASCII representation on the fly
                ascii_table = self._ascii_converter.convert(table)
                items.append((table.bbox.y1, ascii_table))
        
        return items
    
    def _format_text_block_plain(self, block: TextBlock) -> str:
        """Format a text block for plain text output."""
        text = block.text.strip()
        
        if block.block_type == BlockType.HEADING:
            # Make headings stand out
            return f"\n{text.upper()}\n"
        elif block.block_type == BlockType.LIST_ITEM:
            return f"  {text}"
        else:
            return text
    
    def _format_markdown(self, document: StructuredDocument) -> str:
        """
        Format document as Markdown.
        
        Features:
        - Proper heading hierarchy
        - Markdown tables
        - Horizontal rules between pages
        """
        lines: list[str] = []
        
        # Document metadata
        if document.metadata:
            if "title" in document.metadata:
                lines.append(f"# {document.metadata['title']}")
                lines.append("")
            if "author" in document.metadata:
                lines.append(f"*Author: {document.metadata['author']}*")
                lines.append("")
        
        for page in document.pages:
            # Page separator (except for first page)
            if page.page_number > 1:
                lines.append("")
                lines.append("---")
                lines.append("")
                lines.append(f"*Page {page.page_number}*")
                lines.append("")
            
            # Collect and sort content
            content_items = self._collect_page_content_markdown(page)
            content_items.sort(key=lambda x: -x[0])
            
            for _, content in content_items:
                lines.append(content)
                lines.append("")
        
        return "\n".join(lines)
    
    def _collect_page_content_markdown(
        self,
        page: StructuredPage,
    ) -> list[tuple[float, str]]:
        """Collect page content formatted for Markdown."""
        items: list[tuple[float, str]] = []
        
        for block in page.blocks:
            content = self._format_text_block_markdown(block)
            if content.strip():
                items.append((block.bbox.y1, content))
        
        for table in page.tables:
            md_table = self._ascii_converter.convert_to_markdown(table)
            items.append((table.bbox.y1, md_table))
        
        return items
    
    def _format_text_block_markdown(self, block: TextBlock) -> str:
        """Format a text block for Markdown output."""
        text = block.text.strip()
        
        if block.block_type == BlockType.HEADING:
            # Determine heading level based on font size
            # This is a heuristic - larger fonts get higher-level headings
            if block.spans:
                avg_size = sum(s.font.size for s in block.spans) / len(block.spans)
                if avg_size >= 18:
                    return f"## {text}"
                elif avg_size >= 14:
                    return f"### {text}"
                else:
                    return f"#### {text}"
            return f"### {text}"
        elif block.block_type == BlockType.LIST_ITEM:
            # Clean up bullet characters
            clean_text = text.lstrip("•·-* ")
            return f"- {clean_text}"
        else:
            return text
    
    def _format_json(self, document: StructuredDocument) -> str:
        """
        Format document as JSON.
        
        Returns structured JSON with all document data.
        """
        doc_dict = self._document_to_dict(document)
        return json.dumps(doc_dict, indent=2, ensure_ascii=False)
    
    def _document_to_dict(self, document: StructuredDocument) -> dict[str, Any]:
        """Convert a StructuredDocument to a dictionary."""
        return {
            "source_path": document.source_path,
            "page_count": document.page_count,
            "metadata": document.metadata,
            "pages": [
                self._page_to_dict(page)
                for page in document.pages
            ],
        }
    
    def _page_to_dict(self, page: StructuredPage) -> dict[str, Any]:
        """Convert a StructuredPage to a dictionary."""
        page_dict: dict[str, Any] = {
            "page_number": page.page_number,
            "width": page.width,
            "height": page.height,
            "block_count": page.block_count,
            "table_count": page.table_count,
            "header": page.header,
            "footer": page.footer,
            "blocks": [
                self._block_to_dict(block)
                for block in page.blocks
            ],
            "tables": [
                self._table_to_dict(table)
                for table in page.tables
            ],
        }
        
        if self.include_coordinates:
            page_dict["columns"] = [
                {
                    "index": col.index,
                    "bbox": self._bbox_to_dict(col.bbox),
                }
                for col in page.columns
            ]
        
        return page_dict
    
    def _block_to_dict(self, block: TextBlock) -> dict[str, Any]:
        """Convert a TextBlock to a dictionary."""
        block_dict: dict[str, Any] = {
            "text": block.text,
            "type": block.block_type.name,
            "column_index": block.column_index,
        }
        
        if self.include_coordinates:
            block_dict["bbox"] = self._bbox_to_dict(block.bbox)
            block_dict["indentation"] = block.indentation
            block_dict["line_spacing"] = block.line_spacing
        
        return block_dict
    
    def _table_to_dict(self, table: Table) -> dict[str, Any]:
        """Convert a Table to a dictionary."""
        table_dict: dict[str, Any] = {
            "num_rows": table.num_rows,
            "num_cols": table.num_cols,
            "has_header": table.has_header,
            "ascii_representation": table.ascii_representation,
            "cells": [
                self._cell_to_dict(cell)
                for cell in table.cells
            ],
        }
        
        if self.include_coordinates:
            table_dict["bbox"] = self._bbox_to_dict(table.bbox)
        
        return table_dict
    
    def _cell_to_dict(self, cell: "Cell") -> dict[str, Any]:
        """Convert a Cell to a dictionary."""
        from pdf_parser.output.models import Cell
        
        cell_dict: dict[str, Any] = {
            "text": cell.text,
            "row": cell.row,
            "col": cell.col,
            "rowspan": cell.rowspan,
            "colspan": cell.colspan,
            "is_header": cell.is_header,
        }
        
        if self.include_coordinates:
            cell_dict["bbox"] = self._bbox_to_dict(cell.bbox)
        
        return cell_dict
    
    def _bbox_to_dict(self, bbox: "BoundingBox") -> dict[str, float]:
        """Convert a BoundingBox to a dictionary."""
        from pdf_parser.output.models import BoundingBox
        
        return {
            "x0": bbox.x0,
            "y0": bbox.y0,
            "x1": bbox.x1,
            "y1": bbox.y1,
            "width": bbox.width,
            "height": bbox.height,
        }
