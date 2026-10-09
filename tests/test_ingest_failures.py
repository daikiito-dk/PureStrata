"""Failure log (CSV/JSONL) ingestion tests."""

from __future__ import annotations

import json

from purestrata import ingest_failures


def test_all_rows_ingested(failures_csv):
    chunks = ingest_failures(failures_csv)
    assert len(chunks) == 8
    assert all(chunk.kind == "failure_case" for chunk in chunks)


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
