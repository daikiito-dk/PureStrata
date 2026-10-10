"""Tool definitions for LLM function calling.

The same nine tools are exposed three ways:
as JSON Schemas (:func:`json_schemas`), as OpenAI-style function definitions
(:func:`openai_tools`, also understood by xAI Grok and most OpenAI-compatible
endpoints), and as Anthropic-style definitions (:func:`anthropic_tools`).
Over MCP they are exposed by the bundled server (``purestrata serve``).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..types import ALL_KINDS

_TOP_K_PARAM = {
    "type": "integer",
    "minimum": 1,
    "maximum": 50,
    "default": 5,
    "description": "Maximum number of records to return.",
}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="list_corpus",
        description=(
            "Inventory of the PureStrata corpus: total record count, counts by record "
            "kind, and the list of loaded documents."
        ),
        parameters={"type": "object", "properties": {}, "required": []},
    ),
    ToolSpec(
        name="search_documents",
        description=(
            "Full-text search over spec sheets and manuals. Returns ranked passages with "
            "provenance (source file and locator). Supports English and Japanese queries."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search text (English or Japanese)."},
                "kind": {
                    "type": "string",
                    "enum": list(ALL_KINDS),
                    "description": "Restrict the search to one record kind.",
                },
                "top_k": dict(_TOP_K_PARAM),
            },
            "required": ["query"],
        },
    ),
    ToolSpec(
        name="get_safety_notices",
        description=(
            "Safety warnings and cautions, optionally filtered by a query. Use this "
            "before answering questions that involve physical maintenance work."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Optional text to rank notices by."},
                "top_k": {**_TOP_K_PARAM, "default": 10},
            },
            "required": [],
        },
    ),
    ToolSpec(
        name="get_procedure",
        description=(
            "Get the full ordered steps of a maintenance or inspection procedure by its ID."
        ),
        parameters={
            "type": "object",
            "properties": {
                "procedure_id": {
                    "type": "string",
                    "description": "The chunk_id of the procedure (from search_documents).",
                },
            },
            "required": ["procedure_id"],
        },
    ),
    ToolSpec(
        name="search_parts",
        description=(
            "Look up parts from parts lists: part number, name, quantity, and spec. "
            "Optionally filter with a query."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Optional text to filter parts by."},
                "top_k": {**_TOP_K_PARAM, "default": 10},
            },
            "required": [],
        },
    ),
    ToolSpec(
        name="list_drawings",
        description="List CAD drawings in the corpus with their identifiers and layers.",
        parameters={"type": "object", "properties": {}, "required": []},
    ),
    ToolSpec(
        name="get_drawing",
        description=(
            "Get full metadata for one CAD drawing: title block, layers, entity counts, "
            "text annotations, and geometric bounds."
        ),
        parameters={
            "type": "object",
            "properties": {
                "drawing_id": {
                    "type": "string",
                    "description": "Drawing number (from list_drawings) or chunk_id.",
                },
            },
            "required": ["drawing_id"],
        },
    ),
    ToolSpec(
        name="search_failure_cases",
        description=(
            "Search past failure and defect knowledge: symptom, root cause, and "
            "countermeasure. This is the first tool to use when troubleshooting an "
            "equipment problem."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Symptom or problem description (English or Japanese).",
                },
                "equipment": {
                    "type": "string",
                    "description": "Optional equipment name to filter by (e.g. 'LATHE MK3').",
                },
                "top_k": dict(_TOP_K_PARAM),
            },
            "required": ["query"],
        },
    ),
    ToolSpec(
        name="search_drawings",
        description=(
            "Find CAD drawings (DXF) and 3D models (STEP) by geometry and attributes: "
            "hole or cylinder diameter range in millimetres, ISO fit class from diameter "
            "callouts (e.g. 'H7'), material, file format, and optional free text. Returns "
            "the features that matched each filter."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Optional text to rank by (part name, title, product).",
                },
                "min_diameter": {
                    "type": "number",
                    "description": "Minimum circular feature diameter in mm.",
                },
                "max_diameter": {
                    "type": "number",
                    "description": "Maximum circular feature diameter in mm.",
                },
                "fit": {
                    "type": "string",
                    "description": "ISO fit class in a diameter callout, e.g. 'H7' or 'h6'.",
                },
                "material": {
                    "type": "string",
                    "description": "Material such as 'SS400' or 'S45C'.",
                },
                "cad_format": {
                    "type": "string",
                    "enum": ["dxf", "step"],
                    "description": "Restrict to 2D DXF drawings or 3D STEP models.",
                },
                "top_k": {**_TOP_K_PARAM, "default": 10},
            },
            "required": [],
        },
    ),
    ToolSpec(
        name="get_failure_case",
        description="Get one full failure case (symptom, cause, countermeasure) by its ID.",
        parameters={
            "type": "object",
            "properties": {
                "case_id": {
                    "type": "string",
                    "description": "The case_id of the failure case.",
                },
            },
            "required": ["case_id"],
        },
    ),
]

_TOOL_MAP = {tool.name: tool for tool in TOOLS}


def tool_by_name(name: str) -> ToolSpec:
    if name not in _TOOL_MAP:
        raise KeyError(f"Unknown tool: {name}")
    return _TOOL_MAP[name]


def json_schemas() -> list[dict]:
    """Raw JSON Schema definitions (provider neutral)."""
    return [
        {"name": tool.name, "description": tool.description, "parameters": tool.parameters}
        for tool in TOOLS
    ]


def openai_tools() -> list[dict]:
    """OpenAI-style tool definitions, also accepted by xAI Grok and OpenAI-compatible APIs."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in TOOLS
    ]


def anthropic_tools() -> list[dict]:
    """Anthropic-style tool definitions."""
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters,
        }
        for tool in TOOLS
    ]
