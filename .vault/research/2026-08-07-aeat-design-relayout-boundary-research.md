---
tags:
  - '#research'
  - '#aeat-design-relayout-boundary'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:74b9cb9d4d098c864172db1297c83b258fd79bfbf029b7ba01d05078f74fb150'
related: []
---

# `aeat-design-relayout-boundary` research: `revision span vs published AEAT record designs`

A registry revision carries exactly one export layout: one set of byte offsets for
its fixed-width fichero-BOE record. AEAT periodically re-lays out a modelo's Diseño
de Registro — a block gains a rung, every downstream field's offset shifts — and a
revision whose `period_selector` spans two AEAT designs on either side of such a
re-layout encodes one byte layout across two incompatible designs. One of the two
years it claims is then written at the wrong byte offsets. This document grounds
that question for Modelo 303 and Modelo 390, records the shipped pattern that
already avoids it (Modelo 123), and names Modelo 200 as a currently-clean but
structurally-identical forward risk. The evidence is measured, not asserted: two
independent instruments — a box-offset diff and a page-length diff — parse the
bundled AEAT design corpus directly, never a transcribed number.

## Findings

### The generic gate already exists and is landed red, deliberately

`src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`
implements the property with no modelo-specific code: for every exporting
revision, take the published AEAT designs its `period_selector` claims, and
require every pair of them to agree on the offset of every box (or page length)
they share. It is keyed on design-to-design agreement rather than a
casilla-to-official-box mapping, because that mapping barely exists for some
modelos (Modelo 390's casillas are semantic ids; a number-keyed check reports
hundreds of false absences there). The module carries its own anti-vacuity guard
(an unreadable design must fail, never silently pass as "no divergence") and is
the living specification of the boundary set — running it re-derives the exact
numbers below at HEAD; this document is a snapshot, not the authority.

### Modelo 303: two revisions, six named boundaries

The registry currently declares two M303 revisions: `2009-y-siguientes`
(`valid_to=2022`) and `2023-y-siguientes` (open-ended). Both span internal
re-layouts:

- `2009-y-siguientes` claims 2015 and 2017: 74 of 74 shared boxes moved.
- `2009-y-siguientes` claims 2019 and 2021: 74 of 146 shared boxes moved.
- `2009-y-siguientes` claims 2021 and 2022: 39 of 156 shared boxes moved.
- `2023-y-siguientes` claims 2025 and 2026: 125 of 174 shared boxes moved (gate's
  box-diff); independently, a per-app-reachable-field diff restricted to the 86
  casilla ids the registry's own `export/*.toml` actually declares found 56 of
  those 86 diverge, including a -787 byte relocation of casillas `[165]-[167]`
  and a -490 byte relocation of `[168]-[170]` — not a ladder shift, a block moved
  from the tail of the record to the middle.

A second, independent instrument (per-page `TOTAL n POSICIONES` length,
box-number-free) found two FURTHER boundaries the box diff did not surface:
`2009-y-siguientes` 2014→2015, and `2023-y-siguientes` 2024→2025 — both on a
different page than the 2025→2026 finding. Neither instrument subsumes the
other: the box diff needs bracketed markers the page-length signal does not, and
the page-length signal is coarser (page changed size, not which box moved) but
reaches designs — several older PDF extractions — that yield no box markers at
all.

Confirmed once, cross-checked against the registry's own literal encoded
`offset =` values (not just the corpus): the registry's `2023-y-siguientes`
export layout encodes `offset = 169` for casilla `01` and `offset = 974` for
casilla `166`, matching the 2023/2024/2025 designs exactly and NOT the 2026
design — so the revision currently writes bytes for a 2026-period filing using
2025-era offsets, live, today (2026-08-07; Q1 and Q2 2026 have already closed).

### Modelo 390: one revision, five named boundaries, live export proof

The registry declares a single M390 revision, `2010-y-siguientes`, spanning:
2017→2018, 2019→2021, 2021→2022, 2022→2023, 2023→2024 (per the gate). A
different agent on this campaign (`m390-box-layer`) proved this end to end: an
`export_draft` call at `filing_year=2023` succeeds and produces 7698 bytes with
the total cuota written at byte 1628 — past the 2023 record's declared end at
1526. The export does not fail; it silently writes a byte-valid-looking file laid
out for the newest design.

### Modelo 123 is the shipped pattern that already avoids this

M123 declares two revisions: `2019-2023` (bounded, `valid_to=2023-12-31`) and
`2024-y-siguientes` (open). Each names a DISTINCT layout `source_refs` entry
(`aeat-dr-123-2019-2023-v13` vs `aeat-dr-123-2024-v20`). Verified by instrument,
not by reading the declaration alone: the two designs genuinely diverge (5 of 7
shared casillas differ in offset — e.g. casilla `03` at 141 in the 2019-2023
design vs 139 in the 2024 design), and each revision's registry-ENCODED offset
matches its own design exactly: `2019-2023`'s export layout literally declares
`offset = 141` for casilla `03`, `2024-y-siguientes`'s declares `offset = 139`.
This is the two-revisions-two-designs shape the gate wants for M303 and M390; it
already exists once in this registry.

### Modelo 200: a clean-today forward risk of the identical shape

M200 has the largest bundled design history in the tree (28 files spanning
2010-2025) but a single open-ended revision, `2024-y-siguientes`. Today that
revision's claimed span covers only two bundled designs (2024, 2025), and they
agree exactly (14 of 14 shared fields identical offset). No 2026 M200 design is
bundled yet. This is not a current finding — it is the same structural shape
M303 and M390 already hit, one AEAT publication cycle away, and the generic gate
above already covers it: the day a 2026 M200 design is bundled without a
matching revision split, the gate reds automatically with no further engineering.

### Breadth swept, not exhaustive — bounded negatives

Every modelo with >=2 bundled AEAT designs and a literal `offset =` field in its
export layout was checked for the SAME shape (single revision, multiple
designs). Confirmed clean (identical offsets across every design a single
revision claims): M202 (`2025-y-siguientes`, two designs, 49/49 shared fields
identical), M130 and M115 (`2019-y-siguientes`, all-pairs identical, small
samples of 18 and 4 shared casillas respectively). Two modelos in the same
fixed-width-export class are confirmed NOT-clean-but-UNMEASURED, not clean: M111
(`2019-y-siguientes`, 62 `offset =` fields, 8 bundled designs, 0 parse — all PDF
or pre-bracket-era xls) and M349 (`2020-y-siguientes`, 52 `offset =` fields, 2
bundled designs, 0 parse — both PDF). A parser that cannot read a design's
format returns the same answer as a design with no divergence, so these are
reported as a gap, not a clean result.

## Sources

- `src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`
  — the landed gate; its failure text is the live specification of the boundary
  set and should be re-run rather than quoted from memory.
- `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/revision.toml`,
  `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/revision.toml`,
  `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/export/0002-export-layout.part-001.toml:391-394`
  (casilla `01`, `offset = 169`) and `:513-516` (casilla `166`, `offset = 974`).
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes/revision.toml`.
- `src/cadrumo/_data/registry/aeat/modelos/123/revisions/2019-2023/revision.toml`,
  `.../2024-y-siguientes/revision.toml`, and each revision's `export/*.toml`
  (casilla `03`, `offset = 141` vs `offset = 139`).
- `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/revision.toml`.
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_{303,390,123,200,202,130,115,111,349}/files/*.extracted.md`
  — the bundled AEAT record-design corpus, parsed programmatically, never
  transcribed.
- `export_draft` live proof for M390 `filing_year=2023`: reported by
  `m390-box-layer` (this campaign), not independently reproduced here.
