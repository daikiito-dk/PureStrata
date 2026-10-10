"""Geometry helpers shared by the DXF and STEP adapters.

Diameters are stored in the drawing's native units and, when the units are
known, normalized to millimetres so drawings from different CAD systems can
be searched with one filter.
"""

from __future__ import annotations

import re
from collections import defaultdict

MM_PER_UNIT = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0,
    "inches": 25.4,
    "feet": 304.8,
}

# Diameter callouts as written on drawings: "DIA 25 H7", "Ø10", "φ8 h6", and
# AutoCAD's "%%C" diameter control code.
_CALLOUT_RE = re.compile(
    r"(?:\bDIA\b\.?|Ø|⌀|φ|Φ|%%[Cc])\s*(\d+(?:\.\d+)?)(?:\s*([A-Za-z]{1,2}\d{1,2})\b)?"
)


def to_mm(value: float, units: str) -> float | None:
    factor = MM_PER_UNIT.get(units)
    return round(value * factor, 4) if factor is not None else None


def summarize_circular_features(items: list[tuple[float, str]], units: str) -> list[dict]:
    """Group (diameter, layer) pairs into one entry per distinct diameter."""
    counts: dict[float, int] = defaultdict(int)
    layers: dict[float, set[str]] = defaultdict(set)
    for diameter, layer in items:
        key = round(diameter, 4)
        counts[key] += 1
        if layer:
            layers[key].add(layer)
    return [
        {
            "diameter": diameter,
            "diameter_mm": to_mm(diameter, units),
            "count": counts[diameter],
            "layers": sorted(layers[diameter]),
        }
        for diameter in sorted(counts)
    ]


def parse_diameter_callouts(texts: list[str]) -> list[dict]:
    """Extract diameter callouts and ISO fit classes from text annotations."""
    callouts = []
    for text in texts:
        for match in _CALLOUT_RE.finditer(text):
            callouts.append(
                {
                    "nominal": float(match.group(1)),
                    "fit": match.group(2),
                    "text": text,
                }
            )
    return callouts


def size_from_bounds(bounds: dict | None) -> dict | None:
    if not bounds:
        return None
    size = {
        "width": round(bounds["max_x"] - bounds["min_x"], 4),
        "height": round(bounds["max_y"] - bounds["min_y"], 4),
    }
    if "max_z" in bounds:
        size["depth"] = round(bounds["max_z"] - bounds["min_z"], 4)
    return size


def feature_diameter_mm(feature: dict) -> float:
    """Diameter for filtering: millimetres when known, otherwise native units."""
    value = feature.get("diameter_mm")
    return value if value is not None else feature["diameter"]


def format_number(value: float) -> str:
    return f"{value:g}"


def describe_circular_features(features: list[dict], units: str) -> str:
    unit = "mm" if any(f.get("diameter_mm") is not None for f in features) else units
    return ", ".join(
        f"diameter {format_number(feature_diameter_mm(f))} {unit} x{f['count']}" for f in features
    )
