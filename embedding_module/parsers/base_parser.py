"""Abstract base class for document parsers.

A parser is responsible for reading a file from disk and producing
one or more :class:`~embedding_app.document.Document` instances.
Concrete subclasses implement the :meth:`parse` method for a
specific file format.  This design follows the factory method
pattern: clients interact with the abstract interface without
depending on the concrete parser implementation【705524173246349†L27-L34】.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List

from ..document import Document


logger = logging.getLogger(__name__)


class DocumentParser(ABC):
    """Defines the interface for all document parsers.

    Parsers receive a file path and return a list of Documents.
    Implementations should catch and log any exceptions they
    encounter during parsing, raising only when critical.  This
    behaviour allows the calling pipeline to continue processing
    other files while recording detailed error information for
    diagnosis.
    """

    @abstractmethod
    def parse(self, file_path: str) -> List[Document]:
        """Parse the given file and return a list of documents.

        Parameters
        ----------
        file_path:
            Absolute path to the file on disk.  Parsers should not
            assume anything about the existence or validity of the
            file; they are responsible for verifying it.

        Returns
        -------
        list of Document
            One or more documents derived from the source file.  For
            simple file formats such as plain text a single
            document is appropriate; for multi‑page formats such
            as PDF, multiple documents may be returned.
        """
        raise NotImplementedError