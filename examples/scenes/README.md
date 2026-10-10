# SaaS-style walkthrough: Aoba Machinery Works (fictional)

**English** | [日本語](#日本語)

This is a self-contained demo scene for the hosted PureStrata story. It is modeled on the profile that appears again and again in public manufacturing-DX case studies of general industrial machinery makers: drawings and documents digitized but organized by project codes only veterans can navigate, junior engineers building on the wrong drawing and redoing the work, and field-failure knowledge that never reaches the design department. The company and all data here are fictional.

| | |
| --- | --- |
| Company | アオバ機械製作所株式会社 / Aoba Machinery Works Co., Ltd. (fictional) |
| Business | Mid-size industrial machinery maker; axial blower units for plant exhaust and drying lines |
| Product | Axial blower unit AB-200 (5.5 kW, 40 m3/min) |
| Documents | Maintenance manual (JA), bearing cover drawing (DXF), unit assembly (STEP), field service failure log (CSV) |

## Run it

```bash
make scenes                        # or: uv run python examples/scenes/run_scenes.py
```

Four scenes run locally against the bundled data:

1. **A bearing rattles in the field.** A junior service engineer searches past failures in Japanese, gets symptom → cause → countermeasure, and the case arrives already linked to the bearing's parts-table row and the assembly drawing, with source file, SHA-256 fingerprint, and row anchor.
2. **No project codes needed to find a drawing.** Geometry search finds the cover in both DXF and STEP by its 80 mm H7 bore; a layer filter narrows it further.
3. **Check the evidence before the work.** The cover's case flags that two drawings share the part number (ambiguity), and provenance shows exactly which file, row, and revision to trust before touching the machine.
4. **Veteran knowledge becomes training data, only after review.** Failure knowledge is wrapped in a review bundle; a named reviewer approves 3, rejects 1, and only approved records are exported and evaluated offline.

## Why this maps to the SaaS

| Pain point (case-study profile) | PureStrata core | Hosted SaaS adds |
| --- | --- | --- |
| Only veterans can navigate code-based drawing trees | Keyword/geometry search with CJK support | Search for every employee, with SSO and role-based access |
| Juniors redo work from a wrong similar drawing | SHA-256 fingerprints, revision-aware provenance, ambiguity flags | Correct-version guarantee and full audit trail |
| Field failures never reach design | Failure cases linked to parts and drawings by exact ID | Cross-department knowledge loop, notifications |
| Veteran know-how leaves with retirement | Offline expert review, approved-only export, dataset evaluation | Multi-user review queues, reviewer attribution, audit logs |

Everything runs locally: the corpus is plain JSONL you own, and the SaaS layers collaboration on the same format instead of locking it in. The hosted design (control plane with review workflow, SSO, and audit logs; corpora stay in the customer's environment) is in [docs/SAAS.md](../../docs/SAAS.md).

## 日本語

公開されている製造業DXの導入事例に繰り返し現れる「一般産業機械メーカー」のプロファイル（図面はコード管理でベテランしか辿れない、若手が似た別図面で手戻りする、現場の不具合知識が設計に届かない）をモデルにした、SaaSストーリー丸ごとのデモです。会社・データはすべて架空です。

| | |
| --- | --- |
| 企業 | アオバ機械製作所株式会社（架空） |
| 事業 | 中堅産業機械メーカー。プラント排気・乾燥ライン向けの軸流ブロワユニット |
| 製品 | 軸流ブロワユニット AB-200（5.5 kW、40 m3/min） |
| 文書 | 保全マニュアル（日本語）、ベアリングカバー図面（DXF）、ユニット組立（STEP）、現場サービスの故障記録（CSV） |

### 実行方法

```bash
make scenes                        # または: uv run python examples/scenes/run_scenes.py
```

4つのシーンが同梱データに対してローカルで走ります。

1. **現場で軸受が鳴いた。** 若手サービスエンジニアが日本語で過去事例を検索し、現象→原因→対策を得る。事例は軸受の部品表行と組立図面に紐付いており、元ファイル・SHA-256指紋・行アンカーも一緒に届く。
2. **図面探しに管理コードはいらない。** 幾何検索が φ80 H7 の穴から DXF と STEP の両方からカバー図面を見つけ、レイヤーでさらに絞り込める。
3. **作業の前に根拠を確認する。** カバーの事例は「同じ品番を指す図面が2枚」をあいまいフラグで示し、どのファイル・行・版を信じるかを出所が特定する。
4. **熟練工のナレッジはレビューを通ってから学習データに。** 故障ナレッジをレビュー束にし、名前付きレビュー担当者が3件承認・1件却下。承認済みのみ書き出され、オフラインで評価される。

### SaaSとの対応

| 課題（事例プロファイル） | PureStrata コア | SaaSが加えるもの |
| --- | --- | --- |
| コード管理の図面はベテランしか辿れない | CJK対応のキーワード/幾何検索 | 全従業員が検索可能に。SSOとロール別アクセス制御 |
| 若手が似た別図面で手戻り | SHA-256指紋・版を追跡する出所証明、あいまいフラグ | 正しい版の保証と完全な監査証跡 |
| 現場の不具合が設計に届かない | 完全IDで部品・図面に紐付く故障記録 | 部門横断のナレッジループと通知 |
| 熟練工の退職とともに知識が消える | オフライン専門家レビュー、承認済みのみの書き出し、データセット評価 | 多人数のレビューキュー、レビュー担当者の記名、監査ログ |

すべてはローカルで動きます。コーパスは自分が所有するプレーンなJSONLで、SaaSはその形式の上に協業の層を足すだけで、ロックインは生みません。ホスティング設計（レビュー・SSO・監査ログを持つコントロールプレーン。コーパスは顧客環境に残す）は [docs/SAAS.md](../../docs/SAAS.md) にまとめています。
