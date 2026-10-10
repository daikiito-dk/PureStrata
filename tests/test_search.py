"""Search and chunking tests."""

from __future__ import annotations

import importlib.util

import pytest

from purestrata import Corpus, has_cjk, tokenize
from purestrata.pipeline import split_long_text
from purestrata.search import load_local_embedding_encoder
from purestrata.types import MANUAL_SECTION, Chunk, Provenance


def test_tokenize_latin():
    assert tokenize("Spindle Vibration") == ["spindle", "vibration"]
    assert "the" not in tokenize("the spindle")  # English stopwords dropped


def test_tokenize_japanese_bigrams():
    tokens = tokenize("ブレーキ停止時間")
    assert "ブレ" in tokens
    assert "レー" in tokens
    assert "停止" in tokens
    assert "時間" in tokens


def test_has_cjk():
    assert has_cjk("振動")
    assert not has_cjk("vibration only")


def test_split_short_text_unchanged():
    assert split_long_text("short text", target=100, overlap=10) == ["short text"]


def test_split_long_text_sizes():
    paragraph = "Sentence one. " * 100
    pieces = split_long_text(paragraph, target=300, overlap=50)
    assert len(pieces) > 1
    for piece in pieces:
        assert len(piece) <= 300 + 50 + 2
    assert pieces[1].startswith(pieces[0][-50:])


def test_split_respects_paragraph_boundaries():
    text = "First paragraph.\n\n" + "Second long. " * 60
    pieces = split_long_text(text, target=200, overlap=30)
    assert pieces[0] == "First paragraph."


def test_search_english(corpus):
    results = corpus.search("spindle vibration", top_k=5)
    assert results
    assert all(score > 0 for _, score in results)
    top_kinds = {chunk.kind for chunk, _ in results[:3]}
    assert top_kinds & {"failure_case", "manual_section"}


def test_search_japanese(corpus):
    results = corpus.search("ブレーキ停止時間", top_k=3)
    assert results
    matches = [chunk for chunk, _ in results if "ブレーキ" in chunk.text]
    assert matches
    assert any(chunk.kind == "failure_case" for chunk in matches)


def test_search_kind_filter(corpus):
    results = corpus.search("spindle", kinds="part_record", top_k=5)
    assert results
    assert all(chunk.kind == "part_record" for chunk, _ in results)


def test_search_no_match_returns_empty(corpus):
    assert corpus.search("turbine governor") == []


def _semantic_chunks():
    return [
        Chunk(
            chunk_id="shaft-record",
            kind=MANUAL_SECTION,
            text="motor shaft makes loud noise",
            provenance=Provenance("manual", "manual.md", "section 1"),
        ),
        Chunk(
            chunk_id="coolant-record",
            kind=MANUAL_SECTION,
            text="coolant concentration is low",
            provenance=Provenance("manual", "manual.md", "section 2"),
        ),
    ]


def test_hybrid_search_finds_semantic_match_without_bm25_overlap():
    vectors = {
        "motor shaft makes loud noise": [1.0, 0.0],
        "coolant concentration is low": [0.0, 1.0],
        "journal bearing fault": [0.99, 0.1],
    }
    corpus = Corpus(
        _semantic_chunks(),
        embedding_encoder=lambda texts: [vectors[text] for text in texts],
        hybrid_search=True,
    )

    assert corpus.search("journal bearing fault", hybrid=False) == []
    results = corpus.search("journal bearing fault")
    assert results[0][0].chunk_id == "shaft-record"
    assert results[0][1] > 0


def test_hybrid_search_is_opt_in_and_requires_encoder():
    corpus = Corpus(_semantic_chunks())
    assert corpus.search("motor shaft")
    with pytest.raises(ValueError, match="requires a local embedding encoder"):
        corpus.search("unrelated semantic question", hybrid=True)


def test_hybrid_search_rejects_embedding_dimension_mismatch():
    calls = 0

    def encoder(texts):
        nonlocal calls
        calls += 1
        return [[1.0, 0.0] for _text in texts] if calls == 1 else [[1.0]]

    corpus = Corpus(_semantic_chunks(), embedding_encoder=encoder)
    with pytest.raises(ValueError, match="dimensions do not match"):
        corpus.search("query", hybrid=True)


def test_local_encoder_requires_existing_model_directory(tmp_path):
    with pytest.raises(FileNotFoundError, match="Local embedding model not found"):
        load_local_embedding_encoder(tmp_path / "missing-model")


def test_local_encoder_requires_embeddings_extra(tmp_path):
    if importlib.util.find_spec("sentence_transformers") is not None:
        pytest.skip("sentence-transformers is installed; the ImportError path is unreachable")
    with pytest.raises(RuntimeError, match="embeddings' extra"):
        load_local_embedding_encoder(tmp_path)
