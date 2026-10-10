# Security

PureStrata runs inside the user's trust boundary. Its security story is not a set of defenses bolted onto a service but the consequences of how it is built: a local library with no required dependencies, no network calls in the library path, and parsers that read files as text.

## Trust model

The corpus is the user's own data. A `*.strata.jsonl` file is plain JSONL on a local disk, written by `write_chunks` in `src/purestrata/corpus.py` and read back by `Corpus.load`. Whoever can write those files controls what the tools return, exactly as whoever can write a CSV controls what a spreadsheet shows. PureStrata adds no privilege of its own: the library path opens files the caller names, and nothing else.

The consequence is that there is no server-side authorization model to review. Access control, if any, is filesystem access control on the machine holding the corpus.

## Attack surface: parsers and the absence of execution

The library path performs no network I/O and spawns no subprocesses. A scan of `src/purestrata/` shows only standard-library imports (`json`, `re`, `csv`, `hashlib`, `unicodedata`, `math`, `pathlib`, `collections`, `dataclasses`, `argparse`, `sys`, `typing`) apart from two optional extras that are imported inside the function that needs them:

- `from pypdf import PdfReader` inside `_extract_pdf_text` in `src/purestrata/ingest/manual.py`, which raises a `RuntimeError` telling the user to install `purestrata[pdf]` if the import fails.
- `from mcp.server.fastmcp import FastMCP` (mcp 1.x) with a fallback to `from mcp.server.mcpserver import MCPServer` (mcp 2.x) inside `build_mcp_server` in `src/purestrata/mcp_server.py`.

So an air-gapped install of the core imports no third-party code at all. That is the main attack-surface argument for the zero-dependency policy described in [Design decisions](background/design-decisions.md).

Every parser is a hand-written state machine or a regex over decoded text. `src/purestrata/ingest/cad.py` walks DXF group codes; `src/purestrata/ingest/step.py` splits ISO 10303-21 statements on `;` outside string literals; `src/purestrata/ingest/failures.py` uses the standard `csv` module; `src/purestrata/ingest/manual.py` parses Markdown line by line. None of them evaluates, imports, or executes file content. A DXF or STEP file cannot express code that PureStrata will run.

Files are read with `errors="replace"`, so malformed bytes become replacement characters rather than exceptions:

- `src/purestrata/ingest/cad.py:56` and `src/purestrata/ingest/manual.py:101` read text with `encoding="utf-8", errors="replace"`.
- `src/purestrata/ingest/failures.py:69` does the same for CSV and JSONL.
- `src/purestrata/ingest/step.py` decodes Part 21 `\X2\` and `\X4\` escapes as UTF-16-BE and UTF-32-BE with `errors="replace"`.

The practical risk of that choice is silent data loss on a mis-encoded file, not code execution: a garbled manual line is ingested as garbled text and stays visible in the record.

Tool arguments are validated rather than interpreted. `ToolExecutor.execute` in `src/purestrata/tools/executor.py` looks the tool name up in the schema registry and raises `ToolError` for anything unknown; numeric arguments go through `_as_float`; `top_k` is clamped to the range 1 to 50 by `_clamp_top_k`. There is no query language and no path taken from a tool argument.

## Optional extras are PyPI dependencies

`pypdf` and `mcp` are declared in `[project.optional-dependencies]` in `pyproject.toml`. Installing either extends the trusted set to those projects and their transitive dependencies, maintained by third parties. The core has no such exposure, which is why PDF and MCP support sit behind extras instead of being installed by default.

## The MCP boundary

`src/purestrata/mcp_server.py` exists to hand corpus content to another process. Its docstring states the frame: "Run `purestrata serve --corpus <dir>` and register the command in any Model Context Protocol client."

The transport is stdio, so there is no listening socket and no network reachability: the client must be able to spawn the command. But every tool result contains corpus text, metadata, and provenance, which means the connected client reads the corpus. Point the server only at clients you would give the corpus file itself. A local MCP host that forwards tool results to a hosted model turns that boundary into a data-sharing decision.

Errors are returned as JSON with an `error` key rather than raised, so a failed tool call does not kill the session:

```python
except ToolError as exc:
    return json.dumps({"error": str(exc)}, ensure_ascii=False)
```

A tool call that cannot find a record leaks only the id that was requested, not a directory listing.

## Network egress in the example

`examples/api_tool_use.py` is the only networked file in the repository, and it ships as an example rather than as library code. It takes a user-supplied endpoint and key from the environment:

| Variable | Default | Purpose |
| --- | --- | --- |
| `PURESTRATA_BASE_URL` | `https://api.x.ai/v1` | OpenAI-compatible base URL; `/chat/completions` is appended |
| `PURESTRATA_API_KEY` | empty; the script exits if unset | sent as `Authorization: Bearer <key>` |
| `PURESTRATA_MODEL` | `grok-4` | model id passed to the provider |
| `PURESTRATA_CORPUS` | `examples/corpus` next to the script | corpus directory to load |

It imports `json`, `os`, `sys`, `urllib.request`, and `pathlib`, and calls `urllib.request.urlopen` with a 120-second timeout. The loop executes returned tool calls locally with `ToolExecutor` and sends the results back to the configured endpoint as `role: "tool"` messages. So the endpoint sees corpus-derived text for every tool the model calls. It also prints each call to stdout (`-> name(args)`), which lands in terminal scrollback or logs.

The docstring names the boundary plainly: "Your data never leaves your machine except through the API you configure."

## Provenance as the audit control

The control that makes AI answers reviewable is not a permission check but `Provenance`, defined in `src/purestrata/types.py` as `doc_id`, `source_path`, and `locator`. Every chunk carries one, and `_result` in `src/purestrata/tools/executor.py` embeds it under the `source` key of every tool result. An answer traced back to the drawing, section, or spreadsheet row it came from is the audit trail for a manufacturing workflow. See [Records and provenance](primitives/records-and-provenance.md).

## Secrets in the repository

No credentials are stored in the repository. `.github/workflows/pypi.yml` and `.github/workflows/pages.yml` request `id-token: write` and authenticate to PyPI and GitHub Pages through OIDC, so no long-lived token exists in GitHub secrets for those jobs.

A scan of the tracked tree for `secret`, `api_key`, `token`, and `password` returns only the workflow `id-token` lines, the `PURESTRATA_API_KEY` variable name in `examples/api_tool_use.py` (the value is read from the environment, not committed), and unrelated identifier matches such as `tokenize` in `src/purestrata/search.py`. `.gitignore` excludes `.env`, which is the file a user would keep a key in.

## What this page does not claim

- It does not claim the parsers are free of bugs that a hostile file could trigger. They are hand-written state machines over untrusted bytes, and the `errors="replace"` behavior trades exceptions for degradation in text, not in geometry parsing.
- It does not claim the MCP client is trustworthy. The server is a data-sharing boundary by design.
- It does not claim any sandboxing. PureStrata runs with the permissions of the process that started it.
