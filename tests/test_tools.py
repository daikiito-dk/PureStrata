"""Tool executor tests."""

from __future__ import annotations

import pytest

from purestrata import ToolError, ToolExecutor
from purestrata.tools import TOOLS, openai_tools


@pytest.fixture
def executor(corpus):
    return ToolExecutor(corpus)


def test_ten_tools_defined():
    assert len(TOOLS) == 10
    assert len(openai_tools()) == 10


def test_list_corpus(executor, corpus):
    result = executor.execute("list_corpus")
    stats = corpus.stats()
    assert result["total_chunks"] == stats["total_chunks"]
    assert result["by_kind"]["failure_case"] == 8
    assert len(result["documents"]) == 5


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
    formats = {r["drawing_id"]: r["cad_format"] for r in listed["results"]}
    assert formats == {"BRK-0042-A": "dxf", "BRK-ASSY-01": "step"}
    detail = executor.execute("get_drawing", {"drawing_id": "BRK-0042-A"})
    assert detail["metadata"]["title_block"]["material"] == "SS400"
    assert detail["metadata"]["units"] == "mm"
    assert detail["metadata"]["entity_counts"]["TEXT"] == 6
    model = executor.execute("get_drawing", {"drawing_id": "BRK-ASSY-01"})
    assert model["metadata"]["format"] == "step"


def _ids(result: dict) -> set[str]:
    return {record["drawing_id"] for record in result["results"]}


def test_search_drawings_by_diameter_spans_formats(executor):
    result = executor.execute("search_drawings", {"min_diameter": 24, "max_diameter": 26})
    assert _ids(result) == {"BRK-0042-A", "BRK-ASSY-01"}
    for record in result["results"]:
        assert [f["diameter_mm"] for f in record["matched_features"]] == [25.0]


def test_search_drawings_small_holes_only_in_step(executor):
    result = executor.execute("search_drawings", {"max_diameter": 10})
    assert _ids(result) == {"BRK-ASSY-01"}
    assert result["results"][0]["matched_features"][0]["count"] == 2


def test_search_drawings_by_fit_class(executor):
    result = executor.execute("search_drawings", {"fit": "H7"})
    assert _ids(result) == {"BRK-0042-A"}
    assert result["results"][0]["matched_callouts"][0]["nominal"] == 25.0
    assert executor.execute("search_drawings", {"fit": "h7"})["results"] == []


def test_search_drawings_material_format_and_query(executor):
    assert _ids(executor.execute("search_drawings", {"material": "SS400"})) == {
        "BRK-0042-A",
        "BRK-ASSY-01",
    }
    assert _ids(executor.execute("search_drawings", {"material": "S45C"})) == {"BRK-ASSY-01"}
    assert _ids(executor.execute("search_drawings", {"cad_format": "dxf"})) == {"BRK-0042-A"}
    ranked = executor.execute("search_drawings", {"query": "位置決めピン"})
    assert _ids(ranked) == {"BRK-ASSY-01"}
    assert "score" in ranked["results"][0]


def test_search_drawings_rejects_bad_range(executor):
    with pytest.raises(ToolError):
        executor.execute("search_drawings", {"min_diameter": 30, "max_diameter": 10})
    with pytest.raises(ToolError):
        executor.execute("search_drawings", {"min_diameter": "wide"})


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
