"""DXF CAD ingestion tests."""

from __future__ import annotations

import pytest

from purestrata import ingest_dxf
from purestrata.ingest.cad import parse_dxf


def test_parse_dxf_metadata(dxf_path):
    parsed = parse_dxf(dxf_path)
    assert parsed["units"] == "mm"
    assert [layer["name"] for layer in parsed["layers"]] == [
        "PART-OUTLINE",
        "DIMENSIONS",
        "TITLEBLOCK",
    ]
    assert parsed["entity_counts"] == {"LINE": 4, "CIRCLE": 1, "TEXT": 6}
    assert parsed["per_layer_counts"]["PART-OUTLINE"] == {"LINE": 4, "CIRCLE": 1}
    assert parsed["per_layer_counts"]["TITLEBLOCK"] == {"TEXT": 5}


def test_parse_dxf_title_block(dxf_path):
    parsed = parse_dxf(dxf_path)
    assert parsed["title_block"]["dwg_no"] == "BRK-0042-A"
    assert parsed["title_block"]["part_no"] == "BRK-0042"
    assert parsed["title_block"]["title"] == "MOUNTING BRACKET MK3"
    assert parsed["title_block"]["material"] == "SS400"
    assert parsed["title_block"]["scale"] == "1:2"
    assert "BORE DIA 25 H7" in parsed["text_annotations"]


def test_parse_dxf_bounds_from_geometry(dxf_path):
    bounds = parse_dxf(dxf_path)["bounds"]
    assert bounds == {"min_x": 0.0, "min_y": 0.0, "max_x": 100.0, "max_y": 80.0}


def test_dxf_chunk(dxf_path):
    chunks = ingest_dxf(dxf_path)
    assert len(chunks) == 1
    drawing = chunks[0]
    assert drawing.kind == "drawing"
    assert drawing.metadata["drawing_id"] == "BRK-0042-A"
    assert drawing.metadata["units"] == "mm"
    assert drawing.provenance.doc_id == "bracket_mk3"
    assert "MOUNTING BRACKET MK3" in drawing.text
    assert "SS400" in drawing.text
    assert "Layers: PART-OUTLINE, DIMENSIONS, TITLEBLOCK" in drawing.text


def test_dxf_non_finite_values_are_dropped(tmp_path):
    dxf = (
        "0\nSECTION\n2\nHEADER\n"
        "9\n$INSUNITS\n70\n1e999\n"
        "0\nENDSEC\n"
        "0\nSECTION\n2\nENTITIES\n"
        "0\nLINE\n8\nPART-OUTLINE\n"
        "10\n1e999\n20\n0.0\n"
        "11\n10.0\n21\n10.0\n"
        "0\nENDSEC\n0\nEOF\n"
    )
    path = tmp_path / "crafted.dxf"
    path.write_text(dxf, encoding="utf-8")

    parsed = parse_dxf(path)
    assert parsed["units"] == "unspecified"
    # The 1e999 x-coordinate is dropped; the remaining finite endpoints stay.
    assert parsed["bounds"] == {"min_x": 10.0, "min_y": 0.0, "max_x": 10.0, "max_y": 10.0}


def test_ingest_size_limit_is_enforced(monkeypatch, tmp_path):
    import purestrata.types as types

    path = tmp_path / "big.dxf"
    path.write_text("0\nEOF\n", encoding="utf-8")
    monkeypatch.setattr(types, "MAX_INGEST_BYTES", 1)
    with pytest.raises(ValueError, match="exceeds the 1-byte limit"):
        ingest_dxf(path)


def test_dxf_r2018_version_and_lwpolyline_bounds(tmp_path):
    dxf = (
        "0\nSECTION\n2\nHEADER\n"
        "9\n$ACADVER\n1\nAC1032\n"
        "9\n$INSUNITS\n70\n4\n"
        "0\nENDSEC\n"
        "0\nSECTION\n2\nENTITIES\n"
        "0\nLWPOLYLINE\n8\nOUTLINE\n"
        "10\n0.0\n20\n0.0\n"
        "10\n50.0\n20\n0.0\n"
        "10\n50.0\n20\n30.0\n"
        "10\n0.0\n20\n30.0\n"
        "0\nENDSEC\n0\nEOF\n"
    )
    path = tmp_path / "r2018.dxf"
    path.write_text(dxf, encoding="utf-8")

    parsed = parse_dxf(path)
    assert parsed["dxf_version"] == "R2018"
    assert parsed["units"] == "mm"
    assert parsed["entity_counts"] == {"LWPOLYLINE": 1}
    assert parsed["bounds"] == {"min_x": 0.0, "min_y": 0.0, "max_x": 50.0, "max_y": 30.0}
    assert ingest_dxf(path)[0].metadata["dxf_version"] == "R2018"


def test_binary_dxf_is_rejected_with_clear_error(tmp_path):
    path = tmp_path / "binary.dxf"
    path.write_bytes(b"AutoCAD Binary DXF\r\n\x1a\x00\x99\x00")
    with pytest.raises(ValueError, match="Binary DXF is not supported"):
        parse_dxf(path)
