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


def test_ingest_step_and_call_tool(tmp_path, step_path, capsys):
    corpus_dir = str(tmp_path / "corpus")
    assert main(["ingest-step", str(step_path), "--out", corpus_dir]) == 0
    capsys.readouterr()

    args = '{"min_diameter": 8, "max_diameter": 10}'
    assert main(["call", "search_drawings", args, "--corpus", corpus_dir]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["results"][0]["drawing_id"] == "BRK-ASSY-01"

    assert main(["call", "search_drawings", "[1]", "--corpus", corpus_dir]) == 1
    assert "JSON object" in capsys.readouterr().err


def test_missing_file_error(tmp_path, capsys):
    rc = main(["ingest-manual", str(tmp_path / "nope.md"), "--out", str(tmp_path)])
    assert rc == 1
    assert "error:" in capsys.readouterr().err
