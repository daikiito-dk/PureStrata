"""Offline fine-tuning dataset evaluation tests."""

from __future__ import annotations

import json

import pytest

from purestrata import (
    build_chat_records,
    build_cot_records,
    evaluate_dataset,
    format_evaluation_summary,
    write_jsonl,
)

_SOURCE = {
    "doc_id": "failure-log",
    "source_path": "failures.csv",
    "locator": "row 1",
    "chunk_id": "failure-001",
    "record_kind": "failure_case",
}


def test_evaluate_generated_dataset_reports_source_and_kind_coverage(tmp_path, corpus):
    records = build_chat_records(corpus)
    path = write_jsonl(records, tmp_path / "chat.jsonl")

    report = evaluate_dataset(path, "chat")

    assert report["valid_records"] == len(records)
    assert report["invalid_records"] == 0
    assert report["source_coverage"]
    assert report["record_kind_coverage"]["failure_case"] > 0
    assert not any(finding["severity"] == "error" for finding in report["findings"])


def test_evaluate_detects_exact_duplicates_without_printing_record_content(tmp_path):
    record = {
        "instruction": "PRIVATE CUSTOMER QUESTION",
        "reasoning": "A grounded trace.",
        "output": "Answer.",
        "sources": [_SOURCE],
    }
    path = tmp_path / "duplicates.jsonl"
    path.write_text(
        json.dumps(record) + "\n" + json.dumps(record) + "\n",
        encoding="utf-8",
    )

    report = evaluate_dataset(path, "cot")
    summary = format_evaluation_summary(report)

    assert report["exact_duplicate_excess"] == 1
    duplicate_finding = next(
        finding for finding in report["findings"] if finding["code"] == "exact_duplicate"
    )
    assert len(duplicate_finding["examples"]) == 2
    assert "PRIVATE CUSTOMER QUESTION" not in summary
    assert "failures.csv" not in summary


def test_evaluate_flags_incomplete_failure_answer(tmp_path):
    record = {
        "messages": [
            {"role": "system", "content": "System"},
            {
                "role": "user",
                "content": "We are troubleshooting a problem. What is the likely cause?",
            },
            {
                "role": "assistant",
                "content": "Likely cause: not recorded\nCountermeasure: not recorded",
            },
        ],
        "sources": [_SOURCE],
    }
    path = tmp_path / "incomplete.jsonl"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    report = evaluate_dataset(path, "chat")

    assert report["findings"][0]["code"] == "incomplete_failure_answer"
    assert report["findings"][0]["affected_count"] == 1


def test_evaluate_counts_invalid_json_and_invalid_record_shapes(tmp_path):
    path = tmp_path / "invalid.jsonl"
    path.write_text("{}\nnot json\n[]\n", encoding="utf-8")

    report = evaluate_dataset(path, "cot")

    assert report["invalid_records"] == 3
    assert {finding["code"] for finding in report["findings"]} == {
        "invalid_format_or_provenance",
        "invalid_jsonl",
        "invalid_record",
    }


def test_evaluate_rejects_unknown_format_and_has_reproducible_counts(tmp_path, corpus):
    records = build_cot_records(corpus, limit=2)
    path = tmp_path / "cot.jsonl"
    write_jsonl(records, path)

    with pytest.raises(ValueError, match="Unsupported dataset format"):
        evaluate_dataset(path, "unknown")

    first = evaluate_dataset(path, "cot")
    second = evaluate_dataset(path, "cot")
    assert first == second
