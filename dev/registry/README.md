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

Each screen also runs on its own, prints one greppable row per result, and
always exits 0. A screen reports; it never gates. Most results are findings, one
per thing measured; two screens collapse theirs onto the unit somebody fixes -
a reference sitting outside a manifest, a wire-type transition - so their rows
are a report rather than a finding, and the runner's `counts` label on each line
says which. What each one owns:

| Screen | Condition it measures |
| --- | --- |
| `export_ref_symmetry` | casillas claiming an export field the resolved layouts do not carry |
| `casilla_id_grammar` | which identifier grammar each modelo uses, and which mix several |
| `continuity_integrity` | modelos with no continuity, and chains crossing a grammar or standing alone |
| `revision_name_window` | revision names that misstate the window they declare, or claim none |
| `temporal_site_agreement` | a revision's window, selector and deadline windows falling silent or disagreeing |
| `wire_type_compatibility` | the distinct transitions from a casilla's declared type to its rendered wire type |
| `monetary_scale` | monetary fields whose scale is missing, unusual, or unlike their siblings |
| `grade_earned` | declared grades not matching what their prerequisites support, either way |
| `provenance_consistency` | references cited from outside their revision's own manifest |
| `modelo_capability` | what each modelo declares it can do, and where the filing claim and its machinery disagree |
| `footnote_only_wire_facts` | fields whose wire fact sits behind a footnote pointer rather than in their own cell |
| `type_convention_notes` | design notes stating how a whole AEAT type is written to the wire |
| `rule_grounding_coverage` | fields needing a reviewed rule for which no official wording was located at all |
| `note_label_scope` | designs where one note label is defined on more than one sheet |
| `unnumbered_note_scope` | designs carrying an unnumbered note, by the structure that bears on its scope |
| `note_text_drift` | note labels whose wording differs between a modelo's designs |

Three rules keep the suite honest.

**Read the resolved surface, never the authored one.** Export fields are
derived from bindings when a revision loads, and a casilla is reached by three
different linkage paths. Four separate wrong figures in this campaign came from
walking the authored fragments instead. `resolved_export_endpoints` in the
registry export module returns the surface whole; a screen that reassembles it
is reintroducing the defect.

**Key a measurement on every axis the declaration has.** A coordinate that
appears to be declared twice usually is not: the declarations differ on an axis
the key omitted, and that axis is usually named in the identifier. Modelo 210
carries four deadline windows for one annual period, and their ids say why -
`arrendamiento-ingreso`, `cuota-cero`, `devolucion`, `renta-imputada` - because
its deadline depends on what the return produces, which the schema holds in
`resultado_scope` and `tipo_renta_scope`. Nine measurements in this campaign
were wrong this way: a key over modelo and revision reported two screens as
collapsing every row onto one coordinate, a shape pattern read `714-02` as a
numeric range, and a bucket named for what did not match reported 415 findings
where six were real. Read a handful of the values or identifiers before
believing any grouping, and prefer a direct question - `str.isascii()` - to a
pattern that infers one.

**Gate invariants, never counts.** The conditions that are clean across the
whole corpus are gated in `tests/test_declaration_invariant_gates.py`, and each
gate asserts that a class of defect does not occur rather than that a number has
not grown. Conditions still carrying findings are not gated: gating them would
need a tolerance, and a tolerance is the baseline ratchet this project retired.
Each becomes a gate when its data is corrected, not before. Detector teeth live
in each screen's own test, where a representative defect is constructed and
shown to be caught.

## Authoring aids

Not everything under `analysis/` is a screen. A screen measures a condition
across the whole registry and is enrolled in the runner; an authoring aid answers
a question about one design while someone is writing a declaration, and is not.
The gates tell them apart by whether the module defines `screen_authority`, so an
aid is never asked to enrol and a screen can never quietly fail to.

`footnote_pointer_notes` resolves a Contenido cell that holds only a footnote
pointer -- `Nota 4.` -- to the note the design defines for it:

```bash
uv run --no-sync python -m dev.registry.analysis.footnote_pointer_notes <design>.extracted.md
```

It exists because the render-profile eligibility predicate reads a non-blank
Contenido cell as the design having stated the field's wire fact, and a bare
pointer states nothing. Modelo 353's `Nota 4` reads "Solo para periodos 02 y
siguientes" -- an applicability statement carrying no scale, sign or decimals --
which is why the field beneath it renders unscaled beside siblings emitting
cents.

Two rules matter when using it. Take the design from the source reference's own
corpus path rather than searching its directory: several modelos bundle many
designs and one bundles fifteen, so a search resolves a note against an arbitrary
year and still produces an answer. And check the transcription exists before
trusting an empty result, because thirteen bundled designs ship without extracted
text and "no pointers" and "no file" look identical from the outside.

