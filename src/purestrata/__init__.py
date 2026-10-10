"""PureStrata: the open data layer for manufacturing AI.

Ingest drawings, spec sheets, and failure knowledge into a portable,
provenance-tagged corpus, query it from any LLM (MCP server, OpenAI-style
tools, or plain Python), and export the same corpus as fine-tuning
datasets.
"""

from .corpus import Corpus, write_chunks
from .export.evaluation import evaluate_dataset, format_evaluation_summary
from .export.finetune import (
    build_chat_records,
    build_cot_records,
    build_tool_trace_records,
    write_jsonl,
)
from .export.review import (
    approved_records,
    create_review_bundle,
    decide_review,
    get_review_entry,
    list_review_queue,
    write_review_bundle,
)
from .ingest.cad import ingest_dxf
from .ingest.failures import ingest_failures
from .ingest.manual import ingest_manual
from .ingest.step import ingest_step, parse_step
from .search import SearchIndex, has_cjk, tokenize
from .tools import TOOLS, ToolError, ToolExecutor, anthropic_tools, json_schemas, openai_tools
from .types import (
    ALL_KINDS,
    DRAWING,
    FAILURE_CASE,
    MANUAL_SECTION,
    PART_RECORD,
    PROCEDURE,
    SAFETY_NOTICE,
    Chunk,
    Provenance,
    derive_doc_id,
    new_chunk,
)

__version__ = "0.2.0"

__all__ = [
    "ALL_KINDS",
    "DRAWING",
    "FAILURE_CASE",
    "MANUAL_SECTION",
    "PART_RECORD",
    "PROCEDURE",
    "SAFETY_NOTICE",
    "TOOLS",
    "Chunk",
    "Corpus",
    "Provenance",
    "SearchIndex",
    "ToolError",
    "ToolExecutor",
    "anthropic_tools",
    "approved_records",
    "build_chat_records",
    "build_cot_records",
    "build_tool_trace_records",
    "create_review_bundle",
    "decide_review",
    "derive_doc_id",
    "evaluate_dataset",
    "format_evaluation_summary",
    "get_review_entry",
    "has_cjk",
    "ingest_dxf",
    "ingest_failures",
    "ingest_manual",
    "ingest_step",
    "json_schemas",
    "list_review_queue",
    "new_chunk",
    "openai_tools",
    "parse_step",
    "tokenize",
    "write_chunks",
    "write_jsonl",
    "write_review_bundle",
]
