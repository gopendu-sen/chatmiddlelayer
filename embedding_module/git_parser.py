"""Utilities for cloning and processing Git repositories.

This module defines :class:`GitRepositoryHandler` which clones a Git
repository to a temporary location and enumerates files within it
according to user‑supplied filters.  The handler does not perform
parsing itself; instead it delegates to the parser factory at
runtime.

Git repositories often contain a mixture of source code, documentation
and binary assets.  To avoid processing irrelevant files the
handler accepts lists of file extensions to include or exclude and
limits the total number of files processed.  When both include and
exclude lists are provided the exclude list takes precedence.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Iterable, List

try:
    import git  # type: ignore
except ImportError as exc:  # pragma: no cover - optional dependency
    git = None  # type: ignore

from .config import GitSettings
from .factory import ParserFactory
from .document import Document
from .parsers.base_parser import DocumentParser


logger = logging.getLogger(__name__)


class GitRepositoryHandler:
    """Clones a Git repository and yields documents using the parser factory."""

    def __init__(self, settings: GitSettings) -> None:
        if git is None:
            raise RuntimeError(
                "GitPython is required for Git repository handling. "
                "Install gitpython via pip."
            )
        self.settings = settings
        self._temp_dir: tempfile.TemporaryDirectory[str] | None = None

    def clone_repository(self) -> Path:
        """Clone the configured repository into a temporary directory.

        Returns
        -------
        Path
            Path object pointing to the cloned repository.
        """
        self._temp_dir = tempfile.TemporaryDirectory(prefix="repo_clone_")
        clone_path = Path(self._temp_dir.name)
        logger.info("Cloning repository %s into %s", self.settings.url, clone_path)
        try:
            repo = git.Repo.clone_from(self.settings.url, clone_path)
            if self.settings.branch:
                repo.git.checkout(self.settings.branch)
        except Exception:
            logger.exception("Failed to clone repository %s", self.settings.url)
            raise
        return clone_path

    def iter_files(self, repo_path: Path) -> Iterable[str]:
        """Iterate over files in the repository respecting extension filters.

        The include and exclude lists in :class:`GitSettings` control
        which file extensions are considered.  Exclude filters take
        precedence over include filters.  The iteration stops when
        ``max_files`` files have been yielded (if specified).
        """
        include_exts = (
            [ext.lower() for ext in self.settings.include_extensions]
            if self.settings.include_extensions
            else None
        )
        exclude_exts = (
            [ext.lower() for ext in self.settings.exclude_extensions]
            if self.settings.exclude_extensions
            else None
        )
        count = 0
        for root, _, files in os.walk(repo_path):
            for filename in files:
                ext = Path(filename).suffix.lower()
                # Apply filters
                if exclude_exts and ext in exclude_exts:
                    continue
                if include_exts and ext not in include_exts:
                    continue
                yield str(Path(root) / filename)
                count += 1
                if self.settings.max_files and count >= self.settings.max_files:
                    return

    def process(self) -> List[Document]:
        """Clone the repository and parse eligible files into documents.

        Returns
        -------
        list of Document
            All documents parsed from the repository according to the
            configured filters.
        """
        repo_path = self.clone_repository()
        documents: List[Document] = []
        factory = ParserFactory()
        for file_path in self.iter_files(repo_path):
            parser = factory.get_parser(file_path)
            if parser is None:
                logger.debug("GitRepositoryHandler: skipping unsupported file %s", file_path)
                continue
            docs = parser.parse(file_path)
            documents.extend(docs)
        # Clean up temporary directory after processing
        self.cleanup()
        return documents

    def cleanup(self) -> None:
        """Remove the cloned repository from the temporary directory."""
        if self._temp_dir is not None:
            logger.debug("Removing cloned repository at %s", self._temp_dir.name)
            self._temp_dir.cleanup()
            self._temp_dir = None