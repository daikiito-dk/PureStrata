# Tooling

## uv

uv is the single tool on a development machine. It owns the environment, runs every command, and powers no-install usage for end users.

- `uv sync` creates and updates `.venv` from `pyproject.toml` plus the committed `uv.lock` at the repo root.
- `uv run <command>` executes anything inside `.venv`. Every Makefile target is wrapped in it, so the environment is never activated by hand.
- `uv lock` regenerates the lockfile after a version or dependency change. The lockfile records the project's own version too, which is why the release process runs it ([development workflow](development-workflow.md)).
- `uv tool install "purestrata[mcp]"` installs the CLI as a standalone daily-use tool, outside any project environment (`docs/MCP.md` recommends this for regular users).
- `uvx --from "purestrata[mcp]" purestrata serve --corpus <dir>` runs it with no install at all; the first launch downloads packages, so expect a short delay.

`.python-version` pins the dev interpreter (3.12) while `pyproject.toml` keeps `requires-python = ">=3.10"` as the compatibility floor.

Lockfile discipline: `uv.lock` is committed and never edited by hand. After changing `pyproject.toml` (version, extras, dev group), run `uv lock` and commit the result; CI, the release workflow, and every other machine sync from the lockfile, so drifting it desynchronizes all of them.

## pyproject.toml

What to know, section by section:

- Build backend: `hatchling`. The wheel ships `src/purestrata`; the sdist also includes `tests/` and `examples/`.
- Console script: `purestrata = "purestrata.cli:main"`. This is what `make demo`, `uvx`, and MCP clients launch.
- `[project.optional-dependencies]`: `pdf = ["pypdf>=4.0"]`, `mcp = ["mcp>=1.2"]`. Required dependencies: none. This is the zero-dependency policy made mechanical.
- `[dependency-groups] dev`: `pytest`, `ruff`, plus `pypdf` and `mcp`, so a plain `uv sync` yields a fully testable environment.
- `[tool.ruff]`: `line-length = 100`, `select = ["E", "F", "I", "UP", "B"]`.
- `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `addopts = "-q"`.

## Makefile

| Target | What it runs |
| --- | --- |
| `make setup` | `uv sync` |
| `make lint` | `ruff check src tests` plus `ruff format --check src tests` |
| `make format` | `ruff format src tests` plus `ruff check --fix src tests` |
| `make test` | `pytest` |
| `make demo` | ingest all bundled samples into `examples/corpus`, then `inspect` plus two searches (English and Japanese) |
| `make clean` | delete `examples/corpus` and `examples/output` |

## GitHub workflows

Three files in `.github/workflows/`, all running on `ubuntu-latest`:

- `ci.yml`, on every push to `main` and every pull request: `uv sync --all-extras`, `ruff check`, `ruff format --check`, `pytest`. This is the gate the definition of done refers to; a red run blocks landing. It is the only workflow that runs on ordinary commits.
- `pypi.yml`, on every tag matching `v*`: the same install, `ruff check`, and `pytest`, then `uv build` and publication via `pypa/gh-action-pypi-publish` with OIDC trusted publishing (`id-token: write`, no PyPI token stored). Tests run before the build, so a broken version never reaches the index.
- `pages.yml`, on pushes to `main` that touch `site/**` or the workflow file itself (path-filtered), plus manual `workflow_dispatch`: uploads `site/` as the Pages artifact and deploys to GitHub Pages, with a concurrency group that cancels superseded deploys.

Build artifacts never enter the repo: `.gitignore` excludes `dist/`, `examples/corpus/`, `examples/output/`, `.venv/`, and tool caches.

## Why one tool

uv replaces the usual pile: no `requirements.txt`, no separate virtualenv step, no dependency pinning tool. The lockfile makes every environment reproducible (CI and the PyPI build sync from the same `uv.lock`), `uv run` removes the activate-then-forget failure mode, and `uvx` gives end users a no-install path. The dev group in `pyproject.toml` keeps the test toolchain versioned alongside the code instead of in a second file.

The raw equivalents, for when the Makefile is not at hand:

```bash
uv sync --all-extras        # what CI runs: dev group plus the pdf and mcp extras
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest
```

## The site

`site/` is one page, `site/index.html`, with no build step: English content first, then a matching Japanese section, the same order as `README.md` and `docs/MCP.md`. It deploys to the project site through `pages.yml`. Because the workflow is path-filtered, ordinary code pushes do not redeploy it, and the release process only touches it when the embedded version in its JSON-LD metadata needs a bump ([development workflow](development-workflow.md)).

## Related pages

- [Development workflow](development-workflow.md) puts these tools in the day-to-day loop.
- [Testing](testing.md) covers what `pytest` runs.
- [Dependencies](../reference/dependencies.md) explains what the extras are for, and [deployment](../deployment.md) covers the release pipeline end to end.
