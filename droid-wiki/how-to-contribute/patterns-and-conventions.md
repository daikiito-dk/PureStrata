# Patterns and conventions

How the codebase is written. Read this before changing anything; the patterns below repeat across nearly every module.

Active contributors: DK

## Data model conventions

- Everything ingested becomes a `Chunk` built with `new_chunk()` (`src/purestrata/types.py`); never construct `Chunk` directly with a hand-made id.
- Chunk ids are deterministic: SHA-1 over `doc_id::kind::locator`, truncated to 12 hex chars. Consequence: re-ingesting an unchanged file overwrites the same ids, which keeps ingestion idempotent. If you add a record type, reuse the `locator` scheme (e.g. `row 3`, `section 2.1`, `model`) rather than inventing counters.
- `to_dict()`/`from_dict()` pairs on dataclasses are the only serialization boundary. Every written record carries `"schema": "purestrata/v1"`; loaders raise on foreign schema prefixes. Bump the prefix only with a real format break, not for additive metadata changes.
- Record kinds are string constants in `src/purestrata/types.py` (`MANUAL_SECTION` … `FAILURE_CASE`). Do not scatter string literals; import the constants.
- Structured data goes in `chunk.metadata` (JSON-serializable dict, keys documented per kind); human-readable searchable text goes in `chunk.text`. Tools filter on metadata and rank on text, so both matter.

## Provenance discipline

- Every chunk must carry a `Provenance` with a non-empty locator that a human can read. If you cannot name where a record came from, the record is not finished.
- Every new tool must embed the chunk's provenance in its result via `_result()` in `src/purestrata/tools/executor.py`. Results without `source` are a bug.

## Error handling

- Invalid tool arguments or missing records raise `ToolError` from `src/purestrata/tools/executor.py`. The MCP server catches `ToolError` and returns `{"error": ...}` as the tool text; the CLI catches it, prints to stderr, and exits 1.
- Library-level mistakes (unusable input, missing extras) raise built-ins: `ValueError`, `RuntimeError`, `FileNotFoundError`. The CLI maps those to `error: ...` plus exit code 1 (`src/purestrata/cli.py`).
- Parsers never raise on partial data. DXF/STEP adapters skip entities they do not understand and always produce at least one chunk. Prefer degraded output plus honest metadata over exceptions.
- Never return raw `None` where a caller expects a dict: tools return `{"filters": ..., "results": []}` style envelopes.

## Zero-dependency policy

- The core package (`src/purestrata/` except the MCP server) imports only the standard library. New parsing features must not add dependencies; hand-roll the parser and keep it in `src/purestrata/ingest/`.
- Optional capability = optional extra in `pyproject.toml` (`pdf` → `pypdf`, `mcp` → `mcp`) with a runtime error that tells the user the exact `pip install` line (see `src/purestrata/mcp_server.py`).
- Third-party API drift is handled at import time: the MCP server tries `mcp.server.fastmcp.FastMCP` (1.x), then `mcp.server.mcpserver.MCPServer` (2.x), and only then raises.

## Text handling

- `clean_inline()` collapses all whitespace into single spaces; `normalize_block()` preserves paragraph breaks (`src/purestrata/pipeline/clean.py`). Cleaning runs after structural parsing so layout is never destroyed.
- All text is normalized with NFKC and casefolded at tokenize time (`src/purestrata/search.py`); store raw text, normalize at the edges.
- Japanese and English are treated as equals throughout: search tokenizers, column aliases in `src/purestrata/ingest/failures.py`, and severity maps all accept both languages.
- Files are read as UTF-8 (`errors="replace"` where CAD exports may be dirty); CSV opens with `utf-8-sig` to survive Excel BOMs.

## Naming and structure

- Ingest adapters are public `ingest_<thing>(path, doc_id=None) -> list[Chunk]` functions exported from `src/purestrata/__init__.py`; helpers are underscore-private.
- Tool implementation methods are `_tool_<name>` on `ToolExecutor`, mirroring a `ToolSpec` in `src/purestrata/tools/schemas.py`. A schema without a handler raises at call time; both lists must stay in sync (the test `test_ten_tools_defined` enforces the count).
- Module docstrings explain the module's contract in 2-5 lines; function docstrings are one line unless behavior is surprising.
- `from __future__ import annotations` at the top of every module; modern union syntax (`str | None`) everywhere.

## Testing conventions

- Fixtures over the bundled sample data in `tests/conftest.py`; the shared `corpus` fixture ingests both manuals, the DXF, the STEP, and the CSV.
- Integration tests drive real processes and real protocols: `tests/test_mcp.py` runs `purestrata serve` as a subprocess and performs a genuine JSON-RPC initialize/tools-list/tools/call handshake.
- `pytest.importorskip("mcp")` guards optional-extra tests so the suite passes without extras installed.
- Keep the suite fast (currently < 1 s); do not add sleeps, network calls, or large fixtures.

## Style

- Ruff with `select = ["E", "F", "I", "UP", "B"]`, line length 100, and `ruff format` for layout (`pyproject.toml`). Run `make lint` and `make format` before committing.
- Documentation is bilingual: English first, Japanese section second in `README.md` and `docs/MCP.md`. Keep both in sync when you change user-facing behavior.
