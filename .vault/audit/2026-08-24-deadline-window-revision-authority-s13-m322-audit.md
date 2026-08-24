---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:ab76d1d6391ab9c47fbb3c19a18b3b8f632391bd8534cf9e418fa50801e49b32'
related:
  - '[[2026-08-24-deadline-window-revision-authority-plan]]'
  - '[[2026-08-24-deadline-window-revision-authority-W02-P04-S13]]'
---
# `deadline-window-revision-authority` audit: `S13 M322 official-calendar closure`

## Scope

Review W02.P04.S13 for official-source fidelity, canonical ownership, exact census and dates, construct/source closure, payment-cutoff restraint, residual honesty, and absence of redeclared deadline architecture.

## Findings

No code-architecture redeclaration occurred. Vaultspec RAG and exact-symbol confirmation locate one revision selector (`select_revision`), one ownership validator, one authority projection (`ValidatedRegistryAuthority.deadline_windows`), the core `Period` and cadence authority, and one filing-window resolver (`resolve_filing_window`). The M322 changes are registry rows and regressions only.

The bundled official AEAT calendars explicitly name Modelo 322 beneath every authored deadline heading. The resulting census is twelve monthly coordinates for each ejercicio 2022 through 2025 and eleven for 2026. Every row is beneath the revision selected by `select_revision`, has the canonical monthly period identity, cites the relevant calendar, appears in construct closure, and leaves `payment_cutoff_on` absent because the available direct-debit authority does not explicitly list M322.

The sole residual is ejercicio 2026 period 12. Its filing window falls in January 2027, and no official 2027 taxpayer calendar is enrolled. The row must remain absent rather than inferred. Therefore S13 is correctly open.

## Verification

Ruff passed on the exact M322 test. The focused module reached 13 passing assertions; its two bundled-authority projection assertions were blocked by unrelated concurrent dirty M303/M390 semantic-role constraint failures during full-registry validation. The M322-local validator, exact census and date comparisons, source closure, ownership, and all other assertions passed before that unrelated global boundary.

## Recommendations

- Enrol and adjudicate AEAT's official 2027 calendar when published, author `(2026, "12")`, rerun the focused projection boundary, and only then close S13.
