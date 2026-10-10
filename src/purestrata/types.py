"""Core data model for the PureStrata data layer.

Every record in a PureStrata corpus is a :class:`Chunk`: typed text with a
metadata payload and a :class:`Provenance` locator pointing back to the
source file. Provenance is what makes a corpus auditable: every answer a
model gives can be traced to a line in a drawing, a section of a manual, or
a row in a failure log.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

MANUAL_SECTION = "manual_section"
SAFETY_NOTICE = "safety_notice"
PROCEDURE = "procedure"
PART_RECORD = "part_record"
DRAWING = "drawing"
FAILURE_CASE = "failure_case"

ALL_KINDS = (
    MANUAL_SECTION,
    SAFETY_NOTICE,
    PROCEDURE,
    PART_RECORD,
    DRAWING,
    FAILURE_CASE,
)

SCHEMA_VERSION = "purestrata/v1"


def derive_doc_id(path: str | Path) -> str:
    """Derive a stable document id from a file path."""
    stem = Path(path).stem
    return re.sub(r"[^0-9A-Za-z._-]+", "_", stem.strip()).strip("_").lower() or "doc"


def make_chunk_id(doc_id: str, kind: str, locator: str) -> str:
    """Build a stable chunk id from its coordinates.

    The id is deterministic, so re-ingesting an unchanged source file
    produces the same ids and ingestion is idempotent.
    """
    raw = f"{doc_id}::{kind}::{locator}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 fingerprint of a source file's exact bytes."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


MAX_INGEST_BYTES = 256 * 1024 * 1024


def ensure_ingest_size(path: str | Path, max_bytes: int | None = None) -> None:
    """Refuse to ingest files above a size limit.

    Adapters read whole files into memory, so one hostile or broken file
    could otherwise exhaust the host. Pass ``max_bytes`` to override the
    default for legitimately large drawings or models.
    """
    path = Path(path)
    limit = MAX_INGEST_BYTES if max_bytes is None else max_bytes
    size = path.stat().st_size
    if size > limit:
        raise ValueError(f"Refusing to ingest {path}: {size} bytes exceeds the {limit}-byte limit.")


@dataclass
class Provenance:
    """Where a chunk came from, in a human-readable form."""

    doc_id: str
    source_path: str
    locator: str
    source_sha256: str | None = None
    anchor: dict | None = None

    def to_dict(self) -> dict:
        data = {
            "doc_id": self.doc_id,
            "source_path": self.source_path,
            "locator": self.locator,
        }
        if self.source_sha256 is not None:
            data["source_sha256"] = self.source_sha256
        if self.anchor is not None:
            data["anchor"] = self.anchor
        return data

    @classmethod
    def from_dict(cls, data: dict) -> Provenance:
        return cls(
            doc_id=str(data["doc_id"]),
            source_path=str(data["source_path"]),
            locator=str(data["locator"]),
            source_sha256=str(data["source_sha256"]) if data.get("source_sha256") else None,
            anchor=dict(data["anchor"]) if data.get("anchor") is not None else None,
        )

    def __str__(self) -> str:
        return f"{self.source_path} :: {self.locator}"


@dataclass
class Chunk:
    """A typed, searchable record with metadata and provenance."""

    chunk_id: str
    kind: str
    text: str
    provenance: Provenance
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "schema": SCHEMA_VERSION,
            "chunk_id": self.chunk_id,
            "kind": self.kind,
            "text": self.text,
            "metadata": self.metadata,
            "provenance": self.provenance.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Chunk:
        schema = data.get("schema", "")
        if schema and not schema.startswith("purestrata/"):
            raise ValueError(f"Unsupported corpus record schema: {schema!r}")
        return cls(
            chunk_id=str(data["chunk_id"]),
            kind=str(data["kind"]),
            text=str(data["text"]),
            provenance=Provenance.from_dict(data["provenance"]),
            metadata=dict(data.get("metadata") or {}),
        )


def new_chunk(kind: str, text: str, provenance: Provenance, metadata: dict | None = None) -> Chunk:
    """Create a chunk with a deterministic id derived from its coordinates."""
    chunk_id = make_chunk_id(provenance.doc_id, kind, provenance.locator)
    return Chunk(
        chunk_id=chunk_id,
        kind=kind,
        text=text,
        provenance=provenance,
        metadata=metadata or {},
    )
