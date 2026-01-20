"""
Custom exceptions for the PDF Parser library.

This module defines a hierarchy of exceptions for precise error handling
throughout the parsing pipeline. All exceptions inherit from PDFParserError
to allow catching all library-specific errors with a single except clause.
"""

from __future__ import annotations

from typing import Any


class PDFParserError(Exception):
    """
    Base exception for all PDF Parser errors.
    
    All library-specific exceptions inherit from this class, allowing
    callers to catch all PDF parsing errors with a single except clause.
    
    Attributes:
        message: Human-readable error description.
        details: Optional dictionary with additional error context.
    """
    
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """
        Initialize the exception.
        
        Args:
            message: Human-readable error description.
            details: Optional dictionary with additional error context.
        """
        self.message = message
        self.details = details or {}
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        """Format the exception message with optional details."""
        if not self.details:
            return self.message
        details_str = ", ".join(f"{k}={v!r}" for k, v in self.details.items())
        return f"{self.message} ({details_str})"


class PDFLoadError(PDFParserError):
    """
    Raised when a PDF file cannot be loaded.
    
    This can occur when:
    - The file does not exist
    - The file is not a valid PDF
    - The file is encrypted and no password was provided
    - The file is corrupted
    """
    
    def __init__(
        self,
        message: str,
        file_path: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize the exception.
        
        Args:
            message: Human-readable error description.
            file_path: Path to the PDF file that failed to load.
            details: Optional dictionary with additional error context.
        """
        self.file_path = file_path
        combined_details = details or {}
        if file_path:
            combined_details["file_path"] = file_path
        super().__init__(message, combined_details)


class PDFPageError(PDFParserError):
    """
    Raised when there is an error processing a specific page.
    
    This can occur when:
    - The page number is out of range
    - The page content is malformed
    - The page cannot be rendered
    """
    
    def __init__(
        self,
        message: str,
        page_number: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize the exception.
        
        Args:
            message: Human-readable error description.
            page_number: The 1-indexed page number where the error occurred.
            details: Optional dictionary with additional error context.
        """
        self.page_number = page_number
        combined_details = details or {}
        if page_number is not None:
            combined_details["page_number"] = page_number
        super().__init__(message, combined_details)


class LayoutAnalysisError(PDFParserError):
    """
    Raised when layout analysis fails.
    
    This can occur when:
    - Column detection fails
    - Paragraph reconstruction fails
    - Reading order cannot be determined
    """
    
    def __init__(
        self,
        message: str,
        page_number: int | None = None,
        component: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize the exception.
        
        Args:
            message: Human-readable error description.
            page_number: The 1-indexed page number where the error occurred.
            component: The layout component that failed (e.g., "columns", "paragraphs").
            details: Optional dictionary with additional error context.
        """
        self.page_number = page_number
        self.component = component
        combined_details = details or {}
        if page_number is not None:
            combined_details["page_number"] = page_number
        if component:
            combined_details["component"] = component
        super().__init__(message, combined_details)


class TableExtractionError(PDFParserError):
    """
    Raised when table extraction fails.
    
    This can occur when:
    - Table detection fails
    - Cell boundaries cannot be determined
    - Table content cannot be extracted
    """
    
    def __init__(
        self,
        message: str,
        page_number: int | None = None,
        table_index: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize the exception.
        
        Args:
            message: Human-readable error description.
            page_number: The 1-indexed page number where the error occurred.
            table_index: The 0-indexed table number on the page.
            details: Optional dictionary with additional error context.
        """
        self.page_number = page_number
        self.table_index = table_index
        combined_details = details or {}
        if page_number is not None:
            combined_details["page_number"] = page_number
        if table_index is not None:
            combined_details["table_index"] = table_index
        super().__init__(message, combined_details)


class ConfigurationError(PDFParserError):
    """
    Raised when there is a configuration error.
    
    This can occur when:
    - Invalid configuration values are provided
    - Required configuration is missing
    - Configuration conflicts are detected
    """
    
    def __init__(
        self,
        message: str,
        parameter: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize the exception.
        
        Args:
            message: Human-readable error description.
            parameter: The configuration parameter that caused the error.
            details: Optional dictionary with additional error context.
        """
        self.parameter = parameter
        combined_details = details or {}
        if parameter:
            combined_details["parameter"] = parameter
        super().__init__(message, combined_details)
