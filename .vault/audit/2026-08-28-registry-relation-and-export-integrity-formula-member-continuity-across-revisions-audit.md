---
tags:
  - '#audit'
  - '#registry-relation-and-export-integrity'
date: '2026-08-28'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:d539460dcc594ca7b0137ae3984b417f904710d4d3229d15cf4f296695994dd0'
related:
  - "[[2026-08-28-calculation-correctness-campaign-murcia-2022-accumulated-cuota-break-audit]]"
---

# `registry-relation-and-export-integrity` audit: `Formula member continuity across revisions is clean; the one apparent drop is a restructure`

## Scope

## Findings

## Recommendations

## Why this axis

A tier missing from a hand-enumerated total (M390 recargo tabaco) and a value
carried over from a superseded version of a scale (Murcia 2022) are both the same
shape: something that should have crossed a filing-year boundary and did not.
This sweep asks the question directly of every formula in the registry.

## The naive sweep, and why its one hit is not a defect

Comparing each formula id's member set between consecutive revisions of the same
modelo gives **one** hit in 202 comparisons:

> `303` `2022 -> 2023` `modelo-303-iva-resultado` lost `iva.resultado-regimen-general`

Investigated, it is a legitimate restructure:

| | expression |
|---|---|
| 2022 | `subtract(iva.resultado-regimen-general, iva.compensacion-aplicada-periodo)` |
| 2023 | `subtract(add(add(66, 77), 68), iva.compensacion-aplicada-periodo)` |

The casilla did not disappear. In 2023 it is still declared, still `computed` as
`cuota-devengada-total - cuota-deducible-total`, still carries an export ref
(`m303-2023.dp30301.f079`), and is still consumed -- by
`modelo-303-compensacion-aplicada-periodo` and by a new intermediate,
`modelo-303-iva-suma-resultados`. The member moved into an intermediate rather
than being lost.

**A fact worth recording against a future misreading:** casilla `66` in M303 2023
is *not* the régimen general resultado. Its formula is `divide(multiply(64, 65),
100)` -- the porcentaje atribuible al Estado. Anyone matching box numbers to
semantic names by eye would pair `66` with `iva.resultado-regimen-general` and
conclude the 2023 expression re-states the 2022 one. It does not; it adds boxes
77 and 68 as well.

## The corrected formulation, which is the one that matters

Per-formula-id comparison flags a restructure as a loss, so it answers the wrong
question. The right one is whether a casilla still reaches *any* formula:

> for each consecutive revision pair, a casilla consumed in the earlier revision
> and still **declared** in the later one must still be consumed by some formula
> there

Across **70** consecutive revision pairs: **zero**. No casilla is left declared,
exported, and computed by nothing.

Numeric leaf ids are excluded from the join. Casilla ids renumber between filing
years -- modelo 123 grew from 8 boxes to 14 -- so joining on them across a year
boundary compares different boxes. Only stable semantic ids are matched, and the
sweep is blind to a drop expressed purely in numeric ids; that limitation is real
and is the reason this is recorded as a sweep rather than shipped as a gate.

## Not gated, deliberately

The two clean axes swept this campaign were gated because their check has no
legitimate failure mode. This one does: a design may deprecate a box, keeping it
declared for export while no longer computing it. That is lawful, so a ratchet
here would need an allowlist from its first day, and an allowlist with no
instances to justify it is a shape looking for a defect. Recorded as a swept axis
instead, with the probe described precisely enough to re-run.

No production code, registry data or test was changed by this audit.
