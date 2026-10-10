"""Fine-tuning dataset export tests."""

from __future__ import annotations

import json

from purestrata import build_chat_records, build_cot_records, build_tool_trace_records, write_jsonl


def test_chat_records_shape(corpus):
    records = build_chat_records(corpus)
    assert len(records) == 16  # 8 failure cases + 2 procedures + 6 safety notices
    for record in records:
        roles = [m["role"] for m in record["messages"]]
        assert roles == ["system", "user", "assistant"]
        assert record["sources"]
        assert record["sources"][0]["source_path"]


def test_chat_record_content_is_grounded(corpus):
    records = build_chat_records(corpus)
    failures = [r for r in records if "troubleshooting" in r["messages"][1]["content"]]
    assert failures
    for record in failures:
        answer = record["messages"][2]["content"]
        assert "Likely cause:" in answer
        assert "Countermeasure:" in answer
        assert "Source:" in answer


def test_tool_trace_records(corpus):
    records = build_tool_trace_records(corpus)
    assert len(records) == 8
    for record in records:
        messages = record["messages"]
        assert [m["role"] for m in messages] == ["system", "user", "assistant", "tool", "assistant"]
        call = messages[2]["tool_calls"][0]
        assert call["function"]["name"] == "search_failure_cases"
        args = json.loads(call["function"]["arguments"])
        assert args["query"]
        tool_result = json.loads(messages[3]["content"])
        assert tool_result["results"]
        assert "Source:" in messages[4]["content"]


def test_cot_records(corpus):
    records = build_cot_records(corpus)
    assert len(records) == 8
    for record in records:
        assert set(record) == {"instruction", "reasoning", "output", "sources"}
        assert "matches" in record["reasoning"]
        assert record["sources"][0]["locator"]


def test_limit_applied(corpus):
    assert len(build_cot_records(corpus, limit=3)) == 3
    assert len(build_chat_records(corpus, limit=2)) == 2


def test_write_jsonl_roundtrip(corpus, tmp_path):
    records = build_cot_records(corpus, limit=2)
    out = write_jsonl(records, tmp_path / "sub" / "dataset.jsonl")
    assert out.exists()
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["instruction"] == records[0]["instruction"]


def test_write_jsonl_leaves_no_partial_or_temp_files(corpus, tmp_path):
    records = build_cot_records(corpus, limit=2)
    out = write_jsonl(records, tmp_path / "dataset.jsonl")
    assert [path.name for path in tmp_path.iterdir()] == ["dataset.jsonl"]
    loaded = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert loaded == [json.loads(json.dumps(record, default=str)) for record in records]
