"""Offline structural and coverage checks for fine-tuning JSONL datasets."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

DATASET_FORMATS = {"chat", "tool_trace", "cot"}
_MAX_EXAMPLES_PER_FINDING = 100
_MISSING_VALUE_RE = re.compile(r"^(?:not recorded|unspecified|unknown|n/?a|none|—|-)?$", re.I)


def _sample_summary(line_number: int, record: dict | None) -> dict:
    sources = record.get("sources", []) if isinstance(record, dict) else []
    safe_sources = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        safe_sources.append(
            {
                key: source[key]
                for key in ("doc_id", "chunk_id", "record_kind", "source_path", "locator")
                if source.get(key) is not None
            }
        )
    sample_id = next(
        (source.get("chunk_id") for source in safe_sources if source.get("chunk_id")),
        f"line-{line_number}",
    )
    return {"sample_id": sample_id, "line": line_number, "sources": safe_sources}


def _record_shape_error(format_name: str, record: dict) -> str | None:
    if not isinstance(record.get("sources"), list) or not record["sources"]:
        return "record must include a non-empty sources list"
    for source in record["sources"]:
        if not isinstance(source, dict) or not all(
            source.get(field) for field in ("doc_id", "source_path", "locator")
        ):
            return "each source must include doc_id, source_path, and locator"
    if format_name in {"chat", "tool_trace"}:
        messages = record.get("messages")
        roles = (
            ["system", "user", "assistant"]
            if format_name == "chat"
            else ["system", "user", "assistant", "tool", "assistant"]
        )
        if (
            not isinstance(messages, list)
            or [message.get("role") if isinstance(message, dict) else None for message in messages]
            != roles
        ):
            return f"record does not match the {format_name} message format"
    elif not all(
        isinstance(record.get(field), str) for field in ("instruction", "reasoning", "output")
    ):
        return "record does not match the cot format"
    return None


def _answer_text(format_name: str, record: dict) -> str:
    if format_name == "cot":
        return record.get("output", "")
    messages = record.get("messages") or []
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "assistant":
            content = message.get("content")
            return content if isinstance(content, str) else ""
    return ""


def evaluate_dataset(input_path: str | Path, format_name: str) -> dict:
    """Evaluate dataset structure, source provenance, completeness, and coverage."""
    if format_name not in DATASET_FORMATS:
        raise ValueError(f"Unsupported dataset format: {format_name}")

    path = Path(input_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    findings: dict[str, dict] = {}
    source_counts: Counter[str] = Counter()
    kind_counts: Counter[str] = Counter()
    seen_records: dict[str, tuple[int, dict]] = {}
    valid_record_count = 0
    duplicate_count = 0

    def add_finding(
        code: str,
        severity: str,
        message: str,
        line_number: int,
        record: dict | None,
    ) -> None:
        finding = findings.setdefault(
            code,
            {
                "code": code,
                "severity": severity,
                "message": message,
                "affected_count": 0,
                "examples": [],
            },
        )
        finding["affected_count"] += 1
        if len(finding["examples"]) < _MAX_EXAMPLES_PER_FINDING:
            finding["examples"].append(_sample_summary(line_number, record))

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            add_finding(
                "invalid_jsonl",
                "error",
                "line is not valid JSON",
                line_number,
                None,
            )
            continue
        if not isinstance(record, dict):
            add_finding(
                "invalid_record",
                "error",
                "record must be a JSON object",
                line_number,
                None,
            )
            continue

        shape_error = _record_shape_error(format_name, record)
        if shape_error:
            add_finding(
                "invalid_format_or_provenance",
                "error",
                shape_error,
                line_number,
                record,
            )
            continue
        valid_record_count += 1

        for source in record["sources"]:
            source_counts[str(source.get("source_path", "unknown"))] += 1
            kind_counts[str(source.get("record_kind", "unknown"))] += 1

        canonical = json.dumps(
            record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
        )
        fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
        if fingerprint in seen_records:
            duplicate_count += 1
            first_line, first_record = seen_records[fingerprint]
            add_finding(
                "exact_duplicate",
                "warning",
                "record exactly duplicates another dataset record",
                first_line,
                first_record,
            )
            add_finding(
                "exact_duplicate",
                "warning",
                "record exactly duplicates another dataset record",
                line_number,
                record,
            )
        else:
            seen_records[fingerprint] = (line_number, record)

        answer = _answer_text(format_name, record)
        user_content = " ".join(
            message.get("content", "")
            for message in record.get("messages", [])
            if isinstance(message, dict)
            and message.get("role") == "user"
            and isinstance(message.get("content"), str)
        )
        is_failure_sample = (
            format_name == "cot"
            or any(source.get("record_kind") == "failure_case" for source in record["sources"])
            or "troubleshooting a problem" in user_content
        )
        if is_failure_sample:
            missing_fields = []
            for label, pattern in (
                ("cause", r"(?im)^\s*Likely cause\s*:\s*(.*?)\s*$"),
                ("countermeasure", r"(?im)^\s*Countermeasure\s*:\s*(.*?)\s*$"),
            ):
                match = re.search(pattern, answer)
                if match is None or _MISSING_VALUE_RE.fullmatch(match.group(1).strip()):
                    missing_fields.append(label)
            if missing_fields:
                add_finding(
                    "incomplete_failure_answer",
                    "warning",
                    "answer has missing or placeholder failure fields: "
                    + ", ".join(missing_fields),
                    line_number,
                    record,
                )

    return {
        "format": format_name,
        "input": str(path),
        "total_lines": len(lines),
        "valid_records": valid_record_count,
        "invalid_records": sum(
            finding["affected_count"]
            for code, finding in findings.items()
            if finding["severity"] == "error"
        ),
        "exact_duplicate_excess": duplicate_count,
        "record_kind_coverage": dict(sorted(kind_counts.items())),
        "source_coverage": dict(sorted(source_counts.items())),
        "findings": list(findings.values()),
    }


def format_evaluation_summary(report: dict) -> str:
    """Render a concise human-readable summary without record contents."""
    lines = [
        f"Dataset evaluation ({report['format']}): {report['input']}",
        (
            f"Records: {report['valid_records']} valid / "
            f"{report['total_lines']} lines; "
            f"{report['invalid_records']} invalid; "
            f"{report['exact_duplicate_excess']} exact duplicates"
        ),
        "Record kinds: "
        + (
            ", ".join(f"{kind}={count}" for kind, count in report["record_kind_coverage"].items())
            or "none"
        ),
        f"Source files: {len(report['source_coverage'])}",
    ]
    if report["findings"]:
        lines.append("Findings:")
        lines.extend(
            f"- {finding['severity']}: {finding['code']} "
            f"({finding['affected_count']} affected): {finding['message']}"
            for finding in report["findings"]
        )
    else:
        lines.append("Findings: none")
    return "\n".join(lines)
