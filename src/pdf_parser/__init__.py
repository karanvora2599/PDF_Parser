"""
PDF Layout Parser - A layout-aware PDF parsing library.

This library provides tools for extracting text from PDF documents while
preserving the document's structural layout including paragraphs, columns,
tables, and page organization.
"""

from pdf_parser.core.document import PDFDocument
from pdf_parser.core.exceptions import (
    PDFParserError,
    PDFLoadError,
    PDFPageError,
    LayoutAnalysisError,
    TableExtractionError,
)
from pdf_parser.output.models import (
    StructuredDocument,
    StructuredPage,
    TextBlock,
    Table,
    Cell,
)

__version__ = "0.1.0"
__author__ = "PDF Parser Team"

__all__ = [
    # Main entry point
    "PDFDocument",
    # Exceptions
    "PDFParserError",
    "PDFLoadError",
    "PDFPageError",
    "LayoutAnalysisError",
    "TableExtractionError",
    # Data models
    "StructuredDocument",
    "StructuredPage",
    "TextBlock",
    "Table",
    "Cell",
]
