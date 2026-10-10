# MCP server

Active contributors: DK

## Purpose

`src/purestrata/mcp_server.py` exposes a loaded corpus to any Model Context Protocol client over stdio, so hosts such as Claude Desktop, Claude Code, Factory Droid, Cursor, and VS Code can call the ten PureStrata tools without any PureStrata-specific code on their side. The server needs the optional `mcp` extra and raises a `RuntimeError` with the exact install command when that extra is missing. The corpus stays on the machine; clients receive tool results only.

## Key abstractions

| Abstraction | File | Notes |
| --- | --- | --- |
| `build_mcp_server` | `src/purestrata/mcp_server.py` | Resolves the SDK class, binds a `ToolExecutor`, registers one wrapper per tool |
| `serve` | `src/purestrata/mcp_server.py` | `Corpus.load`, then `build_mcp_server`, then `run()` over stdio |
| `run` (inner helper) | `src/purestrata/mcp_server.py` | Strips `None` kwargs, executes, returns JSON text, converts `ToolError` to `{"error": ...}` |
| `ToolExecutor` / `ToolError` | `src/purestrata/tools/executor.py` | All tool behavior; the wrappers add none |
| `Corpus.load` | `src/purestrata/corpus.py` | Reads every `*.strata.jsonl` file under a directory |
| Client setup guide | `docs/MCP.md` | Bilingual (English then Japanese) registration walkthrough |

## How it works

`build_mcp_server(corpus)` resolves the SDK class through an import fallback chain: first `mcp.server.fastmcp.FastMCP` (mcp 1.x), then `mcp.server.mcpserver.MCPServer` (mcp 2.x renamed `FastMCP`). Only when both imports fail does it raise `RuntimeError("The MCP server requires the 'mcp' extra. Install it with: pip install 'purestrata[mcp]'")`. The class is instantiated with the name `"purestrata"`, which is what clients see as `serverInfo.name`.

Each of the ten tools gets one `@mcp.tool()`-decorated wrapper whose signature mirrors the tool's `ToolSpec` parameters (see [LLM tools](llm-tools.md)); the wrapper docstring becomes the client-visible description. Every wrapper calls the shared `run(name, **kwargs)` helper, which:

1. drops `None`-valued kwargs, so defaults come from the executor rather than the wrapper signature;
2. executes `executor.execute(name, clean)` and returns `json.dumps(..., ensure_ascii=False, default=str)`;
3. on `ToolError`, returns `json.dumps({"error": str(exc)}, ensure_ascii=False)`.

Errors therefore travel as tool text, not protocol failures: a client always parses JSON, whether the payload holds results or an error object. `serve(corpus_dir)` loads the corpus with `Corpus.load(corpus_dir)`, builds the server, and calls `mcp.run()`, the stdio transport. The CLI's `purestrata serve --corpus <dir>` is the launch path clients register.

```mermaid
graph LR
    D["corpus directory"] --> L["Corpus.load"]
    L --> B["build_mcp_server"]
    B --> W["ten mcp.tool wrappers"]
    W --> R["run: strip None kwargs"]
    R --> E["ToolExecutor.execute"]
    E --> J["JSON text, results or error"]
    J --> S["mcp.run stdio"]
    S --> C["MCP client"]
```

### Registering clients

`docs/MCP.md` is the authoritative setup guide, written in English with a Japanese section, and it carries the full JSON blocks. The decisions it makes:

- Launch: `uvx --from "purestrata[mcp]" purestrata serve --corpus <dir>` needs no install but downloads packages on the first launch; `uv tool install "purestrata[mcp]"` followed by `purestrata serve --corpus <dir>` starts instantly and suits daily use.
- Paths: MCP clients do not expand `~`, and GUI apps such as Claude Desktop may not see the shell `PATH`, so both the command (`which uvx`) and the corpus directory should be absolute.
- Clients, each with a complete snippet in `docs/MCP.md`: Claude Desktop (edit `claude_desktop_config.json`, restart after saving), Claude Code (`claude mcp add`), Factory Droid (`droid mcp add`, or a team-shared `.factory/mcp.json` that sets `connectTimeout: 60000` to absorb the first `uvx` download), Cursor (`~/.cursor/mcp.json` for all projects or a project-local `.cursor/mcp.json`), and VS Code Copilot agent mode (`.vscode/mcp.json` with `"type": "stdio"`).
- Troubleshooting also lives in `docs/MCP.md`: run the registered command in a terminal first (the server should wait silently for input), warm the `uvx` cache or raise the client timeout when the first launch is slow, and check the corpus with `purestrata inspect` plus a direct `purestrata call` before suspecting the server.

### Tests

Every test in `tests/test_mcp.py` begins with `pytest.importorskip("mcp")`, so the suite passes without the extra. The in-process tests call `server.list_tools()` and `server.call_tool(...)` directly, through a helper that tolerates both SDK result shapes (v1 lists, v2 result objects): the tool names equal `TOOLS`, results parse as JSON and carry `source.source_path`, and a missing `case_id` yields an `{"error": ...}` payload.

`test_mcp_stdio_handshake` goes end to end. It builds a corpus through the CLI (`ingest-step` and `ingest-failures` into a temp directory), spawns `python -m purestrata.cli serve --corpus <dir>` as a subprocess with piped stdio, and drives it the way a real MCP client does: a JSON-RPC `initialize` request (protocolVersion `2025-06-18`) whose response must report `serverInfo.name == "purestrata"`, the `notifications/initialized` notification, a `tools/list` call that must include `search_drawings` and `search_failure_cases`, and a `tools/call` of `search_drawings` with `{"min_diameter": 20}` whose response text must parse as JSON and return drawing `BRK-ASSY-01`. A 30-second watchdog timer kills the process if it hangs. This verifies that the packaged server speaks MCP over stdio, not merely that the SDK objects behave in-process.

## Integration points

- CLI: the `serve` subcommand in `src/purestrata/cli.py` calls `serve()` ([CLI](cli.md)); every config example in `docs/MCP.md` uses that command.
- Packaging: the `mcp` extra in `pyproject.toml` requires `mcp>=1.2`; the dev dependency group installs it so `tests/test_mcp.py` runs in CI.
- Tools: all semantics live in `ToolExecutor` ([LLM tools](llm-tools.md)); the wrappers only translate signatures into text results.
- Corpus: any directory produced by the ingest commands works ([Corpus](../primitives/corpus.md), [Getting started](../overview/getting-started.md)).

## Entry points for modification

- Add a tool to MCP: add one wrapper inside `build_mcp_server` mirroring the new `ToolSpec` signature and calling `run(name, ...)`; keep its docstring in sync with the spec description.
- Support another SDK rename: extend the try/except import chain before the `RuntimeError`.
- Change error reporting: `run` is the only place where `ToolError` becomes `{"error": ...}`.

## Key source files

| File | Role |
| --- | --- |
| `src/purestrata/mcp_server.py` | SDK fallback chain, ten wrappers, `run`, `serve` |
| `src/purestrata/cli.py` | `serve` subcommand |
| `src/purestrata/tools/executor.py` | Tool behavior behind every wrapper |
| `src/purestrata/corpus.py` | `Corpus.load` |
| `docs/MCP.md` | Bilingual client registration guide and troubleshooting |
| `pyproject.toml` | `mcp` extra and dev group |
| `tests/test_mcp.py` | In-process tool tests and the stdio JSON-RPC handshake test |

Related: [LLM tools](llm-tools.md), [CLI](cli.md), [Deployment](../deployment.md), [Patterns and conventions](../how-to-contribute/patterns-and-conventions.md).
