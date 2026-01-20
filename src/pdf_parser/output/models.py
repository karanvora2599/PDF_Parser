"""
Data models for the PDF Parser output.

This module defines the core data structures used to represent parsed PDF content
with full layout information preserved. All models are immutable dataclasses
with complete type annotations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Iterator


class BlockType(Enum):
    """Classification of content blocks."""
    
    PARAGRAPH = auto()
    HEADING = auto()
    LIST_ITEM = auto()
    FOOTNOTE = auto()
    HEADER = auto()
    FOOTER = auto()
    CAPTION = auto()
    UNKNOWN = auto()


class TextAlignment(Enum):
    """Text alignment within a block."""
    
    LEFT = auto()
    CENTER = auto()
    RIGHT = auto()
    JUSTIFY = auto()
    UNKNOWN = auto()


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """
    A rectangular bounding box with coordinates.
    
    Coordinates follow PDF convention: origin at bottom-left of page,
    with y increasing upward. All values are in points (1/72 inch).
    
    Attributes:
        x0: Left edge x-coordinate.
        y0: Bottom edge y-coordinate.
        x1: Right edge x-coordinate.
        y1: Top edge y-coordinate.
    """
    
    x0: float
    y0: float
    x1: float
    y1: float
    
    def __post_init__(self) -> None:
        """Validate bounding box coordinates."""
        if self.x0 > self.x1:
            raise ValueError(f"x0 ({self.x0}) must be <= x1 ({self.x1})")
        if self.y0 > self.y1:
            raise ValueError(f"y0 ({self.y0}) must be <= y1 ({self.y1})")
    
    @property
    def width(self) -> float:
        """Width of the bounding box."""
        return self.x1 - self.x0
    
    @property
    def height(self) -> float:
        """Height of the bounding box."""
        return self.y1 - self.y0
    
    @property
    def area(self) -> float:
        """Area of the bounding box."""
        return self.width * self.height
    
    @property
    def center(self) -> tuple[float, float]:
        """Center point (x, y) of the bounding box."""
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)
    
    def intersects(self, other: BoundingBox) -> bool:
        """Check if this bounding box intersects with another."""
        return not (
            self.x1 < other.x0
            or self.x0 > other.x1
            or self.y1 < other.y0
            or self.y0 > other.y1
        )
    
    def contains(self, other: BoundingBox) -> bool:
        """Check if this bounding box fully contains another."""
        return (
            self.x0 <= other.x0
            and self.x1 >= other.x1
            and self.y0 <= other.y0
            and self.y1 >= other.y1
        )
    
    def vertical_distance(self, other: BoundingBox) -> float:
        """
        Calculate vertical distance between two bounding boxes.
        
        Returns 0 if boxes overlap vertically.
        Positive if other is above self, negative if below.
        """
        if self.y1 < other.y0:
            return other.y0 - self.y1
        elif self.y0 > other.y1:
            return other.y1 - self.y0
        return 0.0
    
    def horizontal_overlap(self, other: BoundingBox) -> float:
        """
        Calculate horizontal overlap between two bounding boxes.
        
        Returns a value between 0 and 1 representing the fraction of
        horizontal overlap relative to the smaller width.
        """
        overlap_left = max(self.x0, other.x0)
        overlap_right = min(self.x1, other.x1)
        
        if overlap_left >= overlap_right:
            return 0.0
        
        overlap_width = overlap_right - overlap_left
        min_width = min(self.width, other.width)
        
        if min_width == 0:
            return 0.0
        
        return overlap_width / min_width


@dataclass(frozen=True, slots=True)
class FontInfo:
    """
    Font information for a text span.
    
    Attributes:
        name: Font family name.
        size: Font size in points.
        is_bold: Whether the font is bold.
        is_italic: Whether the font is italic.
        color: Font color as RGB tuple (0-255 each).
    """
    
    name: str
    size: float
    is_bold: bool = False
    is_italic: bool = False
    color: tuple[int, int, int] = (0, 0, 0)


@dataclass(frozen=True, slots=True)
class TextSpan:
    """
    A contiguous span of text with uniform formatting.
    
    Attributes:
        text: The text content.
        bbox: Bounding box for this span.
        font: Font information.
    """
    
    text: str
    bbox: BoundingBox
    font: FontInfo


@dataclass(frozen=True, slots=True)
class TextBlock:
    """
    A logical text block (paragraph, heading, etc.).
    
    Attributes:
        text: The complete text content of the block.
        bbox: Bounding box encompassing the entire block.
        block_type: Classification of this block.
        spans: Individual text spans that make up this block.
        alignment: Text alignment within the block.
        indentation: Left indentation in points.
        line_spacing: Average vertical spacing between lines.
        column_index: Index of the column this block belongs to (0-indexed).
    """
    
    text: str
    bbox: BoundingBox
    block_type: BlockType = BlockType.PARAGRAPH
    spans: tuple[TextSpan, ...] = field(default_factory=tuple)
    alignment: TextAlignment = TextAlignment.LEFT
    indentation: float = 0.0
    line_spacing: float = 0.0
    column_index: int = 0
    
    @property
    def is_heading(self) -> bool:
        """Check if this block is a heading."""
        return self.block_type == BlockType.HEADING
    
    @property
    def word_count(self) -> int:
        """Count of words in this block."""
        return len(self.text.split())


@dataclass(frozen=True, slots=True)
class Cell:
    """
    A single cell in a table.
    
    Attributes:
        text: Text content of the cell.
        bbox: Bounding box of the cell.
        row: Row index (0-indexed).
        col: Column index (0-indexed).
        rowspan: Number of rows this cell spans.
        colspan: Number of columns this cell spans.
        is_header: Whether this cell is part of a header row.
        alignment: Text alignment within the cell.
    """
    
    text: str
    bbox: BoundingBox
    row: int
    col: int
    rowspan: int = 1
    colspan: int = 1
    is_header: bool = False
    alignment: TextAlignment = TextAlignment.LEFT
    
    @property
    def is_merged(self) -> bool:
        """Check if this cell spans multiple rows or columns."""
        return self.rowspan > 1 or self.colspan > 1


@dataclass(frozen=True, slots=True)
class Table:
    """
    A table extracted from a PDF page.
    
    Attributes:
        cells: All cells in the table.
        bbox: Bounding box of the entire table.
        num_rows: Number of rows in the table.
        num_cols: Number of columns in the table.
        has_header: Whether the table has a header row.
        ascii_representation: Pre-computed ASCII table string.
    """
    
    cells: tuple[Cell, ...]
    bbox: BoundingBox
    num_rows: int
    num_cols: int
    has_header: bool = False
    ascii_representation: str = ""
    
    def get_cell(self, row: int, col: int) -> Cell | None:
        """
        Get the cell at a specific row and column.
        
        Args:
            row: Row index (0-indexed).
            col: Column index (0-indexed).
        
        Returns:
            The cell at the specified position, or None if not found.
        """
        for cell in self.cells:
            if cell.row == row and cell.col == col:
                return cell
            # Check for merged cells
            if (
                cell.row <= row < cell.row + cell.rowspan
                and cell.col <= col < cell.col + cell.colspan
            ):
                return cell
        return None
    
    def get_row(self, row: int) -> list[Cell]:
        """
        Get all cells in a specific row.
        
        Args:
            row: Row index (0-indexed).
        
        Returns:
            List of cells in the row, sorted by column.
        """
        row_cells = [
            cell for cell in self.cells
            if cell.row <= row < cell.row + cell.rowspan
        ]
        return sorted(row_cells, key=lambda c: c.col)
    
    def get_column(self, col: int) -> list[Cell]:
        """
        Get all cells in a specific column.
        
        Args:
            col: Column index (0-indexed).
        
        Returns:
            List of cells in the column, sorted by row.
        """
        col_cells = [
            cell for cell in self.cells
            if cell.col <= col < cell.col + cell.colspan
        ]
        return sorted(col_cells, key=lambda c: c.row)
    
    def iter_rows(self) -> Iterator[list[Cell]]:
        """Iterate over all rows in the table."""
        for row in range(self.num_rows):
            yield self.get_row(row)


@dataclass(frozen=True, slots=True)
class Column:
    """
    A detected text column region on a page.
    
    Attributes:
        bbox: Bounding box of the column region.
        index: Column index from left to right (0-indexed).
        blocks: Text blocks within this column.
    """
    
    bbox: BoundingBox
    index: int
    blocks: tuple[TextBlock, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class StructuredPage:
    """
    A parsed PDF page with full layout information.
    
    Attributes:
        page_number: 1-indexed page number.
        width: Page width in points.
        height: Page height in points.
        blocks: All text blocks on the page in reading order.
        tables: All tables detected on the page.
        columns: Detected column regions.
        header: Header text if detected.
        footer: Footer text if detected.
    """
    
    page_number: int
    width: float
    height: float
    blocks: tuple[TextBlock, ...] = field(default_factory=tuple)
    tables: tuple[Table, ...] = field(default_factory=tuple)
    columns: tuple[Column, ...] = field(default_factory=tuple)
    header: str = ""
    footer: str = ""
    
    @property
    def text(self) -> str:
        """
        Get all text content from the page in reading order.
        
        Tables are included as their ASCII representation.
        """
        parts: list[str] = []
        
        # Collect all content with their y-positions for ordering
        content_items: list[tuple[float, str]] = []
        
        for block in self.blocks:
            content_items.append((block.bbox.y1, block.text))
        
        for table in self.tables:
            content_items.append((table.bbox.y1, table.ascii_representation))
        
        # Sort by vertical position (top to bottom, so higher y first)
        content_items.sort(key=lambda x: -x[0])
        
        return "\n\n".join(item[1] for item in content_items if item[1].strip())
    
    @property
    def block_count(self) -> int:
        """Number of text blocks on the page."""
        return len(self.blocks)
    
    @property
    def table_count(self) -> int:
        """Number of tables on the page."""
        return len(self.tables)


@dataclass(frozen=True, slots=True)
class StructuredDocument:
    """
    A fully parsed PDF document with layout information.
    
    Attributes:
        pages: All pages in the document.
        metadata: Document metadata (title, author, etc.).
        source_path: Path to the source PDF file.
    """
    
    pages: tuple[StructuredPage, ...]
    metadata: dict[str, str] = field(default_factory=dict)
    source_path: str = ""
    
    @property
    def page_count(self) -> int:
        """Total number of pages in the document."""
        return len(self.pages)
    
    @property
    def text(self) -> str:
        """
        Get all text content from the document.
        
        Pages are separated by page markers.
        """
        parts: list[str] = []
        
        for page in self.pages:
            parts.append(f"\n{'=' * 80}")
            parts.append(f"{'PAGE ' + str(page.page_number):^80}")
            parts.append(f"{'=' * 80}\n")
            parts.append(page.text)
        
        return "\n".join(parts)
    
    def get_page(self, page_number: int) -> StructuredPage | None:
        """
        Get a specific page by number.
        
        Args:
            page_number: 1-indexed page number.
        
        Returns:
            The page, or None if page number is out of range.
        """
        if 1 <= page_number <= len(self.pages):
            return self.pages[page_number - 1]
        return None
    
    def iter_pages(self) -> Iterator[StructuredPage]:
        """Iterate over all pages in the document."""
        yield from self.pages
    
    def iter_blocks(self) -> Iterator[tuple[int, TextBlock]]:
        """
        Iterate over all text blocks in the document.
        
        Yields:
            Tuples of (page_number, block).
        """
        for page in self.pages:
            for block in page.blocks:
                yield page.page_number, block
    
    def iter_tables(self) -> Iterator[tuple[int, Table]]:
        """
        Iterate over all tables in the document.
        
        Yields:
            Tuples of (page_number, table).
        """
        for page in self.pages:
            for table in page.tables:
                yield page.page_number, table
