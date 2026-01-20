"""Utilities for retrieving documents from a Confluence space.

This module defines :class:`ConfluenceSpaceHandler` which connects to
an Atlassian Confluence instance using the `atlassian-python-api`
package.  It fetches pages from a specified space and extracts
their textual content for embedding.  Each page becomes a
document with metadata including the page id and title.  HTML
content is converted to plain text using BeautifulSoup.
"""

from __future__ import annotations

import logging
from typing import List

try:
    from atlassian import Confluence  # type: ignore
except ImportError as exc:  # pragma: no cover - optional dependency
    Confluence = None  # type: ignore

try:
    from bs4 import BeautifulSoup  # type: ignore
except ImportError:
    BeautifulSoup = None  # type: ignore

from .config import ConfluenceSettings
from .document import Document


logger = logging.getLogger(__name__)


class ConfluenceSpaceHandler:
    """Retrieves pages from a Confluence space and converts them to documents."""

    def __init__(self, settings: ConfluenceSettings) -> None:
        if Confluence is None:
            raise RuntimeError(
                "The atlassian-python-api library is required to access Confluence. "
                "Install atlassian-python-api via pip."
            )
        if BeautifulSoup is None:
            raise RuntimeError(
                "BeautifulSoup4 is required to parse Confluence page content. "
                "Install bs4 via pip."
            )
        self.settings = settings
        self.client = Confluence(
            url=settings.url,
            username=settings.user,
            password=settings.token,
        )

    def _html_to_text(self, html: str) -> str:
        """Convert Confluence storage format (HTML) to plain text."""
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator="\n", strip=True)

    def process(self) -> List[Document]:
        """Fetch pages from the configured space and return documents.

        Returns
        -------
        list of Document
            Documents extracted from Confluence pages.  Each page is
            represented by a single document.  If a page fails to
            fetch or parse it is logged and skipped.
        """
        max_pages = self.settings.max_pages or float("inf")
        logger.info(
            "Fetching up to %s pages from Confluence space %s",
            max_pages if max_pages != float("inf") else "all",
            self.settings.space_key,
        )
        documents: List[Document] = []
        try:
            # Use the built in method to get page ids and titles.  We set limit
            # to a high value because we handle max_pages ourselves.
            pages = self.client.get_all_pages_from_space(
                space=self.settings.space_key, start=0, limit=max_pages, status="current"
            )
        except Exception:
            logger.exception(
                "ConfluenceSpaceHandler: failed to list pages for space %s",
                self.settings.space_key,
            )
            return documents
        count = 0
        for page in pages:
            if count >= max_pages:
                break
            page_id = page.get("id")
            title = page.get("title", "")
            try:
                page_data = self.client.get_page_by_id(page_id, expand="body.storage")
                storage = page_data.get("body", {}).get("storage", {}).get("value", "")
                text = self._html_to_text(storage)
                metadata = {
                    "page_id": page_id,
                    "title": title,
                    "space_key": self.settings.space_key,
                    "url": f"{self.settings.url}/pages/{page_id}",
                }
                documents.append(Document(text=text, metadata=metadata))
                count += 1
            except Exception:
                logger.exception(
                    "ConfluenceSpaceHandler: failed to fetch or parse page %s (%s)",
                    page_id,
                    title,
                )
        logger.info("Fetched %d pages from Confluence space %s", count, self.settings.space_key)
        return documents