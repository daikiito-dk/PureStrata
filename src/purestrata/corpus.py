"""Corpus storage: a directory of portable, auditable JSONL files.

A corpus is just ``*.strata.jsonl`` files, one JSON object per line per
chunk. No database, no server, no lock-in: companies can drop a corpus on a
file share, ship it to an air-gapped network, or commit small ones to git.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .search import SearchIndex, load_local_embedding_encoder
from .types import ALL_KINDS, Chunk

CORPUS_SUFFIX = ".strata.jsonl"


def write_chunks(chunks: list[Chunk], out_dir: str | Path, doc_id: str) -> Path:
    """Write one ``<doc_id>.strata.jsonl`` file for an ingested document."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{doc_id}{CORPUS_SUFFIX}"
    with open(out_path, "w", encoding="utf-8") as handle:
        for chunk in chunks:
            # allow_nan=False keeps non-standard Infinity/NaN literals out of
            # the JSONL so strict parsers downstream never see them.
            handle.write(json.dumps(chunk.to_dict(), ensure_ascii=False, allow_nan=False))
            handle.write("\n")
    return out_path


class Corpus:
    """An in-memory view of a directory of strata files, with search."""

    def __init__(
        self,
        chunks: list[Chunk],
        embedding_encoder=None,
        hybrid_search: bool = False,
    ):
        self.chunks = list(chunks)
        self._embedding_encoder = embedding_encoder
        self._hybrid_search = hybrid_search
        self._index: SearchIndex | None = None

    @classmethod
    def load(
        cls,
        corpus_dir: str | Path,
        *,
        embedding_model: str | Path | None = None,
        hybrid_search: bool = False,
    ) -> Corpus:
        """Load every ``*.strata.jsonl`` file under ``corpus_dir``."""
        if hybrid_search and not embedding_model:
            raise ValueError("Hybrid search requires a local embedding_model path.")
        if embedding_model and not hybrid_search:
            raise ValueError("embedding_model requires hybrid_search=True.")
        corpus_dir = Path(corpus_dir)
        if not corpus_dir.exists():
            raise FileNotFoundError(f"Corpus directory not found: {corpus_dir}")
        chunks: list[Chunk] = []
        for path in sorted(corpus_dir.glob(f"*{CORPUS_SUFFIX}")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    chunks.append(Chunk.from_dict(json.loads(line)))
        encoder = load_local_embedding_encoder(embedding_model) if embedding_model else None
        return cls(chunks, embedding_encoder=encoder, hybrid_search=hybrid_search)

    @property
    def index(self) -> SearchIndex:
        if self._index is None:
            self._index = SearchIndex(self.chunks, embedding_encoder=self._embedding_encoder)
        return self._index

    def stats(self) -> dict:
        by_kind = Counter(chunk.kind for chunk in self.chunks)
        by_doc = Counter(chunk.provenance.doc_id for chunk in self.chunks)
        return {
            "total_chunks": len(self.chunks),
            "by_kind": {kind: by_kind[kind] for kind in ALL_KINDS if by_kind[kind]},
            "documents": sorted(by_doc),
        }

    def search(
        self, query: str, kinds=None, top_k: int = 5, *, hybrid: bool | None = None
    ) -> list[tuple[Chunk, float]]:
        use_hybrid = self._hybrid_search if hybrid is None else hybrid
        return self.index.search(query, kinds=kinds, top_k=top_k, hybrid=use_hybrid)

    def get(self, chunk_id: str) -> Chunk | None:
        for chunk in self.chunks:
            if chunk.chunk_id == chunk_id:
                return chunk
        return None

    def by_kind(self, *kinds: str) -> list[Chunk]:
        wanted = set(kinds)
        return [chunk for chunk in self.chunks if chunk.kind in wanted]
