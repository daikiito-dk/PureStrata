# Connecting PureStrata to MCP clients

**English** | [日本語](#日本語)

`purestrata serve` runs a [Model Context Protocol](https://modelcontextprotocol.io) server over stdio. Any MCP client can then call the ten PureStrata tools (`search_failure_cases`, `search_drawings`, `get_safety_notices`, and the rest) against your corpus. The corpus stays on your machine; the client only receives the tool results.

## 1. Build a corpus

```bash
uvx purestrata ingest-manual path/to/manuals/*.md --out ~/purestrata-corpus
uvx purestrata ingest-dxf path/to/drawings/*.dxf --out ~/purestrata-corpus
uvx purestrata ingest-step path/to/models/*.step --out ~/purestrata-corpus
uvx purestrata ingest-failures path/to/failures.csv --out ~/purestrata-corpus
uvx purestrata inspect --corpus ~/purestrata-corpus
```

To try it with the bundled samples, clone the repository and run `make demo`; the corpus is written to `examples/corpus`.

## 2. Choose how to launch the server

| Option | Command | When to use |
| --- | --- | --- |
| A. `uvx` (no install) | `uvx --from "purestrata[mcp]" purestrata serve --corpus <dir>` | Quick trials. The first launch downloads packages, which can take a few seconds. |
| B. Installed tool | `uv tool install "purestrata[mcp]"`, then `purestrata serve --corpus <dir>` | Daily use. Starts instantly. |

MCP clients do not expand `~`. Use absolute paths for the corpus directory. GUI apps such as Claude Desktop may not see your shell `PATH`, so use the absolute path of the command (`which uvx` or `which purestrata`).

The examples below use option A. For option B, set `"command"` to the absolute path of `purestrata` and `"args"` to `["serve", "--corpus", "/abs/path/to/corpus"]`.

Optional hybrid search requires the `embeddings` extra and a SentenceTransformer model directory already present on the machine. Add `--embedding-model /abs/path/to/model --hybrid` to the server arguments. For `uvx`, request both extras as `"purestrata[mcp,embeddings]"`. BM25 remains the default; the model loader is configured for local files only and does not fetch model weights.

## 3. Register the server

### Claude Desktop

Edit `claude_desktop_config.json` (Settings > Developer > Edit Config). It is located at `~/Library/Application Support/Claude/` on macOS and `%APPDATA%\Claude\` on Windows.

```json
{
  "mcpServers": {
    "purestrata": {
      "command": "/Users/you/.local/bin/uvx",
      "args": ["--from", "purestrata[mcp]", "purestrata", "serve", "--corpus", "/Users/you/purestrata-corpus"]
    }
  }
}
```

Restart Claude Desktop after saving.

### Claude Code

```bash
claude mcp add purestrata -- uvx --from "purestrata[mcp]" purestrata serve --corpus /Users/you/purestrata-corpus
```

### Factory Droid

```bash
droid mcp add purestrata "uvx --from purestrata[mcp] purestrata serve --corpus /Users/you/purestrata-corpus"
```

Or share it with your team in the project's `.factory/mcp.json`:

```json
{
  "mcpServers": {
    "purestrata": {
      "command": "uvx",
      "args": ["--from", "purestrata[mcp]", "purestrata", "serve", "--corpus", "/abs/path/to/corpus"],
      "connectTimeout": 60000
    }
  }
}
```

### Cursor

Add the same `mcpServers` block as Claude Desktop to `~/.cursor/mcp.json` (all projects) or `.cursor/mcp.json` (one project).

### VS Code (GitHub Copilot agent mode)

Create `.vscode/mcp.json`:

```json
{
  "servers": {
    "purestrata": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "purestrata[mcp]", "purestrata", "serve", "--corpus", "/abs/path/to/corpus"]
    }
  }
}
```

## 4. Try it

With the sample corpus loaded, ask your assistant:

- "The LATHE MK3 vibrates at 5 mm/s during cutting. Check past failures and tell me the likely cause and countermeasure, with sources."
- "Which drawings or models have a 25 mm hole? Which of them specify an H7 fit?"
- "Find DXF drawings with a 25 mm hole on the PART-OUTLINE layer."
- "List the safety precautions before replacing the brake unit on the servo press."
- "プレスのブレーキ停止時間が悪化している。過去の不具合と点検手順を出典付きでまとめて。"

Every tool result includes a `source` with the file path, locator, and source SHA-256 fingerprint. Where available, format-specific anchors identify manual line ranges, failure-log rows, or DXF/STEP entity IDs. The assistant can cite both the source revision and the evidence location. Failure-case results also include `related_records`: part records and drawings whose explicit part/drawing identifiers match the failure row's part number. Multiple exact matches are returned with an `ambiguous` flag; text similarity alone never creates a link.

## 5. Remote MCP (Streamable HTTP)

For teams, the same server also speaks Streamable HTTP with bearer-token authentication. Local stdio stays the default; the corpus still never leaves the machine that serves it.

```bash
export PURESTRATA_TOKEN="$(openssl rand -hex 32)"
purestrata serve --corpus /abs/path/to/corpus --transport http --host 127.0.0.1 --port 8000
```

- The token is read from `--token` or `PURESTRATA_TOKEN`; HTTP transport refuses to start without one.
- The default bind is `127.0.0.1`. Put the server behind TLS before exposing it, for example with Caddy:

```caddy
mcp.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

Clients that support remote MCP register a URL and, with static tokens, send the header themselves:

```json
{
  "mcpServers": {
    "purestrata": {
      "url": "https://mcp.example.com/mcp",
      "headers": { "Authorization": "Bearer <PURESTRATA_TOKEN>" }
    }
  }
}
```

### OAuth architecture (design)

PureStrata is a pure **OAuth resource server**: it validates bearer tokens and never issues them (RFC 9728 protected-resource metadata is advertised automatically).

- **Self-hosting (static token):** one pre-shared token, validated in constant time. Rotate by restarting with a new value. Set `--authorization-server-url` if an authorization server exists; clients doing OAuth discovery will follow it.
- **Hosted SaaS:** the control plane runs the authorization server (authorization code + PKCE, RFC 8414 metadata, JWKS). Its verifier validates short-lived tokens against the JWKS endpoint instead of a static token, and every request is tied to the reviewer identity used in audit logs. See [docs/SAAS.md](SAAS.md).

Security notes: prefer the environment variable over the command line so the token does not land in shell history or the process list (`--token` prints a warning for this reason); use a token of at least 16 random characters (`openssl rand -hex 32`) — shorter ones trigger a startup warning; keep the loopback bind unless a reverse proxy fronts the server (binding a non-loopback address over plaintext HTTP prints a warning, because the token and every response would cross the network unencrypted); failed token checks are logged (without the token itself), and a reverse proxy should also rate-limit requests to slow down online guessing; air-gapped stdio workflows are unaffected.

## Troubleshooting

- **The server does not appear or fails to start.** Run the exact command in a terminal. `purestrata serve` should start and wait silently for input; press Ctrl+C to stop it. An error such as `Corpus directory not found` means the path is wrong.
- **The first launch times out.** `uvx` is still downloading packages. Run the command once in a terminal to warm the cache, switch to option B, or raise the client's connection timeout (for example `connectTimeout` in Droid).
- **Results are empty.** Check the corpus with `purestrata inspect --corpus <dir>` and test a tool directly with `purestrata call search_failure_cases '{"query": "vibration"}' --corpus <dir>`.

---

## 日本語

`purestrata serve` は stdio で動く MCP（Model Context Protocol）サーバーです。MCP に対応したクライアントから、PureStrata の10個のツール（`search_failure_cases`、`search_drawings`、`get_safety_notices` など）を呼び出せます。コーパスは手元のマシンに置いたまま使えます。クライアントに渡るのはツールの結果だけです。

### 1. コーパスを作る

```bash
uvx purestrata ingest-manual path/to/manuals/*.md --out ~/purestrata-corpus
uvx purestrata ingest-dxf path/to/drawings/*.dxf --out ~/purestrata-corpus
uvx purestrata ingest-step path/to/models/*.step --out ~/purestrata-corpus
uvx purestrata ingest-failures path/to/failures.csv --out ~/purestrata-corpus
```

同梱のサンプルで試す場合は、リポジトリを clone して `make demo` を実行してください。`examples/corpus` にコーパスが作られます。

### 2. 起動方法を選ぶ

- **A. `uvx`（インストール不要）**: `uvx --from "purestrata[mcp]" purestrata serve --corpus <dir>`。試すときに向いています。初回はパッケージのダウンロードに数秒かかります。
- **B. ツールとしてインストール**: `uv tool install "purestrata[mcp]"` の後に `purestrata serve --corpus <dir>`。日常的に使う場合に向いており、すぐに起動します。

MCP クライアントは `~` を展開しないため、コーパスのパスは絶対パスで書いてください。Claude Desktop などの GUI アプリはシェルの `PATH` を読まない場合があるため、コマンドも絶対パス（`which uvx` の結果）で指定するのが確実です。

任意のハイブリッド検索には `embeddings` extra と、マシン上に事前配置した SentenceTransformer モデルディレクトリが必要です。サーバー引数に `--embedding-model /abs/path/to/model --hybrid` を追加してください。`uvx` では `"purestrata[mcp,embeddings]"` を指定します。既定はBM25検索で、モデルの重みをネットワークから取得しません。

### 3. クライアントに登録する

英語版の手順 3 にある設定例（Claude Desktop、Claude Code、Factory Droid、Cursor、VS Code）は、そのまま使えます。パスだけ自分の環境に合わせて書き換えてください。

### 4. 試してみる

- 「LATHE MK3 が切削中に 5 mm/s で振動している。過去の不具合から原因と対策を出典付きで教えて」
- 「25 mm の穴がある図面や3Dモデルはどれ？ H7 公差の指示があるのは？」
- 「PART-OUTLINE レイヤーに 25 mm の穴があるDXF図面はどれ？」
- 「サーボプレスのブレーキユニット交換前の安全上の注意を一覧にして」

すべてのツール結果には、ファイルパス・位置情報・元ファイルのSHA-256指紋を含む `source` が付きます。取得できる場合は、マニュアルの行範囲、不具合ログの行、DXF/STEPのエンティティIDも示します。不具合記録の結果には `related_records` も含まれ、部品番号と明示的な識別子が一致する部品・図面を確認できます。一致候補が複数ある場合は `ambiguous` が付き、文章の類似だけで関連付けることはありません。

### 5. リモートMCP（Streamable HTTP）

チーム向けに、同じサーバーがベアラートークン認証付きの Streamable HTTP でも動きます。既定の stdio（ローカル）は変わりません。コーパスはサーバーを動かすマシンから出ません。

```bash
export PURESTRATA_TOKEN="$(openssl rand -hex 32)"
purestrata serve --corpus /abs/path/to/corpus --transport http --host 127.0.0.1 --port 8000
```

- トークンは `--token` または環境変数 `PURESTRATA_TOKEN` から読みます。HTTP ではトークンなしでは起動しません。
- 既定のバインドは `127.0.0.1` です。外部に出す場合は必ずリバースプロキシでTLSを終端してください（Caddy なら `reverse_proxy 127.0.0.1:8000` の1行）。
- リモートMCP対応クライアントは URL とヘッダーで登録します: `"url": "https://mcp.example.com/mcp", "headers": {"Authorization": "Bearer <token>"}`

**OAuth設計**: PureStrataは純粋な OAuth リソースサーバーです（RFC 9728 の保護リソースメタデータを自動公開）。トークンを検証するだけで発行はしません。セルフホストは事前共有トークン（定数時間比較、再起動でローテーション）。ホスティングSaaSではコントロールプレーンが認可サーバー（認可コード + PKCE、RFC 8414、JWKS）を担い、静的トークンの代わりに短命トークンをJWKSで検証します。詳細は [docs/SAAS.md](SAAS.md)。

運用上の注意: シェル履歴やプロセス一覧に残さないためコマンドラインより環境変数を推奨します（`--token` 使用時は警告を表示）。トークンは16文字以上の乱数にしてください（`openssl rand -hex 32`。短い場合は起動時に警告）。リバースプロキシなしならループバックのままにしてください（ループバック以外への平文HTTPバインドは警告を表示。トークンと応答が暗号化されずにネットワークを流れるため）。認証失敗はトークン自体を含めずにログ出力します。オンライン総当たり対策として、リバースプロキシ側でレート制限も設定してください。エアギャップの stdio 運用には影響しません。

### うまく動かないとき

- **サーバーが表示されない、起動しない**: 同じコマンドをターミナルで実行してみてください。正常なら何も表示せずに入力待ちになります（Ctrl+C で終了）。`Corpus directory not found` と出る場合はパスの誤りです。
- **初回起動がタイムアウトする**: `uvx` がまだパッケージをダウンロードしています。一度ターミナルで実行してキャッシュを作るか、方法 B に切り替えるか、クライアント側の接続タイムアウトを延ばしてください（Droid の場合は `connectTimeout`）。
- **結果が空になる**: `purestrata inspect --corpus <dir>` で中身を確認し、`purestrata call search_failure_cases '{"query": "vibration"}' --corpus <dir>` でツールを直接試してください。
