"""Manual (Markdown) ingestion tests."""

from __future__ import annotations

import pytest

from purestrata import ingest_manual
from purestrata.types import MANUAL_SECTION, PART_RECORD, PROCEDURE, SAFETY_NOTICE


def _kinds(chunks: list) -> list[str]:
    return [chunk.kind for chunk in chunks]


def test_en_manual_chunk_kinds(en_manual):
    kinds = _kinds(ingest_manual(en_manual))
    assert kinds.count(MANUAL_SECTION) == 2
    assert kinds.count(SAFETY_NOTICE) == 3
    assert kinds.count(PROCEDURE) == 1
    assert kinds.count(PART_RECORD) == 4
    assert len(kinds) == 10


def test_every_chunk_has_provenance(en_manual):
    for chunk in ingest_manual(en_manual):
        assert chunk.provenance.doc_id == "lathe_mk3_maintenance"
        assert chunk.provenance.source_path.endswith("lathe_mk3_maintenance.md")
        assert chunk.provenance.locator.startswith("section ")


def test_notice_severities(en_manual):
    notices = [c for c in ingest_manual(en_manual) if c.kind == SAFETY_NOTICE]
    assert sorted(n.metadata["severity"] for n in notices) == ["caution", "warning", "warning"]
    electrical = next(n for n in notices if "electrical" in n.text.lower() or "inverter" in n.text)
    assert electrical.metadata["severity"] == "warning"


def test_document_metadata_attached(en_manual):
    for chunk in ingest_manual(en_manual):
        assert chunk.metadata["equipment"] == "LATHE MK3"
        assert chunk.metadata["document"]["revision"] == "4"
        assert chunk.metadata["document"]["manufacturer"] == "Kansai Machine Works"


def test_procedure_steps(en_manual):
    proc = next(c for c in ingest_manual(en_manual) if c.kind == PROCEDURE)
    assert proc.metadata["title"] == "Weekly maintenance"
    steps = proc.metadata["steps"]
    assert len(steps) == 5
    assert "refractometer" in steps[3]
    assert "warm-up program" in steps[4]
    assert proc.metadata["equipment"] == "LATHE MK3"


def test_part_records_from_parts_table(en_manual):
    parts = [c for c in ingest_manual(en_manual) if c.kind == PART_RECORD]
    assert {p.metadata["part_number"] for p in parts} == {
        "SP-4412",
        "CB-1180",
        "TG-0921",
        "OL-0033",
    }
    spindle = next(p for p in parts if p.metadata["part_number"] == "SP-4412")
    assert spindle.metadata["name"] == "Spindle cartridge assembly"
    assert spindle.metadata["quantity"] == "1"
    assert "BT30" in spindle.metadata["spec"]


def test_torque_table_kept_as_prose(en_manual):
    sections = [c for c in ingest_manual(en_manual) if c.kind == MANUAL_SECTION]
    torque = next(c for c in sections if "Torque" in c.metadata["section"])
    assert "Spindle clamp nut" in torque.text
    assert "180" in torque.text
    # the torque table has no part-number column, so it must not become part records
    assert all("M20" not in p.text for p in ingest_manual(en_manual) if p.kind == PART_RECORD)


def test_ja_manual_notices(ja_manual):
    notices = [c for c in ingest_manual(ja_manual) if c.kind == SAFETY_NOTICE]
    assert len(notices) == 3
    warning = next(n for n in notices if n.metadata["severity"] == "warning")
    assert "ブレーキユニット" in warning.text
    assert warning.metadata["section"] == "安全上の注意"


def test_ja_manual_parts_and_procedure(ja_manual):
    chunks = ingest_manual(ja_manual)
    parts = [c for c in chunks if c.kind == PART_RECORD]
    assert {p.metadata["part_number"] for p in parts} == {
        "BK-2207",
        "SC-1183",
        "GR-0521",
        "CL-0087",
    }
    proc = next(c for c in chunks if c.kind == PROCEDURE)
    assert len(proc.metadata["steps"]) == 4
    assert any("ブレーキテスト" in step for step in proc.metadata["steps"])


def test_ja_manual_equipment_metadata(ja_manual):
    for chunk in ingest_manual(ja_manual):
        assert chunk.metadata["equipment"] == "CNC SERVO PRESS PP-220"


def test_deterministic_chunk_ids(en_manual):
    first = ingest_manual(en_manual)
    second = ingest_manual(en_manual)
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]


def test_ingest_manual_rejects_unreadable_pdf(tmp_path):
    pytest.importorskip("pypdf")
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"not a pdf at all, just bytes")
    with pytest.raises(ValueError, match="Could not read PDF"):
        ingest_manual(path)


def test_ingest_html_manual(tmp_path):
    html = """<!DOCTYPE html>
<html><head><title>HP-50 MAINTENANCE MANUAL</title>
<style>body { color: red; }</style>
<script>var tracker = 1;</script></head>
<body>
<h2>Daily inspection</h2>
<p>Check oil level before operation.</p>
<p><strong>WARNING:</strong> High pressure can cause injury.</p>
<h2>Seal replacement</h2>
<ol><li>Depressurize the circuit.</li><li>Replace the seal kit.</li></ol>
<h2>Parts list</h2>
<table>
<tr><th>Part No</th><th>Name</th><th>Qty</th></tr>
<tr><td>SL-0050</td><td>Seal kit</td><td>1</td></tr>
<tr><td>OR-110</td><td>O-ring</td><td>2</td></tr>
</table>
</body></html>
"""
    path = tmp_path / "press_manual.html"
    path.write_text(html, encoding="utf-8")

    chunks = ingest_manual(path)
    kinds = _kinds(chunks)
    assert SAFETY_NOTICE in kinds
    assert PROCEDURE in kinds
    assert PART_RECORD in kinds

    notice = next(c for c in chunks if c.kind == SAFETY_NOTICE)
    assert notice.metadata["severity"] == "warning"
    assert "High pressure" in notice.text
    procedure = next(c for c in chunks if c.kind == PROCEDURE)
    assert procedure.metadata["steps"] == ["Depressurize the circuit.", "Replace the seal kit."]
    assert any("SL-0050" in c.text for c in chunks if c.kind == PART_RECORD)

    full_text = " ".join(c.text for c in chunks)
    assert "tracker" not in full_text
    assert "color: red" not in full_text
