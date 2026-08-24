---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:a38fd750649a7f5a42fc331da7bda8d8568f9fae930299527b2cbabcd57b7a04'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
  - "[[2026-08-24-deadline-window-revision-authority-adr]]"
---

# `deadline-window-revision-authority` audit: `S12 Modelo 303 2023 deadline review`

## Scope

Independent review of the S12 Modelo 303 filing-year 2023 corpus repair and its
focused registry regressions. The review checked all sixteen quarterly and monthly
coordinates, presentation windows, and direct-debit cutoffs against the bundled AEAT
2023 calendar and the bundled AEAT 2024 calendar for the following-January 4T and
month-12 facts. It also checked revision ownership, semantic identity, source
applicability, uniqueness, test bite, and canonical-architecture reuse.

The bundled PDFs match the SHA-256 values declared by the legal source catalogue.
AEAT's 2023 monthly table confirms the ordinary 1-to-30 and 1-to-25 rules plus the
January, March, June, August, and November holiday extensions; its quarterly table
confirms April, July, and October 1-to-20/1-to-15 windows. The 2024 calendar explicitly
lists December 2023 and fourth-quarter 2023 Modelo 303 through 30 January, with bank
domiciliation through 25 January.

## Findings

No critical, high, medium, or low findings.

The sixteen rows exactly match the sixteen selector tokens and carry one unique ID and
one typed `Period` coordinate each under revision `2023`. No other revision retains a
filing-year 2023 copy. The tests pin row count, selector equality, every open/close/debit
date, tax-year identity, identifier shape, source vintage, and exclusive containing
revision; the count-plus-set assertions prevent their dictionary projection from hiding
an extra duplicate.

Vaultspec RAG discovery located the existing `select_revision`,
`deadline_semantic_coordinate`, `ValidatedRegistryAuthority.deadline_windows`, and
filing-window resolver authorities. Exact-symbol confirmation found no new selector,
resolver, period parser, cadence authority, deduplication path, or deadline catalogue in
the S12 changes. The patch is data plus focused tests and therefore introduces no code
re-declaration.

## Recommendations

Accept the reviewed Modelo 303 filing-year 2023 portion of S12. Preserve these rows as
revision-owned law facts and continue the remaining supported-year materialisation and
fleet gates through the already approved plan; add no modelo-local calendar resolver or
runtime deduplication workaround.
