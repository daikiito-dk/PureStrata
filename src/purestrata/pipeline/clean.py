"""Text cleaning helpers applied to extracted prose blocks.

Cleaning happens *after* structural parsing (headings, lists, tables), so it
never destroys layout information. It only normalizes whitespace and
rejoins words that were hyphenated across printed page lines.
"""

from __future__ import annotations

import re

_HYPHEN_RE = re.compile(r"([A-Za-z0-9])-\n([A-Za-z0-9])")
_WHITESPACE_RE = re.compile(r"[ \t\u3000]+")


def dehyphenate(text: str) -> str:
    """Rejoin words broken across lines in extracted PDF text."""
    return _HYPHEN_RE.sub(r"\1\2", text)


def normalize_block(raw: str) -> str:
    """Normalize a block of prose without destroying paragraph breaks."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = dehyphenate(text)
    lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def clean_inline(raw: str) -> str:
    """Collapse all whitespace (including newlines) into single spaces."""
    return _WHITESPACE_RE.sub(" ", raw.replace("\n", " ")).strip()
