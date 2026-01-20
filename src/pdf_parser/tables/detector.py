"""
Table detector for PDF pages.

This module provides the TableDetector class which identifies and extracts
tables from PDF pages using multiple detection strategies.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pdf_parser.core.page import Page

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

from pdf_parser.core.exceptions import TableExtractionError
from pdf_parser.output.models import (
    BoundingBox,
    Cell,
    Table,
    TextAlignment,
)

logger = logging.getLogger(__name__)


class TableSettings:
    """
    Settings for table detection.
    
    These settings control how pdfplumber detects tables.
    Sensible defaults are provided but can be customized.
    """
    
    # Minimum number of rows/columns to consider as a table
    min_rows: int = 2
    min_cols: int = 2
    
    # Table detection parameters for pdfplumber
    vertical_strategy: str = "lines"
    horizontal_strategy: str = "lines"
    
    # Snap tolerance for aligning table edges
    snap_tolerance: int = 3
    
    # Minimum cell size
    min_cell_width: float = 10.0
    min_cell_height: float = 5.0


class TableDetector:
    """
    Detects and extracts tables from PDF pages.
    
    This detector uses pdfplumber as the primary detection engine,
    with fallback strategies for tables without visible borders.
    
    Usage:
        >>> detector = TableDetector()
        >>> tables = detector.detect_tables(page)
    """
    
    def __init__(self, settings: TableSettings | None = None) -> None:
        """
        Initialize the table detector.
        
        Args:
            settings: Optional detection settings. Uses defaults if not provided.
        """
        self.settings = settings or TableSettings()
        self._pdf_cache: dict[str, "pdfplumber.PDF"] = {}
    
    def detect_tables(self, page: "Page") -> list[Table]:
        """
        Detect all tables on a page.
        
        Args:
            page: The Page to analyze.
        
        Returns:
            List of Table objects found on the page.
        """
        if not HAS_PDFPLUMBER:
            logger.warning(
                "pdfplumber not installed, table detection unavailable"
            )
            return []
        
        try:
            tables = self._detect_with_pdfplumber(page)
            
            # Validate detected tables
            valid_tables = [
                t for t in tables
                if self._validate_table(t)
            ]
            
            if valid_tables:
                logger.debug(
                    "Found %d valid tables on page %d",
                    len(valid_tables), page.page_number
                )
            
            return valid_tables
            
        except Exception as e:
            logger.warning(
                "Table detection failed on page %d: %s",
                page.page_number, e
            )
            return []
    
    def _detect_with_pdfplumber(self, page: "Page") -> list[Table]:
        """
        Detect tables using pdfplumber.
        
        This is the primary detection method.
        """
        # Get or create pdfplumber PDF
        plumber_pdf = self._get_pdfplumber_pdf(page)
        
        if plumber_pdf is None:
            return []
        
        # Get the specific page (0-indexed in pdfplumber)
        try:
            plumber_page = plumber_pdf.pages[page.page_number - 1]
        except IndexError:
            logger.error(
                "Page %d not found in pdfplumber PDF",
                page.page_number
            )
            return []
        
        # Configure table detection
        table_settings = {
            "vertical_strategy": self.settings.vertical_strategy,
            "horizontal_strategy": self.settings.horizontal_strategy,
            "snap_tolerance": self.settings.snap_tolerance,
        }
        
        # Find tables
        try:
            plumber_tables = plumber_page.find_tables(table_settings)
        except Exception as e:
            logger.debug("pdfplumber find_tables failed: %s", e)
            return []
        
        # Convert to our Table format
        tables: list[Table] = []
        
        for plumber_table in plumber_tables:
            table = self._convert_pdfplumber_table(plumber_table, page.height)
            if table:
                tables.append(table)
        
        return tables
    
    def _get_pdfplumber_pdf(self, page: "Page") -> "pdfplumber.PDF | None":
        """
        Get or create a pdfplumber PDF for the given page's document.
        """
        # Access the underlying fitz document path
        pdf_path = page._page.parent.name
        
        if pdf_path in self._pdf_cache:
            return self._pdf_cache[pdf_path]
        
        try:
            plumber_pdf = pdfplumber.open(pdf_path)
            self._pdf_cache[pdf_path] = plumber_pdf
            return plumber_pdf
        except Exception as e:
            logger.warning("Failed to open PDF with pdfplumber: %s", e)
            return None
    
    def _convert_pdfplumber_table(
        self,
        plumber_table,
        page_height: float,
    ) -> Table | None:
        """
        Convert a pdfplumber table to our Table format.
        
        Args:
            plumber_table: A pdfplumber Table object.
            page_height: Height of the page (for coordinate conversion).
        
        Returns:
            A Table object, or None if conversion fails.
        """
        try:
            # Extract table data
            data = plumber_table.extract()
            
            if not data or len(data) < self.settings.min_rows:
                return None
            
            # Get table bounding box (pdfplumber uses top-left origin)
            bbox_tuple = plumber_table.bbox
            
            # Convert coordinates (pdfplumber uses top-left, we use bottom-left)
            bbox = BoundingBox(
                x0=bbox_tuple[0],
                y0=page_height - bbox_tuple[3],  # Convert y coordinates
                x1=bbox_tuple[2],
                y1=page_height - bbox_tuple[1],
            )
            
            # Create cells
            cells = self._create_cells_from_data(data, bbox)
            
            if not cells:
                return None
            
            num_rows = len(data)
            num_cols = max(len(row) for row in data) if data else 0
            
            if num_cols < self.settings.min_cols:
                return None
            
            # Detect if first row is a header
            has_header = self._detect_header(data)
            
            return Table(
                cells=tuple(cells),
                bbox=bbox,
                num_rows=num_rows,
                num_cols=num_cols,
                has_header=has_header,
            )
            
        except Exception as e:
            logger.debug("Failed to convert pdfplumber table: %s", e)
            return None
    
    def _create_cells_from_data(
        self,
        data: list[list[str | None]],
        table_bbox: BoundingBox,
    ) -> list[Cell]:
        """
        Create Cell objects from extracted table data.
        
        Since pdfplumber doesn't provide cell-level bounding boxes easily,
        we estimate them based on the table structure.
        """
        if not data:
            return []
        
        num_rows = len(data)
        num_cols = max(len(row) for row in data) if data else 0
        
        if num_rows == 0 or num_cols == 0:
            return []
        
        # Calculate approximate cell dimensions
        cell_width = table_bbox.width / num_cols
        cell_height = table_bbox.height / num_rows
        
        cells: list[Cell] = []
        
        for row_idx, row in enumerate(data):
            for col_idx, cell_text in enumerate(row):
                # Skip None cells (can happen with merged cells)
                if cell_text is None:
                    cell_text = ""
                
                # Calculate cell bounding box
                x0 = table_bbox.x0 + (col_idx * cell_width)
                x1 = x0 + cell_width
                
                # Y coordinates (remember: bottom-left origin, top-to-bottom rows)
                y1 = table_bbox.y1 - (row_idx * cell_height)
                y0 = y1 - cell_height
                
                cell_bbox = BoundingBox(x0, y0, x1, y1)
                
                cell = Cell(
                    text=str(cell_text).strip(),
                    bbox=cell_bbox,
                    row=row_idx,
                    col=col_idx,
                    is_header=(row_idx == 0),
                    alignment=TextAlignment.LEFT,
                )
                
                cells.append(cell)
        
        return cells
    
    def _detect_header(self, data: list[list[str | None]]) -> bool:
        """
        Detect if the first row appears to be a header row.
        
        Heuristics:
        - First row has different formatting (all bold, all caps, etc.)
        - First row has shorter text than data rows
        - First row has no numeric values
        """
        if len(data) < 2:
            return False
        
        first_row = data[0]
        
        if not first_row:
            return False
        
        # Check if first row is all caps
        first_row_text = " ".join(str(c or "") for c in first_row)
        if first_row_text.isupper() and len(first_row_text) > 3:
            return True
        
        # Check if first row has shorter entries on average
        first_row_avg_len = sum(len(str(c or "")) for c in first_row) / len(first_row)
        
        other_lengths: list[float] = []
        for row in data[1:]:
            if row:
                avg_len = sum(len(str(c or "")) for c in row) / len(row)
                other_lengths.append(avg_len)
        
        if other_lengths:
            other_avg = sum(other_lengths) / len(other_lengths)
            if first_row_avg_len < other_avg * 0.7:
                return True
        
        # Check if first row has no numbers
        import re
        has_numbers = any(
            re.search(r'\d+\.?\d*', str(c or ""))
            for c in first_row
            if c
        )
        
        data_rows_have_numbers = any(
            any(re.search(r'\d+\.?\d*', str(c or "")) for c in row if c)
            for row in data[1:]
        )
        
        if not has_numbers and data_rows_have_numbers:
            return True
        
        return False
    
    def _validate_table(self, table: Table) -> bool:
        """
        Validate that a detected table is reasonable.
        
        Filters out false positives like single rows or columns.
        """
        if table.num_rows < self.settings.min_rows:
            return False
        
        if table.num_cols < self.settings.min_cols:
            return False
        
        # Check that table has reasonable dimensions
        if table.bbox.width < self.settings.min_cell_width * 2:
            return False
        
        if table.bbox.height < self.settings.min_cell_height * 2:
            return False
        
        # Check that at least some cells have content
        non_empty_cells = sum(1 for c in table.cells if c.text.strip())
        total_cells = len(table.cells)
        
        if total_cells > 0 and non_empty_cells / total_cells < 0.3:
            # Less than 30% of cells have content - probably not a real table
            return False
        
        return True
    
    def close(self) -> None:
        """Clean up pdfplumber resources."""
        for pdf in self._pdf_cache.values():
            try:
                pdf.close()
            except Exception:
                pass
        self._pdf_cache.clear()
