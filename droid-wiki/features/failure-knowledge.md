# Failure knowledge ingestion

Active contributors: DK

## Purpose

`ingest_failures` turns CSV or JSONL incident rows into one searchable `failure_case` chunk per record. Flexible English and Japanese column names map into consistent metadata, while the synthesized text retains the incident details needed for full-text retrieval.

## Key abstractions

| Abstraction | File | Notes |
| --- | --- | --- |
| `ingest_failures` | `src/purestrata/ingest/failures.py` | Creates one chunk for each input row |
| `_COLUMN_ALIASES`, `_norm_header`, `_field_map` | `src/purestrata/ingest/failures.py` | Maps English/Japanese headers to canonical fields |
| `_read_rows` | `src/purestrata/ingest/failures.py` | Reads CSV with BOM handling or JSONL |
| `_norm_severity`, `_TAG_SPLIT_RE` | `src/purestrata/ingest/failures.py` | Normalizes severity and separates tags |
| `Chunk`, `Provenance`, `FAILURE_CASE` | `src/purestrata/types.py` | Shared record type, locator, and kind |
| `clean_inline` | `src/purestrata/pipeline/clean.py` | Normalizes whitespace in values |

## How it works

```mermaid
graph LR
    SRC["CSV or JSONL"] --> READ["Row reader"]
    READ --> MAP["Header mapping and normalization"]
    MAP --> TEXT["Failure text and metadata"]
    TEXT --> CHUNK["failure_case chunk"]
    CHUNK --> CORPUS["Portable corpus"]
```

`_read_rows` treats a `.jsonl` suffix as UTF-8 JSON Lines, skips blank lines, and parses each remaining line as a JSON object. Other suffixes use `csv.DictReader` with `utf-8-sig`, which removes an Excel UTF-8 BOM. Rows are numbered from one in their file order.

For each row, `_field_map` normalizes each header by collapsing whitespace, hyphens, and periods to underscores after `clean_inline` and `casefold`. It maps canonical field names to the first matching input column. The aliases in `_COLUMN_ALIASES` are:

| Canonical field | English aliases | Japanese aliases |
| --- | --- | --- |
| `case_id` | `case_id`, `id`, `case`, `no`, `case_no` | `件番`, `ケース番号`, `管理番号` |
| `equipment` | `equipment`, `machine`, `asset` | `設備`, `機械`, `装置`, `対象設備` |
| `part_number` | `part_number`, `part_no`, `part` | `品番`, `部品番号`, `図番` |
| `symptom` | `symptom`, `failure`, `problem`, `fault` | `現象`, `症状`, `不具合内容`, `故障` |
| `cause` | `cause`, `root_cause` | `原因`, `真因` |
| `countermeasure` | `countermeasure`, `action`, `fix`, `remedy` | `対策`, `処置` |
| `severity` | `severity`, `level`, `impact` | `重要度`, `深刻度`, `レベル` |
| `reported_at` | `date`, `reported_at`, `report_date` | `報告日`, `発生日`, `日付` |
| `status` | `status`, `state` | `状況`, `ステータス` |
| `tags` | `tags`, `keywords` | `タグ`, `キーワード` |

Each mapped value is cleaned to a single line. Missing or unrecognized severity becomes `unspecified`; recognized values normalize to `low`, `medium`, `high`, or `critical`. The accepted labels include English variants (`minor`, `moderate`, `major`, `severe`) and Japanese labels (`低`/`軽`, `中`, `高`, `重大`). Tags split on semicolon, comma, Japanese comma, vertical bar, or slash; empty items are removed.

The `text` field is synthesized in a stable order: an equipment-specific failure statement (or a generic failure statement), then available symptom, part number, cause, and countermeasure, followed by severity and optional tags. It is one sentence-like string per input row, with labels such as `Symptom:` and `Root cause:` included for retrieval.

Every chunk has `case_id`, `equipment`, `symptom`, `cause`, `countermeasure`, `severity`, and one-based `source_row` in metadata. An empty case ID falls back to `f"{doc_id}-c{index:03d}"`. `part_number`, `reported_at`, `status`, and `tags` are included only when present; `tags` is a list. Provenance keeps the input path and locator `row N`.

## Integration points

- [LLM tools](llm-tools.md) describes how `search_failure_cases` retrieves these chunks and uses their structured fields.
- [Fine-tune exports](fine-tune-exports.md) describes how failure records become chat, tool-trace, and CoT training examples.
- The bundled mixed-language fixture is `examples/data/failures/plant_failures.csv`; the portable corpus flow is described in [Corpus](../primitives/corpus.md).

## Entry points for modification

- Add header spellings to `_COLUMN_ALIASES`; preserve canonical names because tool and export code reads them from metadata.
- Add recognized severity text in `_SEVERITY_MAP`, whose output vocabulary is `low`, `medium`, `high`, `critical`, or `unspecified`.
- Change tag separators in `_TAG_SPLIT_RE`, or the searchable sentence layout in `ingest_failures`.
- Change CSV/JSONL decoding or row behavior in `_read_rows`; preserve one-based locators and `source_row`.
- Use `tests/test_ingest_failures.py` to check aliases, optional metadata, bilingual values, and JSONL input.

## Key source files

| File | Role |
| --- | --- |
| `src/purestrata/ingest/failures.py` | Alias mapping, row parsing, severity, text, metadata, and provenance |
| `src/purestrata/pipeline/clean.py` | Inline normalization for source values |
| `src/purestrata/types.py` | `FAILURE_CASE`, `Provenance`, and `new_chunk` |
| `src/purestrata/tools/executor.py` | Search tool handlers that consume failure metadata |
| `src/purestrata/export/finetune.py` | Fine-tuning records built from failure chunks |
| `tests/test_ingest_failures.py` | CSV, JSONL, and metadata behavior tests |
