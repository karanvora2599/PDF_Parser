"""
ASCII table converter.

This module provides the ASCIITableConverter class which converts
Table objects into formatted ASCII art representations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

from pdf_parser.output.models import Table, Cell, TextAlignment

logger = logging.getLogger(__name__)


@dataclass
class ASCIITableStyle:
    """
    Style configuration for ASCII table rendering.
    
    Attributes:
        horizontal: Character for horizontal lines.
        vertical: Character for vertical lines.
        corner: Character for corners/intersections.
        header_separator: Whether to add a separator after the header row.
        padding: Number of spaces to pad cell content.
        max_cell_width: Maximum width for a cell (text will be wrapped).
        min_cell_width: Minimum width for a cell.
    """
    
    horizontal: str = "-"
    vertical: str = "|"
    corner: str = "+"
    header_separator: bool = True
    padding: int = 1
    max_cell_width: int = 40
    min_cell_width: int = 3


class ASCIITableConverter:
    """
    Converts Table objects to ASCII art format.
    
    This converter creates clean, readable ASCII representations of tables
    with proper alignment, borders, and cell wrapping.
    
    Example output:
        +------------+----------+--------+
        | Product    | Quantity | Price  |
        +------------+----------+--------+
        | Widget A   | 100      | $10.00 |
        | Widget B   | 250      | $15.50 |
        +------------+----------+--------+
    
    Usage:
        >>> converter = ASCIITableConverter()
        >>> ascii_table = converter.convert(table)
    """
    
    def __init__(self, style: ASCIITableStyle | None = None) -> None:
        """
        Initialize the converter.
        
        Args:
            style: Optional style configuration. Uses defaults if not provided.
        """
        self.style = style or ASCIITableStyle()
    
    def convert(self, table: Table) -> str:
        """
        Convert a Table to ASCII format.
        
        Args:
            table: The Table to convert.
        
        Returns:
            ASCII art string representation of the table.
        """
        if not table.cells or table.num_rows == 0 or table.num_cols == 0:
            return ""
        
        try:
            # Build a 2D grid of cell contents
            grid = self._build_grid(table)
            
            # Calculate column widths
            col_widths = self._calculate_column_widths(grid, table.num_cols)
            
            # Render the ASCII table
            lines = self._render_table(grid, col_widths, table.has_header)
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.warning("Failed to convert table to ASCII: %s", e)
            return self._fallback_convert(table)
    
    def _build_grid(self, table: Table) -> list[list[str]]:
        """
        Build a 2D grid of cell contents.
        
        Handles missing cells and merged cells.
        """
        grid: list[list[str]] = []
        
        for row_idx in range(table.num_rows):
            row: list[str] = []
            for col_idx in range(table.num_cols):
                cell = table.get_cell(row_idx, col_idx)
                if cell:
                    row.append(cell.text)
                else:
                    row.append("")
            grid.append(row)
        
        return grid
    
    def _calculate_column_widths(
        self,
        grid: list[list[str]],
        num_cols: int,
    ) -> list[int]:
        """
        Calculate optimal width for each column.
        
        Takes into account:
        - Maximum content width in each column
        - Min/max width constraints
        - Padding
        """
        widths: list[int] = []
        
        for col_idx in range(num_cols):
            # Find maximum content width in this column
            max_width = self.style.min_cell_width
            
            for row in grid:
                if col_idx < len(row):
                    cell_text = row[col_idx]
                    # Handle multi-line content
                    for line in cell_text.split("\n"):
                        max_width = max(max_width, len(line))
            
            # Apply max width constraint
            width = min(max_width, self.style.max_cell_width)
            
            widths.append(width)
        
        return widths
    
    def _render_table(
        self,
        grid: list[list[str]],
        col_widths: list[int],
        has_header: bool,
    ) -> list[str]:
        """
        Render the complete ASCII table.
        """
        lines: list[str] = []
        
        # Top border
        lines.append(self._render_separator(col_widths))
        
        # Render each row
        for row_idx, row in enumerate(grid):
            # Render row content (may span multiple lines for wrapped cells)
            row_lines = self._render_row(row, col_widths)
            lines.extend(row_lines)
            
            # Add separator after header row
            if has_header and row_idx == 0:
                lines.append(self._render_separator(col_widths))
            elif row_idx < len(grid) - 1:
                # Optional: add separator between all rows
                # Uncomment next line for full grid style:
                # lines.append(self._render_separator(col_widths))
                pass
        
        # Bottom border
        lines.append(self._render_separator(col_widths))
        
        return lines
    
    def _render_separator(self, col_widths: list[int]) -> str:
        """
        Render a horizontal separator line.
        
        Example: +--------+--------+--------+
        """
        parts: list[str] = [self.style.corner]
        
        for width in col_widths:
            # Width + padding on both sides
            total_width = width + (self.style.padding * 2)
            parts.append(self.style.horizontal * total_width)
            parts.append(self.style.corner)
        
        return "".join(parts)
    
    def _render_row(
        self,
        row: list[str],
        col_widths: list[int],
    ) -> list[str]:
        """
        Render a data row, handling text wrapping.
        
        Returns multiple lines if any cell content needs wrapping.
        """
        # Wrap cell contents and split into lines
        wrapped_cells: list[list[str]] = []
        
        for col_idx, cell_text in enumerate(row):
            if col_idx < len(col_widths):
                width = col_widths[col_idx]
                wrapped = self._wrap_text(cell_text, width)
                wrapped_cells.append(wrapped)
            else:
                wrapped_cells.append([""])
        
        # Ensure all cells have same number of lines
        max_lines = max(len(cell) for cell in wrapped_cells) if wrapped_cells else 1
        
        for cell in wrapped_cells:
            while len(cell) < max_lines:
                cell.append("")
        
        # Render each line of the row
        output_lines: list[str] = []
        
        for line_idx in range(max_lines):
            parts: list[str] = [self.style.vertical]
            
            for col_idx, col_width in enumerate(col_widths):
                if col_idx < len(wrapped_cells):
                    cell_line = wrapped_cells[col_idx][line_idx]
                else:
                    cell_line = ""
                
                # Pad the cell content
                padding = " " * self.style.padding
                padded = f"{padding}{cell_line.ljust(col_width)}{padding}"
                
                parts.append(padded)
                parts.append(self.style.vertical)
            
            output_lines.append("".join(parts))
        
        return output_lines
    
    def _wrap_text(self, text: str, width: int) -> list[str]:
        """
        Wrap text to fit within the specified width.
        
        Preserves existing line breaks and wraps long lines.
        """
        if not text:
            return [""]
        
        lines: list[str] = []
        
        # First, split on existing newlines
        for paragraph in text.split("\n"):
            if len(paragraph) <= width:
                lines.append(paragraph)
            else:
                # Wrap long lines
                wrapped = self._wrap_line(paragraph, width)
                lines.extend(wrapped)
        
        return lines if lines else [""]
    
    def _wrap_line(self, line: str, width: int) -> list[str]:
        """
        Wrap a single line to fit within the width.
        
        Tries to break on word boundaries.
        """
        if len(line) <= width:
            return [line]
        
        words = line.split()
        lines: list[str] = []
        current_line: list[str] = []
        current_length = 0
        
        for word in words:
            word_len = len(word)
            
            if current_length + word_len + len(current_line) <= width:
                current_line.append(word)
                current_length += word_len
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                
                # Handle words longer than width
                if word_len > width:
                    # Split the word
                    while len(word) > width:
                        lines.append(word[:width-1] + "-")
                        word = word[width-1:]
                    current_line = [word] if word else []
                    current_length = len(word)
                else:
                    current_line = [word]
                    current_length = word_len
        
        if current_line:
            lines.append(" ".join(current_line))
        
        return lines if lines else [""]
    
    def _fallback_convert(self, table: Table) -> str:
        """
        Simple fallback conversion when primary method fails.
        
        Creates a basic text representation without fancy formatting.
        """
        lines: list[str] = []
        
        for row_idx in range(table.num_rows):
            cells = table.get_row(row_idx)
            cell_texts = [c.text for c in cells]
            lines.append(" | ".join(cell_texts))
        
        return "\n".join(lines)
    
    def convert_to_markdown(self, table: Table) -> str:
        """
        Convert a Table to Markdown table format.
        
        This is an alternative output format for Markdown documents.
        
        Args:
            table: The Table to convert.
        
        Returns:
            Markdown table string.
        """
        if not table.cells or table.num_rows == 0 or table.num_cols == 0:
            return ""
        
        lines: list[str] = []
        
        # Build grid
        grid = self._build_grid(table)
        
        # Calculate column widths
        col_widths = self._calculate_column_widths(grid, table.num_cols)
        
        # Render rows
        for row_idx, row in enumerate(grid):
            cells = [
                self._pad_cell(row[i] if i < len(row) else "", col_widths[i])
                for i in range(len(col_widths))
            ]
            lines.append("| " + " | ".join(cells) + " |")
            
            # Add header separator after first row
            if row_idx == 0:
                separators = ["-" * w for w in col_widths]
                lines.append("| " + " | ".join(separators) + " |")
        
        return "\n".join(lines)
    
    def _pad_cell(self, text: str, width: int) -> str:
        """Pad cell text to the specified width."""
        # Replace newlines with spaces for markdown
        text = text.replace("\n", " ")
        return text.ljust(width)[:width]
