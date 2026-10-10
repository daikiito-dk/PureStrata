"""SaaS-style PureStrata walkthrough for a fictional industrial machinery maker.

アオバ機械製作所（架空）の軸流ブロワユニット AB-200 の保全データで、
PureStrata を導入した中堅産業機械メーカーの1日を通しで再現します。

    uv run python examples/scenes/run_scenes.py

想定: 図面・保全記録・不具合対応が紙とベテランの頭の中に埋もれ、
若手が似た別図面で手戻りし、現場の不具合知識が設計に届かない会社。
会社・データはすべて架空です（examples/scenes/README.md を参照）。
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from purestrata import (
    Corpus,
    ToolExecutor,
    approved_records,
    create_review_bundle,
    decide_review,
    format_evaluation_summary,
    ingest_dxf,
    ingest_failures,
    ingest_manual,
    ingest_step,
    list_review_queue,
    write_chunks,
)
from purestrata.export.evaluation import evaluate_dataset
from purestrata.export.finetune import build_cot_records, write_jsonl
from purestrata.export.review import write_review_bundle

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
SCENE_DATA = "examples/scenes/data"

REVIEWER = "主任保全エンジニア 小林"


def banner(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def show_source(record: dict) -> None:
    source = record.get("source") or {}
    fingerprint = (source.get("source_sha256") or "")[:12]
    anchor = source.get("anchor")
    anchor_text = f" anchor={anchor}" if anchor else ""
    print(f"    出所: {source.get('source_path')} :: {source.get('locator')}")
    print(f"    指紋: sha256:{fingerprint}…{anchor_text}")


def main() -> None:
    # Run with repo-relative source paths so provenance stays portable
    # (same convention as `make demo`), regardless of the caller's cwd.
    os.chdir(REPO_ROOT)
    manual = f"{SCENE_DATA}/manuals/ja/aoba_ab200_maintenance.md"
    dxf = f"{SCENE_DATA}/cad/aoba_ab200_cover.dxf"
    step = f"{SCENE_DATA}/cad/aoba_ab200_unit_assy.step"
    failures = f"{SCENE_DATA}/failures/aoba_service_log.csv"

    with tempfile.TemporaryDirectory() as tmp:
        corpus_dir = Path(tmp)

        banner("Scene 0: 現場の紙・Excel・CADをコーパスに取り込む")
        for path, ingest in (
            (manual, ingest_manual),
            (dxf, ingest_dxf),
            (step, ingest_step),
            (failures, ingest_failures),
        ):
            chunks = ingest(path)
            write_chunks(chunks, corpus_dir, chunks[0].provenance.doc_id)
            print(f"  {Path(path).name}: {len(chunks)} 件")
        corpus = Corpus.load(corpus_dir)
        executor = ToolExecutor(corpus)
        print(f"  コーパス合計: {corpus.stats()['total_chunks']} 件（出所・SHA-256指紋付き）")

        banner("Scene 1: 現場で軸受の異音。ベテランに頼らず過去事例を探す")
        results = executor.execute("search_failure_cases", {"query": "軸受 異音 振動", "top_k": 1})
        case = results["results"][0]
        meta = case["metadata"]
        print(f"  事例 {meta['case_id']}: {meta['symptom']}")
        print(f"  原因: {meta['cause']}")
        print(f"  対策: {meta['countermeasure']}")
        show_source(case)
        related = case["related_records"]
        parts = related["parts"]["matches"]
        if parts:
            print(f"  関連部品: {parts[0]['name']}（品番 {related['identifier']}）")
        for drawing in related["drawings"]["matches"]:
            print(f"  関連図面: {drawing['drawing_id']}（{drawing['cad_format']}）")
        if related["drawings"]["ambiguous"]:
            print("  ※ 図面は複数候補のため「あいまい」フラグ付き。正しい版は出所で確認する。")

        banner("Scene 2: 図面を管理コードなしで、寸法とレイヤーから探す")
        hits = executor.execute("search_drawings", {"min_diameter": 70, "max_diameter": 90})
        for hit in hits["results"]:
            for feature in hit.get("matched_features", []):
                diameter = feature.get("diameter_mm", feature.get("diameter"))
                print(f"  {hit['drawing_id']}（{hit['cad_format']}）: 穴径 {diameter} mm")
        layered = executor.execute("search_drawings", {"layer": "notes"})
        for hit in layered["results"]:
            print(f"  レイヤー 'notes': {hit['drawing_id']} {hit['matched_layers']}")

        banner("Scene 3: 回答の根拠を、元ファイルの行・エンティティまで確認する")
        detail = executor.execute("get_failure_case", {"case_id": "aoba_service_log-c005"})
        meta = detail["metadata"]
        print(f"  事例 {meta['case_id']}: {meta['symptom']}")
        print(f"  原因: {meta['cause']}")
        print(f"  対策: {meta['countermeasure']}")
        show_source(detail)
        related = detail["related_records"]
        print(f"  対象部品 {related['identifier']} の紐付け:")
        for part in related["parts"]["matches"]:
            print(f"    部品表: {part['name']} ({part['source']['locator']})")
        for drawing in related["drawings"]["matches"]:
            print(f"    図面: {drawing['drawing_id']}（{drawing['cad_format']}）")
        if related["drawings"]["ambiguous"]:
            print("    ※ 同一品番の図面が2枚。REV（版）は出所で確認してから作業する。")

        banner("Scene 4: 熟練工のナレッジをレビューし、承認済みだけを学習データに")
        records = build_cot_records(corpus)
        bundle = create_review_bundle("cot", records)
        bundle_path = write_review_bundle(bundle, Path(tmp) / "review.jsonl")
        print(f"  レビュー待ち {len(bundle)} 件を作成 -> {bundle_path.name}")
        queue = list_review_queue(bundle_path)
        for entry in queue[:3]:
            decide_review(
                bundle_path,
                entry["review_id"],
                "approved",
                reviewer=REVIEWER,
                notes="作業記録と突合済み",
            )
        decide_review(
            bundle_path,
            queue[-1]["review_id"],
            "rejected",
            reviewer=REVIEWER,
            notes="原因の記載が不十分。再調査して差し替える。",
        )
        statuses = [entry["status"] for entry in list_review_queue(bundle_path)]
        print(
            f"  承認 {statuses.count('approved')} 件 / 却下 {statuses.count('rejected')} 件 /"
            f" 未対応 {statuses.count('pending')} 件（担当者と時刻を記録）"
        )
        approved = approved_records(bundle_path)
        approved_path = write_jsonl(approved, Path(tmp) / "approved_cot.jsonl")
        print(f"  承認済みのみ書き出し: {len(approved)} 件 -> {approved_path.name}")
        report = evaluate_dataset(approved_path, "cot")
        print(format_evaluation_summary(report))

    print()
    print("この流れ（取り込み → 検索 → 出所確認 → レビュー → 承認済み書き出し → 評価）を、")
    print("PureStrata SaaS は多人数の権限管理・監査ログ付きで提供します。")
    print("詳細: examples/scenes/README.md")


if __name__ == "__main__":
    main()
