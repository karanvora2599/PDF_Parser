# PDF Layout Parser

A Python library for extracting structured content from PDF documents while preserving layout information including paragraphs, columns, tables, and page organization.

## Features

- **Layout Preservation**: Maintains document structure including multi-column layouts
- **Paragraph Detection**: Intelligently groups text into coherent paragraphs
- **Column Detection**: Handles 1, 2, 3+ column layouts automatically
- **Table Extraction**: Detects tables and converts them to ASCII format
- **Multiple Output Formats**: Plain text, Markdown, and JSON
- **CLI Tool**: Easy command-line interface for quick processing
- **Programmatic API**: Full Python API for integration

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd PDF_Parser

# Install in development mode
pip install -e ".[dev]"
```

### Dependencies

- Python 3.10+
- PyMuPDF (fitz) - PDF rendering and text extraction
- pdfplumber - Table detection
- click - CLI framework
- numpy - Spatial calculations

## Quick Start

### Command Line

```bash
# Basic parsing
pdf-parser parse document.pdf

# Save to file
pdf-parser parse document.pdf -o output.txt

# Markdown output
pdf-parser parse document.pdf -f markdown -o report.md

# JSON with coordinates
pdf-parser parse document.pdf -f json --include-coordinates -o data.json

# Parse specific pages
pdf-parser parse document.pdf --start-page 5 --end-page 10

# Get document info
pdf-parser info document.pdf

# Analyze page layout
pdf-parser analyze document.pdf --page 3
```

### Python API

```python
from pdf_parser import PDFDocument
from pdf_parser.output.formatter import OutputFormatter, OutputFormat

# Load and parse a PDF
with PDFDocument.load("document.pdf") as doc:
    # Parse the entire document
    structured = doc.parse()
    
    # Access structured content
    for page in structured.pages:
        print(f"Page {page.page_number}:")
        print(f"  Columns: {len(page.columns)}")
        print(f"  Blocks: {page.block_count}")
        print(f"  Tables: {page.table_count}")
        
        # Access text blocks
        for block in page.blocks:
            print(f"  - {block.block_type.name}: {block.text[:50]}...")
        
        # Access tables
        for table in page.tables:
            print(table.ascii_representation)

# Format as Markdown
formatter = OutputFormatter()
markdown = formatter.format(structured, OutputFormat.MARKDOWN)
print(markdown)
```

### Parsing Specific Pages

```python
from pdf_parser import PDFDocument

with PDFDocument.load("document.pdf") as doc:
    # Parse pages 5 through 10
    structured = doc.parse(start_page=5, end_page=10)
    print(structured.text)
```

### Working with Tables

```python
from pdf_parser import PDFDocument

with PDFDocument.load("document.pdf") as doc:
    structured = doc.parse()
    
    # Iterate through all tables
    for page_num, table in structured.iter_tables():
        print(f"Table on page {page_num}:")
        print(f"  Size: {table.num_rows} x {table.num_cols}")
        print(f"  Has header: {table.has_header}")
        print()
        print(table.ascii_representation)
```

## Output Formats

### Plain Text

```
================================================================================
                                    PAGE 1
================================================================================

INTRODUCTION

This paper presents a comprehensive analysis of machine learning approaches
for natural language processing.

+------------------+------------+-------------+
| Model            | Parameters | Accuracy    |
+------------------+------------+-------------+
| BERT-base        | 110M       | 89.2%       |
| GPT-2            | 1.5B       | 91.5%       |
+------------------+------------+-------------+
```

### Markdown

```markdown
### Introduction

This paper presents a comprehensive analysis...

| Model | Parameters | Accuracy |
| ----- | ---------- | -------- |
| BERT-base | 110M | 89.2% |
| GPT-2 | 1.5B | 91.5% |
```

### JSON

```json
{
  "source_path": "document.pdf",
  "page_count": 10,
  "pages": [
    {
      "page_number": 1,
      "blocks": [...],
      "tables": [...]
    }
  ]
}
```

## Architecture

```
pdf_parser/
├── core/
│   ├── document.py     # PDFDocument - main entry point
│   ├── page.py         # Page representation
│   └── exceptions.py   # Error handling
├── layout/
│   ├── analyzer.py     # LayoutAnalyzer - coordinates analysis
│   ├── columns.py      # ColumnDetector - multi-column detection
│   └── paragraphs.py   # ParagraphReconstructor
├── tables/
│   ├── detector.py     # TableDetector using pdfplumber
│   └── ascii_converter.py  # ASCII table formatting
├── output/
│   ├── models.py       # Data models (TextBlock, Table, etc.)
│   └── formatter.py    # OutputFormatter
└── cli.py              # Command-line interface
```

## Error Handling

The library provides specific exceptions for different error conditions:

```python
from pdf_parser import (
    PDFParserError,      # Base exception
    PDFLoadError,        # File loading issues
    PDFPageError,        # Page-specific errors
    LayoutAnalysisError, # Layout detection failures
    TableExtractionError # Table extraction issues
)

try:
    with PDFDocument.load("document.pdf") as doc:
        structured = doc.parse()
except PDFLoadError as e:
    print(f"Could not load PDF: {e}")
except PDFPageError as e:
    print(f"Error on page {e.page_number}: {e}")
except PDFParserError as e:
    print(f"General parsing error: {e}")
```

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=pdf_parser
```

### Code Quality

```bash
# Type checking
mypy src/pdf_parser

# Linting
ruff check src/pdf_parser
```

## License

MIT License
