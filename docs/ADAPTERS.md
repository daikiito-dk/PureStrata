# Optional framework adapters

**English** | [日本語](#日本語)

PureStrata's core has zero required dependencies, and the adapters keep it that way. They live in the `purestrata.adapters` subpackage and activate only when you install the matching extra. `import purestrata` never imports a framework, and no adapter uploads anything: they turn PureStrata records into local framework objects (retriever nodes, example rows, Hugging Face datasets). A test in `tests/adapters/test_isolation.py` enforces this.

| Adapter | Extra | Supported versions |
| --- | --- | --- |
| LlamaIndex retriever | `purestrata[llamaindex]` | `llama-index-core >= 0.10` |
| distilabel pipeline input | `purestrata[distilabel]` | `distilabel >= 1.0` (only needed for `to_dataset`) |

## LlamaIndex

```bash
pip install "purestrata[llamaindex]"
```

`PureStrataRetriever` is a standard LlamaIndex retriever over a local corpus. Use it anywhere LlamaIndex accepts a retriever:

```python
from purestrata import Corpus
from purestrata.adapters.llamaindex import PureStrataRetriever

corpus = Corpus.load("corpus/")
retriever = PureStrataRetriever(corpus, top_k=5)
nodes = retriever.retrieve("journal bearing fault")

node = nodes[0].node
node.id_                       # the PureStrata chunk ID
node.metadata["kind"]          # record kind
node.metadata["provenance"]   # source file, locator, SHA-256 fingerprint, anchor
```

Plug it into a query engine:

```python
from llama_index.core import get_response_synthesizer
from llama_index.core.query_engine import RetrieverQueryEngine

engine = RetrieverQueryEngine(retriever, get_response_synthesizer())
answer = engine.query("The spindle vibrates during cutting. What should we check?")
```

Options:

- `kinds` restricts retrieval to record kinds, exactly like `Corpus.search`.
- `hybrid=True` defers to the corpus's opt-in hybrid search. For semantic scoring, load the corpus with `Corpus.load(..., embedding_model=..., hybrid_search=True)` first (see the README's hybrid search section).

## distilabel

```bash
pip install "purestrata[distilabel]"
```

`records_to_examples` is dependency-free and returns plain rows ready for distilabel's `LoadDataFromDicts` step. `to_dataset` additionally builds a Hugging Face `datasets.Dataset` and needs the extra.

```python
from distilabel.pipeline import Pipeline
from distilabel.steps import LoadDataFromDicts
from purestrata import Corpus, approved_records
from purestrata.adapters.distilabel import records_to_examples
from purestrata.export.finetune import build_cot_records

corpus = Corpus.load("corpus/")

# Recommended: pass records that survived expert review.
# purestrata review create cot --corpus corpus/ --out review.jsonl
# purestrata review decide <id> ... --status approved
# purestrata review export-approved --bundle review.jsonl --out approved.jsonl
examples = records_to_examples(approved_records("review.jsonl"), format="cot")

# Draft records without review also work:
examples = records_to_examples(build_cot_records(corpus), format="cot")

with Pipeline(name="purestrata-cot") as pipeline:
    load = LoadDataFromDicts(data=examples)
    # add your LLM steps here; the purestrata_* columns pass through
```

Every example keeps the provider payload and the full `sources` list, and gains flat columns that survive augmentation steps:

| Column | Content |
| --- | --- |
| `purestrata_chunk_ids` | source chunk IDs |
| `purestrata_record_kinds` | source record kinds |
| `purestrata_doc_ids` | source document IDs |
| `purestrata_source_paths` | source file paths |
| `purestrata_locators` | human-readable locators (section, row, entity) |
| `purestrata_source_sha256` | source file fingerprints |

`format="chat" | "tool_trace" | "cot"` validates the payload shape up front, so a mismatched file fails before the pipeline runs. Records without `sources` are rejected: provenance is the contract.

## Running adapter tests

Adapter tests live in `tests/adapters/`, separate from the core suite, and skip when the extras are missing:

```bash
uv run pytest tests/adapters          # core suite is unaffected; framework tests skip
uv sync --extra llamaindex --extra distilabel
uv run pytest tests/adapters          # now the functional tests run
```

## 日本語

PureStrataのコアは依存ゼロで、アダプターもその原則を守ります。アダプターは `purestrata.adapters` サブパッケージにあり、対応するextraをインストールしたときだけ有効になります。`import purestrata` はフレームワークを一切読み込まず、アダプターもデータをどこにも送信しません。ローカルでフレームワーク用のオブジェクト（リトリーバーノード、学習例、Hugging Faceデータセット）を作るだけです。`tests/adapters/test_isolation.py` がこの保証を検証します。

| アダプター | extra | 対応バージョン |
| --- | --- | --- |
| LlamaIndexリトリーバー | `purestrata[llamaindex]` | `llama-index-core >= 0.10` |
| distilabelパイプライン入力 | `purestrata[distilabel]` | `distilabel >= 1.0`（`to_dataset` のみ必要） |

### LlamaIndex

```bash
pip install "purestrata[llamaindex]"
```

`PureStrataRetriever` はローカルコーパスに対する標準的なLlamaIndexリトリーバーです。

```python
from purestrata import Corpus
from purestrata.adapters.llamaindex import PureStrataRetriever

corpus = Corpus.load("corpus/")
retriever = PureStrataRetriever(corpus, top_k=5)
nodes = retriever.retrieve("ジャーナル軸受の異音")

node = nodes[0].node
node.id_                       # PureStrataのチャンクID
node.metadata["kind"]          # レコード種別
node.metadata["provenance"]    # 元ファイル・位置情報・SHA-256指紋・アンカー
```

- `kinds` は `Corpus.search` と同じくレコード種別で絞り込みます。
- `hybrid=True` はコーパスの明示的なハイブリッド検索設定に従います。意味検索を使うには、先に `Corpus.load(..., embedding_model=..., hybrid_search=True)` で読み込んでください（READMEのハイブリッド検索の節を参照）。

### distilabel

```bash
pip install "purestrata[distilabel]"
```

`records_to_examples` は依存ゼロで、distilabelの `LoadDataFromDicts` ステップにそのまま渡せる行を返します。`to_dataset` は加えてHugging Face `datasets.Dataset` を作ります（extraが必要）。

```python
from distilabel.pipeline import Pipeline
from distilabel.steps import LoadDataFromDicts
from purestrata import Corpus, approved_records
from purestrata.adapters.distilabel import records_to_examples

# 推奨: 専門家レビューを通過したレコードだけを使う
# purestrata review create cot --corpus corpus/ --out review.jsonl
# purestrata review decide <id> ... --status approved
# purestrata review export-approved --bundle review.jsonl --out approved.jsonl
examples = records_to_examples(approved_records("review.jsonl"), format="cot")

with Pipeline(name="purestrata-cot") as pipeline:
    load = LoadDataFromDicts(data=examples)
    # ここにLLMステップを追加します。purestrata_* 列はそのまま保持されます
```

各学習例はプロバイダー形式のペイロードと完全な `sources` を保持し、拡張ステップを通過しても消えない平坦な列（`purestrata_chunk_ids`、`purestrata_record_kinds`、`purestrata_doc_ids`、`purestrata_source_paths`、`purestrata_locators`、`purestrata_source_sha256`）を追加で持ちます。

`format="chat" | "tool_trace" | "cot"` はペイロードの形式を事前に検証します。`sources` のないレコードは拒否されます。出所証明がこのアダプターの契約です。

### アダプターのテスト

アダプターのテストは `tests/adapters/` に隔離されており、extraがない環境ではスキップされます。

```bash
uv run pytest tests/adapters          # コアのスイートには影響しません
uv sync --extra llamaindex --extra distilabel
uv run pytest tests/adapters          # 実行環境で機能テストが走ります
```
