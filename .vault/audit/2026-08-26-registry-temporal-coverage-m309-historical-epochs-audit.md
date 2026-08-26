---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:bce8dac5d30926838dbd933550e2f917056e3ce2573c25866c131ef62b62017f'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
  - "[[2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr]]"
---

# `registry-temporal-coverage` audit: `Modelo 309 historical epochs review`

## Scope

Independent current-HEAD review of Modelo 309's historic-era implementation,
groundwork commit `34285f97b8`, the subsequently landed live split, its corpus
and legal catalogue evidence, M309 tests, and all four locale shards. The
review verified the canonical selector, snapshot-grade refusal, layout resolver,
source bytes, source windows, HFP/2022 legal anchor, and historical layout
geometry. It excludes the independent M165 and M200 lanes.

## Findings

### historical-locale-geometry | medium | Historical locale help reports copied 2023 coordinates

All four locale shards give historical `decl.a-deducir-23` the current-layout
help coordinate `982-998` and label it exercise 2004 in every era. The source
layouts instead place that field at `@792+13` for 2004--2015 and `@943+17` for
2016--2017 and 2018--2022. The same copy pattern affects the locale-side
coordinate help generally, so an operator inspecting a historic casilla receives
the wrong official location. `test_modelo_309_historical_epochs.py` proves only
that labels are nonblank, which allows the incorrect help text to pass.

### continuity-review-rationale | medium | Revision evidence narrative was not reconciled after the split

The 2016--2017, 2018--2022, and 2023-y-siguientes manifests retain a rationale
that says Modelo 309 has no earlier revision and that `valid_from 2003-12-31`
precedes every sibling. The live registry now contains the four bounded/open
eras beginning in 2004, 2016, 2018, and 2023. The 2016--2017 and 2018--2022
review narratives additionally attest one fixed-width record although each
official design parses as the `M30900` and `M30901` record pair. Those
provenance statements explain an empty continuity-evolution family and claim
what review measured; leaving them false undermines the registry's auditable
evidence even though the current advisory continuity policy does not change
runtime selection.

### reviewer-remediation | low | Both review findings have targeted evidence

The locale help leaves were regenerated through `dev.locales set-batch` from each loaded revision's export fields, including the Spanish witness spans 792-804 for 2004-2015, 943-959 for 2016-2017 and 2018-2022, and 982-998 for 2023-y-siguientes. The focused epoch test now checks every shipped locale against those exact offsets. The three continuity narratives now name their real predecessors and the M30900/M30901 pair where applicable; they retain the empty evolution family only because continuity identities have not been adjudicated.

## Recommendations

- For `historical-locale-geometry`, regenerate or author each historic locale
  help record from the era's own resolved export field coordinates and add
  era-specific assertions that fail on the 2023 coordinate or an incorrect
  filing year.
- For `continuity-review-rationale`, replace the copied review/disposition
  prose with the actual four-era topology and record shape. State that no
  continuity IDs are declared if that is the real reason the advisory family is
  empty; do not claim that predecessor revisions do not exist.

## Closure

Re-review of `78577f578d` and audit hygiene `9d1ad6a479`: PASS. The former Medium locale finding is remediated: all 644 nonempty historical help leaves in the four shipped locales contain a coordinate span from their own revision's loaded export layout, including the independent `a-deducir-23` witnesses `792-804`, `943-959`, and `982-998`. The former Medium narrative finding is remediated: every successor now names its actual predecessor topology and the M30900/M30901 pair where that is the official record shape. The four source hashes, complete extraction shapes, manifest selection, generic layout coverage, formula surfaces, and visible pre-design refusal remain sound; no Modelo 309-specific selector, validator, or source resolver was introduced. The focused epoch suite and lint pass. The broad locale-revision parity gate remains independently blocked by the concurrent Modelo 165 migration, not by Modelo 309. No unresolved Critical, High, or Medium finding remains.
