"""Configuration data structures for the vector store generator.

These data classes capture the parameters accepted by the command
line interface as well as optional settings for Git and
Confluence integration and embedding behaviour.  Using data
classes makes it easy to pass structured configuration throughout
the application and provides type hints for improved clarity and
tooling support.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class GitSettings:
    """Options controlling how a Git repository is processed.

    Attributes
    ----------
    url:
        The URL of the Git repository to clone.
    exclude_extensions:
        A list of file extensions to exclude from processing.  If
        provided this list takes precedence over :attr:`include_extensions`.
    include_extensions:
        A list of file extensions to include when processing the
        repository.  If provided only files with these extensions will
        be examined.  When neither include nor exclude lists are
        specified a sensible default is applied to skip binary files
        such as images and archives.
    max_files:
        The maximum number of files to process from the repository.
        When ``None`` all files matching the extension filters are
        processed.
    branch:
        Optional branch name to checkout after cloning.  If not
        specified the repository's default branch is used.
    """

    url: str
    exclude_extensions: Optional[List[str]] = None
    include_extensions: Optional[List[str]] = None
    max_files: Optional[int] = None
    branch: Optional[str] = None


@dataclass
class ConfluenceSettings:
    """Options for retrieving pages from a Confluence space.

    Attributes
    ----------
    url:
        Base URL of the Confluence instance (e.g. ``https://your‑domain.atlassian.net``).
    user:
        User name or email used to authenticate via basic authentication.
    token:
        Personal access token or password associated with the user.
    space_key:
        The key of the Confluence space to crawl.
    max_pages:
        The maximum number of pages to retrieve.  When ``None`` all
        pages are fetched.
    """

    url: str
    user: str
    token: str
    space_key: str
    max_pages: Optional[int] = None


@dataclass
class EmbeddingConfig:
    """Configuration controlling the embedding generation process.

    Attributes
    ----------
    endpoint:
        The base URL of the embedding service.  Default is the local
        endpoint ``http://localhost:8001/v1/embeddings``.  The service
        is expected to accept POST requests with JSON payload
        containing an ``input`` key mapping to a list of strings.
    batch_size:
        Maximum number of documents to send in a single request.  The
        API may impose a limit on the number of inputs per call,
        therefore batching is recommended.  The default of 32 is
        reasonably conservative.
    model_kwargs:
        Additional keyword arguments forwarded to the embedding
        endpoint as part of each request.  This allows callers to
        select specific models or configuration on the server side.
    """

    endpoint: str = "http://localhost:8001/v1/embeddings"
    batch_size: int = 32
    model_kwargs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AppConfig:
    """Top level configuration for the vector store generation application.

    The command line interface populates an instance of this class
    using the user supplied arguments.  It mandates a path where
    the resulting vector store will be written and the desired name
    for the store.  Optionally a session identifier can be provided
    which will be recorded in metadata associated with every
    document.  At least one of ``files_location``, ``git_settings``
    or ``confluence_settings`` must be supplied or the application
    will refuse to run.
    """

    vector_store_path: str
    vector_store_name: str
    session_id: Optional[str] = None
    files_location: Optional[str] = None
    git_settings: Optional[GitSettings] = None
    confluence_settings: Optional[ConfluenceSettings] = None
    embedding_config: EmbeddingConfig = field(default_factory=EmbeddingConfig)