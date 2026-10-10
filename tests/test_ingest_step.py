"""STEP (ISO 10303-21) ingestion and shared geometry helper tests."""

from __future__ import annotations

from purestrata import ingest_dxf, ingest_step, parse_step
from purestrata.ingest.geometry import parse_diameter_callouts, to_mm
from purestrata.ingest.step import decode_string


def test_step_header_and_units(step_path):
    parsed = parse_step(step_path)
    assert parsed["units"] == "mm"
    header = parsed["header"]
    assert header["schema"] == "AUTOMOTIVE_DESIGN"
    assert header["organization"] == "Kansai Machine Works"
    assert header["description"] == "Mounting bracket assembly MK3"


def test_step_products_and_japanese_names(step_path):
    products = {p["id"]: p for p in parse_step(step_path)["products"]}
    assert set(products) == {"BRK-ASSY-01", "BRK-0042", "PIN-0110"}
    assert products["PIN-0110"]["name"] == "位置決めピン"
    assert products["BRK-0042"]["description"] == "SS400 plate t=6"


def test_step_assembly_quantities(step_path):
    parsed = parse_step(step_path)
    edges = {(e["parent"], e["child"]): e["quantity"] for e in parsed["assembly"]}
    assert edges == {("BRK-ASSY-01", "BRK-0042"): 1, ("BRK-ASSY-01", "PIN-0110"): 2}
    assert [p["id"] for p in parsed["root_products"]] == ["BRK-ASSY-01"]


def test_step_cylindrical_features_and_bounds(step_path):
    parsed = parse_step(step_path)
    features = {f["diameter_mm"]: f["count"] for f in parsed["circular_features"]}
    assert features == {9.0: 2, 25.0: 1}
    assert parsed["size"] == {"width": 100.0, "height": 80.0, "depth": 6.0}


def test_step_chunk(step_path):
    chunks = ingest_step(step_path)
    assert len(chunks) == 1
    model = chunks[0]
    assert model.kind == "drawing"
    assert model.metadata["format"] == "step"
    assert model.metadata["drawing_id"] == "BRK-ASSY-01"
    assert model.provenance.locator == "model"
    assert "PIN-0110 x2" in model.text
    assert "diameter 25 mm x1" in model.text


def test_decode_step_strings():
    assert decode_string("'It''s'") == "It's"
    assert decode_string(r"'\X2\30D430F3\X0\'") == "ピン"
    assert decode_string(r"'caf\X\E9'") == "café"


def test_dxf_circular_features_and_fits(dxf_path):
    drawing = ingest_dxf(dxf_path)[0]
    assert drawing.metadata["format"] == "dxf"
    assert drawing.metadata["circular_features"] == [
        {"diameter": 25.0, "diameter_mm": 25.0, "count": 1, "layers": ["PART-OUTLINE"]}
    ]
    assert drawing.metadata["diameter_callouts"][0]["fit"] == "H7"
    assert drawing.metadata["size"] == {"width": 100.0, "height": 80.0}


def test_diameter_callout_variants():
    callouts = parse_diameter_callouts(["Ø10 h6", "%%C8", "BORE DIA 25 H7", "LENGTH 40"])
    assert [(c["nominal"], c["fit"]) for c in callouts] == [(10.0, "h6"), (8.0, None), (25.0, "H7")]


def test_unit_conversion():
    assert to_mm(1.0, "inches") == 25.4
    assert to_mm(2.5, "cm") == 25.0
    assert to_mm(1.0, "unspecified") is None
