"""MCP server: expose a PureStrata corpus to any MCP client.

Run ``purestrata serve --corpus <dir>`` and register the command in any
Model Context Protocol client (Claude Desktop, IDE agents, and other MCP
hosts). The server speaks JSON over stdio; every tool result embeds
provenance so answers stay auditable.

Requires the optional ``mcp`` extra: ``pip install 'purestrata[mcp]'``.
"""

from __future__ import annotations

import json
from pathlib import Path

from .corpus import Corpus
from .tools.executor import ToolError, ToolExecutor


def build_mcp_server(corpus: Corpus):
    """Build an MCP server bound to a corpus."""
    mcp_cls = None
    try:  # mcp 1.x
        from mcp.server.fastmcp import FastMCP as mcp_cls  # type: ignore[no-redef]
    except ImportError:
        try:  # mcp 2.x renamed FastMCP to MCPServer
            from mcp.server.mcpserver import MCPServer as mcp_cls  # type: ignore[no-redef]
        except ImportError as exc:
            raise RuntimeError(
                "The MCP server requires the 'mcp' extra. "
                "Install it with: pip install 'purestrata[mcp]'"
            ) from exc

    mcp = mcp_cls("purestrata")
    executor = ToolExecutor(corpus)

    def run(name: str, **kwargs) -> str:
        clean = {key: value for key, value in kwargs.items() if value is not None}
        try:
            return json.dumps(executor.execute(name, clean), ensure_ascii=False, default=str)
        except ToolError as exc:
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

    @mcp.tool()
    def list_corpus() -> str:
        """Corpus inventory: total records, counts by kind, and loaded documents."""
        return run("list_corpus")

    @mcp.tool()
    def search_documents(query: str, kind: str | None = None, top_k: int = 5) -> str:
        """Search spec sheets and manuals. Returns ranked passages with provenance."""
        return run("search_documents", query=query, kind=kind, top_k=top_k)

    @mcp.tool()
    def get_safety_notices(query: str | None = None, top_k: int = 10) -> str:
        """Safety warnings and cautions, optionally ranked by a query."""
        return run("get_safety_notices", query=query, top_k=top_k)

    @mcp.tool()
    def get_procedure(procedure_id: str) -> str:
        """Full ordered steps of a maintenance procedure by its ID."""
        return run("get_procedure", procedure_id=procedure_id)

    @mcp.tool()
    def search_parts(query: str | None = None, top_k: int = 10) -> str:
        """Parts lookup: part number, name, quantity, spec."""
        return run("search_parts", query=query, top_k=top_k)

    @mcp.tool()
    def list_drawings() -> str:
        """CAD drawings in the corpus, with identifiers and layers."""
        return run("list_drawings")

    @mcp.tool()
    def get_drawing(drawing_id: str) -> str:
        """Full metadata of one CAD drawing: title block, layers, entities, bounds."""
        return run("get_drawing", drawing_id=drawing_id)

    @mcp.tool()
    def search_drawings(
        query: str | None = None,
        min_diameter: float | None = None,
        max_diameter: float | None = None,
        fit: str | None = None,
        material: str | None = None,
        cad_format: str | None = None,
        top_k: int = 10,
    ) -> str:
        """Find DXF drawings and STEP models by hole diameter (mm), fit class, material, format."""
        return run(
            "search_drawings",
            query=query,
            min_diameter=min_diameter,
            max_diameter=max_diameter,
            fit=fit,
            material=material,
            cad_format=cad_format,
            top_k=top_k,
        )

    @mcp.tool()
    def search_failure_cases(query: str, equipment: str | None = None, top_k: int = 5) -> str:
        """Search past failures: symptom, root cause, countermeasure. Use for troubleshooting."""
        return run("search_failure_cases", query=query, equipment=equipment, top_k=top_k)

    @mcp.tool()
    def get_failure_case(case_id: str) -> str:
        """One full failure case by its case_id."""
        return run("get_failure_case", case_id=case_id)

    return mcp


def serve(corpus_dir: str | Path) -> None:
    """Load a corpus directory and run the MCP server over stdio."""
    corpus = Corpus.load(corpus_dir)
    mcp = build_mcp_server(corpus)
    mcp.run()
