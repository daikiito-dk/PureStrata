# Fun facts

Six small things the repository can prove about itself.

## The name is geology

"Strata" are layers of rock laid down over time, and the name is the product pitch in miniature: manuals, CAD drawings, and failure logs stacked into one ordered, source-tagged corpus.

The site states the discipline behind the metaphor plainly: "Every record carries provenance: source file plus locator."

The README calls failure knowledge "the missing stratum," the layer most retrieval stacks never dig into, because they stop at manual text while factory troubleshooting runs on symptom, cause, and countermeasure records.

The favicon in `site/index.html` (line 12) is three offset rounded bars, one orange, one sky blue, one green, standing in for strata. The same mark sits beside the wordmark in the page header.

## A one-machine-shop universe

Every sample file describes one small factory with three machines. `LATHE MK3` has an English maintenance manual; `CNC SERVO PRESS PP-220` has a Japanese one, 保全点検マニュアル. The third machine, `MILLING CENTER MV-5`, appears only in the failure log.

The sample DXF drawing `bracket_mk3.dxf` is part `BRK-0042-A` in material `SS400`, with a `BORE DIA 25 H7` callout.

The sample STEP assembly `bracket_assy_mk3.step` contains `PIN-0110`, a 位置決めピン (locating pin) in `S45C, quenched` steel.

The failure log `examples/data/failures/plant_failures.csv` records the same brake unit, `BK-2207`, failing twice: in English on 2026-05-02 (slide overshoots bottom dead center by 0.3 mm) and in Japanese on 2026-06-03, when the overshoot came back and the root cause turned out to be a clogged cooling fan filter.

## The \X2\ trick

STEP files (ISO 10303-21) cannot hold raw Japanese. Non-ASCII names are stored as UTF-16 code units in hex, wrapped in `\X2\`...`\X0\`, so the sample assembly literally contains `'\X2\4F4D7F6E6C7A308130D430F3\X0\'`.

`src/purestrata/ingest/step.py` turns that back into 位置決めピン with one regex (line 22) and a `utf-16-be` decode (lines 100 to 104), using nothing outside the standard library.

## The MCP import dance

The `mcp` package renamed its server class between major versions: 1.x calls it `FastMCP` (`mcp.server.fastmcp`), and 2.x renamed it to `MCPServer` (`mcp.server.mcpserver`).

Rather than pin one, `build_mcp_server` in `src/purestrata/mcp_server.py` (lines 23 to 27) tries the 1.x import first and falls back to 2.x, raising a message that suggests `pip install 'purestrata[mcp]'` if neither is present.

The import lives inside the function, so the core package never needs `mcp` installed unless you actually start the server. `mcp` is an optional extra anyway.

## From 0.1.0 to 0.2.0 in one day

Both tagged releases landed on 2026-10-10, 5 hours 59 minutes apart: `v0.1.0` at 08:46:12 JST and `v0.2.0` at 14:45:52.

The feature commit that became v0.2.0 is 2 minutes 56 seconds older than its own release tag, which is the sort of cadence you get when the whole history spans 6 hours 52 minutes.

The test suite grew from 62 to 79 the same afternoon, all 79 still passing in 0.66 seconds.

## Zero required dependencies, hand-rolled BM25

The `[project]` table in `pyproject.toml` declares no `dependencies` key at all. The only extras are `pdf` (`pypdf`, for PDF manuals) and `mcp`. DXF, STEP, CSV, JSONL, and Markdown parsing are all standard library.

That includes search. `src/purestrata/search.py` implements BM25 itself and tokenizes Japanese as character bigrams, which the module docstring credits with working well "without a morphological analyzer." No MeCab, no native extensions.
