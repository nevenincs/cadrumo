---
tags:
  - '#audit'
  - '#catalogue-validation'
date: '2026-05-15'
modified: '2026-06-29'
related: []
---



# `catalogue-validation` audit: `M130/M131/M202/M303 catalogue-validation gap diagnosis`

## Scope

Read-only diagnosis of the 73 validation failures raised by
`test_catalogue_verification.py` on `chore/eliminate-shims` at HEAD
`fa354477`. No source mutation; this document classifies the failure
families and points to the canonical fix for each. Mutations are
deliberately left to the agents already working in adjacent regions.

## Findings

The 73 historical failures partitioned into four independent gap families.
Current-state recheck on 2026-06-29 shows all four families are closed or
superseded in the live registry.

### F1 — CLOSED/SUPERSEDED: self-relation `source_periods` missing (6 relations)

Historical finding: the validator required every relation to declare
`source_periods` explicitly while six `previous_quarter` self-relations
used `source_period_offset_from_target = -1`.

Current state 2026-06-29: `_relation_source_periods_for_validation`
derives source periods from `source_period_offset_from_target` and
`target_periods`, and the M303 compensation relation intentionally keeps
`source_periods = ()` with offset `-1`. This is now valid current behavior,
not an open catalogue gap.

Affected: M130 `modelo-130-rel-self-prior-quarter-negative`, M131
`modelo-131-{2019-2023,2024,2025,2026}-rel-self-prior-quarter-negative`,
M303 `modelo-303-rel-self-compensacion-anteriores`.

### F2 — CLOSED: M131 phantom `-v101` source-ref suffix (12 errors)

Historical finding: M131 2024 / 2025 / 2026 referenced non-existent
`aeat-dr-131-{year}-v101` source ids. Current state 2026-06-29: those
revisions cite `aeat-dr-131-2024`, `aeat-dr-131-2025`, and
`aeat-dr-131-2026`; the `-v101` suffix remains only on the valid
historical `aeat-dr-131-2019-2023-v101` source.

### F3 — CLOSED: M202 construct source-ref closure (8 errors)

Historical finding: the M202 `2019-2022` and `2023-2024` foundation
constructs omitted `aeat-modelo-202-instructions`. Current state
2026-06-29: both constructs include `aeat-modelo-202-instructions` and
the revision-specific `aeat-modelo-202-instructions-2023-2024` source ref.

### F4 — CLOSED: M303 missing LIVA articles in legal catalogue (~47 errors)

Historical finding: `registry/aeat/legal/iva.toml` carried only three
LIVA entries and M303 referenced core deduction and prorrata authority
articles that were not yet catalogued:

- `ley-37-1992:art-99` — IVA deducible (compensación-anteriores,
  resultado, compensación-disponible-fin-periodo)
- `ley-37-1992:art-102` — prorrata aplicable
- `ley-37-1992:art-104` — prorrata general
- `ley-37-1992:art-107` — regularización deducciones bienes inversión
- `ley-37-1992:art-108` — concepto de bienes de inversión
- `ley-37-1992:art-109` — procedimiento de regularización
- `ley-37-1992:art-110` — entregas durante el período de
  regularización

Current state 2026-06-29: these LIVA references resolve through the legal
catalogue and the focused M303 registry tests validate the self-relation,
official record-design casillas, and source/legal grounding.

## Recommendations

No follow-up action remains from this historical audit. The current
registry should keep the offset-derived relation semantics for M303, the
versionless M131 2024+ source ids, the M202 construct source-ref closure,
and the resolved LIVA catalogue entries under focused regression coverage.
