"""Command line interface.

purestrata ingest-manual <files...> --out corpus/
purestrata ingest-dxf <files...> --out corpus/
purestrata ingest-step <files...> --out corpus/
purestrata ingest-failures <files...> --out corpus/
purestrata inspect --corpus corpus/
purestrata search "spindle vibration" --corpus corpus/
purestrata call search_drawings '{"min_diameter": 24, "max_diameter": 26}' --corpus corpus/
purestrata tools openai            # print tool schemas for Grok/OpenAI
purestrata export cot --corpus corpus/ --out dataset.jsonl
purestrata evaluate cot dataset.jsonl --out evaluation.json
purestrata review create cot --corpus corpus/ --out review.jsonl
purestrata review export-approved --bundle review.jsonl --out reviewed.jsonl
purestrata serve --corpus corpus/  # MCP server over stdio
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .corpus import Corpus, write_chunks
from .ingest.cad import ingest_dxf
from .ingest.failures import ingest_failures
from .ingest.manual import ingest_manual
from .ingest.step import ingest_step
from .tools import ToolError, anthropic_tools, json_schemas, openai_tools
from .types import ALL_KINDS, derive_doc_id

INGEST_COMMANDS = {
    "ingest-manual": ingest_manual,
    "ingest-dxf": ingest_dxf,
    "ingest-step": ingest_step,
    "ingest-failures": ingest_failures,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="purestrata",
        description="The open data layer for manufacturing AI.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_text in (
        ("ingest-manual", "Ingest Markdown/PDF manuals and spec sheets"),
        ("ingest-dxf", "Ingest ASCII DXF CAD drawings"),
        ("ingest-step", "Ingest STEP (ISO 10303-21) 3D models"),
        ("ingest-failures", "Ingest CSV/JSONL failure logs"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("paths", nargs="+", help="Input file paths")
        p.add_argument("--out", required=True, help="Output corpus directory")

    p = sub.add_parser("search", help="Full-text search across the corpus")
    p.add_argument("query", help="Search text (English or Japanese)")
    p.add_argument("--corpus", default="corpus", help="Corpus directory (default: ./corpus)")
    p.add_argument("--kind", choices=ALL_KINDS, help="Restrict search to one record kind")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--embedding-model", help="Local SentenceTransformer model directory")
    p.add_argument(
        "--hybrid",
        action="store_true",
        help="Combine BM25 and local embedding search (requires --embedding-model)",
    )

    p = sub.add_parser("inspect", help="Print corpus statistics")
    p.add_argument("--corpus", default="corpus", help="Corpus directory (default: ./corpus)")

    p = sub.add_parser("tools", help="Print tool schemas for LLM integrations")
    p.add_argument("format", choices=["openai", "anthropic", "json"])

    p = sub.add_parser("export", help="Export fine-tuning datasets from a corpus")
    p.add_argument("format", choices=["chat", "tool_trace", "cot"])
    p.add_argument("--corpus", default="corpus", help="Corpus directory (default: ./corpus)")
    p.add_argument("--out", required=True, help="Output JSONL path")
    p.add_argument("--limit", type=int, help="Maximum number of records")

    p = sub.add_parser("evaluate", help="Evaluate a fine-tuning dataset locally")
    p.add_argument("format", choices=["chat", "tool_trace", "cot"])
    p.add_argument("input", help="Fine-tuning JSONL path")
    p.add_argument("--out", help="Optional machine-readable JSON report path")

    p = sub.add_parser("review", help="Review training records offline")
    review_sub = p.add_subparsers(dest="review_command", required=True)

    create = review_sub.add_parser("create", help="Create a pending expert-review bundle")
    create.add_argument("format", choices=["chat", "tool_trace", "cot"])
    create.add_argument("--corpus", default="corpus", help="Corpus directory (default: ./corpus)")
    create.add_argument("--out", required=True, help="Output review bundle JSONL path")
    create.add_argument("--limit", type=int, help="Maximum number of records")

    queue = review_sub.add_parser("list", help="List review IDs and statuses")
    queue.add_argument("--bundle", required=True, help="Review bundle JSONL path")

    show = review_sub.add_parser("show", help="Show one review record")
    show.add_argument("review_id", help="Stable review sample ID from the bundle")
    show.add_argument("--bundle", required=True, help="Review bundle JSONL path")

    decide = review_sub.add_parser("decide", help="Approve, reject, or annotate one review sample")
    decide.add_argument("review_id", help="Stable review sample ID from the bundle")
    decide.add_argument("--bundle", required=True, help="Review bundle JSONL path")
    decide.add_argument("--status", choices=["pending", "approved", "rejected"], required=True)
    decide.add_argument("--reviewer", help="Reviewer name or identifier")
    decide.add_argument("--notes", help="Reviewer notes")
    decide.add_argument(
        "--replacement-record",
        help="JSON file containing the reviewed provider-format record; sources must be unchanged",
    )

    approved = review_sub.add_parser(
        "export-approved", help="Export only approved records in the original format"
    )
    approved.add_argument("--bundle", required=True, help="Review bundle JSONL path")
    approved.add_argument("--out", required=True, help="Output JSONL path")

    p = sub.add_parser("call", help="Call one tool locally and print its JSON result")
    p.add_argument("tool", help="Tool name, e.g. search_drawings")
    p.add_argument("arguments", nargs="?", default="{}", help="Tool arguments as a JSON object")
    p.add_argument("--corpus", default="corpus", help="Corpus directory (default: ./corpus)")
    p.add_argument("--embedding-model", help="Local SentenceTransformer model directory")
    p.add_argument("--hybrid", action="store_true", help="Enable local BM25 + embedding search")

    p = sub.add_parser("serve", help="Run the MCP server (stdio) over a corpus")
    p.add_argument("--corpus", default="corpus", help="Corpus directory (default: ./corpus)")
    p.add_argument("--embedding-model", help="Local SentenceTransformer model directory")
    p.add_argument("--hybrid", action="store_true", help="Enable local BM25 + embedding search")
    return parser


def _run_ingest(args: argparse.Namespace) -> int:
    ingest = INGEST_COMMANDS[args.command]
    total = 0
    for path in args.paths:
        if not Path(path).exists():
            print(f"error: file not found: {path}", file=sys.stderr)
            return 1
        chunks = ingest(path)
        doc_id = derive_doc_id(path)
        out_path = write_chunks(chunks, args.out, doc_id)
        total += len(chunks)
        print(f"{path}: {len(chunks)} records -> {out_path}")
    print(f"Total: {total} records written to {args.out}")
    return 0


def _run_search(args: argparse.Namespace) -> int:
    corpus = _load_search_corpus(args)
    results = corpus.search(args.query, kinds=args.kind, top_k=args.top_k)
    if not results:
        print("No records matched.")
        return 0
    for rank, (chunk, score) in enumerate(results, start=1):
        preview = chunk.text[:200].replace("\n", " ")
        print(f"{rank}. [{chunk.kind}] score={score:.3f} id={chunk.chunk_id}")
        print(f"   {preview}")
        print(f"   source: {chunk.provenance}")
    return 0


def _load_search_corpus(args: argparse.Namespace) -> Corpus:
    if args.hybrid and not args.embedding_model:
        raise ValueError("--hybrid requires --embedding-model pointing to a local model directory.")
    if args.embedding_model and not args.hybrid:
        raise ValueError("--embedding-model requires --hybrid; BM25 remains the default.")
    return Corpus.load(
        args.corpus,
        embedding_model=args.embedding_model,
        hybrid_search=args.hybrid,
    )


def _run_export(args: argparse.Namespace) -> int:
    from .export.finetune import (
        build_chat_records,
        build_cot_records,
        build_tool_trace_records,
        write_jsonl,
    )

    builders = {
        "chat": build_chat_records,
        "tool_trace": build_tool_trace_records,
        "cot": build_cot_records,
    }
    corpus = Corpus.load(args.corpus)
    records = builders[args.format](corpus, limit=args.limit)
    out_path = write_jsonl(records, args.out)
    print(f"Exported {len(records)} {args.format} records -> {out_path}")
    return 0


def _run_evaluate(args: argparse.Namespace) -> int:
    from .export.evaluation import evaluate_dataset, format_evaluation_summary

    report = evaluate_dataset(args.input, args.format)
    print(format_evaluation_summary(report))
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"JSON report -> {out_path}")
    return 0


def _run_review(args: argparse.Namespace) -> int:
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

    if args.review_command == "create":
        builders = {
            "chat": build_chat_records,
            "tool_trace": build_tool_trace_records,
            "cot": build_cot_records,
        }
        records = builders[args.format](Corpus.load(args.corpus), limit=args.limit)
        bundle = create_review_bundle(args.format, records)
        out_path = write_review_bundle(bundle, args.out)
        print(f"Created {len(bundle)} pending {args.format} review records -> {out_path}")
        return 0
    if args.review_command == "list":
        print(json.dumps(list_review_queue(args.bundle), indent=2, ensure_ascii=False))
        return 0
    if args.review_command == "show":
        print(
            json.dumps(
                get_review_entry(args.bundle, args.review_id),
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )
        return 0
    if args.review_command == "decide":
        path = decide_review(
            args.bundle,
            args.review_id,
            args.status,
            reviewer=args.reviewer,
            notes=args.notes,
            replacement_record_path=args.replacement_record,
        )
        print(f"Updated review {args.review_id} -> {args.status} in {path}")
        return 0
    if args.review_command == "export-approved":
        records = approved_records(args.bundle)
        out_path = write_jsonl(records, args.out)
        print(f"Exported {len(records)} approved records -> {out_path}")
        return 0
    raise ValueError(f"Unknown review command: {args.review_command}")


def _run_call(args: argparse.Namespace) -> int:
    from .tools import ToolExecutor

    try:
        tool_args = json.loads(args.arguments)
    except json.JSONDecodeError as exc:
        raise ValueError(f"arguments must be a JSON object: {exc}") from exc
    if not isinstance(tool_args, dict):
        raise ValueError("arguments must be a JSON object")
    result = ToolExecutor(_load_search_corpus(args)).execute(args.tool, tool_args)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0


def _run_serve(args: argparse.Namespace) -> int:
    from .mcp_server import serve

    if args.hybrid and not args.embedding_model:
        raise ValueError("--hybrid requires --embedding-model pointing to a local model directory.")
    if args.embedding_model and not args.hybrid:
        raise ValueError("--embedding-model requires --hybrid; BM25 remains the default.")
    serve(args.corpus, embedding_model=args.embedding_model, hybrid_search=args.hybrid)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command in INGEST_COMMANDS:
            return _run_ingest(args)
        if args.command == "search":
            return _run_search(args)
        if args.command == "inspect":
            print(json.dumps(Corpus.load(args.corpus).stats(), indent=2, ensure_ascii=False))
            return 0
        if args.command == "tools":
            schema = {
                "openai": openai_tools,
                "anthropic": anthropic_tools,
                "json": json_schemas,
            }[args.format]
            print(json.dumps(schema(), indent=2, ensure_ascii=False))
            return 0
        if args.command == "export":
            return _run_export(args)
        if args.command == "evaluate":
            return _run_evaluate(args)
        if args.command == "review":
            return _run_review(args)
        if args.command == "call":
            return _run_call(args)
        if args.command == "serve":
            return _run_serve(args)
        parser.error(f"Unknown command: {args.command}")
        return 2
    except (FileNotFoundError, ToolError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
