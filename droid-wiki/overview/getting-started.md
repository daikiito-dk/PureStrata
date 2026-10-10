# Getting started

## Prerequisites

- Python 3.10 or newer
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Install

From PyPI:

```bash
pip install purestrata                 # core, no required dependencies
pip install "purestrata[pdf]"         # optional: PDF manuals via pypdf
pip install "purestrata[mcp]"          # optional: MCP server
```

Or from source for development:

```bash
git clone https://github.com/daikiito-dk/PureStrata
cd PureStrata
make setup        # uv sync (dev tools + all extras)
make demo         # ingest the bundled sample data into examples/corpus, then search it
```

`make demo` ingests two sample manuals (English and Japanese), an ASCII DXF drawing, a STEP assembly model, and a CSV failure log, then runs two searches. The generated corpus lands in `examples/corpus` as `*.strata.jsonl` files.

## Your first corpus

Step by step, using the bundled sample data:

```bash
# 1. Ingest documents (one corpus directory can mix all kinds)
purestrata ingest-manual examples/data/manuals/lathe_mk3_maintenance.md --out corpus/
purestrata ingest-manual examples/data/manuals/ja/cnc_press_maintenance.md --out corpus/
purestrata ingest-dxf examples/data/cad/bracket_mk3.dxf --out corpus/
purestrata ingest-step examples/data/cad/bracket_assy_mk3.step --out corpus/
purestrata ingest-failures examples/data/failures/plant_failures.csv --out corpus/

# 2. Inspect and search (English and Japanese both work)
purestrata inspect --corpus corpus/
purestrata search "spindle vibration" --corpus corpus/
purestrata search "ブレーキ 停止時間" --corpus corpus/

# 3. Call any tool exactly the way an LLM would
purestrata call search_drawings '{"min_diameter": 24, "max_diameter": 26}' --corpus corpus/

# 4. Export fine-tuning datasets from the same corpus
purestrata export chat       --corpus corpus/ --out dataset_chat.jsonl
purestrata export tool_trace --corpus corpus/ --out dataset_tools.jsonl
purestrata export cot        --corpus corpus/ --out dataset_cot.jsonl
```

## Python API

```python
import purestrata as ps

chunks = ps.ingest_manual("manual.md") + ps.ingest_failures("failures.csv")
ps.write_chunks(chunks, "corpus/", "my_doc")

executor = ps.ToolExecutor(ps.Corpus.load("corpus/"))
hits = executor.execute("search_failure_cases", {"query": "spindle vibration", "top_k": 3})
print(hits["results"][0]["source"])   # provenance: file path + locator
```

## Connect an LLM

- **MCP clients** (Claude Desktop, Claude Code, Factory Droid, Cursor, VS Code): follow the step-by-step guide in `docs/MCP.md`, or use the one-liner `uvx --from "purestrata[mcp]" purestrata serve --corpus /abs/path/to/corpus`.
- **OpenAI-compatible APIs** (Grok, OpenAI, local servers): print schemas with `purestrata tools openai` and pass them to the chat completions endpoint; see `examples/api_tool_use.py`.

## Run the tests

```bash
make test    # uv run pytest (79 tests, < 1 s)
make lint    # ruff check + format check
```

The test suite uses the bundled sample data as fixtures (`tests/conftest.py`) and includes a real stdio JSON-RPC handshake against `purestrata serve` (`tests/test_mcp.py`). See [Testing](../how-to-contribute/testing.md) for conventions.
