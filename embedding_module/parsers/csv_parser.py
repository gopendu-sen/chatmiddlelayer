"""Parser for comma‑separated value (CSV) files.

CSV files contain tabular data.  This parser reads the file using
pandas and serialises the resulting DataFrame into a newline
separated string.  The first row of the output contains the
column names.  The entire file is represented as a single
document.  If reading fails an error is logged and no documents
are returned.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import pandas as pd

from .base_parser import DocumentParser
from ..document import Document


logger = logging.getLogger(__name__)


class CSVParser(DocumentParser):
    """Concrete parser for CSV files."""

    def parse(self, file_path: str) -> List[Document]:
        path = Path(file_path)
        documents: List[Document] = []
        if not path.is_file():
            logger.error("CSVParser: %s is not a file", file_path)
            return documents
        try:
            df = pd.read_csv(path)
        except Exception:
            logger.exception("CSVParser: failed to read CSV %s", file_path)
            return documents
        # Serialise DataFrame to a string.  Include header.
        content_lines = [",".join(map(str, df.columns))]
        for _, row in df.iterrows():
            content_lines.append(",".join(map(lambda x: str(x) if x is not None else "", row.values)))
        content = "\n".join(content_lines)
        metadata = {"file_path": str(path)}
        documents.append(Document(text=content, metadata=metadata))
        logger.debug("CSVParser: parsed CSV %s with %d rows", file_path, len(df))
        return documents