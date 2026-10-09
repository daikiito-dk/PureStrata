"""End-to-end quickstart with the bundled sample data.

Ingests manuals, a CAD drawing, and a failure log into a corpus, runs the
same tool calls an LLM would make, and exports fine-tuning datasets.

    uv run python examples/quickstart.py
"""

from __future__ import annotations

from pathlib import Path

import purestrata as ps

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CORPUS_DIR = HERE / "corpus"
OUTPUT_DIR = HERE / "output"


def main() -> None:
    chunks: list[ps.Chunk] = []
    chunks += ps.ingest_manual(DATA / "manuals" / "lathe_mk3_maintenance.md")
    chunks += ps.ingest_manual(DATA / "manuals" / "ja" / "cnc_press_maintenance.md")
    chunks += ps.ingest_dxf(DATA / "cad" / "bracket_mk3.dxf")
    chunks += ps.ingest_failures(DATA / "failures" / "plant_failures.csv")

    by_doc: dict[str, list[ps.Chunk]] = {}
    for chunk in chunks:
        by_doc.setdefault(chunk.provenance.doc_id, []).append(chunk)
    for doc_id, doc_chunks in by_doc.items():
        path = ps.write_chunks(doc_chunks, CORPUS_DIR, doc_id)
        print(f"wrote {len(doc_chunks):>2} records -> {path}")

    corpus = ps.Corpus.load(CORPUS_DIR)
    print("\ncorpus:", corpus.stats())

    executor = ps.ToolExecutor(corpus)
    queries = [
        ("search_failure_cases", {"query": "spindle vibration", "top_k": 3}),
        ("search_documents", {"query": "torque"}),
        ("get_safety_notices", {"query": "electrical"}),
        ("get_drawing", {"drawing_id": "BRK-0042-A"}),
        ("search_documents", {"query": "ブレーキ 停止時間"}),
    ]
    for tool, args in queries:
        print(f"\n== {tool}({args})")
        result = executor.execute(tool, args)
        records = result.get("results", [])
        if records:
            for record in records:
                print(f"  [{record['kind']}] {record['text'][:140]}")
                print(f"    source: {record['source']['source_path']} :: {record['source']['locator']}")
        elif "chunk_id" in result:
            print(f"  [{result['kind']}] {result['text'][:140]}")
            print(f"    source: {result['source']['source_path']} :: {result['source']['locator']}")
        else:
            print(" ", result)

    ps.write_jsonl(ps.build_chat_records(corpus), OUTPUT_DIR / "dataset_chat.jsonl")
    ps.write_jsonl(ps.build_tool_trace_records(corpus, limit=3), OUTPUT_DIR / "dataset_tool_trace.jsonl")
    ps.write_jsonl(ps.build_cot_records(corpus, limit=3), OUTPUT_DIR / "dataset_cot.jsonl")
    print(f"\nexported fine-tuning datasets -> {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
