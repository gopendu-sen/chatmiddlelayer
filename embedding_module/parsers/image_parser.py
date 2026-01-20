"""Parser for image files using OCR.

This parser extracts text from common image formats (.png, .jpg,
.jpeg, .tiff, .bmp) via Tesseract OCR.  Dependencies (`pillow` and
`pytesseract`) are treated as optional: if they are missing or
Tesseract is not available, the parser logs a clear message and
returns no documents.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:  # pragma: no cover - optional dependency
    Image = None  # type: ignore
    UnidentifiedImageError = Exception  # type: ignore

try:
    import pytesseract
except ImportError:  # pragma: no cover - optional dependency
    pytesseract = None  # type: ignore

from .base_parser import DocumentParser
from ..document import Document


logger = logging.getLogger(__name__)


class ImageParser(DocumentParser):
    """Concrete parser that performs OCR on image files."""

    _supported_exts = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}

    def parse(self, file_path: str) -> List[Document]:
        documents: List[Document] = []
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix not in self._supported_exts:
            logger.error("ImageParser: unsupported file extension %s", suffix)
            return documents
        if not path.is_file():
            logger.error("ImageParser: %s is not a file", file_path)
            return documents

        if Image is None or pytesseract is None:
            logger.error(
                "ImageParser: pillow and pytesseract are required. Install with `pip install pillow pytesseract`."
            )
            return documents

        try:
            # Ensure Tesseract binary is reachable; raises if missing.
            pytesseract.get_tesseract_version()
        except Exception:
            logger.exception("ImageParser: Tesseract OCR binary not found or not working for %s", file_path)
            return documents

        try:
            with Image.open(path) as img:
                text = pytesseract.image_to_string(img.convert("RGB"))
        except UnidentifiedImageError:
            logger.exception("ImageParser: failed to identify image %s", file_path)
            return documents
        except Exception:
            logger.exception("ImageParser: failed to extract text from image %s", file_path)
            return documents

        metadata = {"file_path": str(path), "format": suffix.lstrip(".")}
        documents.append(Document(text=text, metadata=metadata))
        logger.debug("ImageParser: extracted text from %s", file_path)
        return documents
