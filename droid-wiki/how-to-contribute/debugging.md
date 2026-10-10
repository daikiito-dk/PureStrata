# Debugging

A runbook of failure modes that actually occur, each with the exact message or symptom and the fix. Error handling rules behind these messages are in [patterns and conventions](patterns-and-conventions.md).

## First moves

Two habits solve most reports quickly:

- Run the exact failing command in a terminal instead of through a client or script. The CLI prints errors to stderr with exit code 1, so a terminal shows what a GUI hides.
- For tool problems, bypass the LLM client with `purestrata call <tool> '<json>' --corpus <dir>` (`src/purestrata/cli.py`). It hits the same executor with the same arguments, so the result, or the identical `error:` line, appears with nothing else in the loop.

## `error: Corpus directory not found: <path>`

`Corpus.load` in `src/purestrata/corpus.py` raises `FileNotFoundError` with this message; the CLI prints it as `error: ...` to stderr and exits 1 (`src/purestrata/cli.py`). Cause: the `--corpus` path is wrong, or you relied on the default (`./corpus`) while the corpus lives elsewhere. Fix the path. In MCP client configs, remember that clients do not expand `~`; use absolute paths (`docs/MCP.md`).

## `error: file not found: <path>`

Every ingest command (`ingest-manual`, `ingest-dxf`, `ingest-step`, `ingest-failures`) checks each input path in `_run_ingest` (`src/purestrata/cli.py`) before parsing, and prints this line to stderr with exit 1. Cause: a typo, a shell glob that matched nothing and got passed literally, or a path from a different working directory. In scripts, pass absolute paths.

## `The MCP server requires the 'mcp' extra. Install it with: pip install 'purestrata[mcp]'`

`RuntimeError` raised by `build_mcp_server` in `src/purestrata/mcp_server.py` when the `mcp` package is missing. Fixes: `pip install "purestrata[mcp]"`; in the repo, `make setup` (the dev dependency group includes `mcp`); under `uvx`, the `--from` argument must be `purestrata[mcp]`, not bare `purestrata`.

## MCP client times out on the first launch

`uvx` downloads the package on first run, which can exceed the client's connection timeout. Three fixes, all documented in `docs/MCP.md`: run the exact command once in a terminal to warm the cache, install it as a tool (`uv tool install "purestrata[mcp]"`, starts instantly), or raise the client's timeout, for example `connectTimeout: 60000` in Droid's `.factory/mcp.json`.

## The MCP server never appears in a GUI client

Claude Desktop and similar GUI apps may not see your shell `PATH`, so `uvx` or `purestrata` resolves to nothing even though it works in a terminal. Fix: put the absolute path of the command in the client config, found with `which uvx` or `which purestrata` (`docs/MCP.md` documents this alongside the config examples). To confirm the server itself is healthy, run `purestrata serve --corpus <dir>` in a terminal; it should start and wait silently for input, and Ctrl+C stops it.

## MCP tool returns `{"error": "..."}`

That is a `ToolError` caught by the server's `run()` (`src/purestrata/mcp_server.py`): invalid arguments, an out-of-range filter, or a missing record id. Reproduce locally without any MCP client:

```bash
purestrata call get_failure_case '{"case_id": "does-not-exist"}' --corpus examples/corpus
```

The CLI hits the same `ToolError`, prints the identical message as `error: ...`, and exits 1 (`tests/test_cli.py` covers this path). If the reproduction succeeds but the client still errors, the arguments the client sends are not what you think; log the exact `tools/call` payload.

## Search returns nothing

Work through three checks:

1. `purestrata inspect --corpus <dir>`: is the corpus loaded at all, and are the expected record kinds there?
2. BM25 drops zero-score matches (`SearchIndex.search` in `src/purestrata/search.py`), so a query sharing no token with any record returns empty rather than ranking noise. Empty means "no match", not "broken".
3. Japanese text is tokenized into character bigrams after NFKC normalization and casefolding. A query must share bigrams with the stored text, so try a shorter substring. Common function words (です, ます, する, the, this) are stop words and never match anything on their own.

## `error: PDF ingestion requires the 'pdf' extra. Install it with: pip install 'purestrata[pdf]'`

Raised by `_extract_pdf_text` in `src/purestrata/ingest/manual.py` when `pypdf` is missing. Install the extra; in the repo, `make setup` already includes it via the dev group.

## DXF ingest succeeds but the drawing record is nearly empty

Binary DXF is not supported. The reader in `src/purestrata/ingest/cad.py` handles ASCII DXF only (its module docstring says so), and per the parser convention it never raises on partial data, so a binary file degrades into a chunk with empty layers, zero entity counts, or nonsense text instead of an error. Fix: re-export ASCII DXF from the CAD application.

## STEP bounds are larger than the model

Expected behavior. Bounds are the extent of all `CARTESIAN_POINT` entities, not an evaluated solid boundary; the `src/purestrata/ingest/step.py` docstring notes they can slightly exceed the solid itself. The reader does not evaluate B-rep topology by design, so treat bounds as an approximation when filtering.

## CI fails on `ruff format --check`

Formatting drift between your tree and `ruff format`. Run `make format` locally (it also runs `ruff check --fix` for auto-fixable lint), commit, and push. `make lint` runs both checks exactly as CI does, so a green local lint means a green CI lint.

## Tests skip locally but run in CI

`pytest.importorskip("mcp")` skips extra-dependent tests when the extras are missing from the environment. CI runs `uv sync --all-extras`, so they always run there. Locally, `make setup` installs both `pypdf` and `mcp` through the dev group; if you skipped setup, run it.

## Related pages

- [Testing](testing.md) for how the suite exercises these paths.
- [MCP server](../features/mcp-server.md) and [full-text search](../features/full-text-search.md) for the features behind these errors.
- [Background: pitfalls](../background/pitfalls.md) for the traps that motivated these designs.
