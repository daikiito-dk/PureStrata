# Design decisions

Each decision below is stated with the code or README passage it rests on. Where the code does not state a motive, the reasoning is marked as an inference.

## 1. Zero required dependencies in the core

`pyproject.toml` declares no `dependencies` key at all. The only third-party packages are optional extras:

```toml
[project.optional-dependencies]
pdf = ["pypdf>=4.0"]
mcp = ["mcp>=1.2"]
```

A walk over `src/purestrata/` confirms it: every module imports from the standard library (`json`, `re`, `csv`, `hashlib`, `unicodedata`, `math`, `pathlib`, `collections`, `dataclasses`, `argparse`, `sys`, `typing`) except `src/purestrata/ingest/manual.py`, which imports `pypdf` inside `_extract_pdf_text`, and `src/purestrata/mcp_server.py`, which imports `mcp` inside `build_mcp_server`. Both raise a message naming the extra to install.

Three reasons are visible in the README: "Zero required dependencies for the core. Runs on your machine, air-gap friendly." An air-gapped factory network may have no reachable package index, so a dependency-free core means a wheel plus `pip` is a complete install. Auditability follows from the same fact: about 2,900 lines across 20 modules is a codebase a reviewer can read end to end, and none of that reading involves third-party code. Minimal attack surface is the third, and it is the subject of [Security](../security.md): no supply chain beyond the standard library, no parser from a package that also does something else.

## 2. Plain JSONL files instead of a database

The docstring of `src/purestrata/corpus.py` states the decision:

> A corpus is just `*.strata.jsonl` files, one JSON object per line per chunk. No database, no server, no lock-in: companies can drop a corpus on a file share, ship it to an air-gapped network, or commit small ones to git.

The format makes that literally true. One file per ingested document, named `<doc_id>.strata.jsonl`, written by `write_chunks`. Loading is `Path.glob` over the suffix plus a `json.loads` per line. There is no migration step, no daemon, and no version-negotiating client. A database would add a service to operate, a backup story, and a place for the corpus to become inaccessible to the tools that need it. The tradeoff is that filtering is done in Python over a list of chunks after a full load, which is fine at corpus sizes measured in documents and not in billions of rows.

## 3. BM25 with CJK character bigrams instead of MeCab or embeddings

`src/purestrata/search.py` documents both halves of the choice:

> Dependency-free BM25 search with CJK (Japanese) support. Latin text is tokenized as lowercased alphanumeric words. CJK text is tokenized into character bigrams, which works well for Japanese without a morphological analyzer and keeps PureStrata free of native extensions.

`tokenize` normalizes with NFKC and `casefold`, extracts Latin words with `_WORD_RE`, and splits CJK runs into overlapping bigrams. A morphological analyzer such as MeCab needs a compiled dependency and a dictionary, which would break decisions 1 and 2 at once. Embeddings would replace determinism with a model: the same corpus and query would rank the same way only if the model and weights are identical, and the ranking would no longer be explainable by term frequencies. `SearchIndex` is Okapi BM25 with the standard `K1 = 1.5`, `B = 0.75`, and it drops zero-score matches, so an empty result list means "no term overlap", which is a deterministic and checkable statement.

## 4. Provenance is mandatory on every record

`src/purestrata/types.py` opens with the reasoning:

> Provenance is what makes a corpus auditable: every answer a model gives can be traced to a line in a drawing, a section of a manual, or a row in a failure log.

The README frames it as a domain requirement rather than a feature: "Provenance is non-negotiable. Every record carries its source file and locator, so any answer an LLM gives can be audited back to the drawing, section, or spreadsheet row it came from." Manufacturing maintenance work is documented for audits and traceability, so a retrieval layer that cannot cite its source is unusable regardless of answer quality.

The constraint is enforced structurally rather than by convention. `new_chunk(kind, text, provenance, metadata=None)` takes `Provenance` as a required positional argument, and `Provenance` requires `doc_id`, `source_path`, and `locator`, so a record cannot be constructed without one. `Chunk.to_dict` serializes it, and `_result` in `src/purestrata/tools/executor.py` puts it in every tool result under the `source` key. Every path to a model therefore carries the citation, because there is no code path that produces a result without it.

## 5. One ToolExecutor behind four surfaces

The docstring of `src/purestrata/tools/executor.py` is explicit:

> The executor is the single implementation behind every integration surface: the MCP server, the Python API, and the CLI all call `ToolExecutor`.

`src/purestrata/mcp_server.py` wraps each tool in a thin function that calls `executor.execute(name, ...)`. `src/purestrata/cli.py` handles `call` and `search` through the same executor. The Python API returns it directly on import. The schemas in `src/purestrata/tools/schemas.py` are one `ToolSpec` list projected into OpenAI and Anthropic shapes by `openai_tools()` and `anthropic_tools()`.

The reason is the failure mode it prevents: four integrations each validating arguments, clamping `top_k`, and shaping results would drift, and a model would then get different answers depending on which client it was talking to. With one implementation, the only per-surface code is argument passing. The cost is that a surface cannot specialize a tool without adding a branch to the executor, which is a deliberate trade.

## 6. `failure_case` is a first-class record kind

The README names the gap: "Most RAG stacks retrieve manual text. Factory troubleshooting runs on *symptom → cause → countermeasure* records. PureStrata treats failure cases as first-class structured data." Failure knowledge is not a document type that ordinary ingestion would recover, because it lives in spreadsheets and incident logs with their own columns, and its unit of value is a case rather than a passage.

The kind is `FAILURE_CASE` in `src/purestrata/types.py`, alongside five others. It gets its own tools (`search_failure_cases`, `get_failure_case`), its own ingester (`src/purestrata/ingest/failures.py` for CSV and JSONL), and its own export templates in `src/purestrata/export/finetune.py`, where `_failure_question` builds a troubleshooting question from the equipment and symptom and `_failure_answer` assembles cause, countermeasure, severity, and source. The tool description in `src/purestrata/tools/schemas.py` states the intended priority: "This is the first tool to use when troubleshooting an equipment problem." A model reading the schemas is pointed at failure knowledge before manual search.

## 7. CoT exports are transparent scaffolds, not finished training data

`src/purestrata/export/finetune.py` describes the third export shape as "instruction / reasoning / output records with sources, a scaffold for chain-of-thought refinement by domain experts." The README states the intent directly: "CoT records are a deliberate scaffold: they are transparent, grounded in structured fields, and built to be reviewed and sharpened by maintenance engineers before training. That expert-in-the-loop pass is where dataset quality comes from."

The generated reasoning is derived from structured fields rather than produced by a model, which means it is inspectable and reproducible from the same corpus. The design assumes a maintenance engineer corrects the text before it trains anything, and the provenance on each record is what makes that review checkable. Exporting model-written rationales would produce data that looks finished while being unauditable, so the choice is to ship something a domain expert can improve.

## 8. Prefix schema versioning with deterministic chunk ids

`SCHEMA_VERSION = "purestrata/v1"` in `src/purestrata/types.py` is written into every record as `"schema": "purestrata/v1"` by `Chunk.to_dict`. On read, `from_dict` accepts a missing schema and any string starting with `purestrata/`, and rejects anything else with `Unsupported corpus record schema`. The reasoning appears to be that a prefix test lets a reader from one minor schema generation open files written by a compatible one, while still refusing a foreign file format outright, and it keeps the version out of the field-by-field validation path.

Ids are deterministic for a related reason. `make_chunk_id(doc_id, kind, locator)` hashes `f"{doc_id}::{kind}::{locator}"` to 12 hex characters of SHA-1, and its docstring states: "The id is deterministic, so re-ingesting an unchanged source file produces the same ids and ingestion is idempotent." Re-running an ingest over the same input overwrites the same file with the same ids, so a re-ingest cannot duplicate records or break references held by an exported dataset. The same derivation is the source of an edge case noted in [Pitfalls](pitfalls.md): the id depends on the locator, so a change to a locator scheme changes every id for that document.
