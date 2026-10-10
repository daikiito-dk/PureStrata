# Pitfalls

Known limitations and sharp edges, each with the file it comes from. These are properties of the current implementation, not bug reports: several are deliberate trades documented in the source, and the rest are recorded in the README roadmap.

## STEP size and topology

The docstring of `src/purestrata/ingest/step.py` states the boundary: "It does not evaluate B-rep topology; bounds are the extent of all `CARTESIAN_POINT` entities, which can slightly exceed the solid itself."

`_point_bounds` takes the minimum and maximum of every point it collected, and `size_from_bounds` reports width, height, and depth from those extents. A model whose bounding box is set by a loose point, an origin marker, or a construction geometry will report a size larger than the part. Assembly trees, product names, units, and cylindrical features are read from entity names and parameter values, so they do not depend on topology evaluation, but any dimension question that needs real solid geometry is out of scope today.

Source: `src/purestrata/ingest/step.py`.

## DXF is ASCII only

The docstring of `src/purestrata/ingest/cad.py` is explicit: "PureStrata ships a minimal, dependency-free DXF reader for the metadata that LLM workflows actually need: layers, entity inventories, text annotations, title-block fields, and geometric bounds. Binary DXF is not supported."

The reader walks group codes in decoded text, so a binary DXF file fails to parse as a drawing rather than failing loudly. R2018 drawing content is also untested; the README lists "HTML/DXF-R2018 support" under Planned. Older ASCII DXF files, which is what this reader targets, are the supported case.

Source: `src/purestrata/ingest/cad.py`, `README.md`.

## Fit-class matching is exact and case-sensitive

`_tool_search_drawings` in `src/purestrata/tools/executor.py` compares the requested fit string with the callout's stored fit using `(callout.get("fit") or "") == fit`. There is no case folding and no normalization, so `H7` and `h7` are different requests and either can return nothing.

The callout is captured by `_CALLOUT_RE` in `src/purestrata/ingest/geometry.py`, which only matches a fit suffix directly after a diameter prefix (`DIA`, `Ø`, `%%C`) and keeps its original case. A fit class written in prose without a diameter prefix is not captured at all, so exact matching is the only behavior available even when the drawing text contains the class.

Source: `src/purestrata/tools/executor.py`, `src/purestrata/ingest/geometry.py`.

## Material filter is a substring test

In the same tool, `material` is matched with `material.casefold() not in haystack.casefold()`, where `haystack` is the title block's `material` field if present or the chunk text otherwise. Case is handled, but everything else is not: `S45C` matches `S45C-H`, and a material named in a note somewhere in the drawing text will match even if the title block says otherwise. There is no material vocabulary or normalization.

Source: `src/purestrata/tools/executor.py`.

## Search is BM25 only

`src/purestrata/search.py` implements Okapi BM25 over token frequencies. There are no embeddings and no semantic fallback, so a query that shares no tokens with a record returns nothing even when the meaning is close; the module drops zero-score matches by design. Synonyms are not expanded, and the README lists "embedding search" under Planned.

Two consequences worth knowing before tuning a query: results depend on term overlap alone, and a query in the wrong language for the record (English query, Japanese record) will not match.

Source: `src/purestrata/search.py`.

## PDF ingestion needs extractable text

`_extract_pdf_text` in `src/purestrata/ingest/manual.py` calls `page.extract_text()` per page and keeps `or ""`, so pages with no text layer contribute an empty page heading and no content. Scanned drawings or photographed pages produce a corpus file with page markers and no text, and nothing in the pipeline reports that as a failure. There is no OCR step and none is planned in the current README roadmap.

Source: `src/purestrata/ingest/manual.py`.

## The `mcp` package renamed its server class

`build_mcp_server` in `src/purestrata/mcp_server.py` tries `from mcp.server.fastmcp import FastMCP` and falls back to `from mcp.server.mcpserver import MCPServer`, with imports labelled "mcp 1.x" and "mcp 2.x renamed FastMCP to MCPServer". Both are supported, and if neither imports the code raises a `RuntimeError` naming the extra to install.

The sharp edge is that the surface is only exercised against whichever version happens to be installed in the environment running the tests. A change in a third `mcp` release that renames or moves the class again would need the same fallback treatment extended, and this is the one place in the library where the test outcome depends on a third-party package's internal layout.

Source: `src/purestrata/mcp_server.py`.

## Chunk ids depend on the locator scheme

`make_chunk_id(doc_id, kind, locator)` in `src/purestrata/types.py` hashes `f"{doc_id}::{kind}::{locator}"`. That determinism is what makes ingestion idempotent, but it also means the id is a function of three things that can each change independently of the source file.

Change a locator scheme (say, from "section path" to "line range") and every id for that document changes. Previously written corpus files still contain the old ids, so a re-ingest into the same directory does not update the existing records, it adds a new file alongside them. Exports that recorded old chunk ids no longer resolve. Anyone editing a locator format should plan to re-ingest the affected documents into a fresh corpus directory rather than in place.

Source: `src/purestrata/types.py`.

## Failure-case search can degrade to unranked candidates

`_tool_search_failure_cases` in `src/purestrata/tools/executor.py` ranks by BM25 when a query is given, but if the ranking comes back empty and equipment-filtered candidates exist, it falls back to `[_result(chunk) for chunk in candidates[:top_k]]`. Those results are in corpus order with no `score` key, so an equipment-only match can look identical in shape to a ranked result while carrying no relevance signal. A model reading the result has no way to tell the two cases apart except by the absence of a score.

Source: `src/purestrata/tools/executor.py`.

## Two files with the same stem collide

`derive_doc_id` in `src/purestrata/types.py` builds the document id from `Path(path).stem`, lowercased with non-alphanumeric characters replaced by underscores. Nothing else from the path is used, so `line1/manual.md` and `line2/manual.md` both become `manual` and both write `manual.strata.jsonl`. Ingesting the second overwrites the first.

Source: `src/purestrata/types.py`, `src/purestrata/corpus.py`.

## Corpus loading is flat and eager

`Corpus.load` globs `*{CORPUS_SUFFIX}` directly under the given directory and does not recurse, so strata files in subdirectories are silently ignored. Every chunk is held in memory as a list, and lookup by id is a linear scan in `Corpus.get` and `_find_by_id`. That is adequate for the corpus sizes the project targets and is a limit worth knowing before pointing it at a directory built by another tool.

Source: `src/purestrata/corpus.py`.

## Demo artifacts are not in the repository

`.gitignore` excludes `examples/corpus/` and `examples/output/`. Both directories exist only after `make demo`, which ingests the bundled sample data and writes the exports. A fresh clone has the source data under `examples/data/` and nothing under `examples/corpus/`, so any command that takes `--corpus examples/corpus` fails until the demo has been run.

Source: `.gitignore`, `Makefile`.
