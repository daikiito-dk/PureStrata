"""CLI tests."""

from __future__ import annotations

import json

from purestrata.cli import main


def test_ingest_search_inspect(tmp_path, en_manual, dxf_path, failures_csv, capsys):
    corpus_dir = str(tmp_path / "corpus")

    assert main(["ingest-manual", str(en_manual), "--out", corpus_dir]) == 0
    assert main(["ingest-dxf", str(dxf_path), "--out", corpus_dir]) == 0
    assert main(["ingest-failures", str(failures_csv), "--out", corpus_dir]) == 0
    out = capsys.readouterr().out
    assert "10 records" in out
    assert "8 records" in out

    assert main(["inspect", "--corpus", corpus_dir]) == 0
    stats = json.loads(capsys.readouterr().out)
    assert stats["total_chunks"] == 19

    assert main(["search", "spindle vibration", "--corpus", corpus_dir, "--top-k", "3"]) == 0
    search_out = capsys.readouterr().out
    assert "score=" in search_out
    assert "source:" in search_out

    assert main(["search", "ブレーキ", "--corpus", corpus_dir]) == 0
    assert "score=" in capsys.readouterr().out


def test_tools_command(capsys):
    for fmt, key in (("openai", "function"), ("anthropic", "input_schema"), ("json", "parameters")):
        assert main(["tools", fmt]) == 0
        data = json.loads(capsys.readouterr().out)
        assert any(key in tool for tool in data)
        names = {
            tool.get("function", {}).get("name") if fmt == "openai" else tool["name"]
            for tool in data
        }
        assert "search_failure_cases" in names


def test_export_commands(tmp_path, en_manual, failures_csv, capsys):
    corpus_dir = str(tmp_path / "corpus")
    main(["ingest-manual", str(en_manual), "--out", corpus_dir])
    main(["ingest-failures", str(failures_csv), "--out", corpus_dir])
    capsys.readouterr()

    chat_out = tmp_path / "chat.jsonl"
    assert main(["export", "chat", "--corpus", corpus_dir, "--out", str(chat_out)]) == 0
    chat_lines = chat_out.read_text(encoding="utf-8").strip().splitlines()
    assert len(chat_lines) == 12  # 3 safety notices + 1 procedure from the manual, 8 failure cases

    cot_out = tmp_path / "cot.jsonl"
    assert (
        main(["export", "cot", "--corpus", corpus_dir, "--out", str(cot_out), "--limit", "3"]) == 0
    )
    cot_lines = cot_out.read_text(encoding="utf-8").strip().splitlines()
    assert len(cot_lines) == 3

    assert "Exported 3 cot records" in capsys.readouterr().out

    report_path = tmp_path / "evaluation.json"
    assert main(["evaluate", "cot", str(cot_out), "--out", str(report_path)]) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["format"] == "cot"
    assert report["valid_records"] == 3
    assert "Dataset evaluation (cot)" in capsys.readouterr().out


def test_review_cli_exports_only_approved_records(tmp_path, en_manual, failures_csv, capsys):
    corpus_dir = str(tmp_path / "corpus")
    main(["ingest-manual", str(en_manual), "--out", corpus_dir])
    main(["ingest-failures", str(failures_csv), "--out", corpus_dir])
    capsys.readouterr()

    bundle_path = tmp_path / "review.jsonl"
    assert (
        main(
            [
                "review",
                "create",
                "cot",
                "--corpus",
                corpus_dir,
                "--out",
                str(bundle_path),
                "--limit",
                "2",
            ]
        )
        == 0
    )
    bundle = [json.loads(line) for line in bundle_path.read_text(encoding="utf-8").splitlines()]
    assert all(entry["status"] == "pending" for entry in bundle)
    review_id = bundle[0]["review_id"]
    capsys.readouterr()

    assert main(["review", "list", "--bundle", str(bundle_path)]) == 0
    queue = json.loads(capsys.readouterr().out)
    assert queue[0]["review_id"] == review_id
    assert queue[0]["sources"]

    assert main(["review", "show", review_id, "--bundle", str(bundle_path)]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["record"] == bundle[0]["record"]

    approved_path = tmp_path / "approved.jsonl"
    assert (
        main(
            [
                "review",
                "export-approved",
                "--bundle",
                str(bundle_path),
                "--out",
                str(approved_path),
            ]
        )
        == 0
    )
    assert approved_path.read_text(encoding="utf-8") == ""
    capsys.readouterr()

    assert (
        main(
            [
                "review",
                "decide",
                review_id,
                "--bundle",
                str(bundle_path),
                "--status",
                "approved",
                "--reviewer",
                "engineer-1",
                "--notes",
                "Verified.",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "review",
                "export-approved",
                "--bundle",
                str(bundle_path),
                "--out",
                str(approved_path),
            ]
        )
        == 0
    )
    exported = [json.loads(line) for line in approved_path.read_text(encoding="utf-8").splitlines()]
    assert len(exported) == 1
    assert exported[0] == bundle[0]["record"]
    assert "sources" in exported[0]


def test_ingest_step_and_call_tool(tmp_path, step_path, dxf_path, capsys):
    corpus_dir = str(tmp_path / "corpus")
    assert main(["ingest-step", str(step_path), "--out", corpus_dir]) == 0
    assert main(["ingest-dxf", str(dxf_path), "--out", corpus_dir]) == 0
    capsys.readouterr()

    args = '{"min_diameter": 8, "max_diameter": 10}'
    assert main(["call", "search_drawings", args, "--corpus", corpus_dir]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["results"][0]["drawing_id"] == "BRK-ASSY-01"

    assert main(["call", "search_drawings", '{"layer": "dimensions"}', "--corpus", corpus_dir]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["results"][0]["matched_layers"] == ["DIMENSIONS"]

    assert main(["call", "search_drawings", "[1]", "--corpus", corpus_dir]) == 1
    assert "JSON object" in capsys.readouterr().err


def test_missing_file_error(tmp_path, capsys):
    rc = main(["ingest-manual", str(tmp_path / "nope.md"), "--out", str(tmp_path)])
    assert rc == 1
    assert "error:" in capsys.readouterr().err


def test_search_hybrid_flags_require_each_other(tmp_path, capsys):
    corpus_dir = str(tmp_path / "corpus")

    rc = main(["search", "query", "--corpus", corpus_dir, "--hybrid"])
    assert rc == 1
    assert "--hybrid requires --embedding-model" in capsys.readouterr().err

    rc = main(["search", "query", "--corpus", corpus_dir, "--embedding-model", str(tmp_path)])
    assert rc == 1
    assert "--embedding-model requires --hybrid" in capsys.readouterr().err


def test_search_hybrid_requires_existing_local_model(tmp_path, capsys):
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    rc = main(
        [
            "search",
            "query",
            "--corpus",
            str(corpus_dir),
            "--embedding-model",
            str(tmp_path / "missing-model"),
            "--hybrid",
        ]
    )
    assert rc == 1
    assert "Local embedding model not found" in capsys.readouterr().err


def test_serve_hybrid_flags_require_each_other(capsys):
    rc = main(["serve", "--corpus", "corpus", "--hybrid"])
    assert rc == 1
    assert "--hybrid requires --embedding-model" in capsys.readouterr().err
