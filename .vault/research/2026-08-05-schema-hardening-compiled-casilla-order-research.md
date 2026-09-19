---
tags:
  - '#research'
  - '#schema-hardening'
date: '2026-08-05'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:0cd1b6c3a1f0958368875169a846c78aaa7c3db1a4eac35229984bea683574d8'
related: []
---

# `schema-hardening` research: `Is compiled casilla order load-bearing`

The loader compiles `revision.casillas` in `sorted(rglob("*.toml"))` order over the
fragment directory, so a casilla fragment's *filename* is its merge position. The
corpus convention `<ordinal>-c<span>.toml` encodes that position in the stem, which
is truthful but means a casilla's filename changes whenever an earlier casilla is
added. Moving to a purely content-derived stem (`c<span>.toml`) would remove that
churn at the cost of permuting compiled order across 24 directories and 10,041
positions. Nothing had established what that order was allowed to move, so the
rename stayed blocked.

The evidence now says the order is presentation-only. Exactly one consumer reads the
sequence — the workbook layout — and its output is self-consistent under permutation.
Every consumer that decides what the taxpayer declares is keyed by `casilla.id`, and
the fixed-width fichero-BOE field order comes from declared layout records, not from
casilla iteration at all. The stale-workbook hazard a reorder creates is already
closed by a different mechanism.

## Findings

### The one genuine sequence consumer is the workbook layout, and it is presentation

`plan_layout` in `src/cadrumo/application/storage/calc_sheets/_layout.py:365` assigns
Entradas/Cálculos rows by iterating `revision.casillas`, so a permutation relocates
every cell. That relocation is internally consistent: the emitted formulas reference
the permuted layout's own addresses. This was measured and pinned by a peer in commit
`bff1bc9f0c`, whose gate
(`src/cadrumo/application/storage/calc_sheets/tests/test_casilla_order_invariance.py`)
asserts that the emitted casilla set, the formula per casilla, the number format per
casilla, and the filing schema collection are all byte-identical under a full
reversal. The same commit corrected `RegistryCasillaCollection.all()`, whose docstring
claimed declaration order while `collection_from_snapshot` had always sorted by
canonical casilla id.

### The fichero-BOE field order is declared data, not derived from casilla order

This was the brief's sharpest suspect and it is clean. `ExportLayoutDefinition` carries
`records`, each with its own ordered `fields`; the fixed-width emission walks that
declared structure. Reversing `revision.casillas` in memory and re-reading the layout
leaves the field sequence identical: Modelo 130 `modelo-130-fichero-boe`, 3 records /
50 fields, invariant; Modelo 303 `modelo-303-fichero-boe`, 8 records / 191 fields,
invariant. 241 fields across the two modelos, zero movement. The layout is a declared
registry section, so the result generalises by construction rather than by sampling.

### The remaining named suspects are order-free by construction

The locale key scanner (`src/cadrumo/locales/_registry_scanner.py:74`) accumulates into
a `set`, so iteration order cannot reach its output. The docs casilla projection
(`dev/docs/terminology/_casilla_projection.py:170`) streams casillas but emits through
`for key in sorted(by_key)` at lines 111 and 149, with per-key sources sorted by
`(valid_from, revision_id)`; the compiled sequence is discarded before the record
tuple is built. The completeness manifest is its own declared revision section, not a
projection of casilla iteration. `dev/docs/sequences/` is the docs sequence runner and
has no relationship to casilla order despite the name.

### The stale-workbook hazard is closed by registry_sha, not by order stability

A reorder would let a previously exported sheet's cell addresses disagree with a fresh
plan, which would be a silent wrong-cell read. That is already prevented: a pulled
workbook is bound to its snapshot through `registry_sha`, which hashes the *ordered*
snapshot JSON, so a permutation changes the SHA and the pull refuses the stale sheet.
Confirmed by direct measurement — under reversal both `plan_layout` output and
`registry_sha` move, which is also the anti-tautology control for every invariance
claim above: had the permutation stopped moving them, the invariance results would
have held vacuously.

### What this does not establish

The probe covers the compiled artifacts. It does not cover operator-visible ordering
in a workbook a taxpayer has already opened and annotated by row position, nor the
readability cost of a layout whose row order stops matching the official form's
sequence. Both are product judgments about presentation, not correctness, and they are
what the go/no-go should weigh. The empirical layout permutation was run on Modelo 130
and Modelo 303; Modelo 100 declares no `ANUAL` period selector under the probe's
addressing and was not exercised directly, though it is covered by the landed gate's
parametrisation.

### The option the evidence favors

Order-free. The rename can proceed under `--allow-reorder` without a correctness
consumer blocking it. The tooling is staged in `tmp/schema_verification_cli/` (`plan
--policy content` then `apply --allow-reorder`), and landing it additionally requires
updating the naming gate
`src/cadrumo/domain/calculations/registry/tests/test_casilla_fragment_naming.py` to the
ordinal-less convention and sweeping filename references across `src/` and `dev/`. What
the ADR must settle is whether the presentation churn — every workbook row moving once,
for every modelo — is worth removing the stem drift, and whether the row order should
instead be made canonical (sorted by official casilla number) so that presentation
stops depending on filenames at all.

## Sources

- `src/cadrumo/application/storage/calc_sheets/_layout.py:365`
- `src/cadrumo/application/storage/calc_sheets/tests/test_casilla_order_invariance.py`
- `src/cadrumo/locales/_registry_scanner.py:74`
- `dev/docs/terminology/_casilla_projection.py:111`, `:149`, `:170`
- `src/cadrumo/domain/calculations/registry/tests/test_casilla_fragment_naming.py`
- commit `bff1bc9f0c`
