"""Offline review bundles for fine-tuning records.

Integrity model: every entry carries a SHA-256 hash of its record and of
its review state (status, reviewer, notes, timestamp), so accidental
corruption and partial hand edits are detected on load, and approvals
without a reviewer decision are refused at export time. The hashes are
unkeyed and stored next to the data, so they do not stop a deliberate
attacker who can rewrite the file and recompute them. Where that threat
matters, protect the bundle with filesystem permissions or an external
signature/manifest.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from ._io import write_lines_atomic

REVIEW_STATUSES = {"pending", "approved", "rejected"}
REVIEW_FORMATS = {"chat", "tool_trace", "cot"}


def _record_sha256(record: dict) -> str:
    payload = json.dumps(
        record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _entry_state_sha256(entry: dict) -> str:
    """Hash the review state (record + status + review) of one entry."""
    payload = json.dumps(
        {
            "record": entry["record"],
            "status": entry["status"],
            "review": entry.get("review"),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_record(format_name: str, record: dict) -> None:
    sources = record.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("Review record must have a non-empty sources list.")
    if any(
        not isinstance(source, dict)
        or not all(source.get(field) for field in ("doc_id", "source_path", "locator"))
        for source in sources
    ):
        raise ValueError("Each review source must include doc_id, source_path, and locator.")
    if format_name in {"chat", "tool_trace"}:
        messages = record.get("messages")
        expected_roles = (
            ["system", "user", "assistant"]
            if format_name == "chat"
            else ["system", "user", "assistant", "tool", "assistant"]
        )
        if (
            not isinstance(messages, list)
            or [message.get("role") if isinstance(message, dict) else None for message in messages]
            != expected_roles
        ):
            raise ValueError(f"Review record does not match the {format_name} message format.")
    elif not all(
        isinstance(record.get(field), str) for field in ("instruction", "reasoning", "output")
    ):
        raise ValueError("Review record does not match the cot format.")


def create_review_bundle(format_name: str, records: list[dict]) -> list[dict]:
    """Wrap provider-format records in a local, pending review envelope."""
    if format_name not in REVIEW_FORMATS:
        raise ValueError(f"Unsupported review format: {format_name}")

    bundle = []
    occurrences: dict[str, int] = {}
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise ValueError(f"Record {index} must be an object.")
        _validate_record(format_name, record)
        record_hash = _record_sha256(record)
        occurrences[record_hash] = occurrences.get(record_hash, 0) + 1
        review_id = hashlib.sha256(
            f"{format_name}:{record_hash}:{occurrences[record_hash]}".encode()
        ).hexdigest()[:24]
        bundle_entry = {
            "review_id": review_id,
            "format": format_name,
            "status": "pending",
            "record_sha256": record_hash,
            "record": record,
            "review": {"reviewer": None, "notes": None, "decided_at": None},
        }
        bundle_entry["state_sha256"] = _entry_state_sha256(bundle_entry)
        bundle.append(bundle_entry)
    return bundle


def _load_review_bundle(bundle_path: str | Path) -> list[dict]:
    path = Path(bundle_path)
    entries = []
    seen_ids = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid review bundle JSON on line {line_number}: {exc}") from exc
        if not isinstance(entry, dict):
            raise ValueError(f"Review bundle line {line_number} must be a JSON object.")
        review_id = entry.get("review_id")
        if not isinstance(review_id, str) or not review_id:
            raise ValueError(f"Review bundle line {line_number} has no review_id.")
        if review_id in seen_ids:
            raise ValueError(f"Duplicate review_id in bundle: {review_id}")
        if entry.get("format") not in REVIEW_FORMATS:
            raise ValueError(f"Unsupported review format on line {line_number}.")
        if entry.get("status") not in REVIEW_STATUSES:
            raise ValueError(f"Unsupported review status on line {line_number}.")
        if not isinstance(entry.get("record"), dict) or not isinstance(
            entry["record"].get("sources"), list
        ):
            raise ValueError(f"Review bundle line {line_number} has no record sources.")
        seen_ids.add(review_id)
        _validate_record(entry["format"], entry["record"])
        entries.append(entry)
    return entries


def list_review_queue(bundle_path: str | Path) -> list[dict]:
    """Return review IDs, statuses, and sources without expanding record payloads."""
    entries = _load_review_bundle(bundle_path)
    for entry in entries:
        _verify_record_integrity(entry)
    return [
        {
            "review_id": entry["review_id"],
            "format": entry["format"],
            "status": entry["status"],
            "sources": entry["record"]["sources"],
            "review": entry.get("review", {}),
        }
        for entry in entries
    ]


def get_review_entry(bundle_path: str | Path, review_id: str) -> dict:
    """Return one complete review entry by its stable ID."""
    entries = _load_review_bundle(bundle_path)
    entry = next((item for item in entries if item["review_id"] == review_id), None)
    if entry is None:
        raise ValueError(f"Review sample not found: {review_id}")
    _verify_record_integrity(entry)
    return entry


def _verify_record_integrity(entry: dict) -> None:
    if entry.get("record_sha256") != _record_sha256(entry["record"]):
        raise ValueError(
            f"Review record {entry['review_id']} was modified without a review decision."
        )
    state_hash = entry.get("state_sha256")
    if state_hash is not None and state_hash != _entry_state_sha256(entry):
        raise ValueError(
            f"Review state of {entry['review_id']} was modified outside decide_review."
        )


def write_review_bundle(bundle: list[dict], out_path: str | Path) -> Path:
    """Write a review bundle as UTF-8 JSONL."""
    path = Path(out_path)
    lines = [json.dumps(entry, ensure_ascii=False, default=str) for entry in bundle]
    write_lines_atomic(path, lines)
    return path


def decide_review(
    bundle_path: str | Path,
    review_id: str,
    status: str,
    *,
    reviewer: str | None = None,
    notes: str | None = None,
    replacement_record_path: str | Path | None = None,
) -> Path:
    """Set one sample's review status, notes, reviewer, or reviewed payload."""
    if status not in REVIEW_STATUSES:
        raise ValueError(f"Unsupported review status: {status}")
    path = Path(bundle_path)
    entries = _load_review_bundle(path)
    target = next((entry for entry in entries if entry["review_id"] == review_id), None)
    if target is None:
        raise ValueError(f"Review sample not found: {review_id}")
    existing_reviewer = (target.get("review") or {}).get("reviewer")
    if status != "pending" and not (reviewer or existing_reviewer):
        raise ValueError("A reviewer is required to approve or reject a sample.")

    if replacement_record_path is not None:
        replacement = json.loads(Path(replacement_record_path).read_text(encoding="utf-8"))
        if not isinstance(replacement, dict):
            raise ValueError("Replacement record must be a JSON object.")
        if replacement.get("sources") != target["record"]["sources"]:
            raise ValueError("Replacement record must preserve the sample's source provenance.")
        _validate_record(target["format"], replacement)
        target["record"] = replacement
        target["record_sha256"] = _record_sha256(replacement)
    else:
        _verify_record_integrity(target)

    target["status"] = status
    review = target.setdefault("review", {})
    if reviewer is not None:
        review["reviewer"] = reviewer
    if notes is not None:
        review["notes"] = notes
    review["decided_at"] = datetime.now(timezone.utc).isoformat()
    target["state_sha256"] = _entry_state_sha256(target)
    write_review_bundle(entries, path)
    return path


def approved_records(bundle_path: str | Path) -> list[dict]:
    """Return only approved provider-format records after checking integrity."""
    records = []
    for entry in _load_review_bundle(bundle_path):
        _verify_record_integrity(entry)
        if entry["status"] != "approved":
            continue
        # Re-apply the approval rule on read: decide_review requires a
        # reviewer, and a hand-edited file must not be able to skip that.
        review = entry.get("review") or {}
        if not review.get("reviewer") or not review.get("decided_at"):
            raise ValueError(
                f"Approved review {entry['review_id']} has no reviewer decision on record."
            )
        records.append(entry["record"])
    return records
