# PureStrata overview

PureStrata is an open-source Python library that turns manufacturing documents into an AI-usable data layer. It ingests maintenance manuals (Markdown/PDF), CAD files (ASCII DXF and STEP AP203/214/242), and failure logs (CSV/JSONL) into one portable corpus of JSONL records, and every record carries provenance: the source file and the position it came from. The same corpus serves live queries from any LLM (MCP server, OpenAI- or Anthropic-style tool calling, Python API, CLI) and exports as fine-tuning datasets (chat, tool_trace, CoT).

The problem it targets: LLMs are weak on manufacturing data because drawings, dense spec sheets, and failure logs never made it into pretraining corpora. Factory troubleshooting runs on symptom → cause → countermeasure records that ordinary RAG stacks do not model. PureStrata gives that knowledge a typed, auditable home that any model can query.

## Key facts

| | |
| --- | --- |
| Repository | https://github.com/daikiito-dk/PureStrata |
| PyPI | https://pypi.org/project/purestrata/ (`pip install purestrata`) |
| Project site | https://daikiito-dk.github.io/PureStrata/ |
| MCP setup guide | `docs/MCP.md` |
| Version | 0.2.0 (schema `purestrata/v1`) |
| License | MIT |
| Python | 3.10+ |
| Core dependencies | none (PDF support: `pypdf`, MCP server: `mcp`, both optional extras) |
| Tools | 10, identical over MCP, OpenAI/Anthropic schemas, Python, and CLI |

## The three record families

| Family | Kinds | Sources |
| --- | --- | --- |
| Spec sheets & manuals | `manual_section`, `procedure`, `safety_notice`, `part_record` | Markdown, PDF |
| Drawings | `drawing` | ASCII DXF, STEP (ISO 10303-21) |
| Failure knowledge | `failure_case` | CSV, JSONL |

## How this wiki is organized

| Section | What it covers |
| --- | --- |
| [Architecture](architecture.md) | Components, data flow, and design principles |
| [Getting started](getting-started.md) | Install, first corpus, first queries, running the tests |
| [Glossary](glossary.md) | Domain vocabulary: provenance, kinds, BM25, fit classes |
| [By the numbers](../by-the-numbers.md) | Codebase statistics snapshot |
| [Lore](../lore.md) | How the project evolved |
| [Features](../features/index.md) | User-visible capabilities, one page per capability |
| [Primitives](../primitives/index.md) | The core domain objects: Chunk, Provenance, Corpus |
| [Deployment](../deployment.md) | CI, PyPI trusted publishing, the GitHub Pages site |
| [Background](../background/index.md) | Why the core has zero dependencies, and known pitfalls |
| [Reference](../reference/index.md) | CLI flags, the `*.strata.jsonl` record format, dependencies |

## Who it is for

- **AI teams inside manufacturers** who need a local, auditable retrieval layer over drawings, manuals, and failure records.
- **Model developers and dataset builders** producing fine-tuning data for manufacturing domains, where provenance and expert review matter.
- **MCP client users** (Claude Desktop, Claude Code, Factory Droid, Cursor, VS Code) who want factory documents queryable with citations.

Every tool result includes its `source` (file path plus locator), so answers can be audited back to the exact drawing, section, or row they came from. That auditability is the product's reason for existing, not a feature bolted on later.
