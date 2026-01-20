"""Parser for plain text files.

This parser handles files with extensions such as ``.txt`` and
``.md``.  The entire contents of the file are read and returned as
a single :class:`~embedding_app.document.Document` instance.  No
additional splitting is performed because plain text files are
usually already manageable in size.  Errors encountered while
opening or reading the file are logged and propagated.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from .base_parser import DocumentParser
from ..document import Document


logger = logging.getLogger(__name__)


class TextParser(DocumentParser):
    """Concrete parser for plain text and markdown files."""

    def parse(self, file_path: str) -> List[Document]:
        path = Path(file_path)
        documents: List[Document] = []
        if not path.is_file():
            logger.error("TextParser: %s is not a file", file_path)
            return documents
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            logger.exception("TextParser: failed to read file %s", file_path)
            return documents
        metadata = {"file_path": str(path)}
        documents.append(Document(text=content, metadata=metadata))
        logger.debug("TextParser: parsed file %s", file_path)
        return documents