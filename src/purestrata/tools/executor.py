"""Local execution of PureStrata tools against a loaded corpus.

The executor is the single implementation behind every integration surface:
the MCP server, the Python API, and the CLI all call :class:`ToolExecutor`.
Tool results are plain JSON-serializable dicts and always carry provenance,
so anything a model answers can be audited back to a source locator.
"""

from __future__ import annotations

from typing import Any

from ..corpus import Corpus
from ..types import DRAWING, FAILURE_CASE, PART_RECORD, PROCEDURE, SAFETY_NOTICE, Chunk
from .schemas import tool_by_name


class ToolError(Exception):
    """Raised when a tool call is invalid or the target record is missing."""


def _source(chunk: Chunk) -> dict:
    return chunk.provenance.to_dict()


def _result(chunk: Chunk, score: float | None = None) -> dict:
    record = {
        "chunk_id": chunk.chunk_id,
        "kind": chunk.kind,
        "text": chunk.text,
        "metadata": chunk.metadata,
        "source": _source(chunk),
    }
    if score is not None:
        record["score"] = round(score, 3)
    return record


def _clamp_top_k(value: Any, default: int) -> int:
    try:
        top_k = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(top_k, 50))


def _as_str(value: Any) -> str:
    return str(value).strip() if value is not None else ""


class ToolExecutor:
    """Execute PureStrata tool calls against a corpus."""

    def __init__(self, corpus: Corpus):
        self.corpus = corpus

    def execute(self, name: str, args: dict | None = None) -> dict:
        try:
            tool_by_name(name)
        except KeyError as exc:
            raise ToolError(f"Unknown tool: {name}") from exc
        args = dict(args or {})
        handler = getattr(self, f"_tool_{name}", None)
        if handler is None:
            raise ToolError(f"Tool is defined but not implemented: {name}")
        return handler(args)

    # -- helpers ---------------------------------------------------------

    def _find_by_id(self, value: str, kind: str | None = None) -> Chunk:
        needle = value.casefold()
        for chunk in self.corpus.chunks:
            if chunk.chunk_id.casefold() == needle:
                if kind is None or chunk.kind == kind:
                    return chunk
        for chunk in self.corpus.chunks:
            if chunk.metadata.get("case_id", "").casefold() == needle and (
                kind is None or chunk.kind == kind
            ):
                return chunk
            if chunk.metadata.get("drawing_id", "").casefold() == needle and (
                kind is None or chunk.kind == kind
            ):
                return chunk
        raise ToolError(f"No record found for id: {value}")

    def _tool_list_corpus(self, args: dict) -> dict:
        return self.corpus.stats()

    def _tool_search_documents(self, args: dict) -> dict:
        query = _as_str(args.get("query"))
        if not query:
            raise ToolError("search_documents requires a non-empty 'query'.")
        top_k = _clamp_top_k(args.get("top_k", 5), 5)
        kind = _as_str(args.get("kind")) or None
        results = self.corpus.search(query, kinds=kind, top_k=top_k)
        return {"query": query, "results": [_result(chunk, score) for chunk, score in results]}

    def _tool_get_safety_notices(self, args: dict) -> dict:
        top_k = _clamp_top_k(args.get("top_k", 10), 10)
        query = _as_str(args.get("query"))
        if query:
            ranked = self.corpus.search(query, kinds=SAFETY_NOTICE, top_k=top_k)
            results = [_result(chunk, score) for chunk, score in ranked]
        else:
            notices = self.corpus.by_kind(SAFETY_NOTICE)[:top_k]
            results = [_result(chunk) for chunk in notices]
        return {"results": results}

    def _tool_get_procedure(self, args: dict) -> dict:
        procedure_id = _as_str(args.get("procedure_id"))
        if not procedure_id:
            raise ToolError("get_procedure requires a 'procedure_id'.")
        chunk = self._find_by_id(procedure_id, PROCEDURE)
        return _result(chunk)

    def _tool_search_parts(self, args: dict) -> dict:
        top_k = _clamp_top_k(args.get("top_k", 10), 10)
        query = _as_str(args.get("query"))
        if query:
            ranked = self.corpus.search(query, kinds=PART_RECORD, top_k=top_k)
            results = [_result(chunk, score) for chunk, score in ranked]
        else:
            parts = self.corpus.by_kind(PART_RECORD)[:top_k]
            results = [_result(chunk) for chunk in parts]
        return {"results": results}

    def _tool_list_drawings(self, args: dict) -> dict:
        drawings = self.corpus.by_kind(DRAWING)
        return {
            "results": [
                {
                    "drawing_id": chunk.metadata.get("drawing_id"),
                    "chunk_id": chunk.chunk_id,
                    "file_name": chunk.metadata.get("file_name"),
                    "units": chunk.metadata.get("units"),
                    "title_block": chunk.metadata.get("title_block", {}),
                    "source": _source(chunk),
                }
                for chunk in drawings
            ]
        }

    def _tool_get_drawing(self, args: dict) -> dict:
        drawing_id = _as_str(args.get("drawing_id"))
        if not drawing_id:
            raise ToolError("get_drawing requires a 'drawing_id'.")
        chunk = self._find_by_id(drawing_id, DRAWING)
        return _result(chunk)

    def _tool_search_failure_cases(self, args: dict) -> dict:
        query = _as_str(args.get("query"))
        equipment = _as_str(args.get("equipment"))
        top_k = _clamp_top_k(args.get("top_k", 5), 5)
        if not query and not equipment:
            raise ToolError("search_failure_cases requires 'query' or 'equipment'.")
        candidates = self.corpus.by_kind(FAILURE_CASE)
        if equipment:
            needle = equipment.casefold()
            candidates = [
                chunk
                for chunk in candidates
                if needle in str(chunk.metadata.get("equipment", "")).casefold()
            ]
        if query:
            all_failures = self.corpus.by_kind(FAILURE_CASE)
            ranked = self.corpus.search(query, kinds=FAILURE_CASE, top_k=max(1, len(all_failures)))
            if equipment:
                candidate_ids = {chunk.chunk_id for chunk in candidates}
                ranked = [
                    (chunk, score) for chunk, score in ranked if chunk.chunk_id in candidate_ids
                ]
            results = [_result(chunk, score) for chunk, score in ranked[:top_k]]
            if not results and candidates:
                results = [_result(chunk) for chunk in candidates[:top_k]]
        else:
            results = [_result(chunk) for chunk in candidates[:top_k]]
        return {"query": query, "equipment": equipment, "results": results}

    def _tool_get_failure_case(self, args: dict) -> dict:
        case_id = _as_str(args.get("case_id"))
        if not case_id:
            raise ToolError("get_failure_case requires a 'case_id'.")
        chunk = self._find_by_id(case_id, FAILURE_CASE)
        return _result(chunk)
