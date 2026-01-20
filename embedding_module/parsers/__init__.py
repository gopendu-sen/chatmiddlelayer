"""Collection of document parser implementations.

Importing this package registers the available parsers so that
:class:`embedding_app.factory.ParserFactory` can discover them.
"""

from .base_parser import DocumentParser
from .txt_parser import TextParser
from .csv_parser import CSVParser
from .xlsx_parser import ExcelParser
from .pdf_parser import PDFParser
from .docx_parser import WordParser
from .image_parser import ImageParser

__all__ = [
    "DocumentParser",
    "TextParser",
    "CSVParser",
    "ExcelParser",
    "PDFParser",
    "WordParser",
    "ImageParser",
]
