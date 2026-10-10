"""Source fingerprints and format-specific provenance anchors."""

from __future__ import annotations

import hashlib

from purestrata import ingest_dxf, ingest_failures, ingest_manual, ingest_step
from purestrata.types import PART_RECORD, PROCEDURE, Provenance


def _fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_manual_records_include_source_hash_and_line_ranges(en_manual):
    chunks = ingest_manual(en_manual)
    part = next(chunk for chunk in chunks if chunk.kind == PART_RECORD)
    lines = en_manual.read_text(encoding="utf-8").splitlines()
    anchor = part.provenance.anchor

    assert part.provenance.source_sha256 == _fingerprint(en_manual)
    assert anchor["line_start"] <= anchor["line_end"] <= len(lines)
    assert anchor["table_row"] == 1
    assert any(
        "PART NO" in line.upper() for line in lines[anchor["line_start"] - 1 : anchor["line_end"]]
    )

    procedure = next(chunk for chunk in chunks if chunk.kind == PROCEDURE)
    assert procedure.provenance.source_sha256 == part.provenance.source_sha256
    assert procedure.provenance.anchor["procedure"] == 1


def test_failure_records_include_source_hash_and_row_anchor(failures_csv):
    failure = ingest_failures(failures_csv)[0]

    assert failure.provenance.source_sha256 == _fingerprint(failures_csv)
    assert failure.provenance.anchor == {"record": 1}
    assert failure.provenance.locator == "row 1"


def test_dxf_circular_feature_uses_entity_handle(tmp_path):
    path = tmp_path / "handled.dxf"
    path.write_text(
        "\n".join(
            [
                "0",
                "SECTION",
                "2",
                "HEADER",
                "9",
                "$INSUNITS",
                "70",
                "4",
                "0",
                "ENDSEC",
                "0",
                "SECTION",
                "2",
                "ENTITIES",
                "0",
                "CIRCLE",
                "5",
                "AB12",
                "8",
                "HOLES",
                "10",
                "0",
                "20",
                "0",
                "40",
                "12.5",
                "0",
                "ENDSEC",
                "0",
                "EOF",
            ]
        ),
        encoding="utf-8",
    )

    drawing = ingest_dxf(path)[0]
    assert drawing.provenance.source_sha256 == _fingerprint(path)
    assert drawing.provenance.anchor == {"entity_refs": ["#AB12"]}
    assert drawing.metadata["circular_features"][0]["entity_refs"] == ["#AB12"]


def test_step_geometry_uses_entity_ids(step_path):
    model = ingest_step(step_path)[0]
    feature_refs = sorted(
        {ref for feature in model.metadata["circular_features"] for ref in feature["entity_refs"]}
    )

    assert model.provenance.source_sha256 == _fingerprint(step_path)
    assert feature_refs
    assert model.provenance.anchor == {"entity_refs": feature_refs}
    assert all(ref.startswith("#") for ref in feature_refs)


def test_legacy_provenance_records_remain_compatible():
    legacy = {
        "doc_id": "manual",
        "source_path": "manual.md",
        "locator": "section 1: Safety",
    }

    assert Provenance.from_dict(legacy).to_dict() == legacy


def test_content_fingerprint_changes_without_changing_chunk_identity(tmp_path):
    path = tmp_path / "manual.md"
    path.write_text("# Maintenance\nCheck the first bearing.\n", encoding="utf-8")
    first = ingest_manual(path)[0]
    path.write_text("# Maintenance\nCheck the replacement bearing.\n", encoding="utf-8")
    second = ingest_manual(path)[0]

    assert first.chunk_id == second.chunk_id
    assert first.provenance.source_sha256 != second.provenance.source_sha256
