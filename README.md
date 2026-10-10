# PureStrata

**English** | [日本語](#日本語)

The open data layer for manufacturing AI. Ingest **drawings, spec sheets, and failure knowledge** into one portable, provenance-tagged corpus — query it from any LLM through MCP or tool calling, then export the same corpus as **fine-tuning datasets**.

Project site: **https://daikiito-dk.github.io/PureStrata/**

Manufacturing is where LLMs struggle most: CAD drawings, dense maintenance manuals, and failure knowledge locked in spreadsheets. Japanese factories in particular hold decades of primary data — drawings, 保全記録, and skilled-worker know-how — that never reaches the open web. PureStrata turns those documents into a structured, auditable layer that model developers and AI teams can actually use.

```
[ manuals (MD/PDF) ]   [ drawings (DXF/STEP) ]   [ failure logs (CSV/JSONL) ]
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
- **Provenance is non-negotiable.** Every record carries its source file, SHA-256 fingerprint, and locator. Format-specific anchors add manual line ranges, failure-log rows, or DXF/STEP entity references where available, so answers can be traced to the source revision and evidence.
- **No lock-in.** The corpus is plain JSONL you own. Zero required dependencies for the core. Runs on your machine, air-gap friendly.

## Install

```bash
uv add purestrata            # or: pip install purestrata
pip install "purestrata[pdf]"    # optional: PDF manual support (pypdf)
pip install "purestrata[mcp]"    # optional: MCP server support
pip install "purestrata[embeddings]"  # optional: local semantic search backend
```

Python 3.10+ required.

## Quickstart

```bash
git clone https://github.com/daikiito-dk/PureStrata
cd PureStrata
make setup
make demo          # ingest the bundled sample data, then search it
make scenes        # SaaS-style walkthrough with a fictional machinery maker (examples/scenes/README.md)
```

Or step by step:

```bash
# 1. Ingest manuals, a drawing, and a failure log into a corpus
purestrata ingest-manual examples/data/manuals/lathe_mk3_maintenance.md --out corpus/
purestrata ingest-manual examples/data/manuals/ja/cnc_press_maintenance.md --out corpus/
purestrata ingest-dxf examples/data/cad/bracket_mk3.dxf --out corpus/
purestrata ingest-step examples/data/cad/bracket_assy_mk3.step --out corpus/
purestrata ingest-failures examples/data/failures/plant_failures.csv --out corpus/

# 2. Inspect and search (English and Japanese)
purestrata inspect --corpus corpus/
purestrata search "spindle vibration" --corpus corpus/
purestrata search "ブレーキ 停止時間" --corpus corpus/
# Optional local hybrid search (requires a pre-provisioned model directory)
purestrata search "bearing noise" --corpus corpus/ --embedding-model /models/e5-small --hybrid

# Call any tool directly, exactly as an LLM would
purestrata call search_drawings '{"min_diameter": 24, "max_diameter": 26}' --corpus corpus/

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
| `drawing` | ASCII DXF files | Title block, layers, entities, hole diameters, fit callouts (e.g. `25 H7`), size |
| `drawing` | STEP files (AP203/AP214/AP242) | Products, assembly tree with quantities, units, cylindrical features, size |
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
| `search_drawings` | Geometry search across DXF and STEP: hole diameter range (mm), fit class, material, format, and exact case-insensitive DXF layer |
| `search_failure_cases` | **Troubleshooting first:** match symptoms against past failures; results link exact part-number matches to parts and drawings |
| `get_failure_case` | One full case by ID, including exact-ID related records and ambiguity flags |

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

**MCP (Model Context Protocol)** — run the bundled server from any MCP client. No install is needed with `uvx`:

```json
{
  "mcpServers": {
    "purestrata": {
      "command": "uvx",
      "args": ["--from", "purestrata[mcp]", "purestrata", "serve", "--corpus", "/abs/path/to/corpus"]
    }
  }
}
```

Step-by-step setup for Claude Desktop, Claude Code, Factory Droid, Cursor, and VS Code, with example prompts and troubleshooting, plus remote deployment over Streamable HTTP with bearer-token auth: **[docs/MCP.md](docs/MCP.md)**.

**LlamaIndex / distilabel** — optional adapters keep provenance intact: retrieve from a PureStrata corpus inside LlamaIndex, or feed reviewed records into distilabel pipelines. Setup and supported versions: **[docs/ADAPTERS.md](docs/ADAPTERS.md)**.

**Python API** — the same tools as a library:

```python
import purestrata as ps

chunks = ps.ingest_manual("manual.md") + ps.ingest_failures("failures.csv")
ps.write_chunks(chunks, "corpus/", "my_doc")
executor = ps.ToolExecutor(ps.Corpus.load("corpus/"))
hits = executor.execute("search_failure_cases", {"query": "spindle vibration", "top_k": 3})

# Optional hybrid search, using a model already present on disk
corpus = ps.Corpus.load("corpus/", embedding_model="/models/e5-small", hybrid_search=True)
hits = corpus.search("journal bearing fault", top_k=5)
```

For optional hybrid search, install `purestrata[embeddings]` and provision a SentenceTransformer model directory locally. BM25 remains the default; PureStrata does not download a model automatically:

```bash
purestrata search "journal bearing fault" --corpus corpus/ \
  --embedding-model /models/e5-small --hybrid
```

## Fine-tuning exports

The same corpus that serves live queries becomes training data:

- **chat** — system/user/assistant JSONL accepted by OpenAI's and xAI's fine-tuning APIs
- **tool_trace** — model-issued tool call → provenance-tagged tool result → grounded answer
- **cot** — instruction / reasoning / output records for chain-of-thought training

CoT records are a deliberate scaffold: they are transparent, grounded in structured fields, and built to be **reviewed and sharpened by maintenance engineers** before training. That expert-in-the-loop pass is where dataset quality comes from — PureStrata keeps the work auditable so it can be done rigorously.

### Evaluate a dataset locally

Check structure, provenance, missing failure fields, exact duplicates, and source/kind coverage without calling an external model:

```bash
purestrata evaluate cot dataset_cot.jsonl --out evaluation.json
```

The terminal summary omits record contents; the optional JSON report lists finding codes and affected sample IDs/source locators.

### Expert review before training

Review generated records locally, then export only approved samples:

```bash
purestrata review create cot --corpus corpus/ --out review.jsonl
purestrata review list --bundle review.jsonl
purestrata review show <review-id> --bundle review.jsonl
purestrata review decide <review-id> --bundle review.jsonl --status approved \
  --reviewer "maintenance-engineer" --notes "Checked against the work order."
purestrata review export-approved --bundle review.jsonl --out reviewed_cot.jsonl
```

Review bundles start as `pending` and retain source provenance. Approve/reject decisions require a reviewer name. To replace a draft with a reviewed answer, provide a JSON record with the same `sources` using `--replacement-record`. The workflow is offline; the regular `export` command remains available for unreviewed drafts.

## Status and roadmap

Current: local ingestion (Markdown, PDF, ASCII DXF, STEP AP203/AP214/AP242, CSV/JSONL), BM25 search with Japanese support, optional local hybrid semantic search, geometry search over drawings (hole diameter, fit class, material, CAD format, DXF layer), MCP server, tool schemas, fine-tune exports, offline dataset evaluation, expert review with approved-only exports, and optional LlamaIndex/distilabel adapters.

Planned: HTML/DXF-R2018 support, and a hosted SaaS for teams that need managed ingestion, access control, and shared expert-review workflows. The SaaS design (control-plane/data-plane split, so corpora can stay on-prem) is written up in [docs/SAAS.md](docs/SAAS.md).

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

プロジェクトサイト: **https://daikiito-dk.github.io/PureStrata/**

製造業はLLMが最も苦手とする領域です。CAD図面、高密度な保全マニュアル、そしてスプレッドシートに閉じ込められた不具合ナレッジ。特に日本の工場には、図面・保全記録・熟練工のノウハウという、Web上に存在しない一次データが蓄積されています。PureStrataはそれらの文書を、構造化され監査可能なデータ層に変換します。

### 特徴

- **3つのレコード族を第一級データとして扱う**: 仕様書（`manual_section` / `procedure` / `safety_notice` / `part_record`）、図面（DXF・STEP：タイトルブロック、レイヤー、注記、穴径・公差クラス、組立構成）、不具合ナレッジ（現象→原因→対策）。特に「不具合ナレッジ」は通常のRAGには欠けている層で、工場のトラブルシューティングの中核です。
- **図面ジオメトリ検索**: `search_drawings` で穴径範囲（mm）・公差クラス（H7等）・材料・CAD形式（DXF/STEP）を横断して絞り込めます。DXFはレイヤー名でも検索できます。
- **任意のローカルハイブリッド検索**: `purestrata[embeddings]` と事前配置したモデルを指定した場合だけ、BM25と意味検索を併用できます。既定の検索は引き続き依存ゼロのBM25です。
- **オプションのフレームワークアダプター**: `purestrata[llamaindex]` でLlamaIndexリトリーバーとして、`purestrata[distilabel]` でdistilabelパイプラインへの取り込みに対応します。出所情報は列として保持されます（[docs/ADAPTERS.md](docs/ADAPTERS.md)）。
- **出所証明**: すべてのレコードが元ファイル・SHA-256指紋・位置情報を保持します。形式に応じてマニュアルの行範囲、不具合ログの行、DXF/STEPのエンティティ参照も記録し、回答の根拠を元ファイルの版と証拠まで追跡できます。
- **ロックインなし**: コーパスはプレーンなJSONL。コアは依存ゼロ。ローカル実行でエアギップ環境にも対応します。
- **日本語対応検索**: 依存ゼロのBM25実装がCJKバイグラム解析に対応し、日本語の不具合記録もそのまま検索できます。
- **Grok / OpenAI / ローカルLLM対応**: OpenAI互換のツール呼び出し用スキーマと、MCPサーバーの両方を同梱（セットアップ手順は [docs/MCP.md](docs/MCP.md)）。特定モデルへの依存はありません。

### クイックスタート

```bash
git clone https://github.com/daikiito-dk/PureStrata
cd PureStrata
make setup
make demo          # サンプルデータを取り込んで検索
make scenes        # 架空の産業機械メーカーによるSaaSストーリーの通し実行（examples/scenes/README.md）

# 手順で実行する場合
purestrata ingest-manual examples/data/manuals/ja/cnc_press_maintenance.md --out corpus/
purestrata ingest-dxf examples/data/cad/bracket_mk3.dxf --out corpus/
purestrata ingest-step examples/data/cad/bracket_assy_mk3.step --out corpus/
purestrata ingest-failures examples/data/failures/plant_failures.csv --out corpus/
purestrata search "ブレーキ 停止時間" --corpus corpus/
purestrata call search_drawings '{"min_diameter": 24, "max_diameter": 26}' --corpus corpus/
purestrata export cot --corpus corpus/ --out dataset_cot.jsonl
```

### 微調整用データセット

`chat`（OpenAI / xAIファインチューニングAPI対応のメッセージ形式）、`tool_trace`（ツール呼び出し→出所付き結果→根拠ある回答）、`cot`（推論過程付き問答）の3形式で書き出せます。CoTレコードは構造化フィールドから生成される透明な雛形であり、保全エンジニアによるレビュー・推敲（ヒューマン・イン・ザ・ループ）を前提に設計されています。データ品質はその専門家レビューで決まるため、PureStrataはその作業を監査可能な形で支えます。

### データセットをローカル評価

外部モデルを呼び出さず、形式・出所・原因/対策の欠落・完全重複・出典/レコード種別の網羅性を確認できます。

```bash
purestrata evaluate cot dataset_cot.jsonl --out evaluation.json
```

ターミナル要約にはレコード本文を表示しません。JSONレポートには検出コードと対象サンプルID・出典位置を記録します。

### 学習前の専門家レビュー

生成データをローカルで確認し、承認したサンプルだけを書き出せます。

```bash
purestrata review create cot --corpus corpus/ --out review.jsonl
purestrata review list --bundle review.jsonl
purestrata review show <review-id> --bundle review.jsonl
purestrata review decide <review-id> --bundle review.jsonl --status approved \
  --reviewer "保全エンジニア" --notes "作業記録と照合済み"
purestrata review export-approved --bundle review.jsonl --out reviewed_cot.jsonl
```

レビュー用JSONLは `pending` 状態で作られ、出所情報を保持します。承認・却下にはレビュー担当者名が必要です。回答を修正する場合は、同じ `sources` を含むJSONレコードを `--replacement-record` で渡します。この手順はオフラインで完結し、通常の `export` による未レビュー下書きの書き出しも引き続き利用できます。

### 開発

```bash
make setup    # uv sync
make lint     # ruff
make test     # pytest
```

### ライセンス

[MIT](LICENSE)
