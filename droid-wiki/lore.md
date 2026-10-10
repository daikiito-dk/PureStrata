# Lore

PureStrata's entire recorded history fits on one day, 2026-10-10 Japan Standard Time (UTC+9). Four eras, bounded by one morning commit, a burst of mid-afternoon work, and a four-minute cleanup at the end.

## Timeline

| Time (JST) | Event |
| --- | --- |
| 08:09:01 | `1785130` Initial release: open data layer for manufacturing AI |
| 08:46:12 | `f1c4778` PyPI trusted publishing workflow, tagged `v0.1.0` |
| 14:42:56 | `63fc38b` STEP ingestion, drawing geometry search, call CLI, MCP guide (+1,156 lines) |
| 14:45:52 | `74d9d8f` Release 0.2.0, tagged `v0.2.0` |
| 14:57:23 | `4e04b6a` Bilingual GitHub Pages site and deploy workflow |
| 15:01:14 | `65a4fd2` Docstring fix and `.gitignore` update |

## Era 1: Initial release (08:09)

Commit `1785130` lands at 08:09:01 and is not a skeleton. It is the whole product in one commit: the three ingestion parsers (Markdown/PDF manuals, ASCII DXF drawings, CSV/JSONL failure logs), the portable `*.strata.jsonl` corpus format, a dependency-free BM25 search with Japanese character-bigram tokenization, nine provider-neutral tool schemas, and the exporters for chat, tool-trace, and chain-of-thought fine-tuning data.

The CLI ships with it: `ingest-manual`, `ingest-dxf`, `ingest-failures`, `inspect`, `search`, `tools`, `export`, `serve`.

Around the code sit a 202-line bilingual English/Japanese README, a 21-line MIT license, a 17-line GitHub Actions CI workflow, and a 62-test suite. The commit message ends on its own scorecard: "62 tests, ruff clean, GitHub Actions CI."

Sample data ships too: an English lathe maintenance manual, a Japanese CNC press maintenance manual, a DXF bracket drawing, and a plant failure log, so every command has something to run against out of the box.

## Era 2: Trusted publishing (08:46)

Thirty-seven minutes later, `f1c4778` adds `.github/workflows/pypi.yml`, 22 lines, and the repository's first tag: `v0.1.0`, on that same commit.

The workflow publishes to PyPI through OIDC trusted publishing whenever a `v*` tag is pushed, and it runs ruff and pytest before the package is built, so, in the words of the commit message, "broken versions never reach the index." A tag push is the only trigger, which is why the feature commit and the first release are the same commit.

## Era 3: STEP and geometry (14:42)

After nearly six quiet hours, the day's largest commit arrives at 14:42:56. `63fc38b` adds 1,156 lines in one go.

The centerpiece is a dependency-free STEP (ISO 10303-21) reader at `src/purestrata/ingest/step.py`, 383 lines covering headers, products, assembly trees with quantities, units, cylindrical features, bounds, and `\X2\` decoding for Japanese names. A new geometry module (94 lines) also pulls hole diameters and fit callouts like `DIA 25 H7` out of DXF. A sample STEP assembly, `examples/data/cad/bracket_assy_mk3.step`, ships with the code so the reader has something real to parse.

The commit then wires the tenth tool, `search_drawings`, across every surface, adds a `purestrata call <tool> '<json>'` CLI command, and writes `docs/MCP.md`, a 152-line setup guide for Claude Desktop, Claude Code, Droid, Cursor, and VS Code in English and Japanese. The test suite grows from 62 to 79, including a real stdio JSON-RPC MCP handshake.

Three minutes later, at 14:45:52, `74d9d8f` bumps the version to 0.2.0 and tags it `v0.2.0`. The day's two releases are 5 hours 59 minutes apart.

## Era 4: The site (14:57)

At 14:57:23, `4e04b6a` adds `site/index.html`, a 341-line bilingual English/Japanese one-pager, and `.github/workflows/pages.yml`, 37 lines, to deploy it. The project site is https://daikiito-dk.github.io/PureStrata/, and the page carries the three-bar mark that answers the project's name.

Four minutes after that, at 15:01:14, the recorded history ends with `65a4fd2`: a one-line fix to a docstring that still counted nine tools when there were ten, plus one line added to `.gitignore`. The day closes by correcting its own tool count.

## Longevity

Nothing is deprecated. At one day old nothing could be, and nothing has been marked for removal.

The longest-standing code is also the load-bearing code. `types.py`, `corpus.py`, and `search.py` have not changed since 08:09:01; they survived the STEP feature, the version bump, and the site launch untouched. Everything added after the initial release (the STEP reader, `geometry.py`, `search_drawings`, the site) sits around those modules rather than replacing them.
