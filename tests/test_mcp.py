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
    from purestrata.tools import TOOLS

    assert {tool.name for tool in tools} == {spec.name for spec in TOOLS}


def test_mcp_search_drawings_tool(corpus):
    pytest.importorskip("mcp")
    import json

    import anyio

    from purestrata.mcp_server import build_mcp_server

    server = build_mcp_server(corpus)
    result = anyio.run(server.call_tool, "search_drawings", {"max_diameter": 10})
    payload = json.loads(_extract_text(result))
    assert [r["drawing_id"] for r in payload["results"]] == ["BRK-ASSY-01"]


def test_mcp_stdio_handshake(tmp_path, step_path, failures_csv):
    """Drive `purestrata serve` the way an MCP client does: JSON-RPC over stdio."""
    pytest.importorskip("mcp")
    import json
    import subprocess
    import sys
    import threading

    from purestrata.cli import main

    corpus_dir = tmp_path / "corpus"
    assert main(["ingest-step", str(step_path), "--out", str(corpus_dir)]) == 0
    assert main(["ingest-failures", str(failures_csv), "--out", str(corpus_dir)]) == 0

    proc = subprocess.Popen(
        [sys.executable, "-m", "purestrata.cli", "serve", "--corpus", str(corpus_dir)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    watchdog = threading.Timer(30, proc.kill)
    watchdog.start()

    def send(message: dict) -> None:
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    def receive(request_id: int) -> dict:
        while True:
            line = proc.stdout.readline()
            assert line, f"server exited early: {proc.stderr.read()}"
            message = json.loads(line)
            if message.get("id") == request_id:
                return message

    try:
        send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "purestrata-test", "version": "0"},
                },
            }
        )
        init = receive(1)
        assert init["result"]["serverInfo"]["name"] == "purestrata"
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = {tool["name"] for tool in receive(2)["result"]["tools"]}
        assert {"search_drawings", "search_failure_cases"} <= names

        send(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "search_drawings", "arguments": {"min_diameter": 20}},
            }
        )
        content = receive(3)["result"]["content"]
        payload = json.loads(content[0]["text"])
        assert payload["results"][0]["drawing_id"] == "BRK-ASSY-01"
    finally:
        watchdog.cancel()
        proc.kill()
        proc.wait()


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
