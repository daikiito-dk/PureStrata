# Background

PureStrata is shaped by a narrow set of constraints rather than a general architecture. The people who need it work in factories where the network is closed, the data belongs to the company, and the maintenance engineers who would have to review any generated training data have no appetite for a toolchain they cannot read. Every structural choice follows from that: the core imports nothing outside the standard library, a corpus is a directory of plain `*.strata.jsonl` files instead of a database, search is a hand-written BM25 implementation with CJK character bigrams instead of a morphological analyzer or embeddings, and the one place that touches the network is a standalone example rather than part of the library. The decisions are individually small and mostly reversible, but they compound into a package that installs on an air-gapped machine, is auditable line by line at about 2,900 lines of source across 20 modules, and produces artifacts a non-programmer can open. The reasoning behind each of them, with the file or README passage it rests on, is on [Design decisions](design-decisions.md).

The same constraints explain the unfinished edges. STEP bounds are the extent of every `CARTESIAN_POINT` entity and B-rep topology is never evaluated, so reported sizes can slightly exceed the solid; DXF support covers ASCII only, with binary files and R2018 drawing content untested; fit-class matching in `search_drawings` is an exact, case-sensitive string comparison, so `H7` and `h7` are different requests; material filtering is a substring test; retrieval is BM25 alone, with no embedding fallback and zero-score matches dropped; PDF ingestion returns nothing at all for scanned pages because there is no OCR; and the chunk id is derived from `doc_id`, kind, and locator, so changing a locator scheme silently orphans a previously written corpus file. None of these is hidden, and several are recorded in the README roadmap. They are collected with their source files on [Pitfalls](pitfalls.md).

## What this section covers

| Page | Contents |
| --- | --- |
| [Design decisions](design-decisions.md) | Why zero required dependencies, JSONL over a database, BM25 with CJK bigrams over MeCab or embeddings, mandatory provenance, one executor behind four surfaces, `failure_case` as a first-class kind, transparent CoT exports, and prefix schema versioning. |
| [Pitfalls](pitfalls.md) | Known limitations and sharp edges, each tied to the file it comes from, from STEP bounds and ASCII-only DXF to exact fit matching, BM25-only retrieval, PDF text extraction, the `mcp` class rename, and chunk-id stability. |

## The constraints the design answers to

- **Air-gap installs.** A factory network may have no PyPI index. The core has zero required dependencies, so `pip install purestrata` from a wheel is the whole install.
- **Local data ownership.** The corpus is the user's file. It can sit on a file share, move on a USB stick, or be committed when small.
- **Auditability.** Reviewers need to read the source and the records, so both stay small and plain.
- **Japanese as a first-class input.** Manuals and failure logs are often Japanese, and the search layer handles that without shipping a native tokenizer.
- **Expert review of generated data.** Fine-tuning exports are scaffolds meant to be corrected by maintenance engineers, so their reasoning is written out rather than hidden in a model.
- **No behavioral drift across surfaces.** MCP, OpenAI schemas, Anthropic schemas, the Python API, and the CLI all reach the same executor, so a tool behaves identically everywhere.
- **A writable, inspectable artifact.** Records are JSON objects on disk, so a corpus can be diffed, corrected by hand, and reviewed in a pull request.
- **One corpus, several consumers.** Live retrieval, tool calling, and fine-tuning exports all read the same files, so a correction made for one consumer benefits the others.
- **Failure knowledge treated as data.** Symptom, cause, and countermeasure are typed fields rather than prose to be re-parsed at query time.

## How the decision write-ups are built

Each entry on [Design decisions](design-decisions.md) states the choice, quotes or points to the code or README passage that carries it, and names the cost. Where the source states the reason, the page says so. Where it does not, the reason is marked as an inference, which is why a few sentences there use "the reasoning appears to be" rather than asserting a motive the code does not record.

That distinction matters for a project whose value is auditability: a reader should be able to tell what the code guarantees from what a maintainer intended.

## Known limitations at a glance

The full list with sources is on [Pitfalls](pitfalls.md). The short version:

- STEP sizes are bounding-box extents, not solid geometry, and B-rep topology is never evaluated.
- DXF ingestion handles ASCII files only; binary DXF is unsupported and R2018 content is untested.
- `search_drawings` fit matching is exact and case-sensitive, and the material filter is a substring test.
- Retrieval is BM25 only; no embeddings, and zero-score matches are dropped rather than ranked low.
- Scanned or photographed PDF pages yield no text, because nothing performs OCR.
- Chunk ids are derived from the locator, so a locator change invalidates an existing corpus file.
- `examples/corpus` and `examples/output` are gitignored and appear only after `make demo`.

## What this section is not

- It is not a changelog or history. That is [Lore](../lore.md).
- It is not a specification. The record format, CLI flags, and configuration live under [Reference](../reference/index.md).
- It is not a roadmap commitment. Items the README lists as planned are recorded there, not promised here.
- It is not an operations guide. Install, publish, and MCP client setup are on [Deployment](../deployment.md).
- It does not restate the domain model. Start at [Primitives](../primitives/index.md) if the terms here are unfamiliar.

## Reading order

1. Read [Design decisions](design-decisions.md) if you are evaluating whether to adopt the library or extend it.
2. Read [Pitfalls](pitfalls.md) if you are about to point it at real factory data.
3. Read both if you are reviewing a change that touches ingestion or search, since most of the sharp edges live in those two areas.

## Where to read next

- [Architecture](../overview/architecture.md) for how the components fit together.
- [Records and provenance](../primitives/records-and-provenance.md) for the record model that the decisions above produce.
- [Deployment](../deployment.md) and [Security](../security.md) for how the constraints show up in shipping and in the trust model.
