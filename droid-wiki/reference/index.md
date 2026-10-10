# Reference

Lookup pages for the parts of PureStrata you need exact answers about: how it is
configured, what a record on disk contains, and what it depends on.

## Pages

- [Configuration](configuration.md): the complete CLI surface generated from
  `src/purestrata/cli.py`, the optional extras, tool-level defaults and clamping,
  MCP client registration, and the environment variables read by
  `examples/api_tool_use.py`.
- [Record format](data-models.md): the `*.strata.jsonl` on-disk format and a
  per-kind metadata reference verified against the ingest adapters.
- [Dependencies](dependencies.md): the zero-runtime-dependency policy, the
  standard-library modules actually used, the optional extras, the dev group, and
  the CI actions.

## Quick facts

| Item | Value | Source |
| --- | --- | --- |
| Package | `purestrata` 0.2.0, MIT | `pyproject.toml` |
| Python | `>=3.10` | `pyproject.toml` |
| Console script | `purestrata = "purestrata.cli:main"` | `pyproject.toml` |
| Corpus file suffix | `.strata.jsonl` | `src/purestrata/corpus.py` |
| Schema marker | `purestrata/v1` | `src/purestrata/types.py` |
| Record kinds | `manual_section`, `safety_notice`, `procedure`, `part_record`, `drawing`, `failure_case` | `src/purestrata/types.py` |
| Chunk id | `sha1(doc_id::kind::locator)[:12]` | `src/purestrata/types.py` |
| Tools | 10, identical over MCP / OpenAI / Anthropic / Python / CLI | `src/purestrata/tools/schemas.py` |
| Optional extras | `pdf` (pypdf>=4.0), `mcp` (mcp>=1.2) | `pyproject.toml` |
| Default corpus directory | `./corpus` (`--corpus` default `corpus`) | `src/purestrata/cli.py` |
| Build backend | hatchling | `pyproject.toml` |
| Dev dependencies | pytest>=8.0, ruff>=0.6, pypdf>=4.0, mcp>=1.2 | `pyproject.toml` |

## Source layout

Where the behavior described on these pages lives:

| Module | Responsibility |
| --- | --- |
| `src/purestrata/cli.py` | argparse CLI, all subcommands |
| `src/purestrata/types.py` | `Chunk`, `Provenance`, kind constants, chunk ids, schema check |
| `src/purestrata/corpus.py` | Loading and writing `*.strata.jsonl`, corpus statistics |
| `src/purestrata/search.py` | Index and scoring |
| `src/purestrata/ingest/manual.py` | Markdown/PDF parsing into four kinds |
| `src/purestrata/ingest/cad.py` | ASCII DXF parsing |
| `src/purestrata/ingest/step.py` | STEP (ISO 10303-21) parsing |
| `src/purestrata/ingest/failures.py` | CSV/JSONL failure logs |
| `src/purestrata/ingest/geometry.py` | Diameter grouping, callout parsing, bounds arithmetic |
| `src/purestrata/tools/schemas.py` | The ten tool definitions in three schema styles |
| `src/purestrata/tools/executor.py` | Tool dispatch and argument clamping |
| `src/purestrata/mcp_server.py` | MCP server over stdio |
| `src/purestrata/export/finetune.py` | chat / tool_trace / cot dataset builders |

## How to read these pages

The record-format tables are transcribed from the code that writes the fields, not
from example output. Where a key is conditional, the table says when it is set. The
configuration table lists every subcommand, positional argument, and flag in
`src/purestrata/cli.py` with its exact default.

For the runtime semantics behind these tables, see
[records and provenance](../primitives/records-and-provenance.md) and
[corpus](../primitives/corpus.md). For usage walkthroughs rather than lookups, see
[getting started](../overview/getting-started.md) and the
[CLI](../features/cli.md) and [MCP server](../features/mcp-server.md) feature pages.
