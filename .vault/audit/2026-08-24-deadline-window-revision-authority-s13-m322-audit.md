---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:26d1871f4999c2e644187660e4ab403c04c0bbdf15dd831723b9045a58263b96'
related:
  - '[[2026-08-24-deadline-window-revision-authority-plan]]'
  - '[[2026-08-24-deadline-window-revision-authority-W02-P04-S13]]'
---

# `deadline-window-revision-authority` audit: `s13 m322`

## Scope

Independently review W02.P04.S13 for primary-source fidelity, exact canonical ownership, authority multiplicity, citation closure, direct-debit restraint, test bite, and absence of redeclared deadline architecture.

## Findings

No findings. The official AEAT 2022 calendar confirms M322 presentation closes for periods 01 through 11, and the bundled 2023 calendar confirms period 12 closes on 30 January 2023. The 2022 domiciliation table names monthly Modelos 303 and 353 but not 322, supporting the explicit absence of `payment_cutoff_on` for every M322 row.

All twelve coordinates occur only beneath revision `2008-2022`; `select_revision` chooses that owner for every month, and `ValidatedRegistryAuthority.deadline_windows` returns exactly twelve ordered rows. Construct membership and source closure are complete. The bundled PDF byte count and SHA-256 match its catalogue record. Thirteen focused tests and Ruff passed.

Vaultspec RAG semantic searches for `M322 monthly filing deadline windows canonical revision ownership` and `deadline window revision authority M322 monthly materialization`, followed by exact-symbol confirmation, found the existing `select_revision`, `ValidatedRegistryAuthority.deadline_windows`, core `Period` and `registry_period_kind`, and `resolve_filing_window` authorities. The engine method with the same public noun delegates read-only to the registry authority. No selector, resolver, cadence authority, period parser, deadline catalogue, or source map was redeclared.

## Recommendations

None.
