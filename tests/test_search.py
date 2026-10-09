"""Search and chunking tests."""

from __future__ import annotations

from purestrata import has_cjk, tokenize
from purestrata.pipeline import split_long_text


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
