"""Simple data structures for representing documents.

The `Document` class encapsulates a chunk of text along with
metadata describing its origin.  A single source file may produce
multiple :class:`Document` instances, for example when splitting
large PDFs into page‑sized chunks.  Downstream components such as
the embedding client and vector store builder operate on sequences
of these objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class Document:
    """Represents a unit of text along with associated metadata.

    Parameters
    ----------
    text:
        The textual content of this document.  Clients should ensure
        that the text is reasonably sized (for example, breaking large
        files into pages or paragraphs) to avoid exceeding model
        context limits.

    metadata:
        A dictionary of arbitrary key/value pairs describing the
        origin of the text.  Typical keys include ``file_path``,
        ``page_number`` for PDF pages, ``sheet_name`` for Excel
        worksheets, or any user‑defined identifiers.  Metadata is
        persisted alongside embeddings so that retrieved vectors can
        be mapped back to their source.
    """

    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Ensure the text field is always a string to avoid runtime
        # surprises from downstream consumers.
        if not isinstance(self.text, str):
            raise TypeError(f"Document.text must be a string, got {type(self.text)!r}")

        # Normalise metadata keys to strings to avoid serialisation issues
        self.metadata = {str(k): v for k, v in self.metadata.items()}