"""Factory for obtaining appropriate document parsers based on file extension.

The factory method design pattern allows the client code to remain
agnostic of concrete parser types【705524173246349†L27-L34】.  When a new
file format needs to be supported a new parser implementation can be
added without modifying existing logic.  This module implements a
simple mapping from file extensions to parser classes.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Type, Optional

from .parsers import DocumentParser, TextParser, CSVParser, ExcelParser, PDFParser, WordParser, ImageParser


logger = logging.getLogger(__name__)


class ParserFactory:
    """Factory for retrieving document parsers by file extension."""

    # Mapping of lower‑case extension to parser class
    _parsers: Dict[str, Type[DocumentParser]] = {
        ".txt": TextParser,
        ".md": TextParser,
        ".csv": CSVParser,
        ".tsv": CSVParser,
        ".xlsx": ExcelParser,
        ".xls": ExcelParser,
        ".pdf": PDFParser,
        ".docx": WordParser,
        ".doc": WordParser,
        ".png": ImageParser,
        ".jpg": ImageParser,
        ".jpeg": ImageParser,
        ".tiff": ImageParser,
        ".bmp": ImageParser,
    }

    @classmethod
    def get_parser(cls, file_path: str) -> Optional[DocumentParser]:
        """Return an appropriate parser instance for the given file.

        Parameters
        ----------
        file_path:
            Absolute path to the file whose extension will be used
            to determine the parser.  Case is ignored when matching.

        Returns
        -------
        DocumentParser or None
            A new parser instance if the extension is supported,
            otherwise ``None``.  Unsupported file types are silently
            ignored; the caller should log this if necessary.
        """
        ext = Path(file_path).suffix.lower()
        parser_cls = cls._parsers.get(ext)
        if parser_cls is None:
            logger.debug("ParserFactory: no parser registered for extension %s", ext)
            return None
        return parser_cls()
