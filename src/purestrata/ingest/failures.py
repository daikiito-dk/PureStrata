"""Ingest failure logs (CSV / JSONL) into failure-case chunks.

Factory failure knowledge usually lives in spreadsheets: one row per
incident with the symptom, the investigated cause, and the
countermeasure. This adapter accepts flexible column names in English or
Japanese and turns each row into a structured, searchable failure case.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from ..pipeline.clean import clean_inline
from ..types import FAILURE_CASE, Chunk, Provenance, derive_doc_id, new_chunk, sha256_file

_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "case_id": ("case_id", "id", "case", "no", "case_no", "件番", "ケース番号", "管理番号"),
    "equipment": ("equipment", "machine", "asset", "設備", "機械", "装置", "対象設備"),
    "part_number": ("part_number", "part_no", "part", "品番", "部品番号", "図番"),
    "symptom": ("symptom", "failure", "problem", "fault", "現象", "症状", "不具合内容", "故障"),
    "cause": ("cause", "root_cause", "原因", "真因"),
    "countermeasure": ("countermeasure", "action", "fix", "remedy", "対策", "処置"),
    "severity": ("severity", "level", "impact", "重要度", "深刻度", "レベル"),
    "reported_at": ("date", "reported_at", "report_date", "報告日", "発生日", "日付"),
    "status": ("status", "state", "状況", "ステータス"),
    "tags": ("tags", "keywords", "タグ", "キーワード"),
}

_SEVERITY_MAP = {
    "low": "low",
    "minor": "low",
    "低": "low",
    "軽": "low",
    "medium": "medium",
    "moderate": "medium",
    "中": "medium",
    "high": "high",
    "major": "high",
    "高": "high",
    "critical": "critical",
    "severe": "critical",
    "重大": "critical",
}

_TAG_SPLIT_RE = re.compile(r"[;,、|/]+")


def _norm_header(name: str) -> str:
    return re.sub(r"[\s\-.]+", "_", clean_inline(name).casefold()).strip("_")


def _field_map(headers: list[str]) -> dict[str, str]:
    """Map canonical field names to the input file's column names."""
    mapping: dict[str, str] = {}
    for header in headers:
        norm = _norm_header(header)
        for field, aliases in _COLUMN_ALIASES.items():
            if norm in aliases and field not in mapping:
                mapping[field] = header
    return mapping


def _read_rows(path: Path) -> list[dict]:
    if path.suffix.lower() == ".jsonl":
        rows = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _norm_severity(raw: str) -> str:
    key = raw.casefold().strip()
    return _SEVERITY_MAP.get(key, "unspecified") if key else "unspecified"


def _value(row: dict, mapping: dict[str, str], field_name: str) -> str:
    column = mapping.get(field_name)
    if not column:
        return ""
    return clean_inline(str(row.get(column) or ""))


def ingest_failures(path: str | Path, doc_id: str | None = None) -> list[Chunk]:
    """Parse a CSV or JSONL failure log into one chunk per incident."""
    path = Path(path)
    source_sha256 = sha256_file(path)
    doc_id = doc_id or derive_doc_id(path)
    chunks: list[Chunk] = []
    for index, row in enumerate(_read_rows(path), start=1):
        mapping = _field_map(list(row.keys()))
        case_id = _value(row, mapping, "case_id") or f"{doc_id}-c{index:03d}"
        equipment = _value(row, mapping, "equipment")
        part_number = _value(row, mapping, "part_number")
        symptom = _value(row, mapping, "symptom")
        cause = _value(row, mapping, "cause")
        countermeasure = _value(row, mapping, "countermeasure")
        severity = _norm_severity(_value(row, mapping, "severity"))
        reported_at = _value(row, mapping, "reported_at")
        status = _value(row, mapping, "status")
        tags = [t.strip() for t in _TAG_SPLIT_RE.split(_value(row, mapping, "tags")) if t.strip()]

        parts = []
        if equipment:
            parts.append(f"Equipment {equipment} shows a failure")
        else:
            parts.append("A failure was reported")
        if symptom:
            parts.append(f"Symptom: {symptom}")
        if part_number:
            parts.append(f"Involved part: {part_number}")
        if cause:
            parts.append(f"Root cause: {cause}")
        if countermeasure:
            parts.append(f"Countermeasure: {countermeasure}")
        parts.append(f"Severity: {severity}")
        if tags:
            parts.append("Tags: " + ", ".join(tags))
        text = ". ".join(parts) + "."

        metadata: dict = {
            "case_id": case_id,
            "equipment": equipment,
            "symptom": symptom,
            "cause": cause,
            "countermeasure": countermeasure,
            "severity": severity,
            "source_row": index,
        }
        if part_number:
            metadata["part_number"] = part_number
        if reported_at:
            metadata["reported_at"] = reported_at
        if status:
            metadata["status"] = status
        if tags:
            metadata["tags"] = tags

        provenance = Provenance(
            doc_id=doc_id,
            source_path=str(path),
            locator=f"row {index}",
            source_sha256=source_sha256,
            anchor={"record": index},
        )
        chunks.append(new_chunk(FAILURE_CASE, text, provenance, metadata))
    return chunks
