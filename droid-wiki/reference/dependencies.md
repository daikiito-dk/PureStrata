# Dependencies

PureStrata installs with no required dependencies. `dependencies` is absent from the
`[project]` table in `pyproject.toml`; only two optional extras add third-party
packages, and both are imported lazily at the point of use.

## The policy in practice

- `pip install purestrata` pulls nothing. Manual (Markdown), DXF, STEP, CSV, and
  JSONL ingestion, search, the ten tools, the exports, and the CLI all run on the
  standard library.
- PDF ingestion and the MCP server are the only features that need a third-party
  package. They fail with an actionable `RuntimeError` naming the extra rather than
  an `ImportError` traceback.
- The two imports sit inside the functions that need them, so importing `purestrata`
  never touches either package.
- Development and CI use a separate dependency group, not runtime dependencies.

## Standard library modules used

Obtained with `rg '^import |^from ' src/purestrata -g '!*__init__*' | sort -u`:

| Module | Used for |
| --- | --- |
| `argparse` | CLI parser in `src/purestrata/cli.py` |
| `collections` (`Counter`, `defaultdict`) | Entity counts in `src/purestrata/ingest/cad.py`, `step.py`; corpus statistics in `src/purestrata/corpus.py` |
| `csv` | Failure-log reading in `src/purestrata/ingest/failures.py` |
| `dataclasses` | `Chunk`, `Provenance` in `src/purestrata/types.py`; `ToolSpec` in `src/purestrata/tools/schemas.py` |
| `hashlib` | `sha1` chunk ids in `src/purestrata/types.py` |
| `json` | Record serialization, tool results, CLI output |
| `math` | BM25-style IDF in `src/purestrata/search.py` |
| `pathlib` | Every file path in the package |
| `re` | Manual, DXF, STEP, and failure-log parsing |
| `sys` | stderr and `sys.exit` in `src/purestrata/cli.py` |
| `typing` | `Any` in tool argument coercion |
| `unicodedata` | NFKC normalization of search text in `src/purestrata/search.py` |
| `__future__` | `from __future__ import annotations` in every module |

No HTTP client, no database driver, no parsing library beyond the bundled adapters.

## Optional extras

| Extra | Requirement | Enables | Import site |
| --- | --- | --- | --- |
| `pdf` | `pypdf>=4.0` | PDF manuals and spec sheets | `_extract_pdf_text` in `src/purestrata/ingest/manual.py` |
| `mcp` | `mcp>=1.2` | `purestrata serve` | `build_mcp_server` in `src/purestrata/mcp_server.py` |

```bash
pip install "purestrata[pdf]"
pip install "purestrata[mcp]"
```

The MCP import handles both major versions of the SDK. `src/purestrata/mcp_server.py`
tries `from mcp.server.fastmcp import FastMCP` first (mcp 1.x) and falls back to
`from mcp.server.mcpserver import MCPServer` (mcp 2.x renamed the class). If neither
imports, it raises `RuntimeError` telling you to install the `mcp` extra.

## Development dependencies

The `dev` group in `pyproject.toml`:

| Package | Constraint | Role |
| --- | --- | --- |
| `pytest` | `>=8.0` | Test runner (`testpaths = ["tests"]`, `addopts = "-q"`) |
| `ruff` | `>=0.6` | Lint and format; `select = ["E", "F", "I", "UP", "B"]`, `line-length = 100` |
| `pypdf` | `>=4.0` | Exercises the PDF path in tests |
| `mcp` | `>=1.2` | Exercises the MCP server path in tests |

`uv sync --all-extras` installs the extras alongside the dev group. `uv.lock` is
committed to the repository, so CI and local runs resolve the same versions.

## Build and packaging

| Item | Value |
| --- | --- |
| Build backend | `hatchling` (`requires = ["hatchling"]`) |
| Wheel packages | `src/purestrata` |
| sdist includes | `src`, `tests`, `examples`, `README.md`, `LICENSE` |
| Lockfile | `uv.lock` (committed) |

## CI actions

Three workflows under `.github/workflows/`:

| Workflow | Trigger | Actions used |
| --- | --- | --- |
| `ci.yml` | push to `main`, pull requests | `actions/checkout@v4`, `astral-sh/setup-uv@v5`; runs `uv sync --all-extras`, `ruff check`, `ruff format --check`, `pytest` |
| `pypi.yml` | tags matching `v*` | `actions/checkout@v4`, `astral-sh/setup-uv@v5`, `pypa/gh-action-pypi-publish@release/v1`; publishes `dist/` with OIDC trusted publishing (`id-token: write`, no token secret) |
| `pages.yml` | push to `main` touching `site/**` or the workflow, plus manual dispatch | `actions/checkout@v4`, `actions/configure-pages@v5`, `actions/upload-pages-artifact@v3` (path `site`), `actions/deploy-pages@v4` |

## Runtime needs of the example

`examples/api_tool_use.py` imports `json`, `os`, `sys`, `urllib.request`, and
`pathlib` from the standard library, plus `Corpus`, `ToolError`, `ToolExecutor`, and
`openai_tools` from `purestrata`. It needs no optional extra and no HTTP client
package; `urllib.request` posts to the configured OpenAI-compatible endpoint. The
environment variables it reads are listed in [configuration](configuration.md).

## Related pages

[Configuration](configuration.md) for how the extras are selected at install time,
[record format](data-models.md) for what ingestion produces, and
[security](../security.md) for the network and data-handling implications of the
optional endpoint in `examples/api_tool_use.py`.
