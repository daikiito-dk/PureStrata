# Manual ingestion

Active contributors: DK

## Purpose

`ingest_manual` reads Markdown manuals directly and extracts text from PDFs through the optional `pypdf` extra. It turns document structure into typed, searchable chunks while keeping each chunk tied to its section and source file.

## Key abstractions

| Abstraction | File | Notes |
| --- | --- | --- |
| `ingest_manual`, `_read_text`, `_extract_pdf_text` | `src/purestrata/ingest/manual.py` | Entry point and Markdown/PDF dispatch |
| `_classify`, `_group_blocks`, `_Section` | `src/purestrata/ingest/manual.py` | Detects structural blocks and groups document sections |
| `_parse_table`, `_map_part_columns`, `_part_chunk` | `src/purestrata/ingest/manual.py` | Converts recognized parts tables to `part_record` chunks |
| `_procedure_chunk`, `_notice_chunk`, `_chunks_from_section` | `src/purestrata/ingest/manual.py` | Builds procedures, notices, and prose section chunks |
| `split_long_text` | `src/purestrata/pipeline/chunk.py` | Splits long prose while retaining overlap |
| `Chunk`, `Provenance`, kind constants | `src/purestrata/types.py` | Record shape, provenance, and deterministic IDs |

## How it works

```mermaid
graph LR
    IN["Markdown or PDF"] --> READ["Text reader"]
    READ --> STRUCT["Section and block parser"]
    STRUCT --> KIND["Manual, procedure, notice, or part chunks"]
    KIND --> SPLIT["Long-prose splitter"]
    SPLIT --> OUT["Chunks with provenance"]
```

### Read and classify

`ingest_manual(path, doc_id=None)` derives a document ID from the path when one is not supplied. `_read_text` reads non-PDF input as UTF-8 with replacement for invalid bytes; a `.pdf` suffix dispatches to `_extract_pdf_text`. PDF extraction imports `pypdf` on demand, adds a `# Page N` heading for each extracted page, and raises a `RuntimeError` with the install command if the extra is missing.

`_parse_markdown` recognizes ATX headings and builds nested titles with ` > ` separators. Before the first heading, lines shaped like `Key: Value` become document metadata. `_doc_tags` attaches those values under `metadata.document` and derives an `equipment` tag from `machine`, `equipment`, or `document` when present.

`_classify` labels nonblank lines as table, quote, numbered list, notice, or prose. `_group_blocks` combines adjacent lines of the same class, but a blank line starts a new block. Section content is then handled according to its block type:

- **Prose** becomes `manual_section` chunks. `normalize_block` cleans whitespace, then `split_long_text` uses a 900-character target and 120-character overlap. A split section gets one locator per part.
- **Numbered lists** become one `procedure` per list block. Step text is stored in `metadata.steps`; the section title is stored as `metadata.title`.
- **Notices** recognize `WARNING`, `CAUTION`, `NOTICE`, `DANGER`, `警告`, `注意`, `重要`, and `ヒント` followed by an English or Japanese colon. A matching first line in a blockquote is also treated as a notice. Severity maps danger/警告 to warning, caution/注意 to caution, and notice/重要/ヒント to note.
- **Tables** become `part_record` chunks only when a header maps a part-number column and at least one data row is present. `_parse_table` skips Markdown separator rows and rejects rows whose cell count differs from the header. Other valid tables are rendered into prose; they are not discarded.

All chunks carry the section title and document tags where applicable. Their provenance locator starts with `section N: <nested title>`; part rows, procedures, notices, and additional prose parts append a descriptive sub-locator. Chunk IDs are then derived from the document ID, kind, and locator by `new_chunk`.

## Integration points

- The `ingest-manual` CLI and Python API write returned chunks into the JSONL corpus; see [Corpus](../primitives/corpus.md).
- The record kinds, metadata, and provenance fields are shared with the data model in [Records and provenance](../primitives/records-and-provenance.md).
- The bundled English and Japanese manuals exercise these parsing paths: `examples/data/manuals/lathe_mk3_maintenance.md` and `examples/data/manuals/ja/cnc_press_maintenance.md`.

## Entry points for modification

- Add or change recognized notice labels and severity mappings in `_NOTICE_RE` and `_SEVERITY_MAP` in `src/purestrata/ingest/manual.py`.
- Change Markdown table column aliases in `_PART_COL_ALIASES`; adjust table handling in `_parse_table` or `_map_part_columns`.
- Change list recognition in `_LIST_RE`, then check grouping and metadata in `_procedure_chunk`.
- Adjust prose sizing by changing the `split_long_text` call in `_chunks_from_section`; the splitter defaults and boundary behavior live in `src/purestrata/pipeline/chunk.py`.
- Keep the parser's English and Japanese examples covered by `tests/test_ingest_manual.py`.

## Key source files

| File | Role |
| --- | --- |
| `src/purestrata/ingest/manual.py` | Manual dispatch, Markdown structure, and chunk constructors |
| `src/purestrata/pipeline/chunk.py` | Sentence-aware long-text splitting with overlap |
| `src/purestrata/pipeline/clean.py` | Inline and block text normalization |
| `src/purestrata/types.py` | Chunk kinds, provenance, and `new_chunk` |
| `tests/test_ingest_manual.py` | English/Japanese, chunk kinds, metadata, and stable-ID coverage |
