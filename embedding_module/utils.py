"""Miscellaneous utility functions used throughout the application.

This module centralises helper functions that are not specific to a
particular component.  It includes common operations such as
generating random identifiers, ensuring directories exist, walking
file hierarchies and configuring the Python logging subsystem.
"""

from __future__ import annotations

import logging
import os
import random
import string
from pathlib import Path
from typing import Iterable, List, Tuple


def setup_logging(log_dir: str, log_level: int = logging.INFO) -> None:
    """Configure logging with both console and file handlers.

    Parameters
    ----------
    log_dir:
        Directory where the log file should be written.  The file
        ``application.log`` will be created inside this directory.
    log_level:
        Logging severity level.  Defaults to :attr:`logging.INFO`.  To
        enable debug messages pass :attr:`logging.DEBUG`.

    The logging configuration is global; invoking this function more
    than once will reconfigure the root logger and may duplicate
    handlers.  It should therefore be called once at application
    startup.
    """
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_file = Path(log_dir) / "application.log"

    # Remove any existing handlers to avoid duplicate log entries
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    root_logger.setLevel(log_level)

    # File handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_formatter = logging.Formatter(
        fmt="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(console_formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def random_suffix(length: int = 4) -> str:
    """Generate a random alphanumeric suffix.

    Parameters
    ----------
    length:
        Number of characters in the generated suffix.  Default is 4.

    Returns
    -------
    str
        A random string composed of uppercase letters and digits.
    """
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choices(alphabet, k=length))


def ensure_unique_path(base_dir: str, desired_name: str) -> str:
    """Ensure that a file or directory name is unique within a directory.

    If the given ``desired_name`` already exists inside ``base_dir``
    the function appends a random suffix separated by an underscore
    until a unique name is obtained.

    Parameters
    ----------
    base_dir:
        Directory in which the file or directory will be created.
    desired_name:
        Proposed name for the resource.  This should not include any
        directory separators.

    Returns
    -------
    str
        A unique name that does not collide with existing files or
        directories inside ``base_dir``.
    """
    base_path = Path(base_dir)
    candidate = desired_name
    while (base_path / candidate).exists():
        candidate = f"{desired_name}_{random_suffix()}"
    return candidate


def list_files(directory: str) -> List[str]:
    """Recursively list all files under a directory.

    Binary files are not filtered by this function; filtering based on
    extension should be performed by callers via the parser factory.

    Parameters
    ----------
    directory:
        Path to the directory to search.

    Returns
    -------
    list of str
        Absolute paths to all files found.
    """
    path_obj = Path(directory)
    if not path_obj.is_dir():
        raise ValueError(f"{directory} is not a directory")
    files: List[str] = []
    for root, _, filenames in os.walk(path_obj):
        for fname in filenames:
            files.append(str(Path(root) / fname))
    return files