# Testing

`make test` runs the whole suite with `pytest -q` (set in `pyproject.toml`): 79 tests in under 1 second. The rules in [patterns and conventions](patterns-and-conventions.md) apply; this page covers the concrete layout.

## Layout

`tests/` mirrors `src/purestrata/`, one file per module:

| File | Covers |
| --- | --- |
| `tests/test_cli.py` | every CLI subcommand through `main()` with `capsys` |
| `tests/test_corpus.py` | `Corpus` load, stats, schema rejection |
| `tests/test_export.py` | chat / tool_trace / cot exports |
| `tests/test_ingest_cad.py` | ASCII DXF parsing |
| `tests/test_ingest_failures.py` | CSV/JSONL failure logs |
| `tests/test_ingest_manual.py` | Markdown manuals: sections, procedures, notices, parts |
| `tests/test_ingest_step.py` | STEP (ISO 10303-21) parsing |
| `tests/test_mcp.py` | the MCP server, in-process and over real stdio |
| `tests/test_search.py` | BM25 index, English and Japanese tokenization |
| `tests/test_tools.py` | `ToolExecutor` behavior for all ten tools |

New module, new test file with the matching name.

## Fixtures

`tests/conftest.py` points the suite at the bundled sample data in `examples/data/`:

- `data_dir` returns `examples/data`
- `en_manual` returns `examples/data/manuals/lathe_mk3_maintenance.md`
- `ja_manual` returns `examples/data/manuals/ja/cnc_press_maintenance.md`
- `dxf_path` returns `examples/data/cad/bracket_mk3.dxf`
- `step_path` returns `examples/data/cad/bracket_assy_mk3.step`
- `failures_csv` returns `examples/data/failures/plant_failures.csv`
- `corpus` ingests all five files and returns the in-memory `Corpus` (no disk involved)

Most tool and MCP tests build on `corpus` because the interesting assertions, ranking, filters, provenance, need all record kinds present at once.

## Patterns worth copying

### Optional-extra guard

```python
def test_something(corpus):
    pytest.importorskip("mcp")
```

The first line of every `mcp`-dependent test in `tests/test_mcp.py`. It keeps the suite green when extras are missing, while CI (which runs `uv sync --all-extras`) always exercises the tests.

### Calling MCP tools in-process

`anyio.run(server.call_tool, name, args)` drives the server object built by `build_mcp_server(corpus)` without a subprocess. The `_extract_text()` helper at the top of `tests/test_mcp.py` normalizes results across MCP SDK versions (1.x returns lists, 2.x returns result objects).

### The real stdio handshake

`test_mcp_stdio_handshake` in `tests/test_mcp.py` is the reason the MCP layer can be trusted:

- starts `purestrata serve` as a real subprocess (`sys.executable -m purestrata.cli serve --corpus ...`)
- arms a `threading.Timer(30, proc.kill)` watchdog so a hung server cannot hang the suite
- performs the genuine JSON-RPC sequence a client performs: `initialize`, `notifications/initialized`, `tools/list`, `tools/call`
- asserts the server identifies itself, lists the expected tools, and returns a provenance-bearing result

Why an integration test next to unit tests: the in-process tests prove tools compute correct answers, but they never spawn a process, frame JSON-RPC over stdio, or negotiate a protocol version. The handshake covers exactly those parts: process startup, line framing, entry-point wiring. It catches bugs that pass every unit test, such as a blocking import, a broken console script, or wrong stdio buffering.

### Tool test shape

Assert envelopes, not incidental formatting: results carry `source` with `source_path` and `locator`, filters actually filter, and invalid input raises `ToolError` under `pytest.raises`. See `tests/test_tools.py` for the pattern; its `executor` fixture is local to that file.

## Adding a test for a new tool

1. Mirror `tests/test_tools.py`: build `ToolExecutor(corpus)`, call `executor.execute("your_tool", {...})`, assert the envelope and the metadata you promised in the schema.
2. Update `test_ten_tools_defined` in `tests/test_tools.py`. Its count assertion (currently 10, checked against both `TOOLS` and `openai_tools()`) is the guardrail that keeps `ToolSpec` schemas and `_tool_*` handlers in sync; leaving it stale fails the suite.
3. If the tool is exposed over MCP, add its name to the handshake assertions in `tests/test_mcp.py` and cover the in-process call path.
4. If the tool needs data the samples do not provide, extend `examples/data/` and `tests/conftest.py` together, and keep the addition small.

## Speed

The suite must stay fast. No sleeps (the handshake watchdog is a timeout, not a delay), no network calls, no large fixtures. A suite that takes seconds gets skipped by its own maintainers, so treat any slowdown as a bug.
