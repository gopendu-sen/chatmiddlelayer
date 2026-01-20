"""Quick connectivity test for embeddings across sources.

Run this script to verify end-to-end connectivity for file, Git,
Confluence, or combined ingestion paths using the existing CLI
pipeline.  Each selected source triggers a separate pipeline run
with a unique vector store name so results do not collide.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Set
from uuid import uuid4

# Allow running directly without installing as a package
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embedding_app.cli import run_pipeline  # type: ignore
from embedding_app.config import (  # type: ignore
    AppConfig,
    ConfluenceSettings,
    EmbeddingConfig,
    GitSettings,
)
from embedding_app.utils import setup_logging  # type: ignore


def build_config(
    *,
    vector_store_path: str,
    store_prefix: str,
    session_id: Optional[str],
    embedding_endpoint: str,
    embedding_batch_size: int,
    files_location: Optional[str],
    git_settings: Optional[GitSettings],
    confluence_settings: Optional[ConfluenceSettings],
) -> AppConfig:
    embed_cfg = EmbeddingConfig(endpoint=embedding_endpoint, batch_size=embedding_batch_size)
    store_name = f"{store_prefix}_{uuid4().hex[:6]}"
    return AppConfig(
        vector_store_path=vector_store_path,
        vector_store_name=store_name,
        session_id=session_id,
        files_location=files_location,
        git_settings=git_settings,
        confluence_settings=confluence_settings,
        embedding_config=embed_cfg,
    )


def schedule_runs(
    *,
    files_location: Optional[str],
    git_settings: Optional[GitSettings],
    confluence_settings: Optional[ConfluenceSettings],
) -> List[Set[str]]:
    runs: List[Set[str]] = []
    sources: List[tuple[str, Optional[object]]] = [
        ("files", files_location),
        ("git", git_settings),
        ("confluence", confluence_settings),
    ]
    present = {name for name, cfg in sources if cfg}
    if files_location:
        runs.append({"files"})
    if git_settings:
        runs.append({"git"})
    if confluence_settings:
        runs.append({"confluence"})
    if len(present) > 1:
        runs.append(present)
    return runs


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quick connectivity test for embeddings across sources.")
    parser.add_argument("--vector_store_path", default="test/output", help="Base directory for test vector stores.")
    parser.add_argument("--store_prefix", default="connectivity", help="Prefix for generated vector store names.")
    parser.add_argument("--session_id", default=None, help="Optional session id to add to metadata.")
    parser.add_argument("--embedding_endpoint", default="http://localhost:8001/v1/embeddings", help="Embedding API URL.")
    parser.add_argument("--embedding_batch_size", type=int, default=8, help="Batch size for embedding requests.")
    parser.add_argument("--files_location", help="File or directory path for file-based test.")
    parser.add_argument("--git_url", help="Git repository URL for git-based test.")
    parser.add_argument("--git_branch", help="Optional branch to checkout.")
    parser.add_argument("--git_include", nargs="*", help="List of file extensions to include (e.g. .py .md).")
    parser.add_argument("--git_exclude", nargs="*", help="List of file extensions to exclude.")
    parser.add_argument("--git_max_files", type=int, help="Maximum files to process from the repo.")
    parser.add_argument("--confluence_url", help="Base Confluence URL (e.g. https://your-domain.atlassian.net).")
    parser.add_argument("--confluence_user", help="Confluence username/email.")
    parser.add_argument("--confluence_token", help="Confluence API token.")
    parser.add_argument("--confluence_space_key", help="Confluence space key.")
    parser.add_argument("--confluence_max_pages", type=int, help="Max pages to fetch from Confluence.")
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    setup_logging(args.vector_store_path, logging.INFO)

    git_cfg = None
    if args.git_url:
        git_cfg = GitSettings(
            url=args.git_url,
            exclude_extensions=args.git_exclude,
            include_extensions=args.git_include,
            max_files=args.git_max_files,
            branch=args.git_branch,
        )

    conf_cfg = None
    if all([args.confluence_url, args.confluence_user, args.confluence_token, args.confluence_space_key]):
        conf_cfg = ConfluenceSettings(
            url=args.confluence_url,
            user=args.confluence_user,
            token=args.confluence_token,
            space_key=args.confluence_space_key,
            max_pages=args.confluence_max_pages,
        )
    elif any([args.confluence_url, args.confluence_user, args.confluence_token, args.confluence_space_key]):
        print("Confluence test requires url, user, token, and space key. Skipping Confluence.")

    runs = schedule_runs(
        files_location=args.files_location,
        git_settings=git_cfg,
        confluence_settings=conf_cfg,
    )

    if not runs:
        print("No sources configured. Provide at least one of --files_location, --git_url, or Confluence settings.")
        return 1

    exit_code = 0
    for source_set in runs:
        label = "-".join(sorted(source_set))
        print(f"\n=== Running {label} connectivity test ===")
        try:
            config = build_config(
                vector_store_path=args.vector_store_path,
                store_prefix=f"{args.store_prefix}_{label}",
                session_id=args.session_id,
                embedding_endpoint=args.embedding_endpoint,
                embedding_batch_size=args.embedding_batch_size,
                files_location=args.files_location if "files" in source_set else None,
                git_settings=git_cfg if "git" in source_set else None,
                confluence_settings=conf_cfg if "confluence" in source_set else None,
            )
            store_name = run_pipeline(config)
            store_dir = Path(args.vector_store_path) / store_name
            print(f"SUCCESS: {label} test created vector store at {store_dir}")
        except Exception as exc:  # pragma: no cover - runtime connectivity
            exit_code = 1
            print(f"FAILED: {label} test -> {exc}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
