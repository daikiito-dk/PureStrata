"""Shared file-writing helpers for the export modules."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_lines_atomic(path: str | Path, lines: list[str]) -> Path:
    """Write lines via a temporary file and rename, so an interrupted write
    never leaves a truncated output behind."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            for line in lines:
                handle.write(line)
                handle.write("\n")
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
    return path
