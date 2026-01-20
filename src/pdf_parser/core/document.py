"""
PDF Document loader and main entry point.

This module provides the PDFDocument class which is the primary interface
for loading and parsing PDF files with layout preservation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

import fitz

from pdf_parser.core.exceptions import PDFLoadError, PDFPageError
from pdf_parser.core.page import Page
from pdf_parser.layout.analyzer import LayoutAnalyzer
from pdf_parser.output.models import StructuredDocument, StructuredPage

logger = logging.getLogger(__name__)


class PDFDocument:
    """
    Main entry point for loading and parsing PDF documents.
    
    This class provides a high-level interface for extracting structured
    content from PDF files while preserving layout information.
    
    Usage:
        >>> doc = PDFDocument.load("document.pdf")
        >>> structured = doc.parse()
        >>> print(structured.text)
    
    Attributes:
        path: Path to the source PDF file.
        page_count: Total number of pages in the document.
        metadata: Document metadata (title, author, etc.).
    """
    
    def __init__(self, fitz_doc: fitz.Document, path: str) -> None:
        """
        Initialize a PDFDocument.
        
        This constructor is not meant to be called directly.
        Use the `load` class method instead.
        
        Args:
            fitz_doc: The underlying PyMuPDF document.
            path: Path to the source PDF file.
        """
        self._doc = fitz_doc
        self.path = path
        self._layout_analyzer = LayoutAnalyzer()
    
    @classmethod
    def load(
        cls,
        path: str | Path,
        password: str | None = None,
    ) -> "PDFDocument":
        """
        Load a PDF document from a file.
        
        Args:
            path: Path to the PDF file.
            password: Optional password for encrypted PDFs.
        
        Returns:
            A PDFDocument instance.
        
        Raises:
            PDFLoadError: If the file cannot be loaded.
        """
        path_str = str(path)
        path_obj = Path(path)
        
        # Validate file exists
        if not path_obj.exists():
            raise PDFLoadError(
                f"PDF file not found: {path_str}",
                file_path=path_str,
            )
        
        # Validate it's a file, not a directory
        if not path_obj.is_file():
            raise PDFLoadError(
                f"Path is not a file: {path_str}",
                file_path=path_str,
            )
        
        # Validate file extension
        if path_obj.suffix.lower() != ".pdf":
            logger.warning(
                "File does not have .pdf extension: %s",
                path_str
            )
        
        try:
            doc = fitz.open(path_str)
        except Exception as e:
            raise PDFLoadError(
                f"Failed to open PDF: {e}",
                file_path=path_str,
                details={"original_error": str(e)},
            ) from e
        
        # Handle encrypted documents
        if doc.is_encrypted:
            if password is None:
                doc.close()
                raise PDFLoadError(
                    "PDF is encrypted and no password was provided",
                    file_path=path_str,
                )
            
            if not doc.authenticate(password):
                doc.close()
                raise PDFLoadError(
                    "Invalid password for encrypted PDF",
                    file_path=path_str,
                )
        
        logger.info(
            "Loaded PDF: %s (%d pages)",
            path_str, len(doc)
        )
        
        return cls(doc, path_str)
    
    @classmethod
    def from_bytes(cls, data: bytes, filename: str = "document.pdf") -> "PDFDocument":
        """
        Load a PDF document from bytes.
        
        Args:
            data: PDF file content as bytes.
            filename: Optional filename for metadata purposes.
        
        Returns:
            A PDFDocument instance.
        
        Raises:
            PDFLoadError: If the data cannot be loaded as a PDF.
        """
        if not data:
            raise PDFLoadError(
                "Cannot load PDF from empty data",
                file_path=filename,
            )
        
        try:
            doc = fitz.open(stream=data, filetype="pdf")
        except Exception as e:
            raise PDFLoadError(
                f"Failed to load PDF from bytes: {e}",
                file_path=filename,
                details={"original_error": str(e)},
            ) from e
        
        return cls(doc, filename)
    
    @property
    def page_count(self) -> int:
        """Total number of pages in the document."""
        return len(self._doc)
    
    @property
    def metadata(self) -> dict[str, str]:
        """
        Document metadata.
        
        Returns:
            Dictionary with keys like 'title', 'author', 'subject', etc.
        """
        meta = self._doc.metadata or {}
        return {k: v for k, v in meta.items() if v}
    
    def get_page(self, page_number: int) -> Page:
        """
        Get a specific page by number.
        
        Args:
            page_number: 1-indexed page number.
        
        Returns:
            A Page instance.
        
        Raises:
            PDFPageError: If the page number is out of range.
        """
        if page_number < 1 or page_number > self.page_count:
            raise PDFPageError(
                f"Page number {page_number} out of range (1-{self.page_count})",
                page_number=page_number,
            )
        
        try:
            fitz_page = self._doc[page_number - 1]
            return Page(fitz_page, page_number)
        except Exception as e:
            raise PDFPageError(
                f"Failed to load page {page_number}: {e}",
                page_number=page_number,
            ) from e
    
    def iter_pages(self) -> Iterator[Page]:
        """
        Iterate over all pages in the document.
        
        Yields:
            Page instances in order.
        """
        for i in range(self.page_count):
            yield self.get_page(i + 1)
    
    def parse(
        self,
        start_page: int = 1,
        end_page: int | None = None,
    ) -> StructuredDocument:
        """
        Parse the document and extract structured content.
        
        This is the main method for extracting content with layout preservation.
        It analyzes each page for columns, paragraphs, and tables, then
        returns a fully structured representation.
        
        Args:
            start_page: First page to parse (1-indexed, inclusive).
            end_page: Last page to parse (1-indexed, inclusive).
                     If None, parse to the end of the document.
        
        Returns:
            A StructuredDocument with all parsed content.
        
        Raises:
            PDFPageError: If a page cannot be processed.
        """
        # Validate page range
        if start_page < 1:
            raise PDFPageError(
                f"Start page must be >= 1, got {start_page}",
                page_number=start_page,
            )
        
        if end_page is None:
            end_page = self.page_count
        elif end_page > self.page_count:
            logger.warning(
                "End page %d exceeds page count %d, using %d",
                end_page, self.page_count, self.page_count
            )
            end_page = self.page_count
        
        if start_page > end_page:
            raise PDFPageError(
                f"Start page ({start_page}) cannot be greater than end page ({end_page})",
                page_number=start_page,
            )
        
        logger.info(
            "Parsing pages %d to %d of %s",
            start_page, end_page, self.path
        )
        
        structured_pages: list[StructuredPage] = []
        
        for page_num in range(start_page, end_page + 1):
            page = self.get_page(page_num)
            
            try:
                structured_page = self._layout_analyzer.analyze_page(page)
                structured_pages.append(structured_page)
            except Exception as e:
                logger.error(
                    "Failed to analyze page %d: %s",
                    page_num, e
                )
                # Continue with basic extraction as fallback
                fallback_page = self._create_fallback_page(page)
                structured_pages.append(fallback_page)
        
        return StructuredDocument(
            pages=tuple(structured_pages),
            metadata=self.metadata,
            source_path=self.path,
        )
    
    def _create_fallback_page(self, page: Page) -> StructuredPage:
        """
        Create a basic StructuredPage when layout analysis fails.
        
        This extracts simple text without layout preservation.
        """
        from pdf_parser.output.models import (
            BoundingBox,
            TextBlock,
            BlockType,
        )
        
        text = page.get_text_simple()
        
        # Create a single block with all text
        if text.strip():
            block = TextBlock(
                text=text,
                bbox=BoundingBox(0, 0, page.width, page.height),
                block_type=BlockType.PARAGRAPH,
            )
            blocks = (block,)
        else:
            blocks = ()
        
        return StructuredPage(
            page_number=page.page_number,
            width=page.width,
            height=page.height,
            blocks=blocks,
        )
    
    def close(self) -> None:
        """Close the document and release resources."""
        if self._doc:
            self._doc.close()
            logger.debug("Closed PDF: %s", self.path)
    
    def __enter__(self) -> "PDFDocument":
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - ensure document is closed."""
        self.close()
    
    def __repr__(self) -> str:
        """String representation."""
        return f"PDFDocument(path={self.path!r}, pages={self.page_count})"
