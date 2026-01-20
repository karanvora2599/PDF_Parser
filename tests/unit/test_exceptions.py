"""Tests for exception classes."""

import pytest

from pdf_parser.core.exceptions import (
    PDFParserError,
    PDFLoadError,
    PDFPageError,
    LayoutAnalysisError,
    TableExtractionError,
    ConfigurationError,
)


class TestPDFParserError:
    """Tests for base PDFParserError."""
    
    def test_basic_message(self):
        """Test exception with just a message."""
        error = PDFParserError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.details == {}
    
    def test_with_details(self):
        """Test exception with details."""
        error = PDFParserError("Error occurred", {"key": "value", "count": 5})
        assert "key='value'" in str(error)
        assert "count=5" in str(error)
        assert error.details["key"] == "value"
    
    def test_inheritance(self):
        """Test that PDFParserError inherits from Exception."""
        error = PDFParserError("Test")
        assert isinstance(error, Exception)


class TestPDFLoadError:
    """Tests for PDFLoadError."""
    
    def test_with_file_path(self):
        """Test error with file path."""
        error = PDFLoadError("File not found", file_path="/path/to/file.pdf")
        assert error.file_path == "/path/to/file.pdf"
        assert "file_path='/path/to/file.pdf'" in str(error)
    
    def test_without_file_path(self):
        """Test error without file path."""
        error = PDFLoadError("Generic load error")
        assert error.file_path is None
        assert str(error) == "Generic load error"
    
    def test_inheritance(self):
        """Test PDFLoadError inherits from PDFParserError."""
        error = PDFLoadError("Test")
        assert isinstance(error, PDFParserError)
        assert isinstance(error, Exception)
    
    def test_combined_details(self):
        """Test that file_path is included in details."""
        error = PDFLoadError(
            "Load failed",
            file_path="/path/to/file.pdf",
            details={"reason": "corrupted"},
        )
        assert error.details["file_path"] == "/path/to/file.pdf"
        assert error.details["reason"] == "corrupted"


class TestPDFPageError:
    """Tests for PDFPageError."""
    
    def test_with_page_number(self):
        """Test error with page number."""
        error = PDFPageError("Page error", page_number=5)
        assert error.page_number == 5
        assert "page_number=5" in str(error)
    
    def test_without_page_number(self):
        """Test error without page number."""
        error = PDFPageError("Generic page error")
        assert error.page_number is None
    
    def test_inheritance(self):
        """Test PDFPageError inherits from PDFParserError."""
        error = PDFPageError("Test")
        assert isinstance(error, PDFParserError)


class TestLayoutAnalysisError:
    """Tests for LayoutAnalysisError."""
    
    def test_with_component(self):
        """Test error with component specified."""
        error = LayoutAnalysisError(
            "Analysis failed",
            page_number=3,
            component="columns",
        )
        assert error.page_number == 3
        assert error.component == "columns"
        assert "component='columns'" in str(error)
    
    def test_without_component(self):
        """Test error without component."""
        error = LayoutAnalysisError("Generic analysis error")
        assert error.component is None
    
    def test_inheritance(self):
        """Test LayoutAnalysisError inherits from PDFParserError."""
        error = LayoutAnalysisError("Test")
        assert isinstance(error, PDFParserError)


class TestTableExtractionError:
    """Tests for TableExtractionError."""
    
    def test_with_table_index(self):
        """Test error with table index."""
        error = TableExtractionError(
            "Table extraction failed",
            page_number=2,
            table_index=0,
        )
        assert error.page_number == 2
        assert error.table_index == 0
        assert "table_index=0" in str(error)
    
    def test_inheritance(self):
        """Test TableExtractionError inherits from PDFParserError."""
        error = TableExtractionError("Test")
        assert isinstance(error, PDFParserError)


class TestConfigurationError:
    """Tests for ConfigurationError."""
    
    def test_with_parameter(self):
        """Test error with parameter name."""
        error = ConfigurationError(
            "Invalid value",
            parameter="column_gap_threshold",
        )
        assert error.parameter == "column_gap_threshold"
        assert "parameter='column_gap_threshold'" in str(error)
    
    def test_inheritance(self):
        """Test ConfigurationError inherits from PDFParserError."""
        error = ConfigurationError("Test")
        assert isinstance(error, PDFParserError)


class TestExceptionCatching:
    """Test that exceptions can be caught appropriately."""
    
    def test_catch_all_pdf_errors(self):
        """Test catching all PDF parser errors with base class."""
        errors = [
            PDFLoadError("load"),
            PDFPageError("page"),
            LayoutAnalysisError("layout"),
            TableExtractionError("table"),
            ConfigurationError("config"),
        ]
        
        for error in errors:
            try:
                raise error
            except PDFParserError as e:
                # All should be catchable as PDFParserError
                assert isinstance(e, PDFParserError)
    
    def test_catch_specific_error(self):
        """Test catching specific error types."""
        error = PDFLoadError("test")
        
        with pytest.raises(PDFLoadError):
            raise error
        
        # Also catchable as base type
        with pytest.raises(PDFParserError):
            raise PDFLoadError("test")
