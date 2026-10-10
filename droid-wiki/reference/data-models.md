# Record format

A corpus is a directory of `*.strata.jsonl` files written by `write_chunks` in
`src/purestrata/corpus.py`: one JSON object per line, one line per record, UTF-8
with `ensure_ascii=False`. The dataclasses behind the format are covered in
[records and provenance](../primitives/records-and-provenance.md).

## Envelope

Every line has the same six top-level fields, produced by `Chunk.to_dict` in
`src/purestrata/types.py`:

| Field | Type | Meaning |
| --- | --- | --- |
| `schema` | string | Always `purestrata/v1` (`SCHEMA_VERSION` in `src/purestrata/types.py`) |
| `chunk_id` | string | `sha1(f"{doc_id}::{kind}::{locator}")[:12]` |
| `kind` | string | One of the six kinds listed below |
| `text` | string | The searchable body of the record |
| `metadata` | object | Kind-specific keys; see the tables below |
| `provenance` | object | `doc_id`, `source_path`, `locator` |

`provenance.locator` is the human-readable position in the source: `section 3: Spindle`,
`section 3: Spindle > row 4`, `drawing`, `model`, or `row 7`.

Corpus loading uses `Chunk.from_dict`. A record whose `schema` is present and does
not start with `purestrata/` raises
`ValueError: Unsupported corpus record schema: '<value>'`. A record with no `schema`
key is accepted (the check is skipped) and `metadata` defaults to `{}` when missing
or null. Only `chunk_id`, `kind`, `text`, and `provenance` are required.

Kinds, in `ALL_KINDS` order in `src/purestrata/types.py`: `manual_section`,
`safety_notice`, `procedure`, `part_record`, `drawing`, `failure_case`.

## Idempotent ids

`make_chunk_id` derives the id only from `doc_id::kind::locator`, so re-ingesting an
unchanged file rewrites byte-identical records. The counters that feed locators are
deterministic per section or document, so the same input always produces the same ids.

## `manual_section`

Written by `_chunks_from_section` in `src/purestrata/ingest/manual.py` from prose
paragraphs. Long prose is split with `split_long_text(target=900, overlap=120)` from
`src/purestrata/pipeline/chunk.py`; when a section yields more than one piece the
locator gains a ` (part N)` suffix.

| Metadata key | Meaning |
| --- | --- |
| `section` | Full heading path, e.g. `3.2 Spindle removal`, joined with ` > ` for nested headings; `(front matter)` before the first heading |
| `document` | Front-matter key/value map collected before the first heading (keys slugified by `_slugify_key`) |
| `equipment` | Present when front matter defines `machine`, `equipment`, or `document`; copied from the first of those that exists |

## `part_record`

Written by `_part_chunk` from a pipe table whose header maps to a `part_number`
column via `_PART_COL_ALIASES` (which also recognizes Japanese headers such as
`品番` and `部品番号`).

| Metadata key | Meaning |
| --- | --- |
| `section`, `document`, `equipment` | Same as `manual_section` |
| `part_number` | Value of the mapped part-number column |
| `name` | Part name column |
| `quantity` | Quantity column |
| `spec` | Specification column |

The last four keys are set only when the column exists and the value is non-empty.
Locator: `section N: <title> > row <n>`, where `n` counts part rows within the section.

## `procedure`

Written by `_procedure_chunk` from a numbered list in a section.

| Metadata key | Meaning |
| --- | --- |
| `title` | Full section heading path |
| `steps` | List of step strings, in document order |
| `document`, `equipment` | Same as `manual_section` |

Locator: `section N: <title> > procedure <n>`.

## `safety_notice`

Written by `_notice_chunk` from `WARNING`/`CAUTION`/`NOTICE`/`DANGER` lines (or the
Japanese equivalents `警告`, `注意`, `重要`, `ヒント`).

| Metadata key | Meaning |
| --- | --- |
| `severity` | `warning` for WARNING/DANGER/警告, `caution` for CAUTION/注意, `note` for NOTICE/重要/ヒント (default `note` when the keyword is unrecognized) |
| `section`, `document`, `equipment` | Same as `manual_section` |

Locator: `section N: <title> > notice <n>`.

## `drawing` (DXF)

Written by `ingest_dxf` in `src/purestrata/ingest/cad.py`; locator is always
`drawing`. `drawing_id` is `title_block["dwg_no"]`, else `title_block["part_no"]`, else the derived doc id.

| Metadata key | Meaning |
| --- | --- |
| `format` | Always `dxf` |
| `drawing_id` | Drawing number used for lookup |
| `file_name` | Base name of the source file |
| `units` | From `$INSUNITS` in the DXF header: `unitless`, `inches`, `feet`, `mm`, `cm`, `m`, or `unspecified` |
| `size` | `{width, height}` computed from `bounds`, rounded to 4 decimals; `depth` added when a Z extent exists |
| `circular_features` | One entry per distinct diameter: `{diameter, diameter_mm, count, layers}`; `diameter_mm` is null when the unit is unknown, `layers` is sorted |
| `diameter_callouts` | One entry per text match of the callout pattern (`DIA`, `Ø`, `φ`, `%%C`): `{nominal, fit, text}`; `fit` is null when absent |
| `layers` | List of `{name, color}` from the TABLES section |
| `entity_counts` | Map of entity type to count |
| `per_layer_counts` | Map of layer name to `{entity type: count}` |
| `text_annotations` | List of joined TEXT/MTEXT strings |
| `title_block` | Map of normalized field name to value, e.g. `dwg_no`, `part_no`, `material`, `scale`, `revision`, `title` |
| `bounds` | `{min_x, min_y, max_x, max_y}`, or null when no geometry has coordinates |
| `blocks` | List of block names |

## `drawing` (STEP)

Written by `ingest_step` in `src/purestrata/ingest/step.py`; locator is always
`model`. `drawing_id` is the root product id, else the derived doc id.

| Metadata key | Meaning |
| --- | --- |
| `format` | Always `step` |
| `drawing_id`, `file_name`, `units`, `size`, `circular_features`, `bounds` | As for DXF; `units` is detected from the STEP unit entities |
| `diameter_callouts` | Always `[]` (STEP carries no drawing callouts) |
| `header` | From the FILE_DESCRIPTION/FILE_NAME/FILE_SCHEMA sections: `description`, `name`, `timestamp`, `originating_system`, `author`, `organization`, `schema`; each present only when found |
| `products` | List of `{id, name, description}` from PRODUCT entities |
| `assembly` | List of `{parent, child, quantity}` derived from NEXT_ASSEMBLY_USAGE_OCCURRENCE links, keyed by product id |
| `layers` | Always `[]` |
| `entity_counts` | Top 25 entity types by count |
| `entity_total` | Total entity count in the file |
| `title_block` | `{title, part_no}` from the root product's name and id |

`header` and `products`/`assembly` are the STEP-only keys; `per_layer_counts`,
`text_annotations`, and `blocks` appear only on DXF drawings.

## `failure_case`

Written by `ingest_failures` in `src/purestrata/ingest/failures.py`, one record per
CSV or JSONL row. Headers are matched via `_COLUMN_ALIASES` (English and Japanese);
locator is `row <n>`, 1-based over data rows.

| Metadata key | Meaning |
| --- | --- |
| `case_id` | Case identifier, or `<doc_id>-c<nnn>` when the log has no id column |
| `equipment` | Equipment or machine name |
| `symptom` | Observed symptom |
| `cause` | Root cause |
| `countermeasure` | Corrective action |
| `severity` | Normalized to `low`, `medium`, `high`, `critical`, or `unspecified` |
| `source_row` | 1-based row index in the input file |
| `part_number` | Set only when present |
| `reported_at` | Set only when present |
| `status` | Set only when present |
| `tags` | Set only when present; a list split on semicolons, commas, `、`, pipes, or slashes |

## Related pages

[Records and provenance](../primitives/records-and-provenance.md) for the dataclasses,
[corpus](../primitives/corpus.md), and [fine-tune exports](../features/fine-tune-exports.md).
