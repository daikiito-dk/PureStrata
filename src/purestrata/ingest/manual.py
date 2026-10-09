"""Ingest technical manuals and spec sheets (Markdown, PDF) into chunks.

The parser recognizes the structure maintenance documents actually use:
ATX headings for sections, numbered lists for procedures, pipe tables for
parts lists, and warning/caution lines (English or Japanese) for safety
notices. PDF is supported through the optional ``pdf`` extra (pypdf).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..pipeline.chunk import split_long_text
from ..pipeline.clean import clean_inline, normalize_block
from ..types import (
    MANUAL_SECTION,
    PART_RECORD,
    PROCEDURE,
    SAFETY_NOTICE,
    Chunk,
    Provenance,
    derive_doc_id,
    new_chunk,
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_LIST_RE = re.compile(r"^\s{0,3}(\d{1,3})[.)]\s+(.*)$")
_TABLE_ROW_RE = re.compile(r"^\s{0,3}\|")
_BLOCKQUOTE_RE = re.compile(r"^\s{0,3}>\s?(.*)$")
_NOTICE_RE = re.compile(
    r"^\s*(?:\*\*)?\s*(WARNING|CAUTION|NOTICE|DANGER|警告|注意|重要|ヒント)"
    r"\s*(?:\*\*)?\s*[:：]\s*(.*)$",
    re.IGNORECASE,
)
_FRONT_MATTER_RE = re.compile(r"^([A-Za-z][A-Za-z0-9 _.\-]{0,40})\s*[:：]\s*(.+)$")

_SEVERITY_MAP = {
    "warning": "warning",
    "danger": "warning",
    "警告": "warning",
    "caution": "caution",
    "注意": "caution",
    "notice": "note",
    "重要": "note",
    "ヒント": "note",
}

_PART_COL_ALIASES: dict[str, set[str]] = {
    "part_number": {
        "part no",
        "part no.",
        "part-no",
        "part number",
        "part_number",
        "part",
        "part#",
        "品番",
        "部品番号",
        "図番",
    },
    "name": {"name", "part name", "description", "名称", "部品名称", "品名"},
    "quantity": {"qty", "qty.", "quantity", "数量", "数"},
    "spec": {"spec", "specification", "仕様", "規格"},
}


def _slugify_key(text: str) -> str:
    return re.sub(r"\s+", "_", clean_inline(text).casefold())


def _strip_md(text: str) -> str:
    return clean_inline(text.replace("**", "").replace("__", "").replace("`", ""))


@dataclass
class _Block:
    kind: str  # "table" | "list" | "notice" | "quote" | "prose"
    lines: list[str]


@dataclass
class _Section:
    index: int
    title: str
    lines: list[str] = field(default_factory=list)


def ingest_manual(path: str | Path, doc_id: str | None = None) -> list[Chunk]:
    """Parse a manual or spec sheet into a list of chunks."""
    path = Path(path)
    doc_id = doc_id or derive_doc_id(path)
    raw = _read_text(path)
    return _parse_markdown(raw, doc_id=doc_id, source_path=str(path))


def _read_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return _extract_pdf_text(path)
    return path.read_text(encoding="utf-8", errors="replace")


def _extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "PDF ingestion requires the 'pdf' extra. Install it with: pip install 'purestrata[pdf]'"
        ) from exc
    reader = PdfReader(str(path))
    parts = []
    for number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        parts.append(f"# Page {number}\n\n{text}")
    return "\n\n".join(parts)


def _classify(line: str) -> str | None:
    if not line.strip():
        return None
    if _TABLE_ROW_RE.match(line):
        return "table"
    if _BLOCKQUOTE_RE.match(line):
        return "quote"
    if _LIST_RE.match(line):
        return "list"
    if _NOTICE_RE.match(line):
        return "notice"
    return "prose"


def _group_blocks(lines: list[str]) -> list[_Block]:
    blocks: list[_Block] = []
    current: _Block | None = None
    pending_blank = False
    for line in lines:
        kind = _classify(line)
        if kind is None:
            pending_blank = True
            continue
        if current is None or kind != current.kind or pending_blank:
            current = _Block(kind=kind, lines=[line])
            blocks.append(current)
            pending_blank = False
            continue
        current.lines.append(line)
    return blocks


def _parse_table(rows: list[str]) -> tuple[list[str], list[dict[str, str]]] | None:
    if len(rows) < 2:
        return None

    def cells(row: str) -> list[str]:
        return [c.strip() for c in row.strip().strip("|").split("|")]

    header = cells(rows[0])
    data_rows: list[dict[str, str]] = []
    for row in rows[1:]:
        row_cells = cells(row)
        if all(re.fullmatch(r":?-{2,}:?", c) for c in row_cells):
            continue
        if len(row_cells) != len(header):
            return None
        data_rows.append({h: c for h, c in zip(header, row_cells, strict=True)})
    return header, data_rows


def _map_part_columns(header: list[str]) -> dict[str, str]:
    """Map canonical part fields to the table's column names."""
    mapping: dict[str, str] = {}
    for column in header:
        key = _strip_md(column).casefold().rstrip(".")
        for field_name, aliases in _PART_COL_ALIASES.items():
            if key in aliases and field_name not in mapping:
                mapping[field_name] = column
    return mapping


def _parse_markdown(raw: str, doc_id: str, source_path: str) -> list[Chunk]:
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    chunks: list[Chunk] = []
    doc_meta: dict[str, str] = {}
    title_stack: list[str] = []
    section_counter = 0
    current: _Section | None = None
    preamble: list[str] = []

    def full_title() -> str:
        return " > ".join(title_stack)

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        chunks.extend(_chunks_from_section(current, doc_id, source_path, doc_meta))
        current = None

    for line in lines:
        heading = _HEADING_RE.match(line)
        if heading:
            flush()
            if not title_stack and preamble:
                section_counter += 1
                front = _Section(
                    index=section_counter, title="(front matter)", lines=list(preamble)
                )
                preamble = []
                chunks.extend(_chunks_from_section(front, doc_id, source_path, doc_meta))
            level = len(heading.group(1))
            title = _strip_md(heading.group(2))
            while len(title_stack) >= level:
                title_stack.pop()
            title_stack.append(title)
            section_counter += 1
            current = _Section(index=section_counter, title=full_title())
            continue
        if current is None:
            front = _FRONT_MATTER_RE.match(line.strip())
            if front:
                doc_meta[_slugify_key(front.group(1))] = clean_inline(front.group(2))
            elif line.strip():
                preamble.append(line)
            continue
        current.lines.append(line)

    flush()

    if current is None and preamble and not chunks:
        section_counter += 1
        front = _Section(index=section_counter, title="(front matter)", lines=preamble)
        chunks.extend(_chunks_from_section(front, doc_id, source_path, doc_meta))
    return chunks


def _doc_tags(doc_meta: dict[str, str]) -> dict:
    tags: dict = {"document": dict(doc_meta)}
    equipment = doc_meta.get("machine") or doc_meta.get("equipment") or doc_meta.get("document")
    if equipment:
        tags["equipment"] = equipment
    return tags


def _chunks_from_section(
    section: _Section, doc_id: str, source_path: str, doc_meta: dict[str, str]
) -> list[Chunk]:
    chunks: list[Chunk] = []
    base_locator = f"section {section.index}: {section.title}"
    tags = _doc_tags(doc_meta)
    notice_counter = 0
    part_counter = 0
    procedure_counter = 0
    prose_buffer: list[str] = []

    for block in _group_blocks(section.lines):
        if block.kind == "table":
            parsed = _parse_table(block.lines)
            if parsed is not None:
                header, rows = parsed
                mapping = _map_part_columns(header)
                if "part_number" in mapping and rows:
                    for row in rows:
                        part_counter += 1
                        chunks.append(
                            _part_chunk(
                                row,
                                mapping,
                                section,
                                base_locator,
                                part_counter,
                                doc_id,
                                source_path,
                                tags,
                            )
                        )
                    continue
                rendered = [
                    "; ".join(f"{h}: {row[h]}" for h in header if row.get(h)) for row in rows
                ]
                prose_buffer.extend(rendered)
                continue
            prose_buffer.extend(block.lines)
            continue
        if block.kind == "list":
            steps = []
            for item in block.lines:
                match = _LIST_RE.match(item)
                if match:
                    steps.append(_strip_md(match.group(2)))
            if steps:
                procedure_counter += 1
                chunks.append(
                    _procedure_chunk(
                        steps, section, base_locator, procedure_counter, doc_id, source_path, tags
                    )
                )
                continue
        if block.kind in ("notice", "quote"):
            first = block.lines[0]
            content_lines = block.lines[1:] if block.kind == "notice" else []
            if block.kind == "quote":
                unquoted = [
                    _BLOCKQUOTE_RE.match(ln).group(1)
                    for ln in block.lines
                    if _BLOCKQUOTE_RE.match(ln)
                ]
                first = unquoted[0] if unquoted else ""
                content_lines = unquoted[1:]
            match = _NOTICE_RE.match(first)
            if match:
                notice_counter += 1
                body = " ".join(
                    [_strip_md(match.group(2))] + [clean_inline(ln) for ln in content_lines]
                )
                severity = _SEVERITY_MAP.get(match.group(1).casefold(), "note")
                chunks.append(
                    _notice_chunk(
                        severity,
                        body,
                        section,
                        base_locator,
                        notice_counter,
                        doc_id,
                        source_path,
                        tags,
                    )
                )
                continue
            if block.kind == "quote":
                prose_buffer.extend(block.lines)
                continue
            # bare keyword line without colon matched nothing; keep it as prose
            prose_buffer.append(first)
            prose_buffer.extend(content_lines)
            continue
        prose_buffer.extend(block.lines)

    if prose_buffer:
        text = normalize_block("\n".join(prose_buffer))
        pieces = split_long_text(text, target=900, overlap=120)
        for i, piece in enumerate(pieces, start=1):
            suffix = f" (part {i})" if len(pieces) > 1 else ""
            provenance = Provenance(
                doc_id=doc_id, source_path=source_path, locator=f"{base_locator}{suffix}"
            )
            body = f"{section.title}\n{piece}" if section.title else piece
            chunks.append(
                new_chunk(MANUAL_SECTION, body, provenance, {"section": section.title, **tags})
            )
    return chunks


def _part_chunk(row, mapping, section, base_locator, number, doc_id, source_path, tags) -> Chunk:
    def value(field_name: str) -> str:
        column = mapping.get(field_name)
        return _strip_md(row.get(column, "")) if column else ""

    part_number = value("part_number")
    name = value("name")
    quantity = value("quantity")
    spec = value("spec")

    text = f"Part {part_number or '—'}: {name}"
    if quantity:
        text += f", qty {quantity}"
    if spec:
        text += f". Spec: {spec}"

    metadata = {"section": section.title, **tags}
    if part_number:
        metadata["part_number"] = part_number
    if name:
        metadata["name"] = name
    if quantity:
        metadata["quantity"] = quantity
    if spec:
        metadata["spec"] = spec
    provenance = Provenance(
        doc_id=doc_id, source_path=source_path, locator=f"{base_locator} > row {number}"
    )
    return new_chunk(PART_RECORD, text, provenance, metadata)


def _procedure_chunk(steps, section, base_locator, number, doc_id, source_path, tags) -> Chunk:
    equipment = tags.get("equipment")
    scope = f" on {equipment}" if equipment else ""
    text = f"Procedure: {section.title}{scope}. Steps: "
    text += " ".join(f"({i}) {step}" for i, step in enumerate(steps, start=1))
    metadata = {"title": section.title, "steps": steps, **tags}
    provenance = Provenance(
        doc_id=doc_id, source_path=source_path, locator=f"{base_locator} > procedure {number}"
    )
    return new_chunk(PROCEDURE, text, provenance, metadata)


def _notice_chunk(
    severity, body, section, base_locator, number, doc_id, source_path, tags
) -> Chunk:
    metadata = {"severity": severity, "section": section.title, **tags}
    provenance = Provenance(
        doc_id=doc_id, source_path=source_path, locator=f"{base_locator} > notice {number}"
    )
    return new_chunk(SAFETY_NOTICE, clean_inline(body), provenance, metadata)
