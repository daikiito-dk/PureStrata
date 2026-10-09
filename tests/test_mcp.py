"""MCP server tests (skipped when the mcp extra is not installed)."""

from __future__ import annotations

import pytest


def _extract_text(result) -> str:
    """Extract tool text across MCP SDK versions (v1 lists, v2 result objects)."""
    content = getattr(result, "content", None)
    if content is not None:
        parts = [getattr(block, "text", None) or str(block) for block in content]
        return "".join(part for part in parts if part)
    if isinstance(result, (list, tuple)):
        return "".join(getattr(block, "text", None) or str(block) for block in result)
    return getattr(result, "text", None) or str(result)


def test_mcp_server_lists_all_tools(corpus):
    pytest.importorskip("mcp")
    import anyio

    from purestrata.mcp_server import build_mcp_server

    server = build_mcp_server(corpus)
    tools = anyio.run(server.list_tools)
    names = {tool.name for tool in tools}
    assert len(names) == 9
    assert "search_failure_cases" in names
    assert "get_drawing" in names


def test_mcp_tool_call_returns_json_with_provenance(corpus):
    pytest.importorskip("mcp")
    import json

    import anyio

    from purestrata.mcp_server import build_mcp_server

    server = build_mcp_server(corpus)
    result = anyio.run(server.call_tool, "search_failure_cases", {"query": "vibration", "top_k": 2})
    payload = json.loads(_extract_text(result))
    assert payload["results"]
    for record in payload["results"]:
        assert record["source"]["source_path"]


def test_mcp_tool_error_is_json_error(corpus):
    pytest.importorskip("mcp")
    import json

    import anyio

    from purestrata.mcp_server import build_mcp_server

    server = build_mcp_server(corpus)
    result = anyio.run(server.call_tool, "get_failure_case", {"case_id": "does-not-exist"})
    payload = json.loads(_extract_text(result))
    assert "error" in payload
