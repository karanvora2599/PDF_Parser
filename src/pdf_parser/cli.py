"""
Command-line interface for the PDF Parser.

This module provides a CLI for parsing PDF files with various options
for output format, page selection, and formatting preferences.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import click

from pdf_parser import PDFDocument, PDFParserError
from pdf_parser.output.formatter import OutputFormatter, OutputFormat


def setup_logging(verbose: bool) -> None:
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.WARNING
    
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
        handlers=[logging.StreamHandler()],
    )


@click.group()
@click.version_option(version="0.1.0", prog_name="pdf-parser")
def main() -> None:
    """
    PDF Layout Parser - Extract structured content from PDFs.
    
    This tool parses PDF files while preserving document structure
    including paragraphs, columns, tables, and page layout.
    """
    pass


@main.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o", "--output",
    type=click.Path(path_type=Path),
    help="Output file path. If not specified, prints to stdout.",
)
@click.option(
    "-f", "--format",
    "output_format",
    type=click.Choice(["text", "markdown", "json"], case_sensitive=False),
    default="text",
    help="Output format.",
)
@click.option(
    "--start-page",
    type=int,
    default=1,
    help="First page to parse (1-indexed).",
)
@click.option(
    "--end-page",
    type=int,
    default=None,
    help="Last page to parse (1-indexed). If not specified, parse to end.",
)
@click.option(
    "--include-coordinates",
    is_flag=True,
    default=False,
    help="Include bounding box coordinates in JSON output.",
)
@click.option(
    "--password",
    type=str,
    default=None,
    help="Password for encrypted PDFs.",
)
@click.option(
    "-v", "--verbose",
    is_flag=True,
    default=False,
    help="Enable verbose output.",
)
def parse(
    input_file: Path,
    output: Optional[Path],
    output_format: str,
    start_page: int,
    end_page: Optional[int],
    include_coordinates: bool,
    password: Optional[str],
    verbose: bool,
) -> None:
    """
    Parse a PDF file and extract structured content.
    
    Examples:
    
        pdf-parser parse document.pdf
        
        pdf-parser parse document.pdf -o output.txt
        
        pdf-parser parse document.pdf -f markdown -o report.md
        
        pdf-parser parse document.pdf --start-page 5 --end-page 10
        
        pdf-parser parse document.pdf -f json --include-coordinates
    """
    setup_logging(verbose)
    
    # Map format string to enum
    format_map = {
        "text": OutputFormat.PLAIN_TEXT,
        "markdown": OutputFormat.MARKDOWN,
        "json": OutputFormat.JSON,
    }
    fmt = format_map[output_format.lower()]
    
    try:
        # Load the PDF
        click.echo(f"Loading: {input_file}", err=True)
        
        with PDFDocument.load(input_file, password=password) as doc:
            click.echo(
                f"Loaded {doc.page_count} pages",
                err=True
            )
            
            # Parse the document
            click.echo("Parsing...", err=True)
            structured = doc.parse(
                start_page=start_page,
                end_page=end_page,
            )
            
            # Format output
            formatter = OutputFormatter(include_coordinates=include_coordinates)
            result = formatter.format(structured, fmt)
            
            # Write output
            if output:
                output.write_text(result, encoding="utf-8")
                click.echo(f"Output written to: {output}", err=True)
            else:
                click.echo(result)
            
            # Summary
            total_blocks = sum(p.block_count for p in structured.pages)
            total_tables = sum(p.table_count for p in structured.pages)
            
            click.echo(
                f"\nSummary: {structured.page_count} pages, "
                f"{total_blocks} text blocks, {total_tables} tables",
                err=True
            )
    
    except PDFParserError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@main.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--password",
    type=str,
    default=None,
    help="Password for encrypted PDFs.",
)
def info(input_file: Path, password: Optional[str]) -> None:
    """
    Display information about a PDF file.
    
    Shows metadata, page count, and basic document structure.
    
    Example:
    
        pdf-parser info document.pdf
    """
    try:
        with PDFDocument.load(input_file, password=password) as doc:
            click.echo(f"File: {input_file}")
            click.echo(f"Pages: {doc.page_count}")
            click.echo()
            
            if doc.metadata:
                click.echo("Metadata:")
                for key, value in doc.metadata.items():
                    if value:
                        click.echo(f"  {key}: {value}")
            else:
                click.echo("Metadata: (none)")
            
            click.echo()
            
            # Quick analysis of first page
            if doc.page_count > 0:
                page = doc.get_page(1)
                click.echo("First page dimensions:")
                click.echo(f"  Width: {page.width:.1f} points")
                click.echo(f"  Height: {page.height:.1f} points")
                
                # Check for text
                raw_blocks = page.extract_raw_blocks()
                click.echo(f"  Text blocks: {len(raw_blocks)}")
    
    except PDFParserError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--page",
    type=int,
    default=1,
    help="Page number to analyze (1-indexed).",
)
@click.option(
    "--password",
    type=str,
    default=None,
    help="Password for encrypted PDFs.",
)
def analyze(input_file: Path, page: int, password: Optional[str]) -> None:
    """
    Analyze the layout of a specific page.
    
    Shows detected columns, blocks, and tables with their positions.
    
    Example:
    
        pdf-parser analyze document.pdf --page 3
    """
    setup_logging(verbose=True)
    
    try:
        with PDFDocument.load(input_file, password=password) as doc:
            if page < 1 or page > doc.page_count:
                click.echo(
                    f"Error: Page {page} out of range (1-{doc.page_count})",
                    err=True
                )
                sys.exit(1)
            
            click.echo(f"Analyzing page {page} of {input_file}")
            click.echo()
            
            # Parse just this page
            structured = doc.parse(start_page=page, end_page=page)
            
            if not structured.pages:
                click.echo("No content found on page")
                return
            
            page_data = structured.pages[0]
            
            # Display results
            click.echo(f"Page dimensions: {page_data.width:.1f} x {page_data.height:.1f}")
            click.echo()
            
            if page_data.columns:
                click.echo(f"Columns detected: {len(page_data.columns)}")
                for col in page_data.columns:
                    click.echo(
                        f"  Column {col.index}: "
                        f"x=[{col.bbox.x0:.1f}, {col.bbox.x1:.1f}], "
                        f"{len(col.blocks)} blocks"
                    )
                click.echo()
            
            click.echo(f"Text blocks: {page_data.block_count}")
            for i, block in enumerate(page_data.blocks):
                block_type = block.block_type.name
                preview = block.text[:50].replace("\n", " ")
                if len(block.text) > 50:
                    preview += "..."
                click.echo(f"  [{i}] {block_type}: {preview!r}")
            
            click.echo()
            click.echo(f"Tables: {page_data.table_count}")
            for i, table in enumerate(page_data.tables):
                click.echo(f"  [{i}] {table.num_rows}x{table.num_cols}")
                if table.ascii_representation:
                    # Show first few lines of ASCII table
                    lines = table.ascii_representation.split("\n")[:4]
                    for line in lines:
                        click.echo(f"      {line}")
                    if len(table.ascii_representation.split("\n")) > 4:
                        click.echo("      ...")
            
            if page_data.header:
                click.echo()
                click.echo(f"Header: {page_data.header}")
            
            if page_data.footer:
                click.echo()
                click.echo(f"Footer: {page_data.footer}")
    
    except PDFParserError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
