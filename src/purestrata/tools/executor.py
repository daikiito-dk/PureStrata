"""Local execution of PureStrata tools against a loaded corpus.

The executor is the single implementation behind every integration surface:
the MCP server, the Python API, and the CLI all call :class:`ToolExecutor`.
Tool results are plain JSON-serializable dicts and always carry provenance,
so anything a model answers can be audited back to a source locator.
"""

from __future__ import annotations

from typing import Any

from ..corpus import Corpus
from ..ingest.geometry import feature_diameter_mm
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


def _as_float(value: Any, name: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ToolError(f"'{name}' must be a number.") from exc


class ToolExecutor:
    """Execute PureStrata tool calls against a corpus."""

    def __init__(self, corpus: Corpus):
        self.corpus = corpus
        self._parts_by_identifier: dict[str, list[Chunk]] = {}
        for part in corpus.by_kind(PART_RECORD):
            identifier = self._normalize_identifier(part.metadata.get("part_number"))
            if identifier:
                self._parts_by_identifier.setdefault(identifier, []).append(part)

        self._drawings_by_identifier: dict[str, list[tuple[Chunk, list[dict]]]] = {}
        for drawing in corpus.by_kind(DRAWING):
            metadata = drawing.metadata
            title_block = metadata.get("title_block") or {}
            identifiers: dict[str, list[dict]] = {}
            for key, value in (
                ("drawing_id", metadata.get("drawing_id")),
                ("dwg_no", title_block.get("dwg_no")),
                ("part_no", title_block.get("part_no")),
            ):
                identifier = self._normalize_identifier(value)
                if identifier:
                    identifiers.setdefault(identifier, []).append({"field": key, "value": value})
            for product in metadata.get("products") or []:
                if not isinstance(product, dict):
                    continue
                value = product.get("id")
                identifier = self._normalize_identifier(value)
                if identifier:
                    identifiers.setdefault(identifier, []).append(
                        {"field": "product_id", "value": value}
                    )
            for identifier, matched_identifiers in identifiers.items():
                self._drawings_by_identifier.setdefault(identifier, []).append(
                    (drawing, matched_identifiers)
                )

    @staticmethod
    def _normalize_identifier(value: Any) -> str:
        """Normalize explicit part/drawing identifiers without fuzzy matching."""
        return _as_str(value).casefold()

    def _related_records(self, chunk: Chunk) -> dict:
        """Find part and drawing records linked by an exact shared identifier."""
        part_number = _as_str(chunk.metadata.get("part_number"))
        identifier = self._normalize_identifier(part_number)
        parts = []
        drawings = []

        if identifier:
            for candidate in self._parts_by_identifier.get(identifier, []):
                parts.append(
                    {
                        "part_number": candidate.metadata.get("part_number"),
                        "name": candidate.metadata.get("name"),
                        "chunk_id": candidate.chunk_id,
                        "source": _source(candidate),
                    }
                )

            for candidate, matched_identifiers in self._drawings_by_identifier.get(identifier, []):
                drawings.append(
                    {
                        "drawing_id": candidate.metadata.get("drawing_id"),
                        "cad_format": candidate.metadata.get("format", "dxf"),
                        "chunk_id": candidate.chunk_id,
                        "matched_identifiers": matched_identifiers,
                        "source": _source(candidate),
                    }
                )

        parts.sort(key=lambda record: record["chunk_id"])
        drawings.sort(key=lambda record: record["chunk_id"])
        return {
            "identifier": part_number or None,
            "parts": {"matches": parts, "ambiguous": len(parts) > 1},
            "drawings": {"matches": drawings, "ambiguous": len(drawings) > 1},
        }

    def _failure_result(self, chunk: Chunk, score: float | None = None) -> dict:
        result = _result(chunk, score)
        result["related_records"] = self._related_records(chunk)
        return result

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
        return {
            "query": query,
            "results": [
                self._failure_result(chunk, score)
                if chunk.kind == FAILURE_CASE
                else _result(chunk, score)
                for chunk, score in results
            ],
        }

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
                    "cad_format": chunk.metadata.get("format", "dxf"),
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

    def _tool_search_drawings(self, args: dict) -> dict:
        query = _as_str(args.get("query"))
        layer = _as_str(args.get("layer"))
        fit = _as_str(args.get("fit"))
        material = _as_str(args.get("material"))
        cad_format = _as_str(args.get("cad_format")).casefold()
        min_d = _as_float(args.get("min_diameter"), "min_diameter")
        max_d = _as_float(args.get("max_diameter"), "max_diameter")
        top_k = _clamp_top_k(args.get("top_k", 10), 10)
        if min_d is not None and max_d is not None and min_d > max_d:
            raise ToolError("'min_diameter' must not exceed 'max_diameter'.")

        drawings = self.corpus.by_kind(DRAWING)
        if query:
            scored = self.corpus.search(query, kinds=DRAWING, top_k=max(1, len(drawings)))
        else:
            scored = [(chunk, None) for chunk in drawings]

        results = []
        for chunk, score in scored:
            meta = chunk.metadata
            if cad_format and meta.get("format", "dxf") != cad_format:
                continue
            matched_layers = []
            if layer:
                layer_names = set((meta.get("per_layer_counts") or {}).keys())
                if not layer_names:
                    layer_names = {
                        entry.get("name", "")
                        for entry in meta.get("layers", [])
                        if isinstance(entry, dict)
                    }
                matched_layers = sorted(
                    name
                    for name in layer_names
                    if name and str(name).casefold() == layer.casefold()
                )
                if not matched_layers:
                    continue
            if material:
                haystack = meta.get("title_block", {}).get("material") or chunk.text
                if material.casefold() not in haystack.casefold():
                    continue
            record = {
                "drawing_id": meta.get("drawing_id"),
                "chunk_id": chunk.chunk_id,
                "cad_format": meta.get("format", "dxf"),
                "title_block": meta.get("title_block", {}),
                "units": meta.get("units"),
                "size": meta.get("size"),
                "circular_features": meta.get("circular_features", []),
                "source": _source(chunk),
            }
            if layer:
                record["matched_layers"] = matched_layers
            if min_d is not None or max_d is not None:
                matched = [
                    feature
                    for feature in meta.get("circular_features", [])
                    if (min_d is None or feature_diameter_mm(feature) >= min_d)
                    and (max_d is None or feature_diameter_mm(feature) <= max_d)
                ]
                if not matched:
                    continue
                record["matched_features"] = matched
            if fit:
                callouts = [
                    callout
                    for callout in meta.get("diameter_callouts", [])
                    if (callout.get("fit") or "") == fit
                ]
                if not callouts:
                    continue
                record["matched_callouts"] = callouts
            if score is not None:
                record["score"] = round(score, 3)
            results.append(record)
        filters = {
            key: value
            for key, value in (
                ("query", query),
                ("layer", layer),
                ("min_diameter", min_d),
                ("max_diameter", max_d),
                ("fit", fit),
                ("material", material),
                ("cad_format", cad_format),
            )
            if value not in (None, "")
        }
        return {"filters": filters, "results": results[:top_k]}

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
            results = [self._failure_result(chunk, score) for chunk, score in ranked[:top_k]]
            if not results and candidates:
                results = [self._failure_result(chunk) for chunk in candidates[:top_k]]
        else:
            results = [self._failure_result(chunk) for chunk in candidates[:top_k]]
        return {"query": query, "equipment": equipment, "results": results}

    def _tool_get_failure_case(self, args: dict) -> dict:
        case_id = _as_str(args.get("case_id"))
        if not case_id:
            raise ToolError("get_failure_case requires a 'case_id'.")
        chunk = self._find_by_id(case_id, FAILURE_CASE)
        return self._failure_result(chunk)
