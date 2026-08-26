---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:99f997328a68deacc8fe5bdb1647160b6d49a3aff20729cd7628442e1c846fe3'
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


