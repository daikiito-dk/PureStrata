# PureStrata

**English** | [日本語](#日本語)

The open data layer for manufacturing AI. Ingest **drawings, spec sheets, and failure knowledge** into one portable, provenance-tagged corpus — query it from any LLM through MCP or tool calling, then export the same corpus as **fine-tuning datasets**.

Manufacturing is where LLMs struggle most: CAD drawings, dense maintenance manuals, and failure knowledge locked in spreadsheets. Japanese factories in particular hold decades of primary data — drawings, 保全記録, and skilled-worker know-how — that never reaches the open web. PureStrata turns those documents into a structured, auditable layer that model developers and AI teams can actually use.

```
[ manuals (MD/PDF) ]   [ drawings (DXF) ]   [ failure logs (CSV/JSONL) ]
        │                     │                      │
        └─────────────────────┴──────────────────────┘
                              ▼
              [ ingest ] clean → structure → provenance
                              ▼
              [ corpus ]  portable *.strata.jsonl files
                              ▼
        ┌─────────────────────┴─────────────────────┐
        ▼                       ▼                    ▼
 [ MCP server ]      [ tool calling (Grok,    [ fine-tuning datasets ]
 any MCP client        OpenAI, local LLMs) ]     chat / tool-trace / CoT
```

## Why this exists

- **LLMs are weak on manufacturing data.** PDF drawings, CAD files, and complex spec sheets are exactly the data that never made it into pretraining corpora.
- **Failure knowledge is the missing stratum.** Most RAG stacks retrieve manual text. Factory troubleshooting runs on *symptom → cause → countermeasure* records. PureStrata treats failure cases as first-class structured data.
- **Provenance is non-negotiable.** Every record carries its source file and locator, so any answer an LLM gives can be audited back to the drawing, section, or spreadsheet row it came from.
- **No lock-in.** The corpus is plain JSONL you own. Zero required dependencies for the core. Runs on your machine, air-gap friendly.

## Install

```bash
uv add purestrata            # or: pip install purestrata
pip install "purestrata[pdf]"    # optional: PDF manual support (pypdf)
pip install "purestrata[mcp]"    # optional: MCP server support
```

Python 3.10+ required.

## Quickstart

```bash
git clone https://github.com/daikiito-dk/PureStrata
cd PureStrata
make setup
make demo          # ingest the bundled sample data, then search it
```

Or step by step:

```bash
# 1. Ingest manuals, a drawing, and a failure log into a corpus
purestrata ingest-manual examples/data/manuals/lathe_mk3_maintenance.md --out corpus/
purestrata ingest-manual examples/data/manuals/ja/cnc_press_maintenance.md --out corpus/
purestrata ingest-dxf examples/data/cad/bracket_mk3.dxf --out corpus/
purestrata ingest-failures examples/data/failures/plant_failures.csv --out corpus/

# 2. Inspect and search (English and Japanese)
purestrata inspect --corpus corpus/
purestrata search "spindle vibration" --corpus corpus/
purestrata search "ブレーキ 停止時間" --corpus corpus/

# 3. Export fine-tuning datasets from the same corpus
purestrata export chat       --corpus corpus/ --out dataset_chat.jsonl
purestrata export tool_trace --corpus corpus/ --out dataset_tools.jsonl
purestrata export cot        --corpus corpus/ --out dataset_cot.jsonl
```

## The three record families

| Kind | Source | What the LLM gets |
| --- | --- | --- |
| `manual_section` | Markdown / PDF manuals | Clean, chunked spec-sheet passages with section paths |
| `procedure` | Numbered lists in manuals | Ordered maintenance steps as structured arrays |
| `safety_notice` | WARNING / CAUTION lines (EN + JA) | Severity-tagged precautions |
| `part_record` | Parts tables | Part number, name, quantity, spec |
| `drawing` | ASCII DXF files | Title block, layers, entity counts, annotations, bounds |
| `failure_case` | CSV / JSONL failure logs | Symptom, root cause, countermeasure, severity, tags |

## Tools (identical over MCP, OpenAI-style calls, and Python)

| Tool | Purpose |
| --- | --- |
| `list_corpus` | Inventory: record counts by kind, loaded documents |
| `search_documents` | Ranked passage search (English and Japanese) |
| `get_safety_notices` | Warnings and cautions, optionally ranked |
| `get_procedure` | Full ordered steps of one procedure |
| `search_parts` | Parts lookup from parts lists |
| `list_drawings` / `get_drawing` | CAD inventory and full drawing metadata |
| `search_failure_cases` | **Troubleshooting first:** match symptoms against past failures |
| `get_failure_case` | One full case by ID |

```bash
purestrata tools openai      # JSON schemas ready for Grok / OpenAI / compatible APIs
purestrata tools anthropic
```

## Integrations

**Grok / OpenAI / any OpenAI-compatible API** — pass the tool schemas to the chat completions endpoint and execute returned tool calls locally. See `examples/api_tool_use.py`:

```bash
export PURESTRATA_BASE_URL=https://api.x.ai/v1
export PURESTRATA_API_KEY=your-key
uv run python examples/api_tool_use.py "The lathe is vibrating during cutting. What should we check?"
```

Your corpus is queried locally; results go back to the model with provenance.

**MCP (Model Context Protocol)** — run the bundled server and register it with any MCP client:

```json
{ "mcpServers": { "purestrata": { "command": "purestrata", "args": ["serve", "--corpus", "/path/to/corpus"] } } }
```

**Python API** — the same tools as a library:

```python
import purestrata as ps

chunks = ps.ingest_manual("manual.md") + ps.ingest_failures("failures.csv")
ps.write_chunks(chunks, "corpus/", "my_doc")
executor = ps.ToolExecutor(ps.Corpus.load("corpus/"))
hits = executor.execute("search_failure_cases", {"query": "spindle vibration", "top_k": 3})
```

## Fine-tuning exports

The same corpus that serves live queries becomes training data:

- **chat** — system/user/assistant JSONL accepted by OpenAI's and xAI's fine-tuning APIs
- **tool_trace** — model-issued tool call → provenance-tagged tool result → grounded answer
- **cot** — instruction / reasoning / output records for chain-of-thought training

CoT records are a deliberate scaffold: they are transparent, grounded in structured fields, and built to be **reviewed and sharpened by maintenance engineers** before training. That expert-in-the-loop pass is where dataset quality comes from — PureStrata keeps the work auditable so it can be done rigorously.

## Status and roadmap

Current: local ingestion (Markdown, PDF, ASCII DXF, CSV/JSONL), BM25 search with Japanese support, MCP server, tool schemas, fine-tune exports.

Planned: HTML/DXF-R2018 support, STEP files, per-layer geometry search, embedding search, evaluation harness for fine-tune sets, and a hosted SaaS for teams that need managed ingestion, access control, and expert review workflows.

## Development

```bash
make setup    # uv sync (installs dev tools and all extras)
make lint     # ruff check + format check
make test     # pytest
```

## License

[MIT](LICENSE)

---

## 日本語

PureStrata は製造業AIのためのオープンなデータレイヤーです。**図面・仕様書・不具合ナレッジ**を1つのポータブルで出所証明（プロビナンス）付きのコーパスに取り込み、MCPやツール呼び出しでどのLLMからでも検索でき、同じコーパスから**微調整用データセット**を書き出せます。

製造業はLLMが最も苦手とする領域です。CAD図面、高密度な保全マニュアル、そしてスプレッドシートに閉じ込められた不具合ナレッジ。特に日本の工場には、図面・保全記録・熟練工のノウハウという、Web上に存在しない一次データが蓄積されています。PureStrataはそれらの文書を、構造化され監査可能なデータ層に変換します。

### 特徴

- **3つのレコード族を第一級データとして扱う**: 仕様書（`manual_section` / `procedure` / `safety_notice` / `part_record`）、図面（DXFタイトルブロック・レイヤー・注記）、不具合ナレッジ（現象→原因→対策）。特に「不具合ナレッジ」は通常のRAGには欠けている層で、工場のトラブルシューティングの中核です。
- **完全な出所証明**: すべてのレコードが元ファイルと位置情報を保持し、LLMの回答がどの図面・セクション・行に遡れるか監査できます。
- **ロックインなし**: コーパスはプレーンなJSONL。コアは依存ゼロ。ローカル実行でエアギップ環境にも対応します。
- **日本語対応検索**: 依存ゼロのBM25実装がCJKバイグラム解析に対応し、日本語の不具合記録もそのまま検索できます。
- **Grok / OpenAI / ローカルLLM対応**: OpenAI互換のツール呼び出し用スキーマと、MCPサーバーの両方を同梱。特定モデルへの依存はありません。

### クイックスタート

```bash
git clone https://github.com/daikiito-dk/PureStrata
cd PureStrata
make setup
make demo          # サンプルデータを取り込んで検索

# 手順で実行する場合
purestrata ingest-manual examples/data/manuals/ja/cnc_press_maintenance.md --out corpus/
purestrata ingest-dxf examples/data/cad/bracket_mk3.dxf --out corpus/
purestrata ingest-failures examples/data/failures/plant_failures.csv --out corpus/
purestrata search "ブレーキ 停止時間" --corpus corpus/
purestrata export cot --corpus corpus/ --out dataset_cot.jsonl
```

### 微調整用データセット

`chat`（OpenAI / xAIファインチューニングAPI対応のメッセージ形式）、`tool_trace`（ツール呼び出し→出所付き結果→根拠ある回答）、`cot`（推論過程付き問答）の3形式で書き出せます。CoTレコードは構造化フィールドから生成される透明な雛形であり、保全エンジニアによるレビュー・推敲（ヒューマン・イン・ザ・ループ）を前提に設計されています。データ品質はその専門家レビューで決まるため、PureStrataはその作業を監査可能な形で支えます。

### 開発

```bash
make setup    # uv sync
make lint     # ruff
make test     # pytest
```

### ライセンス

[MIT](LICENSE)
