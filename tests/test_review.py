"""Offline expert-review workflow tests."""

from __future__ import annotations

import json

import pytest

from purestrata import (
    approved_records,
    build_chat_records,
    build_cot_records,
    build_tool_trace_records,
    create_review_bundle,
    decide_review,
    get_review_entry,
    list_review_queue,
    write_review_bundle,
)


def test_review_bundle_starts_pending_and_has_stable_ids(corpus):
    records = build_cot_records(corpus, limit=2)
    first = create_review_bundle("cot", records)
    second = create_review_bundle("cot", records)

    assert [entry["review_id"] for entry in first] == [entry["review_id"] for entry in second]
    assert all(entry["status"] == "pending" for entry in first)
    assert all(entry["record"]["sources"] for entry in first)
    assert all(entry["review"]["decided_at"] is None for entry in first)


def test_review_list_and_show_return_source_attribution(tmp_path, corpus):
    records = build_cot_records(corpus, limit=1)
    bundle_path = write_review_bundle(
        create_review_bundle("cot", records), tmp_path / "review.jsonl"
    )
    queue = list_review_queue(bundle_path)
    review_id = queue[0]["review_id"]

    assert queue[0]["status"] == "pending"
    assert queue[0]["sources"] == records[0]["sources"]
    assert "record" not in queue[0]
    assert get_review_entry(bundle_path, review_id)["record"] == records[0]


def test_review_bundle_accepts_all_export_formats(corpus):
    format_records = {
        "chat": build_chat_records(corpus, limit=1),
        "tool_trace": build_tool_trace_records(corpus, limit=1),
        "cot": build_cot_records(corpus, limit=1),
    }

    for format_name, records in format_records.items():
        assert create_review_bundle(format_name, records)[0]["format"] == format_name


def test_approved_export_includes_only_approved_records(tmp_path, corpus):
    records = build_cot_records(corpus, limit=3)
    bundle_path = write_review_bundle(
        create_review_bundle("cot", records), tmp_path / "review.jsonl"
    )
    bundle = [json.loads(line) for line in bundle_path.read_text(encoding="utf-8").splitlines()]

    decide_review(
        bundle_path,
        bundle[0]["review_id"],
        "approved",
        reviewer="maintenance-reviewer",
        notes="Cause and action checked against the work order.",
    )
    decide_review(
        bundle_path,
        bundle[1]["review_id"],
        "rejected",
        reviewer="maintenance-reviewer",
        notes="Insufficient evidence.",
    )

    approved = approved_records(bundle_path)
    assert approved == [records[0]]
    updated = [json.loads(line) for line in bundle_path.read_text(encoding="utf-8").splitlines()]
    approved_entry = next(
        entry for entry in updated if entry["review_id"] == bundle[0]["review_id"]
    )
    assert approved_entry["review"]["reviewer"] == "maintenance-reviewer"
    assert approved_entry["review"]["notes"] == "Cause and action checked against the work order."
    assert approved_entry["review"]["decided_at"]


def test_reviewed_replacement_preserves_provenance(tmp_path, corpus):
    record = build_cot_records(corpus, limit=1)[0]
    bundle_path = write_review_bundle(
        create_review_bundle("cot", [record]), tmp_path / "review.jsonl"
    )
    entry = json.loads(bundle_path.read_text(encoding="utf-8"))
    replacement = dict(record, output="Reviewed answer.")
    replacement_path = tmp_path / "replacement.json"
    replacement_path.write_text(json.dumps(replacement), encoding="utf-8")

    decide_review(
        bundle_path,
        entry["review_id"],
        "approved",
        reviewer="maintenance-reviewer",
        replacement_record_path=replacement_path,
    )

    approved = approved_records(bundle_path)
    assert approved[0]["output"] == "Reviewed answer."
    assert approved[0]["sources"] == record["sources"]


def test_replacement_cannot_change_provenance(tmp_path, corpus):
    record = build_cot_records(corpus, limit=1)[0]
    bundle_path = write_review_bundle(
        create_review_bundle("cot", [record]), tmp_path / "review.jsonl"
    )
    entry = json.loads(bundle_path.read_text(encoding="utf-8"))
    replacement = dict(record, sources=[])
    replacement_path = tmp_path / "replacement.json"
    replacement_path.write_text(json.dumps(replacement), encoding="utf-8")

    with pytest.raises(ValueError, match="preserve the sample's source provenance"):
        decide_review(
            bundle_path,
            entry["review_id"],
            "approved",
            reviewer="maintenance-reviewer",
            replacement_record_path=replacement_path,
        )


def test_approved_export_detects_unreviewed_payload_edits(tmp_path, corpus):
    record = build_cot_records(corpus, limit=1)[0]
    bundle_path = write_review_bundle(
        create_review_bundle("cot", [record]), tmp_path / "review.jsonl"
    )
    entry = json.loads(bundle_path.read_text(encoding="utf-8"))
    entry["record"]["output"] = "Edited without a review decision."
    bundle_path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="modified without a review decision"):
        approved_records(bundle_path)


def test_review_validation_rejects_invalid_records(corpus):
    with pytest.raises(ValueError, match="Unsupported review format"):
        create_review_bundle("unknown", [])
    with pytest.raises(ValueError, match="sources list"):
        create_review_bundle("chat", [{"messages": []}])


def test_final_review_decision_requires_reviewer(tmp_path, corpus):
    record = build_cot_records(corpus, limit=1)[0]
    bundle_path = write_review_bundle(
        create_review_bundle("cot", [record]), tmp_path / "review.jsonl"
    )
    entry = json.loads(bundle_path.read_text(encoding="utf-8"))

    with pytest.raises(ValueError, match="reviewer is required"):
        decide_review(bundle_path, entry["review_id"], "approved")
