"""Ingest STEP 3D models (ISO 10303-21, AP203/AP214/AP242) into drawing chunks.

A dependency-free reader for the metadata LLM workflows need from a 3D
model: file header, product names, the assembly tree with quantities,
length units, cylindrical features (holes, bores, pins), and point bounds.
It does not evaluate B-rep topology; bounds are the extent of all
CARTESIAN_POINT entities, which can slightly exceed the solid itself.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from ..pipeline.clean import clean_inline
from ..types import DRAWING, Chunk, Provenance, derive_doc_id, new_chunk, sha256_file
from .geometry import describe_circular_features, size_from_bounds, summarize_circular_features

_ENTITY_RE = re.compile(r"^#(\d+)\s*=\s*(.*)$", re.S)
_SIMPLE_RE = re.compile(r"^([A-Za-z0-9_]+)\s*\((.*)\)$", re.S)
_X2_RE = re.compile(r"\\X2\\((?:[0-9A-Fa-f]{4})+)\\X0\\")
_X4_RE = re.compile(r"\\X4\\((?:[0-9A-Fa-f]{8})+)\\X0\\")
_X_RE = re.compile(r"\\X\\([0-9A-Fa-f]{2})")

_PDF_TYPES = {
    "PRODUCT_DEFINITION_FORMATION",
    "PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE",
}
_PD_TYPES = {"PRODUCT_DEFINITION", "PRODUCT_DEFINITION_WITH_ASSOCIATED_DOCUMENTS"}

_SI_PREFIX_UNITS = {
    ".MILLI.": "mm",
    ".CENTI.": "cm",
    "$": "m",
}
_CONVERSION_UNITS = {"INCH": "inches", "FOOT": "feet"}


class _Ref(int):
    """An entity reference such as #42."""


def _split_statements(text: str) -> list[str]:
    """Split Part 21 text on ';' outside string literals and comments."""
    statements: list[str] = []
    buf: list[str] = []
    i = 0
    in_string = False
    while i < len(text):
        ch = text[i]
        if in_string:
            buf.append(ch)
            if ch == "'":
                in_string = False
        elif ch == "'":
            in_string = True
            buf.append(ch)
        elif ch == "/" and text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = len(text) if end == -1 else end + 2
            continue
        elif ch == ";":
            statements.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def _split_args(text: str) -> list[str]:
    args: list[str] = []
    depth = 0
    in_string = False
    start = 0
    for i, ch in enumerate(text):
        if in_string:
            if ch == "'":
                in_string = False
        elif ch == "'":
            in_string = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            args.append(text[start:i])
            start = i + 1
    last = text[start:]
    if last.strip() or args:
        args.append(last)
    return [arg.strip() for arg in args]


def decode_string(raw: str) -> str:
    """Decode a Part 21 string literal, including \\X2\\ UTF-16 runs used for Japanese."""
    text = raw[1:-1] if raw.startswith("'") and raw.endswith("'") else raw
    text = text.replace("''", "'")
    text = _X2_RE.sub(
        lambda m: bytes.fromhex(m.group(1)).decode("utf-16-be", errors="replace"), text
    )
    text = _X4_RE.sub(
        lambda m: bytes.fromhex(m.group(1)).decode("utf-32-be", errors="replace"), text
    )
    text = _X_RE.sub(lambda m: bytes.fromhex(m.group(1)).decode("latin-1"), text)
    return text.replace("\\\\", "\\")


def _parse_value(token: str):
    token = token.strip()
    if not token or token in ("$", "*"):
        return None
    if token.startswith("'"):
        return decode_string(token)
    if token.startswith("#"):
        try:
            return _Ref(int(token[1:]))
        except ValueError:
            return token
    if token.startswith("("):
        return [_parse_value(part) for part in _split_args(token[1:-1])]
    if token.startswith(".") and token.endswith("."):
        return token
    try:
        return float(token)
    except ValueError:
        pass
    typed = _SIMPLE_RE.match(token)
    if typed:
        inner = _split_args(typed.group(2))
        return _parse_value(inner[0]) if len(inner) == 1 else token
    return token


def _arg(args: list, index: int):
    return args[index] if index < len(args) else None


def _text(value) -> str:
    return clean_inline(value) if isinstance(value, str) else ""


def _read_sections(path: Path) -> tuple[dict[str, list], dict[int, tuple[str, list, str]]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    header: dict[str, list] = {}
    entities: dict[int, tuple[str, list, str]] = {}
    mode: str | None = None
    for statement in _split_statements(text):
        upper = statement.upper()
        if upper == "HEADER":
            mode = "header"
            continue
        if upper == "DATA" or upper.startswith("DATA("):
            mode = "data"
            continue
        if upper == "ENDSEC":
            mode = None
            continue
        if mode == "header":
            match = _SIMPLE_RE.match(statement)
            if match:
                header[match.group(1).upper()] = [
                    _parse_value(arg) for arg in _split_args(match.group(2))
                ]
        elif mode == "data":
            match = _ENTITY_RE.match(statement)
            if not match:
                continue
            entity_id = int(match.group(1))
            body = match.group(2).strip()
            simple = _SIMPLE_RE.match(body)
            if simple and not body.startswith("("):
                args = [_parse_value(arg) for arg in _split_args(simple.group(2))]
                entities[entity_id] = (simple.group(1).upper(), args, body)
            else:
                entities[entity_id] = ("COMPLEX", [], body)
    return header, entities


def _detect_units(entities: dict[int, tuple[str, list, str]]) -> str:
    for kind, _args, raw in entities.values():
        upper = raw.upper().replace(" ", "")
        if kind == "COMPLEX" and "LENGTH_UNIT" in upper:
            for name, units in _CONVERSION_UNITS.items():
                if f"CONVERSION_BASED_UNIT('{name}'" in upper:
                    return units
            match = re.search(r"SI_UNIT\(([^,]*),\.METRE\.\)", upper)
            if match:
                return _SI_PREFIX_UNITS.get(match.group(1), "unspecified")
    return "unspecified"


def _header_info(header: dict[str, list]) -> dict:
    info: dict = {}
    description = _arg(header.get("FILE_DESCRIPTION", []), 0)
    if isinstance(description, list):
        joined = " ".join(_text(d) for d in description if _text(d))
        if joined:
            info["description"] = joined
    file_name = header.get("FILE_NAME", [])
    for index, key in ((0, "name"), (1, "timestamp"), (5, "originating_system")):
        value = _text(_arg(file_name, index))
        if value:
            info[key] = value
    for index, key in ((2, "author"), (3, "organization")):
        values = _arg(file_name, index)
        if isinstance(values, list):
            joined = ", ".join(_text(v) for v in values if _text(v))
            if joined:
                info[key] = joined
    schemas = _arg(header.get("FILE_SCHEMA", []), 0)
    if isinstance(schemas, list) and schemas:
        schema = _text(schemas[0])
        if schema:
            info["schema"] = schema.split()[0]
    return info


def parse_step(path: str | Path) -> dict:
    """Parse a STEP Part 21 file into a metadata summary."""
    path = Path(path)
    header, entities = _read_sections(path)

    products: dict[int, dict] = {}
    pdf_to_product: dict[int, int] = {}
    pd_to_product: dict[int, int] = {}
    for entity_id, (kind, args, _raw) in entities.items():
        if kind == "PRODUCT":
            products[entity_id] = {
                "id": _text(_arg(args, 0)),
                "name": _text(_arg(args, 1)),
                "description": _text(_arg(args, 2)),
            }
        elif kind in _PDF_TYPES and isinstance(_arg(args, 2), _Ref):
            pdf_to_product[entity_id] = int(args[2])
    for entity_id, (kind, args, _raw) in entities.items():
        if kind in _PD_TYPES and isinstance(_arg(args, 2), _Ref):
            product = pdf_to_product.get(int(args[2]))
            if product is not None:
                pd_to_product[entity_id] = product

    edges: Counter[tuple[int, int]] = Counter()
    for kind, args, _raw in entities.values():
        if kind == "NEXT_ASSEMBLY_USAGE_OCCURRENCE":
            parent = pd_to_product.get(int(args[3])) if isinstance(_arg(args, 3), _Ref) else None
            child = pd_to_product.get(int(args[4])) if isinstance(_arg(args, 4), _Ref) else None
            if parent is not None and child is not None:
                edges[(parent, child)] += 1

    children = {child for _parent, child in edges}
    roots = [pid for pid in products if pid not in children]
    assembly = [
        {
            "parent": products[parent]["id"],
            "child": products[child]["id"],
            "quantity": quantity,
        }
        for (parent, child), quantity in edges.items()
    ]

    units = _detect_units(entities)
    cylinders = [
        (float(args[2]) * 2, "", f"#{entity_id}")
        for entity_id, (kind, args, _raw) in entities.items()
        if kind == "CYLINDRICAL_SURFACE" and isinstance(_arg(args, 2), float)
    ]
    if not cylinders:
        cylinders = [
            (float(args[2]) * 2, "", f"#{entity_id}")
            for entity_id, (kind, args, _raw) in entities.items()
            if kind == "CIRCLE" and isinstance(_arg(args, 2), float)
        ]

    points = [
        args[1]
        for kind, args, _raw in entities.values()
        if kind == "CARTESIAN_POINT" and isinstance(_arg(args, 1), list)
    ]
    bounds = _point_bounds(points)
    entity_counts = Counter(kind for kind, _args, _raw in entities.values())

    return {
        "header": _header_info(header),
        "units": units,
        "products": [products[pid] for pid in products],
        "root_products": [products[pid] for pid in roots],
        "assembly": assembly,
        "circular_features": summarize_circular_features(cylinders, units),
        "bounds": bounds,
        "size": size_from_bounds(bounds),
        "entity_counts": dict(entity_counts.most_common(25)),
        "entity_total": len(entities),
    }


def _point_bounds(points: list[list]) -> dict | None:
    coords = [p for p in points if len(p) >= 2 and all(isinstance(v, float) for v in p)]
    if not coords:
        return None
    bounds = {
        "min_x": min(p[0] for p in coords),
        "min_y": min(p[1] for p in coords),
        "max_x": max(p[0] for p in coords),
        "max_y": max(p[1] for p in coords),
    }
    three_d = [p for p in coords if len(p) >= 3]
    if three_d:
        bounds["min_z"] = min(p[2] for p in three_d)
        bounds["max_z"] = max(p[2] for p in three_d)
    return bounds


def ingest_step(path: str | Path, doc_id: str | None = None) -> list[Chunk]:
    """Parse a STEP model into a single searchable drawing chunk."""
    path = Path(path)
    parsed = parse_step(path)
    doc_id = doc_id or derive_doc_id(path)
    root = (parsed["root_products"] or parsed["products"] or [{}])[0]
    drawing_id = root.get("id") or derive_doc_id(path)
    title_block = {k: v for k, v in (("title", root.get("name")), ("part_no", root.get("id"))) if v}

    metadata = {
        "format": "step",
        "drawing_id": drawing_id,
        "file_name": path.name,
        "units": parsed["units"],
        "size": parsed["size"],
        "circular_features": parsed["circular_features"],
        "diameter_callouts": [],
        "header": parsed["header"],
        "products": parsed["products"],
        "assembly": parsed["assembly"],
        "layers": [],
        "entity_counts": parsed["entity_counts"],
        "entity_total": parsed["entity_total"],
        "title_block": title_block,
        "bounds": parsed["bounds"],
    }
    text = _model_text(drawing_id, path.name, parsed, title_block)
    entity_refs = sorted(
        {ref for feature in parsed["circular_features"] for ref in feature.get("entity_refs", [])}
    )
    provenance = Provenance(
        doc_id=doc_id,
        source_path=str(path),
        locator="model",
        source_sha256=sha256_file(path),
        anchor={"entity_refs": entity_refs} if entity_refs else None,
    )
    return [new_chunk(DRAWING, text, provenance, metadata)]


def _model_text(drawing_id: str, file_name: str, parsed: dict, title_block: dict) -> str:
    parts = [f"3D model {drawing_id} ({file_name})"]
    if title_block.get("title"):
        parts.append(f"Title: {title_block['title']}")
    header = parsed["header"]
    if header.get("description"):
        parts.append(f"Description: {header['description']}")
    if header.get("schema"):
        parts.append(f"Schema: {header['schema']}")
    parts.append(f"Units: {parsed['units']}")
    if parsed["products"]:
        names = []
        for product in parsed["products"]:
            label = " ".join(v for v in (product["id"], product["name"]) if v)
            if product["description"]:
                label += f" ({product['description']})"
            names.append(label)
        parts.append("Products: " + "; ".join(names))
    if parsed["assembly"]:
        parts.append(
            "Assembly: "
            + ", ".join(
                f"{edge['parent']} contains {edge['child']} x{edge['quantity']}"
                for edge in parsed["assembly"]
            )
        )
    if parsed["circular_features"]:
        parts.append(
            "Cylindrical features: "
            + describe_circular_features(parsed["circular_features"], parsed["units"])
        )
    size = parsed["size"]
    if size:
        dims = " x ".join(f"{v:g}" for v in size.values())
        parts.append(f"Size: {dims} {parsed['units']}")
    return ". ".join(parts) + "."
