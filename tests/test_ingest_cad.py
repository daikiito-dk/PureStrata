"""DXF CAD ingestion tests."""

from __future__ import annotations

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
