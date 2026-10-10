# Glossary

Domain vocabulary used across the codebase and this wiki.

| Term | Meaning |
| --- | --- |
| Corpus | A directory of `*.strata.jsonl` files holding every ingested record. Loaded by `Corpus.load()` in `src/purestrata/corpus.py`. |
| Chunk | The single record type of the data layer: typed text plus metadata plus provenance (`src/purestrata/types.py`). One corpus line is one chunk. |
| Record kind | The chunk's type tag: `manual_section`, `procedure`, `safety_notice`, `part_record`, `drawing`, or `failure_case`. |
| Provenance | Where a chunk came from: `doc_id`, `source_path`, and a human-readable `locator` (section path, `row 3`, `model`). Every tool result embeds it. |
| Locator | The position part of provenance: a heading path in a manual, a row number in a CSV, `model` for a whole STEP file. |
| `doc_id` | Stable document identifier derived from the source file name by `derive_doc_id()` in `src/purestrata/types.py`. |
| `chunk_id` | Deterministic record id: first 12 hex chars of SHA-1 over `doc_id::kind::locator`, so re-ingesting an unchanged file is idempotent. |
| Schema version | The string `purestrata/v1` written into every record; loaders reject records with a foreign schema prefix. |
| BM25 | Okapi ranking function over the corpus, implemented dependency-free in `src/purestrata/search.py` (k1=1.5, b=0.75). |
| CJK bigram | Tokenization for Japanese: consecutive character pairs instead of morphological analysis, so no MeCab or native extensions are needed. |
| DXF | AutoCAD Drawing Interchange Format. PureStrata reads ASCII DXF via group-code pairs (`src/purestrata/ingest/cad.py`). |
| STEP | ISO 10303-21 (Part 21) exchange format for 3D models, AP203/AP214/AP242. Parsed dependency-free in `src/purestrata/ingest/step.py`. |
| Part 21 | The textual encoding of STEP files: `#123 = ENTITY_NAME(args);` statements, with `HEADER` and `DATA` sections. |
| Assembly tree | Parent-child product structure recovered from `NEXT_ASSEMBLY_USAGE_OCCURRENCE` entities in a STEP file, with quantities. |
| Circular feature | A grouped hole/bore/pin summary: diameter, diameter in mm, count, and layers (`src/purestrata/ingest/geometry.py`). |
| Diameter callout | A drawing annotation like `DIA 25 H7` or `Ø10`; parsed into nominal diameter plus ISO fit class. |
| Fit class | ISO 286 tolerance class from a callout, e.g. `H7` (hole-basis) or `h6` (shaft-basis). Matched case-sensitively by `search_drawings`. |
| Title block | The identification region of a drawing (title, part number, material); also synthesized for STEP models from the root product. |
| MCP | Model Context Protocol: stdio JSON-RPC protocol for exposing tools to LLM clients, served by `purestrata serve`. |
| Tool schema | One of the ten tool specs rendered as raw JSON Schema, OpenAI function definitions, or Anthropic definitions (`src/purestrata/tools/schemas.py`). |
| `ToolExecutor` | The single class that executes tool calls against a corpus; every surface (MCP, API schemas, CLI, Python) calls it (`src/purestrata/tools/executor.py`). |
| tool_trace | A fine-tune export format: model-issued tool call, provenance-tagged tool result, then a grounded answer (`src/purestrata/export/finetune.py`). |
| CoT | Chain-of-thought fine-tune export: instruction, transparent reasoning scaffold grounded in the record's fields, and output. |
| Trusted publishing | PyPI's OIDC-based release flow: a tag push (workflow in `.github/workflows/pypi.yml`) publishes with no stored token. |
| Extra | Optional dependency group: `purestrata[pdf]` adds `pypdf`, `purestrata[mcp]` adds the `mcp` server library. |
| uv / uvx | Python package/project manager used for development (`uv sync`) and for running the CLI without installing (`uvx --from "purestrata[mcp]" ...`). |
