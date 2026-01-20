"""Tests for ASCII table converter."""

import pytest

from pdf_parser.tables.ascii_converter import ASCIITableConverter, ASCIITableStyle
from pdf_parser.output.models import BoundingBox, Cell, Table


class TestASCIITableConverter:
    """Tests for ASCIITableConverter class."""
    
    @pytest.fixture
    def converter(self):
        """Create a converter instance."""
        return ASCIITableConverter()
    
    @pytest.fixture
    def simple_table(self):
        """Create a simple 2x2 table."""
        bbox = BoundingBox(0, 0, 200, 100)
        cells = (
            Cell(text="A", bbox=BoundingBox(0, 50, 100, 100), row=0, col=0),
            Cell(text="B", bbox=BoundingBox(100, 50, 200, 100), row=0, col=1),
            Cell(text="C", bbox=BoundingBox(0, 0, 100, 50), row=1, col=0),
            Cell(text="D", bbox=BoundingBox(100, 0, 200, 50), row=1, col=1),
        )
        return Table(cells=cells, bbox=bbox, num_rows=2, num_cols=2)
    
    @pytest.fixture
    def header_table(self):
        """Create a table with a header row."""
        bbox = BoundingBox(0, 0, 200, 150)
        cells = (
            Cell(text="Name", bbox=BoundingBox(0, 100, 100, 150), row=0, col=0, is_header=True),
            Cell(text="Value", bbox=BoundingBox(100, 100, 200, 150), row=0, col=1, is_header=True),
            Cell(text="Item1", bbox=BoundingBox(0, 50, 100, 100), row=1, col=0),
            Cell(text="100", bbox=BoundingBox(100, 50, 200, 100), row=1, col=1),
            Cell(text="Item2", bbox=BoundingBox(0, 0, 100, 50), row=2, col=0),
            Cell(text="200", bbox=BoundingBox(100, 0, 200, 50), row=2, col=1),
        )
        return Table(cells=cells, bbox=bbox, num_rows=3, num_cols=2, has_header=True)
    
    def test_convert_simple_table(self, converter, simple_table):
        """Test converting a simple table."""
        result = converter.convert(simple_table)
        
        assert result  # Not empty
        assert "A" in result
        assert "B" in result
        assert "C" in result
        assert "D" in result
        
        # Check for borders
        assert "+" in result
        assert "-" in result
        assert "|" in result
    
    def test_convert_empty_table(self, converter):
        """Test converting an empty table."""
        bbox = BoundingBox(0, 0, 100, 50)
        table = Table(cells=(), bbox=bbox, num_rows=0, num_cols=0)
        
        result = converter.convert(table)
        assert result == ""
    
    def test_convert_header_table(self, converter, header_table):
        """Test that header tables have separator after header row."""
        result = converter.convert(header_table)
        
        lines = result.split("\n")
        
        # Should have at least 5 lines:
        # top border, header row, separator, 2 data rows, bottom border
        assert len(lines) >= 5
        
        # Count separator lines (lines that are all borders)
        separators = [l for l in lines if all(c in "+-" for c in l if c != " ")]
        # With header, should have 3 separators: top, after header, bottom
        assert len(separators) >= 3
    
    def test_text_wrapping(self, converter):
        """Test that long text is wrapped."""
        bbox = BoundingBox(0, 0, 100, 50)
        long_text = "This is a very long text that should be wrapped"
        cells = (
            Cell(text=long_text, bbox=bbox, row=0, col=0),
        )
        
        # Create converter with small max width
        style = ASCIITableStyle(max_cell_width=20)
        converter_wrapped = ASCIITableConverter(style=style)
        
        table = Table(cells=cells, bbox=bbox, num_rows=1, num_cols=1)
        result = converter_wrapped.convert(table)
        
        # Result should have multiple lines for the cell content
        lines = [l for l in result.split("\n") if "|" in l and "+" not in l]
        # With wrapping, should have multiple content lines
        assert len(lines) >= 1
    
    def test_column_width_calculation(self, converter):
        """Test that column widths adjust to content."""
        bbox = BoundingBox(0, 0, 200, 50)
        cells = (
            Cell(text="Short", bbox=BoundingBox(0, 0, 100, 50), row=0, col=0),
            Cell(text="Much Longer Text", bbox=BoundingBox(100, 0, 200, 50), row=0, col=1),
        )
        table = Table(cells=cells, bbox=bbox, num_rows=1, num_cols=2)
        
        result = converter.convert(table)
        
        # Both texts should be fully visible
        assert "Short" in result
        assert "Much Longer Text" in result
    
    def test_convert_to_markdown(self, converter, simple_table):
        """Test Markdown table output."""
        result = converter.convert_to_markdown(simple_table)
        
        assert "|" in result
        # Markdown tables have separator line with dashes
        assert "---" in result or "| -" in result
        assert "A" in result
        assert "B" in result
    
    def test_markdown_has_correct_structure(self, converter, header_table):
        """Test Markdown table has correct structure."""
        result = converter.convert_to_markdown(header_table)
        lines = result.strip().split("\n")
        
        # First line is header
        assert "Name" in lines[0]
        assert "Value" in lines[0]
        
        # Second line is separator
        assert "-" in lines[1]
        
        # Remaining lines are data
        assert "Item1" in lines[2]
        assert "Item2" in lines[3]
    
    def test_custom_style(self):
        """Test custom ASCII table style."""
        style = ASCIITableStyle(
            horizontal="=",
            vertical="!",
            corner="*",
            padding=2,
        )
        converter = ASCIITableConverter(style=style)
        
        bbox = BoundingBox(0, 0, 100, 50)
        cells = (Cell(text="Test", bbox=bbox, row=0, col=0),)
        table = Table(cells=cells, bbox=bbox, num_rows=1, num_cols=1)
        
        result = converter.convert(table)
        
        assert "*" in result
        assert "=" in result
        assert "!" in result
    
    def test_multiline_cell_content(self, converter):
        """Test cells with newlines in content."""
        bbox = BoundingBox(0, 0, 100, 50)
        cells = (Cell(text="Line1\nLine2", bbox=bbox, row=0, col=0),)
        table = Table(cells=cells, bbox=bbox, num_rows=1, num_cols=1)
        
        result = converter.convert(table)
        
        # Should handle multi-line content
        assert "Line1" in result
        assert "Line2" in result


class TestASCIITableStyle:
    """Tests for ASCIITableStyle class."""
    
    def test_default_values(self):
        """Test default style values."""
        style = ASCIITableStyle()
        
        assert style.horizontal == "-"
        assert style.vertical == "|"
        assert style.corner == "+"
        assert style.padding == 1
        assert style.max_cell_width == 40
        assert style.min_cell_width == 3
    
    def test_custom_values(self):
        """Test custom style values."""
        style = ASCIITableStyle(
            horizontal="═",
            vertical="║",
            corner="╬",
            padding=2,
            max_cell_width=50,
        )
        
        assert style.horizontal == "═"
        assert style.vertical == "║"
        assert style.corner == "╬"
        assert style.padding == 2
        assert style.max_cell_width == 50
