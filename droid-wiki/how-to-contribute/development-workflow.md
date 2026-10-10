# Development workflow

## The local loop

```bash
git clone https://github.com/daikiito-dk/PureStrata
cd PureStrata
make setup    # uv sync: .venv with the dev group (pytest, ruff, pypdf, mcp)
```

Edit code under `src/purestrata/` or tests under `tests/`, then work the loop:

```bash
make format   # ruff format + ruff check --fix, for when lint complains
make lint     # ruff check + ruff format --check, exactly what CI runs
make test     # pytest, 79 tests, under 1 second
make demo     # end-to-end eyeball pass over the bundled samples
```

`make demo` is the eyeball step. It drives the real CLI over real data: `ingest-manual` on both sample manuals (English and Japanese), `ingest-dxf`, `ingest-step`, `ingest-failures` into `examples/corpus`, then `purestrata inspect` and two searches (English and Japanese). Unit tests cover components; `make demo` covers the commands a user actually types, in sequence, with the output a user actually sees. Both `examples/corpus` and `examples/output` are gitignored, so the demo never leaks into a commit. `make clean` removes them anyway.

Every Makefile target runs through `uv run`, so the virtual environment is never activated by hand. `.python-version` pins the dev interpreter (3.12) while `pyproject.toml` keeps `requires-python = ">=3.10"` as the floor. Run `make lint` and `make test` before every commit; CI runs the same commands and nothing else.

## Commit conventions

The history is the spec. Verify with `git log --pretty=format:'%h %ad %s%n%b' --date=iso`:

- One-line imperative subject, no trailing period:
  - `Add bilingual GitHub Pages intro site and deploy workflow`
  - `Fix tool-count docstring and ignore local wiki artifacts`
  - `Release 0.2.0`
- Body only when the change needs it. The house pattern (see the STEP ingestion commit `63fc38b`) is one short paragraph stating what the commit delivers, then one bullet per feature area:

```text
Add STEP ingestion, drawing geometry search, call CLI, and MCP setup guide
- Dependency-free STEP (ISO 10303-21) reader: header, products, assembly
  tree with quantities, units, cylindrical features, bounds, \X2\ decoding
- DXF circular features (hole diameters, mm-normalized) and fit callouts
  (DIA 25 H7, Ø, %%C)
...
Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>
```

- Trailer on every commit: `Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>`. Work happens in Droid sessions, and the trailer is how the repo records that.
- Commits land on `main` directly. CI on push is the gate.

## What CI does when you push

`.github/workflows/ci.yml` runs on `ubuntu-latest` for every push to `main` and every pull request, in this order: `actions/checkout`, `astral-sh/setup-uv`, then `uv sync --all-extras`, `uv run ruff check src tests`, `uv run ruff format --check src tests`, `uv run pytest`. That is the same sequence as `make setup` + `make lint` + `make test`, and the package set is identical too: the dev group installed by plain `uv sync` already contains `pypdf` and `mcp`, so `--all-extras` adds nothing new. A green local run predicts a green CI run. If lint or format fails remotely but passes locally, your lockfile is stale or your ruff differs; run `make format`, commit, and push again.

## Release process

A release is a version-bump commit plus an annotated tag. The 0.2.0 release (commit `74d9d8f`, tag `v0.2.0`) touched exactly three files, which gives the checklist:

1. Bump `version` in `pyproject.toml`.
2. Bump `__version__` in `src/purestrata/__init__.py`. The two must match.
3. Run `uv lock`; the lockfile records the project's own version, so it changes too.
4. Commit with subject `Release X.Y.Z`.
5. Create an annotated tag carrying a one-line summary of what the version delivers, in the style of v0.2.0:
   `git tag -a vX.Y.Z -m "PureStrata X.Y.Z: STEP ingestion, drawing geometry search, call CLI, MCP setup guide"`
6. `git push && git push --tags`.

Pushing the tag fires `.github/workflows/pypi.yml`: `uv sync --all-extras`, `ruff check`, `pytest`, `uv build`, then publication to PyPI through OIDC trusted publishing (`id-token: write`, no stored token). The tests run before the build, so a red suite blocks the release instead of shipping a broken wheel. The pipeline is described end to end in [deployment](../deployment.md); the workflow files themselves are covered in [tooling](tooling.md).

One extra check: `site/index.html` embeds the version in its JSON-LD `softwareVersion` field. If it has drifted from the new release, update it in the same cycle; the site redeploys on its own via `.github/workflows/pages.yml` (see [tooling](tooling.md)).

## Related pages

- [Testing](testing.md) for what `make test` actually runs and how to extend it.
- [Patterns and conventions](patterns-and-conventions.md) for the rules to apply while editing.
- [Getting started](../overview/getting-started.md) for the user-side view of the same commands.
