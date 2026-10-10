# Configuration

PureStrata has no configuration file. Everything is set at call time: command-line
flags, the choice of optional extras, tool arguments, and a small set of environment
variables read by the example script. This page is the exhaustive list.

## CLI reference

Entry point: `purestrata = "purestrata.cli:main"` (`pyproject.toml`). The parser is
built in `src/purestrata/cli.py` with argparse, so `--help` works on the program and
on each subcommand. A subcommand is required (`required=True` on the subparsers).

| Command | Positional args | Flags | Defaults |
| --- | --- | --- | --- |
| `ingest-manual` | `paths...` (one or more file paths) | `--out <dir>` (required) | none |
| `ingest-dxf` | `paths...` (one or more file paths) | `--out <dir>` (required) | none |
| `ingest-step` | `paths...` (one or more file paths) | `--out <dir>` (required) | none |
| `ingest-failures` | `paths...` (one or more file paths) | `--out <dir>` (required) | none |
| `search` | `query` | `--corpus <dir>`, `--kind <kind>`, `--top-k <int>` | `--corpus corpus`, `--kind` unset, `--top-k 5` |
| `inspect` | none | `--corpus <dir>` | `--corpus corpus` |
| `tools` | `format` (`openai`, `anthropic`, `json`) | none | none |
| `export` | `format` (`chat`, `tool_trace`, `cot`) | `--corpus <dir>`, `--out <path>` (required), `--limit <int>` | `--corpus corpus`, `--limit` unset |
| `call` | `tool`, `arguments` (optional JSON object, default `{}`) | `--corpus <dir>` | `--corpus corpus` |
| `serve` | none | `--corpus <dir>` | `--corpus corpus` |

Notes on the ingest commands:

- The four ingest commands share one code path (`_run_ingest` in
  `src/purestrata/cli.py`). Each input file is parsed by its adapter
  (`src/purestrata/ingest/manual.py`, `cad.py`, `step.py`, `failures.py`) and written
  as a separate `<doc_id>.strata.jsonl` file inside `--out`.
- `--out` is created if it does not exist (`write_chunks` in `src/purestrata/corpus.py`).
- Ingest commands have no `--corpus` flag; output location is always `--out`.
- A missing input file prints `error: file not found: <path>` to stderr and returns 1,
  stopping the run at that file.
- On success the command prints one line per file (`<path>: <n> records -> <out_path>`)
  and a `Total: <n> records written to <out>` line.

Notes on the other commands:

- `--corpus` defaults to the relative path `corpus`, i.e. `./corpus` in the current
  working directory. `Corpus.load` raises `FileNotFoundError` if the directory does
  not exist, which the top-level handler prints as `error: ...` with exit code 1.
- `--kind` on `search` accepts only the six record kinds (argparse `choices`).
- `--top-k` on `search` is an unclamped integer at the CLI layer; the executor clamp
  applies to tool calls. See "Tool-level defaults" below.
- `export --limit` is unset by default, meaning every available record.
- `call` parses `arguments` with `json.loads` and requires a JSON object; a list or
  scalar raises `ValueError`, printed as `error: arguments must be a JSON object`.
- `tools` prints schemas and takes no `--corpus`; `call` reads a corpus and prints one
  tool result as indented JSON.
- Exit codes: 0 on success, 1 on `FileNotFoundError`, `ToolError`, `RuntimeError`, or
  `ValueError`, 2 on argparse errors.

## Optional extras

Core installs with zero required dependencies. Two extras add capability:

| Extra | Command | Provides | Where it is imported |
| --- | --- | --- | --- |
| `pdf` | `pip install "purestrata[pdf]"` | `pypdf>=4.0` | lazily inside `_extract_pdf_text` in `src/purestrata/ingest/manual.py` |
| `mcp` | `pip install "purestrata[mcp]"` | `mcp>=1.2` | inside `build_mcp_server` in `src/purestrata/mcp_server.py` |

Without the `pdf` extra, ingesting a PDF raises
`RuntimeError: PDF ingestion requires the 'pdf' extra. Install it with: pip install 'purestrata[pdf]'`.
Without the `mcp` extra, `purestrata serve` raises the equivalent message naming the
`mcp` extra. Markdown manuals, DXF, STEP, CSV, and JSONL ingestion need no extras.

## Tool-level defaults

Tool parameter schemas live in `src/purestrata/tools/schemas.py`; execution and
clamping live in `src/purestrata/tools/executor.py`.

| Tool | `top_k` default | Notes |
| --- | --- | --- |
| `search_documents` | 5 | `kind` filter optional |
| `get_safety_notices` | 10 | |
| `get_procedure` | not applicable | takes `procedure_id` |
| `search_parts` | 10 | |
| `list_drawings` | not applicable | no parameters |
| `get_drawing` | not applicable | takes `drawing_id` |
| `search_drawings` | 10 | filters: `min_diameter`, `max_diameter`, `fit`, `material`, `cad_format` |
| `search_failure_cases` | 5 | optional `equipment` filter |
| `get_failure_case` | not applicable | takes `case_id` |
| `list_corpus` | not applicable | no parameters |

`_clamp_top_k(value, default)` in `src/purestrata/tools/executor.py` returns the
default for any non-integer value and otherwise clamps to the range 1..50
(`max(1, min(top_k, 50))`). `_TOP_K_PARAM` in `src/purestrata/tools/schemas.py`
advertises the same range to models with `"minimum": 1, "maximum": 50`. The kind
filter on `search_documents` is an enum of the six record kinds; the CLI `--kind`
flag offers the same choices.

## MCP client registration

`purestrata serve --corpus <dir>` runs the MCP server over stdio. Registration JSON
for Claude Desktop, Claude Code, Factory Droid, Cursor, and VS Code is in
`docs/MCP.md`; use that file as the source of truth rather than copying blocks from
here. The no-install form of the launch command is:

```bash
uvx --from "purestrata[mcp]" purestrata serve --corpus /abs/path/to/corpus
```

For daily use, `uv tool install "purestrata[mcp]"` once and then set the client's
`command` to the absolute path of `purestrata` with
`["serve", "--corpus", "/abs/path/to/corpus"]`. Two constraints from `docs/MCP.md`:
MCP clients do not expand `~`, and GUI apps may not see your shell `PATH`, so use
absolute paths for both the command and the corpus.

## Environment variables

The library and CLI read no environment variables. The only reader in the repository
is `examples/api_tool_use.py`, which reads four:

| Variable | Default in the script | Purpose |
| --- | --- | --- |
| `PURESTRATA_BASE_URL` | `https://api.x.ai/v1` | OpenAI-compatible base URL; `/chat/completions` is appended |
| `PURESTRATA_API_KEY` | `""` | Bearer token; the script exits with code 1 and prints `Set PURESTRATA_API_KEY to run this example.` when empty |
| `PURESTRATA_MODEL` | `grok-4` | Model id sent in the request payload |
| `PURESTRATA_CORPUS` | `<repo>/examples/corpus` | Corpus directory loaded by `ToolExecutor` |

`examples/quickstart.py` reads no environment variables.

## Related pages

[Record format](data-models.md) for what the ingest commands write,
[dependencies](dependencies.md) for the extras in packaging context,
[CLI](../features/cli.md) and [MCP server](../features/mcp-server.md) for
walkthroughs, and [deployment](../deployment.md) for running a corpus in production.
