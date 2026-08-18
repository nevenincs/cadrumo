# Registry authoring tooling

Development-only tooling that produces the export knowledge Cadrumo ships.
Nothing in this tree goes into the wheel — only its verified output does.

## The bigger picture

Cadrumo takes someone's real financial data — invoices, ledger, profile — works
out what they owe on Spanish tax returns (modelos 303, 390, 184, 100…),
verifies it, and hands them an export they file with AEAT themselves. The
application never files for them.

The hardest part of that is the export format. AEAT does not accept a
spreadsheet of numbers: each modelo has a fixed-width text-file format where
every value must sit in an exact character position, with exact width, padding,
sign rules, and literal markers — `"<T"` at byte 1, a tax ID at byte 5, and so
on, for hundreds of fields. One wrong byte and the filing is rejected.

Cadrumo therefore ships a knowledge base — the registry under
`src/cadrumo/_data/registry/` — describing every modelo for every filing year:
the casillas, the calculation formulas, the legal references, and the exact
record layouts. At runtime the app loads this data, fills values in, and writes
the file.

That knowledge is derived, never hand-typed. AEAT publishes official design
documents per modelo and year, and the generator in this tree turns them into
the record files the app ships. Three authored inputs feed it:

- the **official design** — field positions and lengths, hash-pinned;
- the **semantic map** (`mappings/`) — what each field MEANS: which casilla it
  addresses, which law grounds it;
- the **render profile** (`render_profiles/`) — how numbers are PRINTED:
  digits, decimals, sign policy, blank-vs-zero, each rule carrying a
  human-written evidence block.

The pipeline renders a complete `export/` tree from those three, validates it
through the real registry loader and authority, and publishes it into the
shipped registry with full provenance — every field traceable to the official
document, the reviewer's decision, and the legal provision. See
`mappings/README.md` and `render_profiles/README.md` for the authored-data
contracts.

## Layout

- `pipeline/` — the generation pipeline: render → validate → publish → check.
- `parity/` — official-workbook parity harness (`python -m
  dev.registry.parity.maintenance_cli`).
- `analysis/` — registry census and classification tools.
- `aeip/` — the anexo-A AEIP continuity planner.
- `conformance/` — registry governance surface (`python -m
  dev.registry.conformance report|audit`).
- `newmodelo/` — scaffold a new modelo revision and its calc-grade checklist.
- `mappings/`, `render_profiles/` — the authored inputs described above.
- `tests/` — the pipeline, parity, and analysis suites.
