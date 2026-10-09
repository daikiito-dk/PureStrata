"""Ingest CAD drawings (ASCII DXF) into PureStrata chunks.

PureStrata ships a minimal, dependency-free DXF reader for the metadata
that LLM workflows actually need: layers, entity inventories, text
annotations, title-block fields, and geometric bounds. Binary DXF is not
supported.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

from ..pipeline.clean import clean_inline
from ..types import DRAWING, Chunk, Provenance, derive_doc_id, new_chunk

_UNIT_CODES = {
    0: "unitless",
    1: "inches",
    2: "feet",
    4: "mm",
    5: "cm",
    6: "m",
}

_MTEXT_ESCAPE_RE = re.compile(r"\\[Pp]")
_TITLE_FIELD_RE = re.compile(r"^([A-Za-z][A-Za-z0-9 _/.\-#]{0,40}?)\s*[:：]\s*(.+)$")

_X_CODES = frozenset({10, 11, 12, 13})
_Y_CODES = frozenset({20, 21, 22, 23})


def _to_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _to_int(value: str) -> int | None:
    try:
        return int(float(value))
    except ValueError:
        return None


def _read_pairs(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    pairs: list[tuple[int, str]] = []
    i = 0
    while i < len(lines) - 1:
        try:
            code = int(lines[i].strip())
        except ValueError:
            i += 1
            continue
        pairs.append((code, lines[i + 1].strip()))
        i += 2
    return pairs


def _clean_text(value: str) -> str:
    value = _MTEXT_ESCAPE_RE.sub(" ", value)
    value = value.replace("{", "").replace("}", "")
    return clean_inline(value)


def _norm_key(key: str) -> str:
    return re.sub(r"[^0-9a-z]+", "_", key.casefold()).strip("_")


def parse_dxf(path: str | Path) -> dict:
    """Parse an ASCII DXF file into a metadata summary."""
    path = Path(path)
    layers: list[dict] = []
    blocks: list[dict] = []
    entities: list[dict] = []
    header_vars: dict[str, str] = {}

    section: str | None = None
    expecting_section_name = False
    current_entity: dict | None = None
    current_layer: dict | None = None
    current_block: dict | None = None
    current_var: str | None = None

    for code, value in _read_pairs(path):
        if code == 0:
            marker = value.upper()
            if marker == "SECTION":
                expecting_section_name = True
                section = None
                current_entity = current_layer = current_block = None
                continue
            if marker == "ENDSEC":
                section = None
                current_entity = current_layer = current_block = None
                continue
            if section == "ENTITIES":
                current_entity = {
                    "type": marker,
                    "layer": "",
                    "texts": [],
                    "points": {},
                    "radius": None,
                }
                entities.append(current_entity)
            elif section == "TABLES" and marker == "LAYER":
                current_layer = {"name": "", "color": None}
                layers.append(current_layer)
            elif section == "BLOCKS" and marker == "BLOCK":
                current_block = {"name": ""}
                blocks.append(current_block)
            continue
        if expecting_section_name:
            if code == 2:
                section = value.upper()
                expecting_section_name = False
            continue
        if section == "HEADER":
            if code == 9:
                current_var = value.strip()
            elif current_var is not None:
                header_vars.setdefault(f"{current_var}:{code}", value.strip())
            continue
        if current_entity is not None:
            if code == 8:
                current_entity["layer"] = value
            elif code in (1, 3):
                current_entity["texts"].append(value)
            elif code in _X_CODES or code in _Y_CODES:
                current_entity["points"][code] = _to_float(value)
            elif code == 40:
                current_entity["radius"] = _to_float(value)
            continue
        if current_layer is not None:
            if code == 2:
                current_layer["name"] = value
            elif code == 62:
                current_layer["color"] = _to_int(value)
            continue
        if current_block is not None:
            if code == 2:
                current_block["name"] = value
            continue

    units_code = _to_int(header_vars.get("$INSUNITS:70", ""))
    units = _UNIT_CODES.get(units_code or -1, "unspecified")

    text_annotations = []
    title_block: dict[str, str] = {}
    entity_counts: Counter[str] = Counter()
    per_layer_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for entity in entities:
        entity_counts[entity["type"]] += 1
        per_layer_counts[entity["layer"] or "0"][entity["type"]] += 1
        if entity["type"] in ("TEXT", "MTEXT"):
            joined = _clean_text(" ".join(entity["texts"]))
            if joined:
                text_annotations.append(joined)
                match = _TITLE_FIELD_RE.match(joined)
                if match:
                    title_block.setdefault(_norm_key(match.group(1)), clean_inline(match.group(2)))

    return {
        "units": units,
        "layers": layers,
        "blocks": [b["name"] for b in blocks],
        "entity_counts": dict(entity_counts),
        "per_layer_counts": {name: dict(counts) for name, counts in per_layer_counts.items()},
        "text_annotations": text_annotations,
        "title_block": title_block,
        "bounds": _compute_bounds(entities),
    }


def _compute_bounds(entities: list[dict]) -> dict | None:
    xs: list[float] = []
    ys: list[float] = []
    for entity in entities:
        points = entity["points"]
        kind = entity["type"]
        if kind == "LINE":
            for x_code, y_code in ((10, 20), (11, 21)):
                if x_code in points and y_code in points and points[x_code] is not None:
                    xs.append(points[x_code])
                    ys.append(points[y_code])
        elif kind in ("CIRCLE", "ARC"):
            radius = entity["radius"]
            if radius is not None and 10 in points and 20 in points and points[10] is not None:
                xs.extend([points[10] - radius, points[10] + radius])
                ys.extend([points[20] - radius, points[20] + radius])
        elif (
            kind in ("TEXT", "MTEXT") and points.get(10) is not None and points.get(20) is not None
        ):
            xs.append(points[10])
            ys.append(points[20])
    if not xs:
        return None
    return {"min_x": min(xs), "min_y": min(ys), "max_x": max(xs), "max_y": max(ys)}


def ingest_dxf(path: str | Path, doc_id: str | None = None) -> list[Chunk]:
    """Parse a DXF drawing into a single searchable drawing chunk."""
    path = Path(path)
    parsed = parse_dxf(path)
    doc_id = doc_id or derive_doc_id(path)
    title_block = parsed["title_block"]
    drawing_id = title_block.get("dwg_no") or title_block.get("part_no") or derive_doc_id(path)

    text = _drawing_text(drawing_id, path.name, title_block, parsed)
    metadata = {
        "drawing_id": drawing_id,
        "file_name": path.name,
        "units": parsed["units"],
        "layers": parsed["layers"],
        "entity_counts": parsed["entity_counts"],
        "per_layer_counts": parsed["per_layer_counts"],
        "text_annotations": parsed["text_annotations"],
        "title_block": title_block,
        "bounds": parsed["bounds"],
        "blocks": parsed["blocks"],
    }
    provenance = Provenance(doc_id=doc_id, source_path=str(path), locator="drawing")
    return [new_chunk(DRAWING, text, provenance, metadata)]


def _drawing_text(drawing_id: str, file_name: str, title_block: dict, parsed: dict) -> str:
    parts = [f"Drawing {drawing_id} ({file_name})"]
    for key, label in (
        ("title", "Title"),
        ("material", "Material"),
        ("scale", "Scale"),
        ("revision", "Revision"),
        ("part_no", "Part"),
    ):
        if key in title_block:
            parts.append(f"{label}: {title_block[key]}")
    parts.append(f"Units: {parsed['units']}")
    layer_names = [layer["name"] for layer in parsed["layers"] if layer["name"]]
    if layer_names:
        parts.append("Layers: " + ", ".join(layer_names))
    counts = parsed["entity_counts"]
    if counts:
        parts.append(
            "Entities: " + ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))
        )
    annotations = parsed["text_annotations"]
    if annotations:
        parts.append("Annotations: " + "; ".join(annotations[:10]))
    return ". ".join(parts) + "."
