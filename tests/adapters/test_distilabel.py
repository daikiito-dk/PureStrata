"""distilabel adapter tests.

``records_to_examples`` is dependency-free and always runs. ``to_dataset``
is covered only when the distilabel extra (its ``datasets`` dependency) is
installed.
"""

from __future__ import annotations

import importlib.util

import pytest

from purestrata.adapters.distilabel import records_to_examples, to_dataset
from purestrata.export.finetune import build_chat_records, build_cot_records


def test_examples_keep_payload_and_add_provenance_columns(corpus):
    records = build_chat_records(corpus, limit=3)
    examples = records_to_examples(records, format="chat")

    assert len(examples) == 3
    for record, example in zip(records, examples, strict=True):
        assert example["messages"] == record["messages"]
        assert example["sources"] == record["sources"]
        assert example["purestrata_chunk_ids"] == [record["sources"][0]["chunk_id"]]
        assert example["purestrata_record_kinds"] == [record["sources"][0]["record_kind"]]
        assert example["purestrata_doc_ids"] == [record["sources"][0]["doc_id"]]
        assert example["purestrata_source_paths"] == [record["sources"][0]["source_path"]]
        assert example["purestrata_locators"] == [record["sources"][0]["locator"]]
        assert example["purestrata_source_sha256"] == [record["sources"][0]["source_sha256"]]


def test_examples_reject_records_without_sources():
    with pytest.raises(ValueError, match="provenance is required"):
        records_to_examples([{"instruction": "x", "reasoning": "y", "output": "z"}])


def test_examples_validate_format_shape():
    with pytest.raises(ValueError, match="does not match the chat format"):
        records_to_examples([{"instruction": "x", "sources": [{}]}], format="chat")
    with pytest.raises(ValueError, match="Unsupported format"):
        records_to_examples([{"sources": [{}]}], format="dpo")


def test_to_dataset_requires_extra():
    if importlib.util.find_spec("datasets") is not None:
        pytest.skip("datasets is installed; the ImportError path is unreachable")
    with pytest.raises(RuntimeError, match="distilabel' extra"):
        to_dataset(
            [{"instruction": "x", "reasoning": "y", "output": "z", "sources": [{}]}],
            format="cot",
        )


def test_to_dataset_builds_hf_dataset(corpus):
    pytest.importorskip("datasets")
    records = build_cot_records(corpus, limit=2)
    dataset = to_dataset(records, format="cot")

    assert len(dataset) == 2
    assert "purestrata_chunk_ids" in dataset.column_names
    assert "instruction" in dataset.column_names
    row = dataset[0]
    assert row["instruction"]
    assert row["purestrata_chunk_ids"][0]
    assert row["purestrata_locators"][0]
