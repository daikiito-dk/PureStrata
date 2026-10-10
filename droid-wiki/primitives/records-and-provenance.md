# Records and provenance

Active contributors: DK

## Purpose

`src/purestrata/types.py` defines the data model every other module depends on: the six record kinds, the deterministic chunk-id scheme, and the `Provenance` and `Chunk` dataclasses. Provenance is what makes a corpus auditable, because every answer a model gives can be traced to a line in a drawing, a section of a manual, or a row in a failure log. This page documents the module's exact behavior so changes to it are deliberate.

## Key abstractions

| Abstraction | File | Notes |
| --- | --- | --- |
| Kind constants and `ALL_KINDS` | `src/purestrata/types.py` | `MANUAL_SECTION`, `SAFETY_NOTICE`, `PROCEDURE`, `PART_RECORD`, `DRAWING`, `FAILURE_CASE` |
| `SCHEMA_VERSION` | `src/purestrata/types.py` | The string `purestrata/v1` written into every serialized record |
| `derive_doc_id` | `src/purestrata/types.py` | Stable document id from a file path |
| `make_chunk_id` | `src/purestrata/types.py` | Deterministic chunk id from `doc_id`, `kind`, and `locator` |
| `Provenance` | `src/purestrata/types.py` | `doc_id`, `source_path`, `locator`, with `to_dict`/`from_dict` |
| `Chunk` | `src/purestrata/types.py` | `chunk_id`, `kind`, `text`, `provenance`, `metadata` |
| `new_chunk` | `src/purestrata/types.py` | The constructor callers should use; derives the id for them |

## How it works

```mermaid
graph LR
    PATH["source path"] --> DID["derive_doc_id"]
    DID --> PROV["Provenance(doc_id, source_path, locator)"]
    PROV --> NC["new_chunk(kind, text, provenance)"]
    NC --> MID["make_chunk_id(doc_id::kind::locator)"]
    MID --> CH["Chunk"]
```

### Kinds

The six constants are string literals (`"manual_section"`, `"safety_notice"`, `"procedure"`, `"part_record"`, `"drawing"`, `"failure_case"`). `ALL_KINDS` is the ordered tuple in that sequence, and modules that need a stable kind order (such as corpus statistics) iterate it instead of redefining a list. Adapters and tools import the constants rather than repeating the strings.

### `derive_doc_id(path)`

Takes the path's stem, strips surrounding whitespace, replaces any run of characters outside `[0-9A-Za-z._-]` with a single underscore, strips leading and trailing underscores, and lowercases the result. If nothing remains, it returns `"doc"`. The result is used as the file name of the document's corpus file and as the `doc_id` inside its provenance.

### `make_chunk_id(doc_id, kind, locator)`

Builds the string `doc_id::kind::locator`, encodes it as UTF-8, and returns the first 12 hex characters of its SHA-1 digest. The id depends only on those three coordinates, so re-ingesting an unchanged source file reproduces identical ids and overwrites its own records rather than duplicating them. Changing any coordinate (moving a section, renaming a file) produces a new id, which is intended.

### `Provenance`

A dataclass with `doc_id`, `source_path`, and `locator`. `to_dict()` returns those three keys; `from_dict()` reads them and coerces each to `str`. `__str__` renders `"<source_path> :: <locator>"`, which is the form injected into tool results and fine-tuning answers. The locator is expected to be human-readable: a section number, a row index (`row 3`), or an entity id such as `model`.

### `Chunk`

A dataclass with `chunk_id`, `kind`, `text`, `provenance`, and `metadata` (a JSON-serializable dict, defaulting to empty). Searchable human text lives in `text`; structured fields that tools filter on live in `metadata`.

`to_dict()` emits the record in a fixed key order with the schema marker first:

```
{"schema": "purestrata/v1", "chunk_id": ..., "kind": ..., "text": ..., "metadata": ..., "provenance": {...}}
```

`from_dict()` reads the `schema` key and raises `ValueError` if a non-empty schema does not start with `purestrata/`. It treats a missing schema as acceptable, so records written by older code still load. This is the boundary that keeps a corpus directory from silently mixing incompatible formats.

### `new_chunk`

`new_chunk(kind, text, provenance, metadata=None)` calls `make_chunk_id(provenance.doc_id, kind, provenance.locator)` and returns a `Chunk`. Adapters should never build a `Chunk` with a hand-made id; using this function is what keeps the id scheme consistent.

## Integration points

- Every ingest adapter (`src/purestrata/ingest/manual.py`, `src/purestrata/ingest/cad.py`, `src/purestrata/ingest/step.py`, `src/purestrata/ingest/failures.py`) ends by calling `new_chunk`.
- `src/purestrata/corpus.py` serializes with `to_dict` and parses with `from_dict`; see [Corpus](corpus.md).
- `src/purestrata/search.py` reads `kind` and `text` and imports `ALL_KINDS`.
- `src/purestrata/tools/executor.py` builds each tool result from `chunk.provenance` via `_result`.
- `src/purestrata/export/finetune.py` embeds `provenance.to_dict()` in every record's `sources`.

## Entry points for modification

- Add a kind: define a constant and append it to `ALL_KINDS` in `src/purestrata/types.py`, then teach the consuming adapter to emit it.
- Change id length or hash: `make_chunk_id` in `src/purestrata/types.py`. This invalidates existing ids, so treat it as a format break.
- Change the record envelope: `Chunk.to_dict`/`Chunk.from_dict` in `src/purestrata/types.py`; bump `SCHEMA_VERSION` only for a real format break.
- Follow the conventions in [Patterns and conventions](../how-to-contribute/patterns-and-conventions.md) before extending the model.

## Key source files

| File | Role |
| --- | --- |
| `src/purestrata/types.py` | The entire data model documented here |
| `src/purestrata/corpus.py` | Serialization boundary: `write_chunks` and `Corpus.load` |
| `src/purestrata/search.py` | Consumes `kind` and `text`, iterates `ALL_KINDS` |
| `src/purestrata/tools/executor.py` | Attaches provenance to tool results |
| `tests/test_corpus.py` | Round-trip, idempotent re-ingestion, and foreign-schema rejection |

Related: [Corpus](corpus.md), [Failure knowledge](../features/failure-knowledge.md), [Manual ingestion](../features/manual-ingestion.md), [Full-text search](../features/full-text-search.md).
