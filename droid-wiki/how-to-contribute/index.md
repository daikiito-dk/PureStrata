# Contributing

PureStrata is small on purpose: about 2,900 source lines under `src/purestrata/` and roughly 900 more under `tests/`. One person can hold the whole design in their head, and everything is in scope: ingestion adapters, search, tools, the MCP server, the CLI, exports, docs, and the site. Development happens in Droid sessions, lands as direct commits on `main`, and CI is the gate. There is no review queue to wait behind.

## Picking up work

There is no issue triage. The practical way to find work is the code and the docs themselves. The areas, with their entry points:

- Ingestion adapters: `src/purestrata/ingest/manual.py`, `src/purestrata/ingest/cad.py`, `src/purestrata/ingest/step.py`, `src/purestrata/ingest/failures.py`
- Search: `src/purestrata/search.py` (BM25 over Latin words and CJK character bigrams)
- Tools: `src/purestrata/tools/schemas.py` and `src/purestrata/tools/executor.py` (ten tools exposed over four front ends)
- MCP server: `src/purestrata/mcp_server.py`
- CLI: `src/purestrata/cli.py`
- Fine-tuning exports: `src/purestrata/export/finetune.py`
- Docs: `README.md` (English then Japanese), `docs/MCP.md`, `site/index.html`

Read [patterns and conventions](patterns-and-conventions.md) before writing code. It records the rules this codebase is actually written to: `ToolError` for tool-level failures, a standard-library-only core, provenance embedded in every result, deterministic chunk ids.

## Before the first change

Verify the loop works end to end on your machine before touching anything:

```bash
git clone https://github.com/daikiito-dk/PureStrata
cd PureStrata
make setup     # uv sync: pytest, ruff, and both extras (pypdf, mcp)
make test      # 79 passing in under 1 second
make demo      # full ingest of the bundled samples, then two searches
```

If any of those three fails, fix the environment first ([tooling](tooling.md), [debugging](debugging.md)); otherwise every later failure is ambiguous. `make demo` writes to `examples/corpus`, which is gitignored, so it never pollutes a commit.

## Definition of done

A change is finished only when all of these hold:

1. `make lint` is clean: `ruff check` plus `ruff format --check`, line length 100, rules `E`/`F`/`I`/`UP`/`B` in `pyproject.toml`.
2. `make test` passes. The suite currently runs 79 tests in under a second; a change that slows it down is not done.
3. User-facing changes update both halves of `README.md`: the English section and the `## 日本語` section. Changes to MCP setup update `docs/MCP.md` the same way.
4. No new required dependencies in the core. New parsing capability is hand-rolled inside `src/purestrata/ingest/`; anything that truly needs a third-party library becomes an optional extra in `pyproject.toml` (`pdf`, `mcp`).
5. Provenance survives: every tool result still embeds `source` with the file path and locator, invalid arguments still raise `ToolError`, and written records keep the `purestrata/v1` schema prefix.

"User-facing" means anything a person can observe: CLI commands and their output, tool schemas (`src/purestrata/tools/schemas.py`), the corpus record format, ingestion behavior, and MCP setup. Internal refactors need no docs update beyond docstrings.

## How changes land

The git history is the style reference (`git log --pretty=format:'%h %ad %s%n%b' --date=iso`):

- Subject: one imperative line, no trailing period. Examples from this repo: `Add bilingual GitHub Pages intro site and deploy workflow`, `Fix tool-count docstring and ignore local wiki artifacts`, `Release 0.2.0`.
- Body: present only when the change needs explanation. The house pattern is a short paragraph stating what the commit delivers, then one bullet per area (see the STEP ingestion commit `63fc38b`).
- Trailer: `Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>` on every commit, because development happens in Droid sessions and the trailer records that.
- CI (`.github/workflows/ci.yml`) runs on every push to `main` and every pull request and must be green. It mirrors the local loop: `uv sync --all-extras`, `ruff check`, `ruff format --check`, `pytest`.

If you work from a fork and open a pull request, the same rules apply unchanged, and the release process in [development workflow](development-workflow.md) stays with the maintainer. Outside contributions are welcome as pull requests against `main` (the default branch); a short issue first is fine for anything that changes the corpus format or the tool schemas.

## Pages in this section

- [Development workflow](development-workflow.md): the local loop, commit conventions, and the tag-based release process.
- [Testing](testing.md): fixtures over the bundled samples, the real stdio MCP handshake, and how to test a new tool.
- [Debugging](debugging.md): a runbook of real failure modes with their exact messages and fixes.
- [Tooling](tooling.md): uv, `pyproject.toml`, the Makefile, and the three GitHub workflows.
- [Patterns and conventions](patterns-and-conventions.md): the code-level rules, written down once.

New to the project? Start with [the overview](../overview/index.md) and [getting started](../overview/getting-started.md). For the reasoning behind the rules, see [design decisions](../background/design-decisions.md).
