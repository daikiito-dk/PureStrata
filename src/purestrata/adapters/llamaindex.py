"""LlamaIndex adapter: retrieve from a PureStrata corpus inside LlamaIndex.

Requires the optional ``llamaindex`` extra:

    pip install 'purestrata[llamaindex]'

Supported: ``llama-index-core >= 0.10`` (the ``BaseRetriever`` API). The
retriever wraps the local PureStrata corpus; nothing leaves the machine.
Every node carries the PureStrata chunk ID and full provenance, so answers
built on these retrievals stay auditable.
"""

from __future__ import annotations

from ..corpus import Corpus
from ..types import Chunk

try:
    # Imported from the stable submodules: the top-level `llama_index.core`
    # namespace trimmed these re-exports in newer releases (>= 0.14).
    from llama_index.core.retrievers import BaseRetriever
    from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
except ImportError as exc:  # pragma: no cover - exercised via tests when the extra is absent
    raise RuntimeError(
        "The LlamaIndex adapter requires the 'llamaindex' extra. "
        "Install it with: pip install 'purestrata[llamaindex]'"
    ) from exc

__all__ = ["PureStrataRetriever", "chunk_to_node"]


def chunk_to_node(chunk: Chunk) -> TextNode:
    """Convert one PureStrata record into a TextNode with provenance metadata."""
    metadata = {
        "chunk_id": chunk.chunk_id,
        "kind": chunk.kind,
        "provenance": chunk.provenance.to_dict(),
        "record_metadata": chunk.metadata,
    }
    return TextNode(id_=chunk.chunk_id, text=chunk.text, metadata=metadata)


class PureStrataRetriever(BaseRetriever):
    """A LlamaIndex retriever over a local PureStrata corpus.

    Retrieval runs on the corpus in memory (BM25 by default, or the corpus's
    opt-in hybrid search via ``hybrid=True``). No documents are uploaded;
    ``hybrid`` only changes local scoring, matching ``Corpus.search``.
    """

    def __init__(
        self,
        corpus: Corpus,
        top_k: int = 5,
        kinds: str | tuple[str, ...] | list[str] | None = None,
        hybrid: bool | None = None,
    ) -> None:
        super().__init__()
        self._corpus = corpus
        self._top_k = top_k
        self._kinds = kinds
        self._hybrid = hybrid

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        results = self._corpus.search(
            query_bundle.query_str,
            kinds=self._kinds,
            top_k=self._top_k,
            hybrid=self._hybrid,
        )
        return [
            NodeWithScore(node=chunk_to_node(chunk), score=float(score)) for chunk, score in results
        ]
