"""Failure log (CSV/JSONL) ingestion tests."""

from __future__ import annotations

import json

import pytest

from purestrata import ingest_failures


def test_all_rows_ingested(failures_csv):
    chunks = ingest_failures(failures_csv)
    assert len(chunks) == 8
    assert all(chunk.kind == "failure_case" for chunk in chunks)


def test_malformed_jsonl_lines_are_skipped(tmp_path):
    path = tmp_path / "failures.jsonl"
    path.write_text(
        "[1, 2, 3]\n"
        '{"case_id": "C-1", "equipment": "Press", "symptom": "oil leak"}\n'
        "{broken json\n",
        encoding="utf-8",
    )
    chunks = ingest_failures(path)
    assert len(chunks) == 1
    assert chunks[0].metadata["case_id"] == "C-1"


def test_csv_field_overflow_is_a_graceful_error(tmp_path):
    path = tmp_path / "failures.csv"
    path.write_text(
        "case_id,symptom\nC-1," + "x" * (200 * 1024) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Could not parse CSV"):
        ingest_failures(path)


def test_ids_and_severity(failures_csv):
    chunks = ingest_failures(failures_csv)
    by_row = {chunk.metadata["source_row"]: chunk for chunk in chunks}
    assert by_row[1].metadata["case_id"] == "plant_failures-c001"
    assert by_row[3].metadata["severity"] == "critical"
    assert by_row[2].metadata["severity"] == "medium"
    assert by_row[7].metadata.get("part_number") is None
    assert by_row[3].metadata["part_number"] == "BK-2207"
    assert by_row[1].metadata["tags"] == ["spindle", "vibration"]


def test_japanese_row_preserved(failures_csv):
    chunks = ingest_failures(failures_csv)
    ja = next(chunk for chunk in chunks if "ブレーキ停止時間" in chunk.text)
    assert "ゲートドライバ" in ja.metadata["cause"]
    assert "フィルタ" in ja.metadata["countermeasure"]
    assert "brake" in ja.metadata["tags"]


def test_reported_at_mapped(failures_csv):
    chunks = ingest_failures(failures_csv)
    assert all(chunk.metadata.get("reported_at") for chunk in chunks)


def test_jsonl_input(tmp_path, failures_csv):
    import csv

    with open(failures_csv, encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    jsonl = tmp_path / "failures.jsonl"
    with open(jsonl, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    chunks = ingest_failures(jsonl)
    assert len(chunks) == 8
    assert {c.metadata["severity"] for c in chunks} >= {"low", "medium", "high", "critical"}
