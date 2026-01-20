"""Tests for output data models."""

import pytest

from pdf_parser.output.models import (
    BoundingBox,
    FontInfo,
    TextSpan,
    TextBlock,
    Cell,
    Table,
    Column,
    StructuredPage,
    StructuredDocument,
    BlockType,
    TextAlignment,
)


class TestBoundingBox:
    """Tests for BoundingBox class."""
    
    def test_create_valid_bbox(self):
        """Test creating a valid bounding box."""
        bbox = BoundingBox(10, 20, 100, 200)
        assert bbox.x0 == 10
        assert bbox.y0 == 20
        assert bbox.x1 == 100
        assert bbox.y1 == 200
    
    def test_invalid_x_coordinates(self):
        """Test that x0 > x1 raises ValueError."""
        with pytest.raises(ValueError, match="x0.*must be <= x1"):
            BoundingBox(100, 20, 10, 200)
    
    def test_invalid_y_coordinates(self):
        """Test that y0 > y1 raises ValueError."""
        with pytest.raises(ValueError, match="y0.*must be <= y1"):
            BoundingBox(10, 200, 100, 20)
    
    def test_width_height(self):
        """Test width and height properties."""
        bbox = BoundingBox(10, 20, 110, 220)
        assert bbox.width == 100
        assert bbox.height == 200
    
    def test_area(self):
        """Test area calculation."""
        bbox = BoundingBox(0, 0, 100, 50)
        assert bbox.area == 5000
    
    def test_center(self):
        """Test center point calculation."""
        bbox = BoundingBox(0, 0, 100, 100)
        assert bbox.center == (50, 50)
    
    def test_intersects_true(self):
        """Test intersection detection - overlapping boxes."""
        box1 = BoundingBox(0, 0, 100, 100)
        box2 = BoundingBox(50, 50, 150, 150)
        assert box1.intersects(box2)
        assert box2.intersects(box1)
    
    def test_intersects_false(self):
        """Test intersection detection - non-overlapping boxes."""
        box1 = BoundingBox(0, 0, 50, 50)
        box2 = BoundingBox(100, 100, 150, 150)
        assert not box1.intersects(box2)
        assert not box2.intersects(box1)
    
    def test_intersects_touching(self):
        """Test intersection detection - touching boxes share edge."""
        box1 = BoundingBox(0, 0, 50, 50)
        box2 = BoundingBox(50, 0, 100, 50)
        # Touching at edge - boxes share a boundary, so they do intersect
        assert box1.intersects(box2)
    
    def test_contains_true(self):
        """Test containment - inner box within outer."""
        outer = BoundingBox(0, 0, 100, 100)
        inner = BoundingBox(25, 25, 75, 75)
        assert outer.contains(inner)
    
    def test_contains_false(self):
        """Test containment - boxes overlap but not contained."""
        box1 = BoundingBox(0, 0, 100, 100)
        box2 = BoundingBox(50, 50, 150, 150)
        assert not box1.contains(box2)
        assert not box2.contains(box1)
    
    def test_horizontal_overlap_full(self):
        """Test horizontal overlap - full overlap."""
        box1 = BoundingBox(0, 0, 100, 50)
        box2 = BoundingBox(0, 100, 100, 150)
        assert box1.horizontal_overlap(box2) == 1.0
    
    def test_horizontal_overlap_partial(self):
        """Test horizontal overlap - partial overlap."""
        box1 = BoundingBox(0, 0, 100, 50)
        box2 = BoundingBox(50, 100, 150, 150)
        overlap = box1.horizontal_overlap(box2)
        assert 0 < overlap < 1
    
    def test_horizontal_overlap_none(self):
        """Test horizontal overlap - no overlap."""
        box1 = BoundingBox(0, 0, 50, 50)
        box2 = BoundingBox(100, 0, 150, 50)
        assert box1.horizontal_overlap(box2) == 0.0
    
    def test_vertical_distance(self):
        """Test vertical distance calculation."""
        box1 = BoundingBox(0, 0, 100, 50)
        box2 = BoundingBox(0, 100, 100, 150)
        # box2 is above box1
        assert box1.vertical_distance(box2) == 50


class TestFontInfo:
    """Tests for FontInfo class."""
    
    def test_create_font_info(self):
        """Test creating font info."""
        font = FontInfo(
            name="Arial",
            size=12.0,
            is_bold=True,
            is_italic=False,
            color=(0, 0, 0),
        )
        assert font.name == "Arial"
        assert font.size == 12.0
        assert font.is_bold
        assert not font.is_italic
    
    def test_default_values(self):
        """Test default values."""
        font = FontInfo(name="Times", size=10.0)
        assert not font.is_bold
        assert not font.is_italic
        assert font.color == (0, 0, 0)


class TestTextBlock:
    """Tests for TextBlock class."""
    
    def test_create_text_block(self):
        """Test creating a text block."""
        bbox = BoundingBox(0, 0, 100, 50)
        block = TextBlock(
            text="Hello world",
            bbox=bbox,
            block_type=BlockType.PARAGRAPH,
        )
        assert block.text == "Hello world"
        assert block.block_type == BlockType.PARAGRAPH
    
    def test_is_heading(self):
        """Test is_heading property."""
        bbox = BoundingBox(0, 0, 100, 50)
        heading = TextBlock(text="Title", bbox=bbox, block_type=BlockType.HEADING)
        paragraph = TextBlock(text="Text", bbox=bbox, block_type=BlockType.PARAGRAPH)
        
        assert heading.is_heading
        assert not paragraph.is_heading
    
    def test_word_count(self):
        """Test word count property."""
        bbox = BoundingBox(0, 0, 100, 50)
        block = TextBlock(text="Hello world test", bbox=bbox)
        assert block.word_count == 3


class TestCell:
    """Tests for Cell class."""
    
    def test_create_cell(self):
        """Test creating a table cell."""
        bbox = BoundingBox(0, 0, 50, 20)
        cell = Cell(text="Value", bbox=bbox, row=0, col=0)
        assert cell.text == "Value"
        assert cell.row == 0
        assert cell.col == 0
    
    def test_is_merged(self):
        """Test merged cell detection."""
        bbox = BoundingBox(0, 0, 50, 20)
        normal = Cell(text="A", bbox=bbox, row=0, col=0)
        merged = Cell(text="B", bbox=bbox, row=0, col=0, colspan=2)
        
        assert not normal.is_merged
        assert merged.is_merged


class TestTable:
    """Tests for Table class."""
    
    def test_create_table(self):
        """Test creating a table."""
        bbox = BoundingBox(0, 0, 200, 100)
        cells = (
            Cell(text="A", bbox=BoundingBox(0, 80, 100, 100), row=0, col=0),
            Cell(text="B", bbox=BoundingBox(100, 80, 200, 100), row=0, col=1),
            Cell(text="C", bbox=BoundingBox(0, 60, 100, 80), row=1, col=0),
            Cell(text="D", bbox=BoundingBox(100, 60, 200, 80), row=1, col=1),
        )
        table = Table(cells=cells, bbox=bbox, num_rows=2, num_cols=2)
        
        assert table.num_rows == 2
        assert table.num_cols == 2
        assert len(table.cells) == 4
    
    def test_get_cell(self):
        """Test getting a specific cell."""
        bbox = BoundingBox(0, 0, 200, 100)
        cells = (
            Cell(text="A", bbox=BoundingBox(0, 0, 100, 50), row=0, col=0),
            Cell(text="B", bbox=BoundingBox(100, 0, 200, 50), row=0, col=1),
        )
        table = Table(cells=cells, bbox=bbox, num_rows=1, num_cols=2)
        
        cell = table.get_cell(0, 1)
        assert cell is not None
        assert cell.text == "B"
    
    def test_get_row(self):
        """Test getting a row."""
        bbox = BoundingBox(0, 0, 200, 100)
        cells = (
            Cell(text="A", bbox=BoundingBox(0, 50, 100, 100), row=0, col=0),
            Cell(text="B", bbox=BoundingBox(100, 50, 200, 100), row=0, col=1),
            Cell(text="C", bbox=BoundingBox(0, 0, 100, 50), row=1, col=0),
            Cell(text="D", bbox=BoundingBox(100, 0, 200, 50), row=1, col=1),
        )
        table = Table(cells=cells, bbox=bbox, num_rows=2, num_cols=2)
        
        row0 = table.get_row(0)
        assert len(row0) == 2
        assert row0[0].text == "A"
        assert row0[1].text == "B"


class TestStructuredPage:
    """Tests for StructuredPage class."""
    
    def test_create_page(self):
        """Test creating a structured page."""
        page = StructuredPage(
            page_number=1,
            width=612,
            height=792,
        )
        assert page.page_number == 1
        assert page.width == 612
        assert page.height == 792
    
    def test_block_count(self):
        """Test block count property."""
        bbox = BoundingBox(0, 0, 100, 50)
        blocks = (
            TextBlock(text="A", bbox=bbox),
            TextBlock(text="B", bbox=bbox),
        )
        page = StructuredPage(
            page_number=1, width=612, height=792, blocks=blocks,
        )
        assert page.block_count == 2
    
    def test_table_count(self):
        """Test table count property."""
        bbox = BoundingBox(0, 0, 200, 100)
        tables = (
            Table(cells=(), bbox=bbox, num_rows=0, num_cols=0),
        )
        page = StructuredPage(
            page_number=1, width=612, height=792, tables=tables,
        )
        assert page.table_count == 1


class TestStructuredDocument:
    """Tests for StructuredDocument class."""
    
    def test_create_document(self):
        """Test creating a structured document."""
        pages = (
            StructuredPage(page_number=1, width=612, height=792),
            StructuredPage(page_number=2, width=612, height=792),
        )
        doc = StructuredDocument(pages=pages, source_path="test.pdf")
        
        assert doc.page_count == 2
        assert doc.source_path == "test.pdf"
    
    def test_get_page(self):
        """Test getting a specific page."""
        pages = (
            StructuredPage(page_number=1, width=612, height=792),
            StructuredPage(page_number=2, width=612, height=792),
        )
        doc = StructuredDocument(pages=pages)
        
        page = doc.get_page(2)
        assert page is not None
        assert page.page_number == 2
    
    def test_get_page_out_of_range(self):
        """Test getting a page that doesn't exist."""
        pages = (StructuredPage(page_number=1, width=612, height=792),)
        doc = StructuredDocument(pages=pages)
        
        assert doc.get_page(0) is None
        assert doc.get_page(5) is None
    
    def test_iter_pages(self):
        """Test iterating through pages."""
        pages = (
            StructuredPage(page_number=1, width=612, height=792),
            StructuredPage(page_number=2, width=612, height=792),
        )
        doc = StructuredDocument(pages=pages)
        
        page_numbers = [p.page_number for p in doc.iter_pages()]
        assert page_numbers == [1, 2]
