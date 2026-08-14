---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:c39db6eed4c0581864e30593c21e99f54507254d6808f40bbc84ee54379cbcac'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# `aeat-export-fragment-generator-authority` audit: `S69 Modelo 303 2024-late semantic map review`

## Scope

Independent review of the 2024-late semantic map, source-bound render profile, consolidated
census, and hand-reviewed epoch-delta table against S69, the S63 declaration index, the S67/S68
predecessor maps, and the accepted generator authority. This audit closes the gap flagged by the
`2026-08-10-aeat-export-fragment-generator-authority-plan` reconciliation pass: unlike the closed
S67 and S68 rows, no S69 review record existed, and a green test suite is not itself proof the
required per-epoch hand review was performed. Every figure below was independently re-derived
against the tree rather than taken from the map author's own measurement.

## Findings

### S69 Modelo 303 2024-late semantic map review | info | bijection and per-record totals confirmed exact

The consolidated census (`m303_semantic_census.py`, `M303_SEMANTIC_CENSUS_EXPECTATIONS["2024-late"]`)
states 413 fixed-record anchors plus the 13 shared DP30300 prefix anchors, 426 total. Direct entry
counts in each mapping fragment reproduce this exactly and bijectively: DP30301 88, DP30302 163,
DP30303 38, DP30304 43, DP30305 68, DP303DID 13, summing to 413. This is 20 more fixed anchors than
2024-early's 393 (82/153/34/43/68/13), matching the row's stated delta.

### S69 Modelo 303 2024-late semantic map review | info | every added anchor resolves to a reviewed home

Manual review of the introduced/retired-home table in `test_modelo_303_semantic_maps.py`
(`_EPOCH_SURFACES["2024-late"]`), cross-checked against the mapping TOML, confirms each of the 20
new anchors: DP30301 gains 6 at ordinals 80-85, one casilla each for casillas 165-170 — the RDL
4/2024 transitional super-reducido rung (base, tipo, cuota) plus its recargo de equivalencia
companion. DP30302 gains 10 (153 to 163), all ten resolving to régimen-simplificado projection
facts for DANA eligibility and DANA/Lorca reduction slots
(`_M303_2024_LATE_SIMPLIFIED_ADDITIONS`), which is the same reviewed regulatory block S66 grounds.
DP30303 gains 4 physical anchors (34 to 38) while the reviewed table records 6 home changes in that
record, because ordinal 29 is a genuine re-home rather than a new anchor: it moves from the 2023/
2024-early `computed:m303_complementaria_marker` to `producer:amendment_evidence.is_rectificativa`,
consistent with the row's requirement that this region be hand-reviewed per epoch rather than
inherited. No introduced or retired home in the reviewed table is unaccounted for against the
measured map diff.

### S69 Modelo 303 2024-late semantic map review | info | DP30302 nonnumbered simplified-regime share confirmed

The census's `simplified_ordinal_spans` for 2024-late are `range(6, 78)` and `range(90, 162)` with
filler ordinals `{92, 94, 121, 123}`, giving 72 + 72 - 4 = 140 nonnumbered DP30302 anchors admitted
through the S63 declaration index, matching the row's stated share exactly. The filler carve-outs
are asserted to stay `filler`-kind by the census's own gate
(`census_m303_semantic_map`'s `misclassified_reserved` check), not merely assumed.

### S69 Modelo 303 2024-late semantic map review | info | source identity and test-green status confirmed

Both the semantic map (`0001-records.toml`) and the render profile (`0001-blank-numeric.toml`)
declare `source_ref = "aeat-dr-303-2024-late"` and the same `source_sha256`, matching each other.
Re-running the epoch-scoped suite directly (`pytest dev/registry/tests/test_modelo_303_semantic_maps.py
-k "2024-late" -n 0`) reproduces 25 passed, 0 failed against the current working tree.

### S69 Modelo 303 2024-late semantic map review | low | the authored work is uncommitted

`dev/registry/mappings/modelo_303/2024-late/`, `dev/registry/render_profiles/modelo_303/2024-late/`
were already committed in the tracked history (the render profile via `47fc74515d`), but the mapping
directory itself, the new consolidated `dev/registry/m303_semantic_census.py`, and
`dev/registry/tests/test_modelo_303_semantic_maps.py` are untracked (`git status --porcelain`
reports `??`). The row's authoring and hand-review clauses are satisfied by content; the row cannot
be treated as closed until this lands as a real commit. This audit reviews the content on disk as
of 2026-08-14 and makes no claim about anything not yet committed.

### S69 Modelo 303 2024-late semantic map review | medium | this consolidation amends the already-closed S67 and S68 rows

The uncommitted change set also modifies `dev/registry/mappings/modelo_303/2023/0002-dp30301.toml`
and `dev/registry/mappings/modelo_303/2024-early/0002-dp30301.toml` (`git status` shows both `M`),
re-homing DP30301 ordinal 32 (export field `f032`, source row 37) from a hard literal `"00500"` to
`casilla_id = "154"` in both epochs. This moves each epoch's `casilla` class total from 105 to 106
and its `literal` class total from 40 to 39, confirmed against the deletion diff of the previously
committed `m303_2023_semantic_census.py` and `m303_2024_early_semantic_census.py` (both showed
`casilla: 105` / `literal: 40` before this change). The S67 and S68 audits recorded zero findings
against the pre-amendment state; that verdict does not become wrong, but the reviewed surface it
was measured against has changed. Owners of S67/S68 should be aware their rows' underlying totals
moved as a side effect of S69's authoring, not of any action against those rows directly.

The re-homing driver was independently verified against the bundled official design text
(`04-303-...-xls.xlsx.extracted.md`): DP30301 row 37 / ordinal 32 (casilla 154, "Tipo % [154]")
carries content `"Nota 8. Nota 7"` with **no** `Constante` value, unlike every sibling Tipo % field.
Nota 8 for this sheet states the field's value is `Constante "00500"` for "09 y 3T de 2024" and
`Constante "00750"` "A partir de 10 y 4T de 2024 y ejercicios posteriores" — a value that changes at
a period boundary, which no single literal in a design-scoped map can express, so a casilla is the
only correct home. **Nota 7 is not the driver of this re-homing** and does not itself require any
change to representation; an earlier characterization citing Nota 7 for this slot was incorrect and
is superseded by this finding.

### S69 Modelo 303 2024-late semantic map review | low | Nota 7's permissive foral-filer allowance is uniformly unimplemented, not inconsistently

Nota 7 ("Tributación exclusivamente a una Administración Foral... se podrán cumplimentarán con el
valor '00000'") is referenced by exactly ten DP30301 Tipo %/Recargo fields in the bundled 2024-late
design: ordinals 29, 32, 35, 38, 47, 50, 53, 56, 81, 84. Direct inspection of all ten entries in
`0002-dp30301.toml` (2024-late) shows a mix of `literal` (six) and `casilla` (four, including the
re-homed ordinal 32) kinds, none carrying any conditional foral-alternate value path, and the render
profile's three singleton rules do not touch any of them. This is uniform across all ten slots — no
slot implements the Nota 7 allowance and none is treated differently from the others — so this is a
known, evenly-applied gap rather than a defect specific to the re-homed slot or to this epoch. A
distinct "foral taxation" identification flag already exists as a producer key on DP30301 (per the
2023 semantic-home-assignments reference), but it is not wired to any of these ten rate fields.
Closing this gap (deciding whether/how a foral-filer election should route an alternate "00000"
value through these ten fields) is a semantic-home ruling this audit does not make; it is recorded
here as a genuine, currently-unaddressed gap for escalation.

## Recommendations

Do not close S69 until the reviewed content (`dev/registry/mappings/modelo_303/2024-late/`,
`dev/registry/m303_semantic_census.py`, `dev/registry/tests/test_modelo_303_semantic_maps.py`, and
the amended 2023/2024-early DP30301 casilla-154 re-homing) lands as a real, atomic commit — the
review found the content correct, but content sitting uncommitted on disk is not a landed row.

Flag the S67/S68 casilla-total drift (105 to 106 casilla, 40 to 39 literal, both epochs) to whoever
owns those rows so it is a recorded, intentional side effect rather than a silent change discovered
later.

Escalate the Nota 7 permissive foral-filer allowance (ten DP30301 rate/recargo slots, none
implemented) for an explicit ruling: either route it through the existing foral-taxation producer
flag as a conditional override, or record a deliberate decision not to implement an optional
alternate value AEAT itself states as non-mandatory ("se podrán cumplimentarán"). Do not resolve it
inside a future epoch's map row without that ruling, or the same gap will recur unreviewed in S70
and S71.
