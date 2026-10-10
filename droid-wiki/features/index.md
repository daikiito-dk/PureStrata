# Features

PureStrata's user-visible capabilities, one page each. Each capability starts with an ingest adapter that reads a source document and emits typed records, and every record carries provenance back to the file and position it came from. From that corpus, the same records serve search, LLM tools, an MCP server, the CLI, and fine-tuning exports.

## Pages

| Page | What it covers |
| --- | --- |
| [Manual ingestion](manual-ingestion.md) | Markdown and PDF manuals parsed into four record kinds (`manual_section`, `procedure`, `safety_notice`, `part_record`) |
| [CAD ingestion](cad-ingestion/index.md) | ASCII DXF and STEP (ISO 10303-21) drawings plus the shared geometry helpers, with per-format sub-pages for [DXF](cad-ingestion/dxf.md) and [STEP](cad-ingestion/step.md) |
| [Failure knowledge](failure-knowledge.md) | CSV and JSONL failure logs ingested as `failure_case` records through flexible English/Japanese column aliases |
| [Full-text search](full-text-search.md) | Dependency-free Okapi BM25 over records, with Latin word tokens and CJK character bigrams |
| [LLM tools](llm-tools.md) | The ten tools and the single `ToolExecutor` that implements all of them |
| [MCP server](mcp-server.md) | stdio MCP integration so Claude Desktop and other MCP clients can query a corpus |
| [CLI](cli.md) | The `purestrata` commands: ingest, search, inspect, tools, export, call, serve |
| [Fine-tune exports](fine-tune-exports.md) | chat, tool_trace, and CoT training datasets built from the same corpus |

## What every capability shares

Four properties hold across all of the pages above, because they come from the shared primitives rather than from individual features:

| Property | Where it comes from |
| --- | --- |
| Provenance on every record | `Chunk.provenance` in `src/purestrata/types.py`; see [Records and provenance](../primitives/records-and-provenance.md) |
| Plain-file storage | A directory of `*.strata.jsonl`; see [Corpus](../primitives/corpus.md) |
| One corpus per working set | `Corpus.load` over a directory, so ingestion and querying are decoupled |
| Zero required dependencies | Standard library only; `pypdf` and `mcp` are optional extras (see [Dependencies](../reference/dependencies.md)) |

The consequence is that adding a source format, a tool, or an output shape does not touch the other capabilities. The corpus is the only shared contract.

## How the pages relate

Ingestion is the entry point: [Manual ingestion](manual-ingestion.md), [CAD ingestion](cad-ingestion/index.md), and [Failure knowledge](failure-knowledge.md) each produce records through the shared data model. Records are stored as `*.strata.jsonl` files and loaded into memory.

[Full-text search](full-text-search.md) ranks records for a query. [LLM tools](llm-tools.md) wrap search and record access as ten callable tools behind one executor. [MCP server](mcp-server.md), the [CLI](cli.md), and the Python API all call that same executor, so an integration cannot behave differently from the others. [Fine-tune exports](fine-tune-exports.md) read the identical corpus, which is what keeps retrieval and training data consistent.

## Record kinds produced

Each ingestion capability emits a subset of the six record kinds defined in `src/purestrata/types.py`. A corpus directory mixes them freely, and tools filter on kind at query time.

| Capability | Kinds produced |
| --- | --- |
| [Manual ingestion](manual-ingestion.md) | `manual_section`, `procedure`, `safety_notice`, `part_record` |
| [CAD ingestion](cad-ingestion/index.md) | `drawing` |
| [Failure knowledge](failure-knowledge.md) | `failure_case` |
| Search, tools, exports | Consume all kinds; produce none |

## Common workflow

1. Ingest source documents with the CLI (`purestrata ingest-manual`, `ingest-dxf`, `ingest-step`, `ingest-failures`), writing `*.strata.jsonl` into a corpus directory.
2. Inspect the result with `purestrata inspect --corpus <dir>` to confirm counts per kind and per document.
3. Query it locally with `purestrata search`, or serve it to a model with `purestrata serve` for MCP clients.
4. Optionally export training data with `purestrata export` from the same directory.

Steps 1 through 4 are independent after ingestion: the corpus files are the handoff point, so no step needs the process that produced them to still be running.

## Choosing where to start

- Getting documents in: read [Manual ingestion](manual-ingestion.md) first, then the format page that matches your files.
- Looking something up by hand: [Full-text search](full-text-search.md) and the `search` command in the [CLI](cli.md).
- Wiring an assistant to a corpus: [MCP server](mcp-server.md) for hosted clients, [LLM tools](llm-tools.md) for direct tool calling.
- Building a training set: [Fine-tune exports](fine-tune-exports.md).

## Related wiki sections

- [Architecture](../overview/architecture.md) for the internal wiring behind these pages.
- [Glossary](../overview/glossary.md) for terminology used across them.
- [Primitives](../primitives/index.md) for the objects every capability shares.
- [Reference](../reference/index.md) for CLI flags, the record format, and dependencies.
- [Background](../background/index.md) for the design trade-offs behind the zero-dependency core.
