"""Parser for Microsoft Excel files (.xlsx, .xls).

Excel workbooks may contain multiple sheets.  This parser uses
pandas to load each sheet into a DataFrame and converts it into a
newline separated string similar to the CSV parser.  Each sheet is
represented as a separate document with the sheet name recorded
in the metadata.  Errors reading the file result in an empty
list of documents and are logged.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import pandas as pd

from .base_parser import DocumentParser
from ..document import Document


logger = logging.getLogger(__name__)


class ExcelParser(DocumentParser):
    """Concrete parser for Excel workbooks."""

    def parse(self, file_path: str) -> List[Document]:
        path = Path(file_path)
        documents: List[Document] = []
        if not path.is_file():
            logger.error("ExcelParser: %s is not a file", file_path)
            return documents
        try:
            xls = pd.ExcelFile(path)
        except Exception:
            logger.exception("ExcelParser: failed to open Excel file %s", file_path)
            return documents
        for sheet_name in xls.sheet_names:
            try:
                df = xls.parse(sheet_name)
            except Exception:
                logger.exception("ExcelParser: failed to parse sheet %s in %s", sheet_name, file_path)
                continue
            # Serialise sheet
            content_lines = [",".join(map(str, df.columns))]
            for _, row in df.iterrows():
                content_lines.append(",".join(map(lambda x: str(x) if x is not None else "", row.values)))
            content = "\n".join(content_lines)
            metadata = {"file_path": str(path), "sheet_name": sheet_name}
            documents.append(Document(text=content, metadata=metadata))
        logger.debug("ExcelParser: parsed %d sheets from %s", len(documents), file_path)
        return documents