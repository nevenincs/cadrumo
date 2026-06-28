---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-05-27'
modified: '2026-05-27'
step_id: S55
related:
  - '[[2026-05-26-cross-domain-continuity-plan]]'
---

# cross-domain-continuity P14.S55 — Decision record: backfill 2024 pyme bracket

## Decision

Architecture verdict (Task #42): **OPTION (a) APPROVED** — backfill 2024 pyme
bracket within the `2024-y-siguientes` revision without revising its identity.

The `is.modelo-200.tipo-gravamen-pyme` parameter in
`src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/parameters.toml`
had bracket windows starting only at 2025-01-01, leaving the revision's declared
`valid_from = 2024-01-01` date range uncovered.  Any Modelo 200 filing for a
micro-empresa (INCN < 1.000.000 EUR) with a 2024 fiscal year would raise a
`bracket_no_window` runtime error.

## Authority

The 2024 micro-empresa / pyme flat rate is **23 %**, grounded in:

- **LIS Art. 29** (Ley 27/2014, BOE-A-2014-12328) as in force for períodos
  impositivos iniciados en 2024 — the pre-2025 flat pyme rate before the
  two-tranche micro-empresa scale (17 %/20 %) was introduced for 2025.
- **AEAT Manual de Sociedades 2024** ("Tipos de gravamen vigentes") —
  confirms the 23 % rate for micro-empresas in ejercicios iniciados en 2024.

## Scope

The fix is a pure TOML data backfill:

- Add one `BracketEntry` with `valid_from = 2024-01-01`, `valid_to = 2024-12-31`,
  `marginal_rate = "0.23"`, `fixed_addition = "0"`, `lower_bound = "0"`.
- Preserve existing 2025 (17 %/20 %) and 2026 (19 %/21 %) bracket windows
  exactly.
- Update the existing test assertion that excluded 23 % from all windows to
  correctly permit it only in the 2024 window.

No revision identity change is required; `2024-y-siguientes` remains the
correct revision name for this period range.
