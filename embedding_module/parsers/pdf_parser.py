"""Parser for PDF documents.

This parser uses the PyPDF2 library to extract text from each page
of a PDF.  Each page becomes a separate document with the page
number recorded in metadata.  If the PDF cannot be read the
parser logs the error and returns an empty list.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

try:
    import PyPDF2
except ImportError as exc:  # pragma: no cover - import optional
    PyPDF2 = None  # type: ignore

from .base_parser import DocumentParser
from ..document import Document


logger = logging.getLogger(__name__)


class PDFParser(DocumentParser):
    """Concrete parser for Portable Document Format (PDF) files."""

    def parse(self, file_path: str) -> List[Document]:
        documents: List[Document] = []
        if PyPDF2 is None:
            logger.error(
                "PDFParser: PyPDF2 library is not installed. Please install PyPDF2 to parse PDFs."
            )
            return documents
        path = Path(file_path)
        if not path.is_file():
            logger.error("PDFParser: %s is not a file", file_path)
            return documents
        try:
            with path.open("rb") as fh:
                reader = PyPDF2.PdfReader(fh)
                num_pages = len(reader.pages)
                for idx, page in enumerate(reader.pages):
                    try:
                        text = page.extract_text() or ""
                    except Exception:
                        logger.exception(
                            "PDFParser: failed to extract text from page %d of %s",
                            idx,
                            file_path,
                        )
                        text = ""
                    metadata = {
                        "file_path": str(path),
                        "page_number": idx + 1,
                        "num_pages": num_pages,
                    }
                    documents.append(Document(text=text, metadata=metadata))
        except Exception:
            logger.exception("PDFParser: failed to read PDF %s", file_path)
            return documents
        logger.debug("PDFParser: extracted %d pages from %s", len(documents), file_path)
        return documents