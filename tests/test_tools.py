"""Tool executor tests."""

from __future__ import annotations

import pytest

from purestrata import ToolError, ToolExecutor
from purestrata.tools import TOOLS, openai_tools


@pytest.fixture
def executor(corpus):
    return ToolExecutor(corpus)


def test_nine_tools_defined():
    assert len(TOOLS) == 9
    assert len(openai_tools()) == 9


def test_list_corpus(executor, corpus):
    result = executor.execute("list_corpus")
    stats = corpus.stats()
    assert result["total_chunks"] == stats["total_chunks"]
    assert result["by_kind"]["failure_case"] == 8
    assert len(result["documents"]) == 4


def test_search_documents_with_sources(executor):
    result = executor.execute("search_documents", {"query": "torque", "top_k": 3})
    assert result["results"]
    for record in result["results"]:
        assert record["source"]["source_path"]
        assert record["source"]["locator"]
        assert "score" in record


def test_search_documents_kind_restriction(executor):
    result = executor.execute(
        "search_documents", {"query": "spindle", "kind": "failure_case", "top_k": 5}
    )
    assert result["results"]
    assert all(record["kind"] == "failure_case" for record in result["results"])


def test_procedure_roundtrip(executor):
    found = executor.execute("search_documents", {"query": "warm-up program", "kind": "procedure"})
    assert found["results"]
    proc = executor.execute("get_procedure", {"procedure_id": found["results"][0]["chunk_id"]})
    assert len(proc["metadata"]["steps"]) == 5
    assert proc["kind"] == "procedure"


def test_safety_notices(executor):
    result = executor.execute("get_safety_notices", {"query": "electrical"})
    assert result["results"]
    assert all(r["kind"] == "safety_notice" for r in result["results"])
    ranked = result["results"][0]
    assert "power" in ranked["text"].lower()


def test_parts_lookup(executor):
    result = executor.execute("search_parts", {"query": "spindle cartridge", "top_k": 5})
    assert any("SP-4412" in r["text"] for r in result["results"])


def test_list_drawings_and_get_drawing(executor):
    listed = executor.execute("list_drawings")
    assert [r["drawing_id"] for r in listed["results"]] == ["BRK-0042-A"]
    detail = executor.execute("get_drawing", {"drawing_id": "BRK-0042-A"})
    assert detail["metadata"]["title_block"]["material"] == "SS400"
    assert detail["metadata"]["units"] == "mm"
    assert detail["metadata"]["entity_counts"]["TEXT"] == 6


def test_failure_case_search_with_equipment_filter(executor):
    result = executor.execute(
        "search_failure_cases",
        {"query": "vibration", "equipment": "CNC SERVO PRESS PP-220", "top_k": 5},
    )
    assert result["results"]
    for record in result["results"]:
        assert "CNC SERVO PRESS PP-220" in record["metadata"]["equipment"]


def test_failure_case_by_equipment_only(executor):
    result = executor.execute("search_failure_cases", {"equipment": "MILLING CENTER MV-5"})
    assert len(result["results"]) == 1
    assert "PC-04" in result["results"][0]["metadata"]["symptom"]


def test_get_failure_case_by_case_id(executor):
    result = executor.execute("get_failure_case", {"case_id": "plant_failures-c003"})
    assert result["metadata"]["severity"] == "critical"
    assert "BK-2207" in result["metadata"]["part_number"]


def test_missing_record_raises(executor):
    with pytest.raises(ToolError):
        executor.execute("get_failure_case", {"case_id": "no-such-case"})


def test_unknown_tool_raises(executor):
    with pytest.raises(ToolError):
        executor.execute("not_a_tool", {})


def test_empty_query_raises(executor):
    with pytest.raises(ToolError):
        executor.execute("search_documents", {"query": ""})
