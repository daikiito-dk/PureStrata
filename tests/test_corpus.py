"""Corpus storage and round-trip tests."""

from __future__ import annotations

import json

import pytest

from purestrata import Corpus, ingest_manual, write_chunks


def test_write_and_load_roundtrip(tmp_path, en_manual):
    chunks = ingest_manual(en_manual)
    out = write_chunks(chunks, tmp_path, "test_doc")
    assert out.name == "test_doc.strata.jsonl"

    loaded = Corpus.load(tmp_path)
    assert len(loaded.chunks) == len(chunks)
    by_id = {chunk.chunk_id: chunk for chunk in loaded.chunks}
    for original in chunks:
        restored = by_id[original.chunk_id]
        assert restored.text == original.text
        assert restored.kind == original.kind
        assert restored.metadata == original.metadata
        assert restored.provenance == original.provenance


def test_stats(corpus):
    stats = corpus.stats()
    assert stats["total_chunks"] == 29
    assert stats["by_kind"]["drawing"] == 2
    assert stats["by_kind"]["part_record"] == 8
    assert stats["by_kind"]["safety_notice"] == 6
    assert len(stats["documents"]) == 5


def test_reingestion_is_idempotent(tmp_path, en_manual):
    from purestrata import write_chunks

    chunks = ingest_manual(en_manual)
    write_chunks(chunks, tmp_path, chunks[0].provenance.doc_id)
    write_chunks(chunks, tmp_path, chunks[0].provenance.doc_id)
    loaded = Corpus.load(tmp_path)
    assert len(loaded.chunks) == len(chunks)  # overwrite, no duplication


def test_load_missing_directory_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        Corpus.load(tmp_path / "does_not_exist")


def test_rejects_foreign_schema(tmp_path):
    bad = tmp_path / "bad.strata.jsonl"
    bad.write_text(json.dumps({"schema": "other/v9", "chunk_id": "x"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        Corpus.load(tmp_path)
