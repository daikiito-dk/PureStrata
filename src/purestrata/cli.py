"""Command line interface.

purestrata ingest-manual <files...> --out corpus/
purestrata ingest-dxf <files...> --out corpus/
purestrata ingest-failures <files...> --out corpus/
purestrata inspect --corpus corpus/
purestrata search "spindle vibration" --corpus corpus/
purestrata tools openai            # print tool schemas for Grok/OpenAI
purestrata export cot --corpus corpus/ --out dataset.jsonl
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
from .tools import ToolError, anthropic_tools, json_schemas, openai_tools
from .types import ALL_KINDS, derive_doc_id

INGEST_COMMANDS = {
    "ingest-manual": ingest_manual,
    "ingest-dxf": ingest_dxf,
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

    p = sub.add_parser("inspect", help="Print corpus statistics")
    p.add_argument("--corpus", default="corpus", help="Corpus directory (default: ./corpus)")

    p = sub.add_parser("tools", help="Print tool schemas for LLM integrations")
    p.add_argument("format", choices=["openai", "anthropic", "json"])

    p = sub.add_parser("export", help="Export fine-tuning datasets from a corpus")
    p.add_argument("format", choices=["chat", "tool_trace", "cot"])
    p.add_argument("--corpus", default="corpus", help="Corpus directory (default: ./corpus)")
    p.add_argument("--out", required=True, help="Output JSONL path")
    p.add_argument("--limit", type=int, help="Maximum number of records")

    p = sub.add_parser("serve", help="Run the MCP server (stdio) over a corpus")
    p.add_argument("--corpus", default="corpus", help="Corpus directory (default: ./corpus)")
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
    corpus = Corpus.load(args.corpus)
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


def _run_serve(args: argparse.Namespace) -> int:
    from .mcp_server import serve

    serve(args.corpus)
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
        if args.command == "serve":
            return _run_serve(args)
        parser.error(f"Unknown command: {args.command}")
        return 2
    except (FileNotFoundError, ToolError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
