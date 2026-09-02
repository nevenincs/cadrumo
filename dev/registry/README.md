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
- `analysis/` — registry census, classification, and the declaration screens
  (`python -m dev.registry.analysis.screens`).
- `aeip/` — the anexo-A AEIP continuity planner.
- `conformance/` — registry governance surface (`python -m
  dev.registry.conformance report|coverage|closure|stamp`).
- `newmodelo/` — scaffold a new modelo revision and its calc-grade checklist.
- `mappings/`, `render_profiles/` — the authored inputs described above.
- `tests/` — the pipeline, parity, and analysis suites.

## Declaration screens

The registry declares the same fact in several places and reconciles the copies
afterwards. The screens under `analysis/` measure whether those copies agree.
Run them all against one loaded registry:

```bash
uv run --no-sync python -m dev.registry.analysis.screens
```

Each screen also runs on its own, prints one greppable row per finding, and
always exits 0. A screen reports; it never gates. What each one owns:

| Screen | Condition it measures |
| --- | --- |
| `export_ref_symmetry` | casillas claiming an export field the resolved layouts do not carry |
| `casilla_id_grammar` | which identifier grammar each modelo uses, and which mix several |
| `continuity_integrity` | modelos with no continuity, and chains crossing a grammar or standing alone |
| `revision_name_window` | revision names that misstate the window they declare, or claim none |
| `temporal_site_agreement` | a revision's window, selector and deadline windows falling silent or disagreeing |
| `wire_type_compatibility` | the transition from a casilla's declared type to its rendered wire type |
| `monetary_scale` | monetary fields whose scale is missing, unusual, split across two fields, or unlike their siblings |
| `grade_earned` | declared grades not matching what their prerequisites support, either way |
| `provenance_consistency` | child citations falling outside their revision's own manifest |

Two rules keep the suite honest.

**Read the resolved surface, never the authored one.** Export fields are
derived from bindings when a revision loads, and a casilla is reached by three
different linkage paths. Four separate wrong figures in this campaign came from
walking the authored fragments instead. `resolved_export_endpoints` in the
registry export module returns the surface whole; a screen that reassembles it
is reintroducing the defect.

**Gate invariants, never counts.** The conditions that are clean across the
whole corpus are gated in `tests/test_declaration_invariant_gates.py`, and each
gate asserts that a class of defect does not occur rather than that a number has
not grown. Conditions still carrying findings are not gated: gating them would
need a tolerance, and a tolerance is the baseline ratchet this project retired.
Each becomes a gate when its data is corrected, not before. Detector teeth live
in each screen's own test, where a representative defect is constructed and
shown to be caught.
