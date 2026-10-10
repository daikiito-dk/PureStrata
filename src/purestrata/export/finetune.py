"""Export a corpus into fine-tuning dataset formats.

The same corpus that serves live RAG queries is also the raw material for
training data. Three shapes are produced:

- ``chat``: system/user/assistant message JSONL, the format accepted by
  OpenAI's and xAI's fine-tuning APIs.
- ``tool_trace``: message JSONL that includes a model-issued tool call,
  the tool result, and the grounded final answer, for tool-use training.
- ``cot``: instruction / reasoning / output records with sources, a
  scaffold for chain-of-thought refinement by domain experts.

Every record carries provenance, so dataset quality can be audited and
reproduced from the source documents.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..corpus import Corpus
from ..tools.executor import ToolError, ToolExecutor
from ..types import FAILURE_CASE, PROCEDURE, SAFETY_NOTICE, Chunk
from ._io import write_lines_atomic

SYSTEM_PROMPT = (
    "You are a manufacturing maintenance assistant. Answer using verified maintenance "
    "and failure knowledge, and cite the source locator of every record you rely on."
)


def _sources(chunk: Chunk) -> list[dict]:
    return [
        {
            **chunk.provenance.to_dict(),
            "chunk_id": chunk.chunk_id,
            "record_kind": chunk.kind,
        }
    ]


def _failure_question(chunk: Chunk) -> str:
    meta = chunk.metadata
    equipment = meta.get("equipment", "")
    symptom = meta.get("symptom", "")
    where = f" on equipment '{equipment}'" if equipment else ""
    observed = f" We observe: {symptom.rstrip('.。')}." if symptom else ""
    return (
        f"We are troubleshooting a problem{where}.{observed}"
        " What is the likely cause and the countermeasure?"
    )


def _failure_answer(chunk: Chunk) -> str:
    meta = chunk.metadata
    lines = []
    part = meta.get("part_number")
    if part:
        lines.append(f"Involved part: {part}")
    lines.append(f"Likely cause: {meta.get('cause') or 'not recorded'}")
    lines.append(f"Countermeasure: {meta.get('countermeasure') or 'not recorded'}")
    lines.append(f"Severity: {meta.get('severity', 'unspecified')}")
    lines.append(f"Source: {chunk.provenance}")
    return "\n".join(lines)


def _procedure_qa(chunk: Chunk) -> dict | None:
    meta = chunk.metadata
    steps = meta.get("steps") or []
    if not steps:
        return None
    equipment = meta.get("equipment")
    scope = f" on {equipment}" if equipment else ""
    question = f"List the steps of '{meta.get('title', 'the procedure')}'{scope}."
    answer = "\n".join(f"{i}. {step}" for i, step in enumerate(steps, start=1))
    answer += f"\nSource: {chunk.provenance}"
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ],
        "sources": _sources(chunk),
    }


def _safety_qa(chunk: Chunk) -> dict | None:
    if not chunk.text.strip():
        return None
    question = (
        f"What safety precaution applies to '{chunk.metadata.get('section', 'this equipment')}'?"
    )
    answer = f"{chunk.text}\nSource: {chunk.provenance}"
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ],
        "sources": _sources(chunk),
    }


def build_chat_records(corpus: Corpus, limit: int | None = None) -> list[dict]:
    """Build chat-format fine-tuning records from failure cases, procedures, and notices."""
    records: list[dict] = []
    for chunk in corpus.chunks:
        record = None
        if chunk.kind == FAILURE_CASE:
            record = {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _failure_question(chunk)},
                    {"role": "assistant", "content": _failure_answer(chunk)},
                ],
                "sources": _sources(chunk),
            }
        elif chunk.kind == PROCEDURE:
            record = _procedure_qa(chunk)
        elif chunk.kind == SAFETY_NOTICE:
            record = _safety_qa(chunk)
        if record is not None:
            records.append(record)
    return records[:limit] if limit else records


def build_tool_trace_records(corpus: Corpus, limit: int | None = None) -> list[dict]:
    """Build tool-use fine-tuning records from failure cases.

    Each record shows the model choosing ``search_failure_cases`` with a
    symptom-driven query, receiving provenance-tagged results, and
    answering from them.
    """
    executor = ToolExecutor(corpus)
    records: list[dict] = []
    for i, chunk in enumerate(corpus.by_kind(FAILURE_CASE), start=1):
        meta = chunk.metadata
        symptom = meta.get("symptom") or meta.get("cause") or chunk.text[:120]
        question = _failure_question(chunk)
        call_args = {"query": symptom, "top_k": 3}
        try:
            tool_result = executor.execute("search_failure_cases", call_args)
        except ToolError:
            continue
        call_id = f"call_{i:04d}"
        final = _failure_answer(chunk)
        record = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": "search_failure_cases",
                                "arguments": json.dumps(call_args, ensure_ascii=False),
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps(tool_result, ensure_ascii=False, default=str),
                },
                {"role": "assistant", "content": final},
            ],
            "sources": _sources(chunk),
        }
        records.append(record)
    return records[:limit] if limit else records


def build_cot_records(corpus: Corpus, limit: int | None = None) -> list[dict]:
    """Build chain-of-thought records from failure cases.

    The reasoning trace is a transparent scaffold over structured fields,
    designed to be reviewed and sharpened by maintenance engineers before
    training. That expert-in-the-loop pass is where dataset quality comes
    from; these records make the work auditable.
    """
    records: list[dict] = []
    for chunk in corpus.by_kind(FAILURE_CASE):
        meta = chunk.metadata
        cause = meta.get("cause") or "not recorded"
        countermeasure = meta.get("countermeasure") or "not recorded"
        reasoning = (
            f"The report concerns equipment '{meta.get('equipment', 'unspecified')}'. "
            f"The observed symptom is: {meta.get('symptom', 'unspecified')}. "
            f"Failure case {meta.get('case_id', chunk.chunk_id)} in the verified history "
            f"matches this equipment and symptom. Its recorded root cause was: {cause}. "
            f"The applied countermeasure was: {countermeasure}. "
            "Since the symptom matches the recorded case, the same root cause is the most "
            "likely explanation, and the same countermeasure applies before further "
            "investigation."
        )
        records.append(
            {
                "instruction": _failure_question(chunk),
                "reasoning": reasoning,
                "output": _failure_answer(chunk),
                "sources": _sources(chunk),
            }
        )
    return records[:limit] if limit else records


def write_jsonl(records: list[dict], out_path: str | Path) -> Path:
    """Write records as JSONL atomically and return the path.

    The write goes through a temporary file and rename, so an interrupted
    export never replaces a good dataset with a truncated one.
    """
    lines = [json.dumps(record, ensure_ascii=False, default=str) for record in records]
    return write_lines_atomic(out_path, lines)
