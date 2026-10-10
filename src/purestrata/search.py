"""Dependency-free BM25 search with CJK (Japanese) support.

Latin text is tokenized as lowercased alphanumeric words. CJK text is
tokenized into character bigrams, which works well for Japanese without a
morphological analyzer and keeps PureStrata free of native extensions.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from .types import ALL_KINDS, Chunk

_WORD_RE = re.compile(r"[0-9A-Za-z_]+")
_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\u3005\u3007]+")

K1 = 1.5
B = 0.75

_STOPWORDS = frozenset(
    """a an and are as at be by for from has have in is it of on or that the this to was with
    です ます する した ため もの こと どこ いつ""".split()
)


def has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text))


def tokenize(text: str) -> list[str]:
    """Tokenize mixed Latin/CJK text for indexing and querying."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    tokens: list[str] = []
    for match in _WORD_RE.finditer(normalized):
        token = match.group(0)
        if token not in _STOPWORDS:
            tokens.append(token)
    for run in _CJK_RE.finditer(normalized):
        seq = run.group(0)
        if len(seq) == 1:
            tokens.append(seq)
        else:
            tokens.extend(seq[i : i + 2] for i in range(len(seq) - 1))
    return tokens


def load_local_embedding_encoder(
    model_path: str | Path,
) -> Callable[[list[str]], list[list[float]]]:
    """Load a SentenceTransformer from disk without allowing network access."""
    model_path = Path(model_path)
    if not model_path.is_dir():
        raise FileNotFoundError(f"Local embedding model not found: {model_path}")
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "Local semantic search requires the 'embeddings' extra. "
            "Install it with: pip install 'purestrata[embeddings]'"
        ) from exc
    model = SentenceTransformer(str(model_path), local_files_only=True)

    def encode(texts: list[str]) -> list[list[float]]:
        vectors = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return [[float(value) for value in vector] for vector in vectors]

    return encode


class SearchIndex:
    """Okapi BM25 index over a list of chunks."""

    def __init__(
        self,
        chunks: list[Chunk],
        embedding_encoder: Callable[[list[str]], list[list[float]]] | None = None,
    ):
        self._chunks = list(chunks)
        self._doc_tokens = [tokenize(chunk.text) for chunk in self._chunks]
        self._doc_len = [len(tokens) for tokens in self._doc_tokens]
        self._avgdl = sum(self._doc_len) / len(self._doc_len) if self._doc_len else 0.0
        self._df: Counter[str] = Counter()
        for tokens in self._doc_tokens:
            self._df.update(set(tokens))
        self._embedding_encoder = embedding_encoder
        self._doc_vectors = (
            self._encode([chunk.text for chunk in self._chunks])
            if embedding_encoder and self._chunks
            else []
        )

    def __len__(self) -> int:
        return len(self._chunks)

    def _score(self, query_tokens: list[str], idx: int) -> float:
        doc_tokens = self._doc_tokens[idx]
        doc_len = self._doc_len[idx] or 1
        counts = Counter(doc_tokens)
        score = 0.0
        n_docs = len(self._chunks)
        for token in query_tokens:
            tf = counts.get(token, 0)
            if tf == 0:
                continue
            df = self._df.get(token, 0)
            idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
            score += idf * (tf * (K1 + 1)) / (tf + K1 * (1 - B + B * doc_len / self._avgdl))
        return score

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._embedding_encoder(texts)
        if len(vectors) != len(texts):
            raise ValueError("Embedding encoder returned the wrong number of vectors.")
        normalized = []
        dimensions = None
        for vector in vectors:
            values = [float(value) for value in vector]
            if dimensions is None:
                dimensions = len(values)
            if not values or len(values) != dimensions or not all(math.isfinite(v) for v in values):
                raise ValueError("Embedding encoder returned empty or inconsistent vectors.")
            norm = math.sqrt(sum(value * value for value in values))
            normalized.append([value / norm for value in values] if norm else values)
        return normalized

    def search(
        self,
        query: str,
        kinds: str | tuple[str, ...] | list[str] | None = None,
        top_k: int = 5,
        hybrid: bool = False,
    ) -> list[tuple[Chunk, float]]:
        """Return (chunk, score) pairs ranked by BM25 relevance.

        ``kinds`` restricts the search to one or more chunk kinds. Zero-score
        matches are dropped.
        """
        if isinstance(kinds, str):
            kind_filter = {kinds}
        elif kinds is None:
            kind_filter = None
        else:
            kind_filter = set(kinds)
        if hybrid and self._embedding_encoder is None:
            raise ValueError("Hybrid search requires a local embedding encoder.")
        query_tokens = tokenize(query)
        if not query_tokens and not hybrid:
            return []
        lexical_scores = []
        for idx, chunk in enumerate(self._chunks):
            if kind_filter is not None and chunk.kind not in kind_filter:
                continue
            if chunk.kind not in ALL_KINDS:
                continue
            score = self._score(query_tokens, idx) if query_tokens else 0.0
            lexical_scores.append((idx, score))
        if not hybrid:
            results = [(self._chunks[idx], score) for idx, score in lexical_scores if score > 0]
            results.sort(key=lambda pair: pair[1], reverse=True)
            return results[:top_k]

        query_vector = self._encode([query])[0]
        if self._doc_vectors and len(query_vector) != len(self._doc_vectors[0]):
            raise ValueError("Query and document embedding dimensions do not match.")
        max_lexical = max((score for _idx, score in lexical_scores), default=0.0)
        results = []
        for idx, lexical_score in lexical_scores:
            semantic_score = sum(
                query_value * document_value
                for query_value, document_value in zip(
                    query_vector, self._doc_vectors[idx], strict=True
                )
            )
            normalized_lexical = lexical_score / max_lexical if max_lexical else 0.0
            combined_score = (normalized_lexical + max(0.0, semantic_score)) / 2
            if combined_score > 0:
                results.append((self._chunks[idx], combined_score))
        results.sort(key=lambda pair: pair[1], reverse=True)
        return results[:top_k]
