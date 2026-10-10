# Hosted PureStrata SaaS: control-plane architecture

**English** | [日本語](#日本語)

This is the technical design for the hosted service announced in the roadmap: managed ingestion, access control, and shared expert-review workflows. It commits to one decision up front, and everything else follows from it: **the SaaS is a collaboration layer on the open corpus format, never a custody trap.** Customers who cannot send drawings to any cloud are first-class users of the OSS core; the SaaS serves everyone else without abandoning them.

## 1. Principles

1. **Same format, everywhere.** The SaaS reads and writes the same plain JSONL corpus (`purestrata/v1`) the OSS core does. Export everything, leave anytime, run offline after.
2. **Control plane / data plane split.** Workflow state (review queues, permissions, audit logs) can live in the cloud while corpus data stays in the customer's environment. Each customer picks its position on this dial per deployment, not per contract.
3. **Provenance is the contract.** The SaaS extends the existing provenance model (SHA-256 source fingerprints, locators, anchors, reviewer identity) into an operational audit trail: who retrieved, who changed, who approved what, when.
4. **No silent egress.** No LLM call, no telemetry, no cross-region copy without an explicit, logged configuration. Air-gapped runners keep working.

## 2. Topology

```
                     +--------------------------------------+
                     |        Control plane (SaaS)          |
                     |  Tokyo region (single region)        |
                     |                                      |
  SSO / SCIM  --->   |  - Auth: OAuth 2.1 AS (PKCE, JWKS)  |
  (Entra ID etc.)    |  - API gateway + web app             |
                     |  - Review workflow service           |
                     |  - Audit log (append-only)           |
                     |  - Ingestion orchestration (jobs)    |
                     |  - Tenant metadata, billing           |
                     +----------|---------------------------+
                                | HTTPS, short-lived tokens
                                v
        +-------------------------------------------+
        |        Data plane (customer chooses)      |
        |                                           |
        |  A. On-prem runner (pulls jobs, no inbound)
        |     corpus stays on customer storage      |
        |                                           |
        |  B. Single-tenant VPC (customer account)  |
        |                                           |
        |  C. Managed tenancy (SaaS storage,        |
        |     per-tenant keys, Tokyo region)        |
        +-------------------------------------------+
                                |
                                v
                    MCP / tool-calling clients
                    (remote Streamable HTTP, bearer auth)
```

- **A (on-prem runner):** a small agent on customer infrastructure polls the control plane for jobs (ingest, re-index, export), executes them locally with the OSS core, and returns only metadata and hashes. Drawings never leave the plant. Fits air-gapped networks with a one-way transfer of metadata.
- **B (single-tenant VPC):** the same services deployed into the customer's cloud account. The control plane is theirs; PureStrata operates it.
- **C (managed tenancy):** multi-tenant SaaS storage for customers who accept cloud hosting. Tenant isolation is enforced with per-tenant data keys and tenant-scoped object storage prefixes, enforced at the service layer, not by convention.

## 3. Identity, access, and the MCP path

- **People:** SSO via OIDC (Entra ID and Google Workspace first), SCIM provisioning, RBAC roles: `admin`, `ingest`, `reviewer`, `engineer`, `viewer`. Reviewer identity strings recorded in review decisions must resolve to SSO identities in the SaaS.
- **MCP clients:** the SaaS control plane is the OAuth 2.1 authorization server. It advertises RFC 8414 AS metadata and issues short-lived access tokens via authorization code + PKCE. The PureStrata server (OSS `--transport http` or the hosted endpoint) is a pure resource server: it validates tokens against the control plane's JWKS and never issues tokens itself (see docs/MCP.md). Static pre-shared tokens remain the self-hosting option.
- **Runner ↔ control plane:** mutual TLS with per-runner client certificates; jobs are pulled, never pushed, so no inbound firewall openings.

## 4. Data residency and tenancy

- The control plane and any managed tenancy run in the Tokyo region only. No cross-region replication by default.
- Manufacturing documents can be controlled technology under Japanese export-control rules when stored or processed abroad; keeping processing domestic by default removes the most common objection. Customers remain responsible for classifying their own data, and the docs say so plainly rather than giving legal advice.
- Envelope encryption: per-tenant data encryption keys (DEK) wrapped by a customer-scoped root key. Customer-managed root keys are supported in option C and default in option B.
- Backup and DR: control-plane state is backed up daily with quarterly restore drills; corpus JSONL is inherently re-derivable from customer sources (the OSS ingesters are deterministic and idempotent), which is documented as the customer's own DR path in options A and B.

## 5. Review workflow and audit

The OSS review bundle (pending/approved/rejected, reviewer, notes, record hashes) becomes a multi-user service:

- Queues, assignments, notifications, and approval chains (optionally two-person rule for records flagged `critical`).
- The SaaS enforces what the OSS already models: decisions require an authenticated reviewer, and replacement records must preserve `sources`.
- The audit log is append-only: every retrieval, edit, decision, and export with actor, timestamp, target record, and source fingerprint. It extends, rather than replaces, the provenance already embedded in every record, and it is exportable as JSON for the customer's own SIEM.

## 6. LLM routing

- BYOK by default: customers register their own keys. Region pinning is a first-class option: Azure OpenAI (Japan East), AWS Bedrock (ap-northeast-1), or a local model via the same tool-calling interface.
- The corpus never travels to an LLM; tool results do, with provenance. No-provider configurations (pure search, review, and export) are fully supported.
- No training on customer data, ever; provider agreements and the docs state this, and the architecture keeps the corpus itself out of any prompt path the SaaS does not control.

## 7. Delivery phases

- **Phase 0 (now):** OSS core is complete for local use; enterprise support and the on-prem runner pilot (option A) are the first commercial offer.
- **Phase 1:** control plane with SSO, review workflow, audit log; corpora stay in the customer environment (options A and B).
- **Phase 2:** managed tenancy (option C), managed ingestion jobs for high-volume formats, OCR for scanned manuals (Japanese first), and SaaS-hosted remote MCP endpoints.

## 8. Security and compliance foundation

- Dependency and secret scanning in CI; published releases are built and attested in CI (already the case via PyPI trusted publishing).
- Annual third-party penetration test before general availability of Phase 1; findings drive fixes, and an executive summary is shareable with customers.
- Security questionnaire (診断シート) answers are derived from this document plus the repo's security review; the answer pack grows with the phases above.
- ISO/IEC 27001 (ISMS) certification is a Phase 2 objective, sequenced after the control-plane surface stabilizes.

## 9. What stays open

The core (ingesters, search, tools, review bundle format, provenance model, adapters) remains MIT and dependency-free. The SaaS-proprietary surface is exactly the collaboration layer: authentication, workflow services, orchestration, audit storage, and hosted endpoints. The corpus format and the record families are the contract between them, and any competitor may implement the same contract; that is the point.

## 日本語

ロードマップで予告したホスティングサービス（マネージド取り込み・アクセス制御・専門家レビューの共有）の技術設計です。最初に一つだけ決めたことがあり、他はすべてそこから導いています: **SaaSはオープンなコーパス形式の上に載る協業の層であり、データを人質に取らない。** 図面をクラウドに出せない企業も、OSSコアの一級ユーザーのままです。

### 原則

1. **同じ形式をどこでも。** SaaSもOSSコアと同じプレーンなJSONLコーパス（`purestrata/v1`）を読み書きします。いつでも全件書き出して、いつでもやめられます。
2. **コントロールプレーン／データプレーン分離。** ワークフロー状態（レビュー、権限、監査ログ）はクラウドに置きつつ、コーパスは顧客環境に残せます。どこに置くかは契約ではなく導入単位で選びます。
3. **出所証明が契約。** 既存の出所モデル（SHA-256指紋・位置情報・アンカー・レビュー担当者）を運用の監査証跡に拡張します: 誰がいつ、何を取り出し、変え、承認したか。
4. **黙示的な送信は一切しない。** 明示的・記録された設定なしに、LLM呼び出しも、テレメトリも、他リージョン複製もしません。エアギャップのランナーは動き続けます。

### トポロジー（図は英語版を参照）

- **A. オンプレランナー**: 顧客環境の小さなエージェントがジョブを引きに行き、OSSコアでローカル実行してメタデータとハッシュだけを返します。図面は工場から出ません。エアギャップにも使えます。
- **B. シングルテナントVPC**: 同じサービス構成を顧客のクラウドアカウントに展開し、PureStrataが運用します。
- **C. マネージドテナンシー**: SaaSストレージ（東京リージョン、テナント別暗号鍵、接頭辞分離）を許容する顧客向け。

### 認証・認可とMCP経路

- **人**: OIDC SSO（Entra ID / Google Workspace）とSCIM。ロールは `admin` / `ingest` / `reviewer` / `engineer` / `viewer`。レビュー担当者の記名はSSOの実名に解決されます。
- **MCPクライアント**: コントロールプレーンがOAuth 2.1認可サーバー（RFC 8414メタデータ、認可コード + PKCE）。PureStrataサーバーは純粋なリソースサーバーとしてJWKSで短命トークンを検証するだけです（docs/MCP.md）。セルフホストは事前共有トークンのまま使えます。
- **ランナー↔コントロールプレーン**: 相互TLS、ジョブはpullのみ。顧客側の受信ポートは開けません。

### データ所在とテナンシー

- コントロールプレーンとマネージドテナンシーは東京リージョンのみ。既定での他リージョン複製はありません。
- 製造文書は管理法上の技術該当になり得るため、国内処理を既定にすることで最も多い拒否理由を排除します。分類は顧客の責任と明記します（法的助言ではありません）。
- エンベロープ暗号: テナント別DEKを顧客スコープのルート鍵でラップ。顧客管理鍵はCで対応、Bで既定。
- バックアップは日次、復旧訓練は四半期ごと。コーパス自体は顧客の一次資料から再生成できる（取り込みは決定的で冪等）ため、AとBでは顧客自身のDR経路として文書化します。

### レビューと監査

OSSのレビュー束（pending/approved/rejected・担当者・記録ハッシュ）を多人数サービス化します。キュー・割当・通知・承認チェーン（`critical` はダブルチェック規定）。OSSが既に守っている規則（承認には実名、差し替えは `sources` 保持）をSaaSが強制します。監査ログは追記専用で、全操作に操作者・時刻・対象レコード・指紋を記録し、JSONで書き出せます。

### LLMルーティング

BYOK既定。リージョン固定（Azure OpenAI 東日本、AWS東京、ローカルLLM）は第一級オプション。コーパスはLLMに行かず、出所付きのツール結果だけが行きます。学習利用なし。

### 提供段階

- **フェーズ0（現在）**: OSSコアはローカル利用が完結。商用第一弾はエンタープライズサポートとオンプレランナーのパイロット（A）。
- **フェーズ1**: SSO・レビュー・監査ログを持つコントロールプレーン。コーパスは顧客環境のまま（AとB）。
- **フェーズ2**: マネージドテナンシー（C）、大量形式のマネージド取り込み、スキャンマニュアルのOCR（日本語優先）、ホスト型リモートMCP。

### セキュリティ基盤

CIでの依存関係・シークレットスキャン、リリースはCIで構築・署名（PyPI trusted publishingで実現済み）。フェーズ1のGA前に第三者ペネトレーションテスト（要約は顧客に共有可能）。診断シートの回答は本書とリポジトリのセキュリティレビューから作成します。ISMS（ISO/IEC 27001）はフェーズ2の目標。

### オープンであるもの

コア（取り込み・検索・ツール・レビュー束形式・出所モデル・アダプター）はMIT・依存ゼロのまま。SaaS固有の面は協業層（認証・ワークフロー・オーケストレーション・監査保存・ホスト型エンドポイント）だけです。コーパス形式とレコード族が両者の契約で、競合が同じ契約を実装できることは、狙いのうちです。
